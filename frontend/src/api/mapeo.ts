/**
 * Traduccion backend -> interfaz. Es el unico archivo que conoce la forma real
 * de las respuestas de ResurgeAgent; el resto del frontend solo ve los tipos de
 * `types.ts`.
 *
 * LA REGLA QUE NO SE ROMPE: el backend emite GeoJSON RFC 7946, y en GeoJSON las
 * coordenadas van [longitud, latitud], no al reves. El tipo `Incident` de la
 * interfaz usa {lat, lng} porque es lo que consume Leaflet. Invertir el par pone
 * un incidente de Bogota (lat 4.61 positiva, lon -74.08 negativa) en mitad del
 * oceano Indico. Por eso la conversion vive en `latLngDeGeoJSON` y en ningun
 * otro sitio: hay una funcion que corregir, no catorce.
 */
import type {
  AuditEvent, DecisionSignature, Incident, LatLng, MatchSuggestion,
  TriageComponent, ZonePolygon,
} from './types';

// ---------------------------------------------------------------- forma cruda

/** Punto GeoJSON tal como lo emite `nucleo.geo.Punto.a_geojson()`. */
interface PuntoGeoJSON {
  type: 'Point';
  coordinates: [number, number];
}

interface GeometriaGeoJSON {
  type: string;
  coordinates: unknown;
}

/** `RespuestaGeo.a_dict()` guardada en `operacion.datos.ruta`. */
export interface RutaCruda {
  incidente_id?: string;
  accesible?: boolean;
  distancia_km?: number;
  duracion_min?: number;
  geometria?: GeometriaGeoJSON;
  motivo?: string;
}

export interface TriageCrudo {
  incidente_id: string;
  posicion: number;
  puntuacion: number;
  componentes: Record<string, number>;
}

export interface DecisionCruda {
  id: string;
  incidente_id: string;
  aprobada: boolean;
  coordinador_id: string;
  justificacion: string;
  momento: string;
}

/** `Operacion.a_dict()` del Orquestador. */
export interface OperacionCruda {
  incidente_id: string;
  correlacion_id: string;
  estado: string;
  historial?: unknown[];
  decision?: DecisionCruda | null;
  triage?: TriageCrudo | null;
  datos?: {
    ruta?: RutaCruda | null;
    geo_degradado?: boolean;
    /** El Orquestador solo la adjunta si el lote la trajo; hoy suele faltar. */
    zonas_afectadas?: ColeccionZonas | null;
  };
}

export interface ListadoOperaciones {
  alcance: string;
  radio_km: number;
  total: number;
  operaciones: OperacionCruda[];
}

/** `IncidenteVerificado.a_dict()`, que viaja dentro del evento de auditoria. */
export interface IncidenteCrudo {
  verified_incident_id: string;
  category: string;
  severity: string;
  urgency: string;
  location: PuntoGeoJSON;
  confidence_score: number;
  resumen: string;
  personas_afectadas: number | null;
  necesidades: string[];
  verificado_en: string;
}

export interface EventoCrudo {
  id: string;
  tipo: string;
  agente: string;
  correlacion_id: string;
  momento: string;
  detalle: Record<string, unknown>;
}

export interface TrazaCruda {
  correlacion_id: string;
  eventos: EventoCrudo[];
}

export interface ColeccionZonas {
  type: string;
  features: {
    type: string;
    geometry: GeometriaGeoJSON;
    properties: Record<string, unknown>;
  }[];
}

// --------------------------------------------------------------- utilidades

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null;
}

function esPar(valor: unknown): valor is [number, number] {
  return Array.isArray(valor) && valor.length >= 2
    && typeof valor[0] === 'number' && typeof valor[1] === 'number';
}

/**
 * Convierte un par GeoJSON [lon, lat] al par [lat, lng] de Leaflet.
 *
 * Comprobacion a ojo con una coordenada de Bogota: el backend emite
 * `[-74.0811, 4.6103]`; esta funcion devuelve `[4.6103, -74.0811]`, es decir
 * latitud positiva (norte del ecuador) y longitud negativa (oeste de Greenwich).
 * Si alguna vez ves `[-74.08, 4.61]` llegando a Leaflet, el error esta aqui.
 */
export function latLngDeGeoJSON(coordenadas: [number, number]): LatLng {
  const [lon, lat] = coordenadas;
  return [lat, lon];
}

