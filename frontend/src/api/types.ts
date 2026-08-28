export type PriorityBand = 'CRITICO' | 'ALTO' | 'MEDIO';

export type SeverityId = 'critical' | 'high' | 'medium';

export type IncidentCategory = 'Incendio' | 'Inundacion' | 'Derrumbe' | 'Rescate';

export type CoordinatorScope = 'zona' | 'general';

export interface Incident {
  id: string;
  title: string;
  score: number;
  lat: number;
  lng: number;
  /** Distancia al usuario, en km. */
  distanceKm: number;
  need: string;
  /** Minutos transcurridos desde el reporte. */
  ageMinutes: number;
  /** Estado de la operacion en el Orquestador. Ausente en las misiones de
      plataforma, que no exponen la maquina de estados. */
  estado?: string;
  /** Hilo de auditoria al que pertenece. Ausente por el mismo motivo. */
  correlationId?: string;
}

export interface TrackStep {
  label: string;
  meta: string;
  done: boolean;
}

export interface TrackedReport {
  id: string;
  title: string;
  score: number;
  steps: TrackStep[];
  unreadMessages: number;
}

export interface ReportDraft {
  category: IncidentCategory | null;
  severity: SeverityId;
  description: string;
  hasPhoto: boolean;
  address: string;
  phone: string;
  otp: string;
  /** Ubicacion real del navegador. `null` mientras no haya permiso o lectura:
      se envia solo cuando existe, nunca una coordenada de relleno. */
  lat: number | null;
  lng: number | null;
}

export interface SubmittedReport {
  id: string;
  status: 'recibido' | 'pendiente_verificacion' | 'en_cola_local';
}

/** Un vertice de una geometria, ya en el orden que entiende Leaflet: [lat, lng]. */
export type LatLng = [number, number];

/** Poligono de zona afectada que emite el agente geoespacial. */
export interface ZonePolygon {
  id: string;
  /** Anillos del poligono, exterior primero, ya en [lat, lng]. */
  rings: LatLng[][];
  severity: string;
  incidentCount: number;
}

/** Firma del coordinador ya aplicada sobre un incidente. */
export interface DecisionSignature {
  id: string;
  coordinatorId: string;
  approved: boolean;
  justification: string;
  at: string;
}

/** Componente de la puntuacion de triage, tal como lo desglosa el backend. */
export interface TriageComponent {
  label: string;
  value: number;
}

/**
 * Lo que el coordinador necesita para firmar. No hay agente de matching montado
 * en el backend, asi que aqui no se propone un voluntario concreto: se muestra
 * lo que el sistema si sabe (triage, ruta, necesidades) y se firma sobre eso.
 */
export interface MatchSuggestion {
  incidentId: string;
  incidentTitle: string;
  score: number;
  estado: string;
  correlationId: string;
  summary: string;
  needs: string[];
  affectedPeople: number | null;
  confidence: number | null;
  triageComponents: TriageComponent[];
  triagePosition: number | null;
  routeKm: number | null;
  routeMinutes: number | null;
  routeAccessible: boolean | null;
  route: LatLng[];
  zones: ZonePolygon[];
  /** true cuando el agente geoespacial no respondio y la operacion va degradada. */
  geoDegraded: boolean;
  signature: DecisionSignature | null;
  lat: number | null;
  lng: number | null;
}

/** Sentido de la firma. Los tres se traducen a un POST /orquestador/decisiones. */
export type MatchDecision = 'assign' | 'reject' | 'suspend';

/** Evento de la traza de auditoria de una operacion. */
export interface AuditEvent {
  id: string;
  type: string;
  agent: string;
  at: string;
  /** Resumen legible del detalle; el detalle crudo va aparte. */
  summary: string;
}

export interface Mission {
  incidentId: string;
  title: string;
  address: string;
  etaMinutes: number;
  distanceKm: number;
  mode: string;
  route: [number, number][];
  checklist: { key: string; label: string }[];
}

export interface RecoveryQuestion {
  id: string;
  question: string;
  options: string[];
}

export interface RecoveryPlanStep {
  tag: string;
  title: string;
  body: string;
}

export interface QueuedSync {
  id: string;
  title: string;
  meta: string;
  score: number;
}

export interface VolunteerSignup {
  fullName: string;
  document: string;
  phone: string;
  resource: string;
}
