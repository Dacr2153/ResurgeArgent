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
}

export interface SubmittedReport {
  id: string;
  status: 'recibido' | 'pendiente_verificacion' | 'en_cola_local';
}

export interface MatchSuggestion {
  incidentId: string;
  incidentTitle: string;
  score: number;
  slaMinutes: number;
  volunteerName: string;
  volunteerRole: string;
  distanceKm: number;
  etaMinutes: number;
  completedMissions: number;
  compatibility: number;
  currentLoad: string;
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
