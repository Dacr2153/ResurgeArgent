import type { PriorityBand } from '../api/types';

export interface BandStyle {
  band: PriorityBand;
  /** Etiqueta con acento, para lectura. */
  label: string;
  /** Glifo: la prioridad nunca se comunica solo por color. */
  glyph: string;
  /** Relleno del disco. */
  color: string;
  /** Color de texto accesible sobre el fondo de papel. */
  textColor: string;
}

export function bandOf(score: number): BandStyle {
  if (score > 80) {
    return { band: 'CRITICO', label: 'CRÍTICO', glyph: '!', color: 'var(--color-accent-2)', textColor: 'var(--color-accent-2-700)' };
  }
  if (score >= 50) {
    return { band: 'ALTO', label: 'ALTO', glyph: '▲', color: 'var(--color-process-yellow)', textColor: 'var(--color-neutral-700)' };
  }
  return { band: 'MEDIO', label: 'MEDIO', glyph: '●', color: 'var(--color-accent)', textColor: 'var(--color-accent-700)' };
}

/** Version con hex literal, para Leaflet (que no resuelve custom properties
    dentro del HTML de un divIcon inyectado). */
export function bandHex(score: number): { color: string; glyph: string; label: string } {
  if (score > 80) return { color: '#d6006c', glyph: '!', label: 'CRÍTICO' };
  if (score >= 50) return { color: '#edbb00', glyph: '▲', label: 'ALTO' };
  return { color: '#0088b0', glyph: '●', label: 'MEDIO' };
}

export function formatAge(minutes: number): string {
  if (minutes < 60) return `hace ${minutes} min`;
  const h = Math.floor(minutes / 60);
  return `hace ${h} h`;
}

export function formatDistance(km: number): string {
  return `${km.toFixed(1)} km`;
}
