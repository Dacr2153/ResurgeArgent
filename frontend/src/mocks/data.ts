import type {
  Incident, Mission, MatchSuggestion, QueuedSync,
  RecoveryPlanStep, RecoveryQuestion, TrackedReport,
} from '../api/types';

export const INCIDENTS: Incident[] = [
  { id: 'INC-2481', title: 'Incendio · Jr. Camaná 654',        score: 92, lat: -12.0489, lng: -77.0378, distanceKm: 0.8, need: '2 brigadistas',   ageMinutes: 4 },
  { id: 'INC-2482', title: 'Derrumbe · Av. Abancay 490',       score: 86, lat: -12.0533, lng: -77.0309, distanceKm: 1.4, need: 'rescate',         ageMinutes: 9 },
  { id: 'INC-2483', title: 'Inundación · Rímac, Cuadra 3',     score: 71, lat: -12.0301, lng: -77.0281, distanceKm: 2.6, need: 'bombas de agua',  ageMinutes: 12 },
  { id: 'INC-2484', title: 'Rescate · Barrios Altos',          score: 64, lat: -12.0466, lng: -77.0231, distanceKm: 2.1, need: '1 voluntario',    ageMinutes: 18 },
  { id: 'INC-2485', title: 'Inundación · Jr. Huanta',          score: 58, lat: -12.0512, lng: -77.0245, distanceKm: 1.9, need: 'traslado',        ageMinutes: 22 },
  { id: 'INC-2486', title: 'Incendio menor · La Victoria',     score: 44, lat: -12.0632, lng: -77.0231, distanceKm: 3.4, need: 'verificación',    ageMinutes: 26 },
  { id: 'INC-2487', title: 'Fuga de gas · Breña',              score: 49, lat: -12.0578, lng: -77.0501, distanceKm: 2.8, need: 'verificación',    ageMinutes: 31 },
  { id: 'INC-2488', title: 'Árbol caído · Jesús María',        score: 38, lat: -12.0741, lng: -77.0451, distanceKm: 4.2, need: 'cuadrilla',       ageMinutes: 38 },
  { id: 'INC-2489', title: 'Techo dañado · San Martín',        score: 41, lat: -12.0398, lng: -77.0489, distanceKm: 3.1, need: 'lona',            ageMinutes: 44 },
  { id: 'INC-2490', title: 'Corte de luz · Cercado',           score: 33, lat: -12.0442, lng: -77.0331, distanceKm: 1.1, need: 'reporte',         ageMinutes: 52 },
];

/** Radio operativo del coordinador de zona, en km. */
export const ZONE_RADIUS_KM = 3;

export const TRACKED_REPORT: TrackedReport = {
  id: 'INC-2481',
  title: 'Incendio · Jr. Camaná 654',
  score: 92,
  unreadMessages: 1,
  steps: [
    { label: 'Reporte recibido',          meta: '14:02 · verificado por SMS',              done: true },
    { label: 'Priorizado · CRÍTICO 92',   meta: '14:03 · agrupado con 2 reportes vecinos', done: true },
    { label: 'Brigada asignada',          meta: '14:07 · Ana Q. · ETA 9 min',              done: true },
    { label: 'Atendido',                  meta: 'pendiente',                                done: false },
  ],
};

export const MISSION: Mission = {
  incidentId: 'INC-2481',
  title: 'Incendio · Jr. Camaná 654',
  address: 'Jr. Camaná 654 · contacto: coordinador de zona (visible solo durante la misión)',
  etaMinutes: 9,
  distanceKm: 2.4,
  mode: 'a pie',
  route: [[-12.0464, -77.0428], [-12.0478, -77.0409], [-12.0489, -77.0378]],
  checklist: [
    { key: 'agua',     label: 'Agua · 6 L' },
    { key: 'botiquin', label: 'Botiquín completo' },
    { key: 'casco',    label: 'Casco y guantes' },
    { key: 'radio',    label: 'Radio y batería externa' },
  ],
};

export const MATCH: Omit<MatchSuggestion, 'incidentId' | 'incidentTitle' | 'score'> = {
  slaMinutes: 12,
  volunteerName: 'Ana Quispe',
  volunteerRole: 'brigada médica',
  distanceKm: 1.2,
  etaMinutes: 7,
  completedMissions: 14,
  compatibility: 0.91,
  currentLoad: '0/2',
};

export const RECOVERY_QUESTIONS: RecoveryQuestion[] = [
  { id: 'vivienda', question: '¿Tu vivienda quedó habitable?',                          options: ['Sí, con daños menores', 'Parcialmente', 'No, está inhabitable'] },
  { id: 'salud',    question: '¿Alguien de tu familia necesita atención médica continua?', options: ['No', 'Sí, una persona', 'Sí, dos o más'] },
  { id: 'medios',   question: '¿Perdiste documentos o medios de trabajo?',              options: ['Ninguno', 'Documentos', 'Medios de trabajo'] },
];

export const RECOVERY_PLAN: RecoveryPlanStep[] = [
  { tag: 'PASO 1 · HOY',      title: 'Constancia de damnificado',  body: 'Preséntate en el módulo municipal con el ID INC-2481 y tu DNI.' },
  { tag: 'PASO 2 · 72 H',     title: 'Evaluación estructural',     body: 'Un ingeniero de Defensa Civil verifica la vivienda antes de habitarla.' },
  { tag: 'PASO 3 · 15 DÍAS',  title: 'Bono de reconstrucción',     body: 'Solicítalo con la constancia y el informe estructural adjuntos.' },
];

export const SYNC_QUEUE: QueuedSync[] = [
  { id: 'q1', title: 'Reporte · Incendio Jr. Camaná', meta: 'con foto · 1.2 MB · en cola desde 14:02', score: 92 },
  { id: 'q2', title: 'Reporte · Techo dañado',        meta: 'sin foto · en cola desde 13:48',          score: 41 },
];

export const RESOURCES = ['Brigada médica', 'Transporte', 'Rescate', 'Agua y víveres', 'Logística'];

export const CATEGORIES = [
  { label: 'Incendio',   hint: 'humo, fuego' },
  { label: 'Inundación', hint: 'agua, huaico' },
  { label: 'Derrumbe',   hint: 'estructura' },
  { label: 'Rescate',    hint: 'persona atrapada' },
] as const;

export const SEVERITIES = [
  { id: 'critical', label: 'Crítico', detail: 'vidas en riesgo', score: 92 },
  { id: 'high',     label: 'Alto',    detail: 'daño en curso',   score: 65 },
  { id: 'medium',   label: 'Medio',   detail: 'contenido',       score: 40 },
] as const;
