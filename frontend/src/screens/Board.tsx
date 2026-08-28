import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { bandOf, formatAge, formatDistance } from '../lib/band';

const FILTERS: { label: string; radiusKm: number | null }[] = [
  { label: '2 km', radiusKm: 2 },
  { label: '5 km', radiusKm: 5 },
  { label: 'Toda la zona', radiusKm: null },
];

export default function Board() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState(FILTERS[0]);
  const { data: missions, loading } = useAsync(() => api.listMissions(filter.radiusKm), [filter.radiusKm]);

  return (
    <Screen back="/">
      <ScreenHeader
        kicker="Misiones · tiempo real"
        action={
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--color-accent-700)' }}>
            <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-accent)' }} />
            WS activo
          </span>
        }
      />

      <h1 className="subtitle" style={{ margin: '10px 0 16px' }}>Cerca de ti</h1>

      <div style={{ display: 'flex', gap: 6, marginBottom: 18, flexWrap: 'wrap' }}>
        {FILTERS.map((f) => (
          <button key={f.label} type="button" className="chip" aria-pressed={filter.label === f.label} onClick={() => setFilter(f)}>
            {f.label}
          </button>
        ))}
      </div>

      {loading && <div className="note">Buscando misiones…</div>}

      {!loading && missions?.length === 0 && (
        <div className="note">No hay misiones abiertas en este radio.</div>
      )}

      <div className="stack">
        {missions?.map((m) => {
          const b = bandOf(m.score);
          return (
            <button key={m.id} type="button" className="row-btn" onClick={() => navigate(`/voluntario/mapa/${m.id}`)}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, letterSpacing: '.1em', color: b.textColor }}>
                <PriorityMark score={m.score} />
                {b.label} · {m.score}
              </span>
              <span style={{ display: 'block', fontSize: 19, margin: '6px 0 3px' }}>{m.title}</span>
              <span className="note" style={{ display: 'block' }}>
                {formatDistance(m.distanceKm)} · {m.need} · {formatAge(m.ageMinutes)}
              </span>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}
