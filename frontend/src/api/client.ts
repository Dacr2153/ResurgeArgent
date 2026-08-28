/**
 * Punto unico de acceso a datos.
 *
 * Todo resuelve contra el backend real de ResurgeAgent. No hay capa de ejemplo:
 * si el backend no esta levantado, las pantallas lo dicen y no inventan nada.
 * La traduccion de formas vive en `mapeo.ts`; aqui solo estan las rutas y el
 * orden de las llamadas.
 */
import { ApiError, request, requestOrNull } from './http';
import {
  eventosDeTraza, eventosDelIncidente, incidenteDeOperacion, incidentesVerificadosDeTraza,
  sugerenciaDeOperacion,
  type IncidenteCrudo, type ListadoOperaciones, type OperacionCruda, type TrazaCruda,
} from './mapeo';
import type {
  AuditEvent, CoordinatorScope, Incident, MatchDecision, MatchSuggestion, Mission, QueuedSync,
  RecoveryPlanStep, RecoveryQuestion, ReportDraft, SubmittedReport,
  TrackedReport, VolunteerSignup,
} from './types';

/** Radio operativo del coordinador de zona, en km. Es el mismo valor que asume
    `RADIO_ZONA_KM` en el adaptador REST del Orquestador. */
export const ZONE_RADIUS_KM = 3;

/** Firma del coordinador que acompana a toda decision. El dominio exige un
    responsable identificado: sin `coordinatorId` el backend responde 400. */
export interface Signature {
  coordinatorId: string;
  justification: string;
}

export interface EmergencyApi {
  /** Incidentes visibles segun el alcance RBAC del coordinador. */
  listIncidents(scope: CoordinatorScope): Promise<Incident[]>;
  /** Misiones abiertas para un voluntario, filtradas por radio en km. */
  listMissions(radiusKm: number | null): Promise<Incident[]>;
  getIncident(id: string): Promise<Incident | null>;
  getTrackedReport(id: string): Promise<TrackedReport | null>;
  submitReport(draft: ReportDraft, opts: { offline: boolean; verified: boolean }): Promise<SubmittedReport>;
  registerVolunteer(signup: VolunteerSignup): Promise<{ status: string }>;
  getMission(incidentId: string): Promise<Mission>;
  getMatchSuggestion(incidentId: string): Promise<MatchSuggestion>;
  assignMatch(incidentId: string, action: MatchDecision, signature: Signature): Promise<{ message: string }>;
  /** Traza de auditoria del hilo, acotada al incidente que se esta mirando. */
  getAuditTrail(correlationId: string, incidentId: string): Promise<AuditEvent[]>;
  getRecoveryQuestions(): Promise<RecoveryQuestion[]>;
  getRecoveryPlan(answers: Record<string, string>): Promise<RecoveryPlanStep[]>;
  getSyncQueue(): Promise<QueuedSync[]>;
  flushSyncQueue(): Promise<{ sent: number }>;
}

// --------------------------------------------------------- reporte ciudadano

/** Categorias de la interfaz -> categorias CAP 1.2, que es lo que habla el
    backend. La traduccion va en este sentido y no al reves: el estandar es del
    dominio, y la etiqueta amable es de la pantalla. */
const CATEGORIA_A_CAP: Record<string, string> = {
  Incendio: 'Fire',
  Inundacion: 'Met',
  Derrumbe: 'Geo',
  Rescate: 'Rescue',
};

const SEVERIDAD_A_CAP: Record<string, string> = {
  critical: 'Extreme',
  high: 'Severe',
  medium: 'Moderate',
};

/** Un reporte critico o alto no admite espera; uno medio se atiende, pero no
    interrumpe. Es la traduccion literal de <urgency> en CAP 1.2. */
const URGENCIA_A_CAP: Record<string, string> = {
  critical: 'Immediate',
  high: 'Immediate',
  medium: 'Expected',
};

