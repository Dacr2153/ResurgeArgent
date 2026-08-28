import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityTag } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';

export default function Matching() {
  const { id = 'INC-2481' } = useParams();
  const { data: match, loading } = useAsync(() => api.getMatchSuggestion(id), [id]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  async function act(action: 'assign' | 'reassign' | 'reject') {
    setBusy(true);
    const res = await api.assignMatch(id, action);
    setNote(res.message);
    setBusy(false);
  }

  if (loading || !match) return <Screen back="/dashboard"><div className="note">Calculando asignación…</div></Screen>;

  return (
    <Screen back="/dashboard">
      <ScreenHeader kicker="Asignación sugerida" />

      <h1 style={{ fontSize: 26, lineHeight: 1.1, margin: '8px 0 4px' }}>{match.incidentTitle}</h1>
      <div style={{ marginBottom: 22, display: 'flex', alignItems: 'center', gap: 7, fontSize: 12 }}>
        <PriorityTag score={match.score} size={16} />
        <span style={{ color: 'var(--color-neutral-700)', letterSpacing: '.1em' }}>· SLA {match.slaMinutes} min</span>
      </div>

      <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Recurso propuesto</div>
        <div style={{ fontSize: 21 }}>{match.volunteerName} · {match.volunteerRole}</div>
        <div className="note" style={{ marginTop: 4 }}>
          {match.distanceKm} km · ETA {match.etaMinutes} min · disponible · {match.completedMissions} misiones completadas
        </div>
        <div style={{ display: 'flex', gap: 20, marginTop: 16 }}>
          <span className="note">
            Compatibilidad
            <span style={{ display: 'block', fontSize: 24, color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
              {match.compatibility.toFixed(2)}
            </span>
          </span>
          <span className="note">
            Carga actual
            <span style={{ display: 'block', fontSize: 24, color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
              {match.currentLoad}
            </span>
          </span>
        </div>
      </div>

      <div className="stack" style={{ gap: 8, marginTop: 28 }}>
        <button type="button" className="btn btn--primary" disabled={busy} onClick={() => act('assign')}>Asignar</button>
        <button type="button" className="btn btn--secondary" disabled={busy} onClick={() => act('reassign')}>Reasignar manualmente</button>
        <button
          type="button"
          className="btn btn--ghost"
          style={{ color: 'var(--color-accent-2-700)', minHeight: 48 }}
          disabled={busy}
          onClick={() => act('reject')}
        >
          Rechazar sugerencia
        </button>
      </div>

      {note && <div className="callout callout--info" style={{ marginTop: 16 }} role="status">{note}</div>}
    </Screen>
  );
}