/** Idem, pero devolviendo el objeto {lat, lng} que usa el tipo `Incident`. */
export function puntoDeGeoJSON(punto: PuntoGeoJSON | undefined): { lat: number; lng: number } | null {
  if (!punto || !esPar(punto.coordinates)) return null;
  const [lat, lng] = latLngDeGeoJSON(punto.coordinates);
  return { lat, lng };
}

/** Vertices de una LineString GeoJSON, ya en [lat, lng]. */
export function lineaDeGeoJSON(geometria: GeometriaGeoJSON | undefined): LatLng[] {
  if (!geometria || geometria.type !== 'LineString' || !Array.isArray(geometria.coordinates)) return [];
  return geometria.coordinates.filter(esPar).map(latLngDeGeoJSON);
}

/** Anillos de un Polygon GeoJSON, ya en [lat, lng]. */
function anillosDeGeoJSON(geometria: GeometriaGeoJSON | undefined): LatLng[][] {
  if (!geometria || !Array.isArray(geometria.coordinates)) return [];
  const anillos = geometria.type === 'Polygon'
    ? geometria.coordinates
    : geometria.type === 'MultiPolygon'
      ? geometria.coordinates.flat()
      : [];
  return (anillos as unknown[])
    .filter(Array.isArray)
    .map((anillo) => (anillo as unknown[]).filter(esPar).map(latLngDeGeoJSON))
    .filter((anillo) => anillo.length >= 3);
}

export function zonasDeColeccion(coleccion: ColeccionZonas | null | undefined): ZonePolygon[] {
  if (!coleccion || !Array.isArray(coleccion.features)) return [];
  return coleccion.features.map((feature, indice) => {
    const props = feature.properties ?? {};
    return {
      id: String(props.celda_id ?? `zona-${indice}`),
      rings: anillosDeGeoJSON(feature.geometry),
      severity: String(props.severidad_agregada ?? 'desconocida'),
      incidentCount: typeof props.conteo_incidentes === 'number' ? props.conteo_incidentes : 0,
    };
  }).filter((zona) => zona.rings.length > 0);
}

/** Minutos transcurridos desde una marca ISO. Nunca negativo: un reloj del
    servidor unos segundos por delante no debe pintar "hace -1 min". */
export function minutosDesde(iso: string | undefined, ahora = Date.now()): number {
  if (!iso) return 0;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.round((ahora - t) / 60000));
}

// ------------------------------------------------------------- vocabulario

/** Categorias CAP 1.2 (OASIS) en castellano. El backend habla el estandar; la
    interfaz habla el idioma de quien opera. */
const CATEGORIA_CAP: Record<string, string> = {
  Geo: 'Movimiento de tierra',
  Met: 'Meteorologico',
  Safety: 'Seguridad publica',
  Security: 'Seguridad',
  Rescue: 'Rescate',
  Fire: 'Incendio',
  Health: 'Salud',
  Env: 'Ambiental',
  Transport: 'Transporte',
  Infra: 'Infraestructura',
  CBRNE: 'Material peligroso',
  Other: 'Otro',
};

export function etiquetaCategoria(categoria: string | undefined): string {
  if (!categoria) return 'Incidente';
  return CATEGORIA_CAP[categoria] ?? categoria;
}

const ESTADO_LEGIBLE: Record<string, string> = {
  recibido: 'Recibido',
  verificado: 'Verificado',
  localizado: 'Localizado',
  priorizado: 'Priorizado',
  pendiente_aprobacion: 'Pendiente de firma',
  asignado: 'Asignado',
  en_curso: 'En curso',
  atendido: 'Atendido',
  descartado: 'Descartado',
  suspendido: 'Suspendido',
};

export function etiquetaEstado(estado: string): string {
  return ESTADO_LEGIBLE[estado] ?? estado.replace(/_/g, ' ');
}

const COMPONENTE_TRIAGE: Record<string, string> = {
  severidad: 'Severidad',
  urgencia: 'Urgencia',
  personas: 'Personas afectadas',
  base: 'Base',
  multiplicador_confianza: 'Multiplicador de confianza',
};

function componentesTriage(triage: TriageCrudo | null | undefined): TriageComponent[] {
  if (!triage || !esObjeto(triage.componentes)) return [];
  return Object.entries(triage.componentes).map(([clave, valor]) => ({
    label: COMPONENTE_TRIAGE[clave] ?? clave.replace(/_/g, ' '),
    value: typeof valor === 'number' ? valor : 0,
  }));
}

// ------------------------------------------------------------ construccion

