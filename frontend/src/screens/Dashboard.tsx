import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { MapView } from '../components/MapView';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { useAppState } from '../state/AppState';
import { bandOf, formatAge, formatDistance } from '../lib/band';

export default function Dashboard() {
  const navigate = useNavigate();
  const { scope } = useAppState();
  const [cluster, setCluster] = useState(true);
  const { data: incidents, loading } = useAsync(() => api.listIncidents(scope), [scope]);

  const points = useMemo(
    () => (incidents ?? []).map((i) => ({ lat: i.lat, lng: i.lng, score: i.score, title: i.title })),
    [incidents],
  );

  const kicker = scope === 'general' ? 'Coordinador general · Lima Centro' : 'Coordinador de zona · Cercado';

  return (
    <Screen back="/login">
      <ScreenHeader
        kicker={kicker}
        action={<span className="note">{incidents?.length ?? 0} activos</span>}
      />

      <h1 className="subtitle" style={{ margin: '8px 0 14px' }}>Mapa operativo</h1>

      <MapView mode="dashboard" height={250} center={[-12.052, -77.038]} zoom={13} points={points} cluster={cluster} />

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginTop: 7 }}>
        <span className="note note--quiet">
          {cluster
            ? 'Marcadores agrupados por densidad · toca un grupo para abrirlo'
            : 'Marcador por incidente · sin agrupar'}
        </span>
        <button type="button" className="link-btn" onClick={() => setCluster((v) => !v)}>
          {cluster ? 'Desagrupar' : 'Agrupar'}
        </button>
      </div>

      <div className="kicker" style={{ margin: '22px 0 6px' }}>Cola de incidentes</div>

      {loading && <div className="note">Cargando incidentes…</div>}

      <div>
        {incidents?.slice(0, 5).map((i) => {
          const b = bandOf(i.score);
          return (
            <button key={i.id} type="button" className="row-btn" style={{ padding: '14px 0' }} onClick={() => navigate(`/matching/${i.id}`)}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <PriorityMark score={i.score} />
                <span style={{ flex: 1, fontSize: 17 }}>{i.title}</span>
                <span style={{ fontSize: 12, letterSpacing: '.08em', color: b.textColor }}>{b.label}</span>
              </span>
              <span className="note" style={{ display: 'block', marginTop: 4, paddingLeft: 24 }}>
                {formatDistance(i.distanceKm)} · {i.need} · {formatAge(i.ageMinutes)}
              </span>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}
