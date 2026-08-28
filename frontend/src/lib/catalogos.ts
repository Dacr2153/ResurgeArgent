/**
 * Catalogos de la interfaz: las opciones que se le ofrecen a quien rellena un
 * formulario. No son datos de ejemplo, son vocabulario de pantalla; el backend
 * los traduce a CAP 1.2 en `api/client.ts`.
 */
import type { IncidentCategory, SeverityId } from '../api/types';

export const CATEGORIES: { label: IncidentCategory; hint: string }[] = [
  { label: 'Incendio', hint: 'humo, fuego' },
  { label: 'Inundacion', hint: 'agua, huaico' },
  { label: 'Derrumbe', hint: 'estructura' },
  { label: 'Rescate', hint: 'persona atrapada' },
];

/**
 * El `score` de cada severidad es solo para pintar el disco de prioridad
 * mientras se rellena el formulario. La puntuacion real la calcula el motor de
 * triage del backend con severidad, urgencia, personas y confianza: lo que se
 * ve aqui no condiciona la cola.
 */
export const SEVERITIES: { id: SeverityId; label: string; detail: string; score: number }[] = [
  { id: 'critical', label: 'Critico', detail: 'vidas en riesgo', score: 92 },
  { id: 'high', label: 'Alto', detail: 'dano en curso', score: 65 },
  { id: 'medium', label: 'Medio', detail: 'contenido', score: 40 },
];

export const RESOURCES = ['Brigada medica', 'Transporte', 'Rescate', 'Agua y viveres', 'Logistica'];