/**
 * Titulo de la fila. La categoria CAP da el "que"; la ubicacion, el "donde".
 * Se prefiere el resumen del agente de verificacion como ubicacion porque
 * nombra el sitio ("km 4 via La Calera") en vez de dar dos numeros; solo si no
 * hay resumen se cae a las coordenadas, que siempre existen.
 */
function tituloIncidente(verificado: IncidenteCrudo | undefined, punto: { lat: number; lng: number } | null): string {
  const categoria = etiquetaCategoria(verificado?.category);
  const resumen = verificado?.resumen?.trim();
  if (resumen) return `${categoria} · ${resumen}`;
  if (punto) return `${categoria} · ${punto.lat.toFixed(4)}, ${punto.lng.toFixed(4)}`;
  return categoria;
}

/** La puntuacion de triage llega en [0,1] y `bandOf()` corta en 50 y 80: hay
    que escalarla a 0-100 o todo el tablero se pintaria como MEDIO. */
export function puntuacionA100(triage: TriageCrudo | null | undefined): number {
  if (!triage || typeof triage.puntuacion !== 'number') return 0;
  return Math.max(0, Math.min(100, Math.round(triage.puntuacion * 100)));
}

function necesidadesLegibles(verificado: IncidenteCrudo | undefined): string {
  const necesidades = verificado?.necesidades ?? [];
  if (!necesidades.length) return 'necesidad sin declarar';
  return necesidades.slice(0, 3).join(', ').replace(/_/g, ' ');
}

/** Extrae de una traza el ultimo `incidente_verificado` de cada incidente. */
export function incidentesVerificadosDeTraza(traza: TrazaCruda | null): Map<string, IncidenteCrudo> {
  const mapa = new Map<string, IncidenteCrudo>();
  for (const evento of traza?.eventos ?? []) {
    if (evento.tipo !== 'incidente_verificado') continue;
    const detalle = evento.detalle as unknown as IncidenteCrudo;
    if (detalle?.verified_incident_id) mapa.set(detalle.verified_incident_id, detalle);
  }
  return mapa;
}

/**
 * `Incident` de la interfaz a partir de la operacion del Orquestador mas el
 * incidente verificado que vive en la traza de auditoria.
 *
 * La operacion no lleva dentro los datos del incidente (solo su id, el triage y
 * la ruta): la categoria, la ubicacion, las necesidades y el `verificado_en`
 * salen del evento `incidente_verificado` que dejo el agente de verificacion.
 * Por eso el tablero pide la traza ademas de la lista.
 */
export function incidenteDeOperacion(
  operacion: OperacionCruda,
  verificado: IncidenteCrudo | undefined,
): Incident {
  const punto = puntoDeGeoJSON(verificado?.location);
  const ruta = operacion.datos?.ruta ?? null;
  return {
    id: operacion.incidente_id,
    title: tituloIncidente(verificado, punto),
    score: puntuacionA100(operacion.triage),
    lat: punto?.lat ?? 0,
    lng: punto?.lng ?? 0,
    distanceKm: typeof ruta?.distancia_km === 'number' ? ruta.distancia_km : 0,
    need: necesidadesLegibles(verificado),
    ageMinutes: minutosDesde(verificado?.verificado_en),
    estado: operacion.estado,
    correlationId: operacion.correlacion_id,
  };
}

function firmaDeDecision(decision: DecisionCruda | null | undefined): DecisionSignature | null {
  if (!decision) return null;
  return {
    id: decision.id,
    coordinatorId: decision.coordinador_id,
    approved: decision.aprobada,
    justification: decision.justificacion,
    at: decision.momento,
  };
}

export function sugerenciaDeOperacion(
  operacion: OperacionCruda,
  verificado: IncidenteCrudo | undefined,
): MatchSuggestion {
  const punto = puntoDeGeoJSON(verificado?.location);
  const ruta = operacion.datos?.ruta ?? null;
  return {
    incidentId: operacion.incidente_id,
    incidentTitle: tituloIncidente(verificado, punto),
    score: puntuacionA100(operacion.triage),
    estado: operacion.estado,
    correlationId: operacion.correlacion_id,
    summary: verificado?.resumen ?? '',
    needs: verificado?.necesidades ?? [],
    affectedPeople: verificado?.personas_afectadas ?? null,
    confidence: typeof verificado?.confidence_score === 'number' ? verificado.confidence_score : null,
    triageComponents: componentesTriage(operacion.triage),
    triagePosition: operacion.triage?.posicion ?? null,
    routeKm: typeof ruta?.distancia_km === 'number' ? ruta.distancia_km : null,
    routeMinutes: typeof ruta?.duracion_min === 'number' ? ruta.duracion_min : null,
    routeAccessible: typeof ruta?.accesible === 'boolean' ? ruta.accesible : null,
    route: lineaDeGeoJSON(ruta?.geometria),
    zones: zonasDeColeccion(operacion.datos?.zonas_afectadas),
    geoDegraded: operacion.datos?.geo_degradado === true,
    signature: firmaDeDecision(operacion.decision),
    lat: punto?.lat ?? null,
    lng: punto?.lng ?? null,
  };
}

