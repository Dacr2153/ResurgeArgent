import { bandOf } from '../lib/band';

/**
 * Disco de prioridad. La prioridad nunca se comunica solo por color: el disco
 * lleva siempre un glifo y va acompanado de la etiqueta textual de la banda.
 */
export function PriorityMark({ score, size = 16 }: { score: number; size?: number }) {
  const b = bandOf(score);
  return (
    <span
      aria-hidden="true"
      style={{
        width: size, height: size, flex: `0 0 ${size}px`,
        borderRadius: '50%',
        background: b.color,
        color: b.band === 'ALTO' ? 'var(--color-text)' : '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: Math.round(size * 0.62), lineHeight: 1,
      }}
    >
      {b.glyph}
    </span>
  );
}

/** Disco + etiqueta "CRÍTICO · 92", el par que se repite en todo el producto. */
export function PriorityTag({ score, size = 17 }: { score: number; size?: number }) {
  const b = bandOf(score);
  return (
    <span style={{
      display: 'flex', alignItems: 'center', gap: 7,
      color: b.textColor, fontSize: 13, letterSpacing: '.1em',
    }}>
      <PriorityMark score={score} size={size} />
      {b.label} · {score}
    </span>
  );
}
