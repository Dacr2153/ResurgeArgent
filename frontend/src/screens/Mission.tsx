import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { MapView } from '../components/MapView';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';

export default function Mission() {
  const navigate = useNavigate();
  const { id = 'INC-2481' } = useParams();
  const { data: mission, loading } = useAsync(() => api.getMission(id), [id]);
  const [checked, setChecked] = useState<Record<string, boolean>>({ agua: true });
  const [supportOpen, setSupportOpen] = useState(false);

  if (loading || !mission) return <Screen back="/voluntario/misiones"><div className="note">Cargando misión…</div></Screen>;

  return (
    <Screen back="/voluntario/misiones">
      <ScreenHeader kicker={`Misión activa · ${mission.incidentId}`} />

      <div style={{ marginTop: 8 }}>
        <MapView mode="route" height={230} route={mission.route} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', margin: '14px 0 4px' }}>
        <span style={{ fontSize: 24, fontWeight: 600 }}>ETA {mission.etaMinutes} min</span>
        <span className="note">{mission.distanceKm} km · {mission.mode}</span>
      </div>
      <p className="lede" style={{ fontSize: 15 }}>{mission.address}</p>

      <div className="kicker" style={{ margin: '24px 0 10px' }}>Checklist de recursos</div>
      <div className="stack" style={{ gap: 2 }}>
        {mission.checklist.map((item) => {
          const on = !!checked[item.key];
          return (
            <button
              key={item.key}
              type="button"
              role="checkbox"
              aria-checked={on}
              onClick={() => setChecked((prev) => ({ ...prev, [item.key]: !prev[item.key] }))}
              style={{
                display: 'flex', alignItems: 'center', gap: 11, width: '100%', minHeight: 46,
                textAlign: 'left', background: 'none', border: 'none', fontSize: 16, cursor: 'pointer', padding: 0,
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 22, height: 22, flex: '0 0 22px', borderRadius: 'var(--radius-md)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                  background: on ? 'var(--color-accent)' : 'var(--color-neutral-100)',
                  color: on ? '#fff' : 'transparent',
                  border: on ? '1px solid var(--color-accent)' : '1px solid var(--color-border-strong)',
                }}
              >
                ✓
              </span>
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="stack" style={{ gap: 8, marginTop: 26 }}>
        <button type="button" className="btn btn--primary" onClick={() => navigate(`/recuperacion/${mission.incidentId}`)}>
          Marcar como atendido
        </button>
        <button type="button" className="btn btn--outline-danger" onClick={() => setSupportOpen((v) => !v)}>
          Necesito apoyo
        </button>
      </div>

      {supportOpen && (
        <div className="callout callout--alert" style={{ marginTop: 14 }} role="status">
          Canal directo abierto con el coordinador de zona · llamada en curso 00:07. Toca para escalar a bomberos (105).
        </div>
      )}
    </Screen>
  );
}