// ------------------------------------------------------------------ traza

const AGENTE_LEGIBLE: Record<string, string> = {
  'agente-1-orquestador': 'Orquestador',
  'agente-2-ingesta': 'Ingesta',
  'agente-3-verificacion': 'Verificacion',
  'agente-4-matching': 'Matching',
  'agente-5-geoespacial': 'Geoespacial',
  'coordinador-humano': 'Coordinador',
};

const EVENTO_LEGIBLE: Record<string, string> = {
  tarea_delegada: 'Tarea delegada',
  reporte_recibido: 'Reporte admitido',
  reporte_descartado: 'Reporte descartado',
  incidente_fusionado: 'Reportes fusionados',
  incidente_verificado: 'Incidente verificado',
  confianza_calculada: 'Confianza calculada',
  transicion_estado: 'Cambio de estado',
  decision_humana_registrada: 'Firma del coordinador',
  error: 'Error',
};

function textoDetalle(evento: EventoCrudo): string {
  const d = evento.detalle ?? {};
  const trozo = (clave: string): string | null => {
    const valor = d[clave];
    if (valor === undefined || valor === null || valor === '') return null;
    return String(valor);
  };

  switch (evento.tipo) {
    case 'transicion_estado': {
      const origen = trozo('origen');
      const estado = trozo('estado');
      const motivo = trozo('motivo');
      const salto = origen && estado ? `${etiquetaEstado(origen)} → ${etiquetaEstado(estado)}` : '';
      return [salto, motivo].filter(Boolean).join(' · ');
    }
    case 'tarea_delegada':
      return [trozo('paso'), trozo('receptor') ?? trozo('agente'), trozo('performativa')]
        .filter(Boolean).join(' · ');
    case 'incidente_verificado':
      return [
        etiquetaCategoria(trozo('category') ?? undefined),
        trozo('severity'),
        trozo('resumen'),
      ].filter(Boolean).join(' · ');
    case 'incidente_fusionado': {
      const origenes = d.reportes_origen;
      const cuantos = Array.isArray(origenes) ? origenes.length : 0;
      return `${cuantos} reporte(s) colapsados en un solo hecho`;
    }
    case 'decision_humana_registrada':
      return [
        d.aprobada === true ? 'aprobada' : 'rechazada',
        trozo('coordinador_id') ? `por ${trozo('coordinador_id')}` : null,
        trozo('justificacion'),
      ].filter(Boolean).join(' · ');
    case 'reporte_descartado':
      return trozo('motivo') ?? 'sin motivo declarado';
    case 'error':
      return trozo('error') ?? trozo('motivo') ?? 'fallo sin detalle';
    default:
      return trozo('motivo') ?? trozo('canal') ?? '';
  }
}

export function eventosDeTraza(traza: TrazaCruda | null): AuditEvent[] {
  return (traza?.eventos ?? []).map((evento) => ({
    id: evento.id,
    type: EVENTO_LEGIBLE[evento.tipo] ?? evento.tipo.replace(/_/g, ' '),
    agent: AGENTE_LEGIBLE[evento.agente] ?? evento.agente,
    at: evento.momento,
    summary: textoDetalle(evento),
  }));
}

/** Solo los eventos que tocan a un incidente concreto, mas los del hilo que no
    nombran incidente (delegaciones, errores de saga): sin esos ultimos la traza
    perderia justo el "que agente hizo que" que el panel quiere ensenar. */
export function eventosDelIncidente(eventos: EventoCrudo[], incidenteId: string): EventoCrudo[] {
  return eventos.filter((evento) => {
    const d = evento.detalle ?? {};
    const propio = d.incidente_id ?? d.verified_incident_id;
    if (typeof propio === 'string') return propio === incidenteId;
    return evento.tipo !== 'reporte_recibido' && evento.tipo !== 'reporte_descartado';
  });
}