function reporteDesdeBorrador(draft: ReportDraft, verified: boolean): Record<string, unknown> {
  const partes = [draft.category ?? 'Emergencia', draft.description.trim(), draft.address.trim()]
    .filter((p) => p.length > 0);
  const reporte: Record<string, unknown> = {
    // El motor de ingesta descarta todo reporte con texto vacio, asi que se
    // compone siempre algo: categoria, descripcion y direccion, lo que haya.
    texto: partes.join(' · '),
    canal: 'app',
    fuente: {
      // Sin autenticacion de ciudadano el telefono es el unico identificador
      // estable que hay; sin telefono, la fuente es anonima y el motor de
      // verificacion le dara menos peso, que es exactamente lo correcto.
      id: draft.phone.trim() ? `ciudadano:${draft.phone.trim()}` : 'ciudadano:anonimo',
      tipo: 'ciudadano',
      nombre: '',
      reputacion: verified ? 0.6 : 0.4,
    },
    categoria: draft.category ? CATEGORIA_A_CAP[draft.category] ?? 'Other' : 'Other',
    severidad: SEVERIDAD_A_CAP[draft.severity] ?? 'Unknown',
    urgencia: URGENCIA_A_CAP[draft.severity] ?? 'Unknown',
    // Un reporte con el telefono verificado es un hecho observado por una
    // persona identificable; sin verificar, solo es probable.
    certeza: verified ? 'Observed' : 'Likely',
    metadatos: {
      direccion: draft.address,
      foto_adjunta: draft.hasPhoto,
      telefono_verificado: verified,
    },
  };
  if (draft.lat !== null && draft.lng !== null) {
    // GeoJSON RFC 7946: [longitud, latitud]. Ver `mapeo.ts`.
    reporte.ubicacion = { type: 'Point', coordinates: [draft.lng, draft.lat] };
  }
  return reporte;
}

interface RespuestaEmergencia {
  correlacion_id: string;
  incidentes: OperacionCruda[];
  reportes_descartados?: { total: number; por_motivo: Record<string, number> };
}

// ------------------------------------------------------------------- cliente

class HttpApi implements EmergencyApi {
  /** Cache de trazas por hilo dentro de una misma llamada al tablero: un lote de
      diez incidentes comparte un solo `correlacion_id`, y pedir la traza diez
      veces seria diez veces el mismo JSON. */
  private async trazasDe(operaciones: OperacionCruda[]): Promise<Map<string, IncidenteCrudo>> {
    const hilos = [...new Set(operaciones.map((o) => o.correlacion_id).filter(Boolean))];
    const trazas = await Promise.all(
      hilos.map((hilo) => requestOrNull<TrazaCruda>(`/orquestador/auditoria/${encodeURIComponent(hilo)}`)),
    );
    const verificados = new Map<string, IncidenteCrudo>();
    for (const traza of trazas) {
      for (const [id, incidente] of incidentesVerificadosDeTraza(traza)) {
        verificados.set(id, incidente);
      }
    }
    return verificados;
  }

  async listIncidents(scope: CoordinatorScope): Promise<Incident[]> {
    const listado = await request<ListadoOperaciones>('/orquestador/operaciones', {
      query: { alcance: scope, radio_km: ZONE_RADIUS_KM },
    });
    const operaciones = listado.operaciones ?? [];
    const verificados = await this.trazasDe(operaciones);
    return operaciones
      .map((op) => incidenteDeOperacion(op, verificados.get(op.incidente_id)))
      .sort((a, b) => b.score - a.score);
  }

  async listMissions(radiusKm: number | null): Promise<Incident[]> {
    // Plataforma ya devuelve la forma de `Incident` (ver `presentadores.py`);
    // lo unico que falta son los campos de la maquina de estados, que una
    // mision abierta no expone.
    const misiones = await request<Incident[]>('/plataforma/misiones', {
      query: { radio_km: radiusKm ?? undefined },
    });
    return misiones.sort((a, b) => b.score - a.score);
  }

  async getIncident(id: string): Promise<Incident | null> {
    const operacion = await requestOrNull<OperacionCruda>(`/orquestador/operaciones/${encodeURIComponent(id)}`);
    if (!operacion) return null;
    const verificados = await this.trazasDe([operacion]);
    return incidenteDeOperacion(operacion, verificados.get(operacion.incidente_id));
  }

  getTrackedReport(id: string): Promise<TrackedReport | null> {
    return requestOrNull<TrackedReport>(`/plataforma/reportes/${encodeURIComponent(id)}`);
  }

