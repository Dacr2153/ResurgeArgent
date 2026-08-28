/**
 * Punto unico de acceso a datos.
 *
 * Hoy todo resuelve contra `mocks/` con latencia simulada. Cuando el backend
 * de ResurgeAgent este listo, se implementa `HttpApi` con el mismo contrato
 * (`EmergencyApi`) y se cambia la constante `api` de abajo: ninguna pantalla
 * necesita tocarse, porque ninguna importa los mocks directamente.
 */
import type {
  CoordinatorScope, Incident, MatchSuggestion, Mission, QueuedSync,
  RecoveryPlanStep, RecoveryQuestion, ReportDraft, SubmittedReport,
  TrackedReport, VolunteerSignup,
} from './types';
import {
  INCIDENTS, MATCH, MISSION, RECOVERY_PLAN, RECOVERY_QUESTIONS,
  SYNC_QUEUE, TRACKED_REPORT, ZONE_RADIUS_KM,
} from '../mocks/data';

export interface EmergencyApi {
  /** Incidentes visibles segun el alcance RBAC del coordinador. */
  listIncidents(scope: CoordinatorScope): Promise<Incident[]>;
  /** Misiones abiertas para un voluntario, filtradas por radio en km. */
  listMissions(radiusKm: number | null): Promise<Incident[]>;
  getIncident(id: string): Promise<Incident | null>;
  getTrackedReport(id: string): Promise<TrackedReport | null>;
  submitReport(draft: ReportDraft, opts: { offline: boolean; verified: boolean }): Promise<SubmittedReport>;
  registerVolunteer(signup: VolunteerSignup): Promise<{ status: 'en_verificacion' }>;
  getMission(incidentId: string): Promise<Mission>;
  getMatchSuggestion(incidentId: string): Promise<MatchSuggestion>;
  assignMatch(incidentId: string, action: 'assign' | 'reassign' | 'reject'): Promise<{ message: string }>;
  getRecoveryQuestions(): Promise<RecoveryQuestion[]>;
  getRecoveryPlan(answers: Record<string, string>): Promise<RecoveryPlanStep[]>;
  getSyncQueue(): Promise<QueuedSync[]>;
  flushSyncQueue(): Promise<{ sent: number }>;
}

const LATENCY_MS = 220;

function delay<T>(value: T, ms = LATENCY_MS): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

let reportCounter = 2490;

class MockApi implements EmergencyApi {
  listIncidents(scope: CoordinatorScope) {
    const visible = scope === 'zona'
      ? INCIDENTS.filter((i) => i.distanceKm <= ZONE_RADIUS_KM)
      : INCIDENTS;
    return delay([...visible].sort((a, b) => b.score - a.score));
  }

  listMissions(radiusKm: number | null) {
    const visible = radiusKm === null
      ? INCIDENTS
      : INCIDENTS.filter((i) => i.distanceKm <= radiusKm);
    return delay([...visible].sort((a, b) => b.score - a.score).slice(0, 5));
  }

  getIncident(id: string) {
    return delay(INCIDENTS.find((i) => i.id === id) ?? null);
  }

  getTrackedReport(id: string) {
    // El mock devuelve siempre el mismo reporte, con el ID pedido.
    return delay<TrackedReport | null>({ ...TRACKED_REPORT, id });
  }

  submitReport(_draft: ReportDraft, opts: { offline: boolean; verified: boolean }) {
    reportCounter += 1;
    const id = `INC-${reportCounter}`;
    const status: SubmittedReport['status'] = opts.offline
      ? 'en_cola_local'
      : opts.verified ? 'recibido' : 'pendiente_verificacion';
    return delay({ id, status });
  }

  registerVolunteer(_signup: VolunteerSignup) {
    return delay({ status: 'en_verificacion' as const }, 400);
  }

  getMission(incidentId: string) {
    const incident = INCIDENTS.find((i) => i.id === incidentId);
    return delay({
      ...MISSION,
      incidentId,
      title: incident?.title ?? MISSION.title,
    });
  }

  getMatchSuggestion(incidentId: string) {
    const incident = INCIDENTS.find((i) => i.id === incidentId) ?? INCIDENTS[0];
    return delay<MatchSuggestion>({
      ...MATCH,
      incidentId: incident.id,
      incidentTitle: incident.title,
      score: incident.score,
    });
  }

  assignMatch(_incidentId: string, action: 'assign' | 'reassign' | 'reject') {
    const message = {
      assign: 'Asignada a Ana Quispe · notificación enviada · SLA en curso.',
      reassign: 'Modo manual: elige entre 6 recursos disponibles en un radio de 3 km.',
      reject: 'Sugerencia rechazada · el incidente vuelve al pool de análisis.',
    }[action];
    return delay({ message }, 320);
  }

  getRecoveryQuestions() {
    return delay(RECOVERY_QUESTIONS);
  }

  getRecoveryPlan(_answers: Record<string, string>) {
    return delay(RECOVERY_PLAN, 500);
  }

  getSyncQueue() {
    return delay(SYNC_QUEUE);
  }

  flushSyncQueue() {
    return delay({ sent: SYNC_QUEUE.length }, 700);
  }
}

export const api: EmergencyApi = new MockApi();