  async submitReport(
    draft: ReportDraft,
    opts: { offline: boolean; verified: boolean },
  ): Promise<SubmittedReport> {
    if (opts.offline) {
      // Sin red el reporte no va al Orquestador: se encola en plataforma, que es
      // la cola real que luego vacia la pantalla de sincronizacion.
      const encolado = await request<QueuedSync>('/plataforma/sincronizacion/reportes', {
        method: 'POST',
        body: {
          titulo: `${draft.category ?? 'Emergencia'} · ${draft.address || 'sin direccion'}`,
          meta: draft.hasPhoto ? 'con foto · en cola local' : 'sin foto · en cola local',
          puntuacion: 0,
          carga: reporteDesdeBorrador(draft, opts.verified),
        },
      });
      return { id: encolado.id, status: 'en_cola_local' };
    }

    const respuesta = await request<RespuestaEmergencia>('/orquestador/emergencias', {
      method: 'POST',
      // Timeout mas largo: este POST arrastra la saga completa (ingesta,
      // verificacion y geoespacial) y es la peticion mas cara del sistema.
      timeoutMs: 30000,
      body: { entrada: { reportes: [reporteDesdeBorrador(draft, opts.verified)] } },
    });

    const incidente = respuesta.incidentes?.[0];
    if (!incidente) {
      const motivos = Object.keys(respuesta.reportes_descartados?.por_motivo ?? {}).join(', ');
      throw new ApiError(
        'peticion',
        '/orquestador/emergencias',
        motivos
          ? `El reporte no genero ningun incidente: la ingesta lo descarto (${motivos.replace(/_/g, ' ')}).`
          : 'El reporte no genero ningun incidente. Revisa la descripcion e intenta de nuevo.',
      );
    }
    return { id: incidente.incidente_id, status: opts.verified ? 'recibido' : 'pendiente_verificacion' };
  }

  registerVolunteer(signup: VolunteerSignup): Promise<{ status: string }> {
    return request<{ status: string }>('/plataforma/voluntarios', { method: 'POST', body: signup });
  }

  getMission(incidentId: string): Promise<Mission> {
    return request<Mission>(`/plataforma/misiones/${encodeURIComponent(incidentId)}`);
  }

  async getMatchSuggestion(incidentId: string): Promise<MatchSuggestion> {
    const operacion = await request<OperacionCruda>(`/orquestador/operaciones/${encodeURIComponent(incidentId)}`);
    const verificados = await this.trazasDe([operacion]);
    return sugerenciaDeOperacion(operacion, verificados.get(operacion.incidente_id));
  }

  async assignMatch(
    incidentId: string,
    action: MatchDecision,
    signature: Signature,
  ): Promise<{ message: string }> {
    const operacion = await request<OperacionCruda>('/orquestador/decisiones', {
      method: 'POST',
      body: {
        incidente_id: incidentId,
        aprobada: action === 'assign',
        coordinador_id: signature.coordinatorId,
        justificacion: signature.justification,
        // Rechazar descarta el incidente; suspender lo aparta a la espera de mas
        // informacion. Son dos destinos distintos en la maquina de estados.
        suspender: action === 'suspend',
      },
    });
    const mensaje = {
      assign: `Firmado por ${signature.coordinatorId}. El incidente pasa a ${operacion.estado}.`,
      reject: `Rechazo registrado por ${signature.coordinatorId}. El incidente pasa a ${operacion.estado}.`,
      suspend: `Suspendido por ${signature.coordinatorId} a la espera de mas informacion (${operacion.estado}).`,
    }[action];
    return { message: mensaje };
  }

  async getAuditTrail(correlationId: string, incidentId: string): Promise<AuditEvent[]> {
    if (!correlationId) return [];
    const traza = await requestOrNull<TrazaCruda>(`/orquestador/auditoria/${encodeURIComponent(correlationId)}`);
    if (!traza) return [];
    return eventosDeTraza({
      correlacion_id: traza.correlacion_id,
      eventos: eventosDelIncidente(traza.eventos ?? [], incidentId),
    });
  }

  getRecoveryQuestions(): Promise<RecoveryQuestion[]> {
    return request<RecoveryQuestion[]>('/plataforma/recuperacion/preguntas');
  }

  getRecoveryPlan(answers: Record<string, string>): Promise<RecoveryPlanStep[]> {
    return request<RecoveryPlanStep[]>('/plataforma/recuperacion/plan', {
      method: 'POST',
      body: { respuestas: answers },
    });
  }

  getSyncQueue(): Promise<QueuedSync[]> {
    return request<QueuedSync[]>('/plataforma/sincronizacion');
  }

  flushSyncQueue(): Promise<{ sent: number }> {
    return request<{ sent: number }>('/plataforma/sincronizacion', { method: 'POST' });
  }
}

export const api: EmergencyApi = new HttpApi();
