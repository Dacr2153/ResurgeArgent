import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { MapView } from '../components/MapView';
import { Cargando, ErrorPanel, Vacio } from '../components/Estado';
import { api, ZONE_RADIUS_KM } from '../api/client';
import { useAsync } from '../api/useAsync';
import { etiquetaEstado } from '../api/mapeo';
import { useAppState } from '../state/AppState';
import { bandOf, formatAge, formatDistance } from '../lib/band';

export default function Dashboard() {
  const navigate = useNavigate();
  const { scope, coordinatorId } = useAppState();
  const [cluster, setCluster] = useState(true);
  const { data: incidents, loading, error, reload } = useAsync(() => api.listIncidents(scope), [scope]);

  // Un incidente sin ubicacion verificada llega en (0,0), que es un punto en el
  // golfo de Guinea: pintarlo seria peor que no pintarlo.
  const points = useMemo(
    () => (incidents ?? [])
      .filter((i) => i.lat !== 0 || i.lng !== 0)
      .map((i) => ({ lat: i.lat, lng: i.lng, score: i.score, title: i.title })),
    [incidents],
  );

  const kicker = scope === 'general'
    ? `Coordinador general${coordinatorId ? ` · ${coordinatorId}` : ''}`
    : `Coordinador de zona · radio ${ZONE_RADIUS_KM} km`;

  return (
    <Screen back="/login">
      <ScreenHeader
        kicker={kicker}
        action={<span className="note">{incidents?.length ?? 0} en cola</span>}
      />

      <h1 className="subtitle" style={{ margin: '8px 0 14px' }}>Mapa operativo</h1>

      {points.length > 0 && (
        <>
          <MapView mode="dashboard" height={250} points={points} cluster={cluster} />
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
        </>
      )}

      {!loading && !error && points.length === 0 && incidents && incidents.length > 0 && (
        <Vacio
          titulo="Ningún incidente de la cola tiene ubicación verificada."
          ayuda="El agente de verificación no pudo fijar coordenadas: la cola sigue siendo válida, el mapa no."
        />
      )}

      <div className="kicker" style={{ margin: '22px 0 6px' }}>Cola de incidentes</div>

      {loading && <Cargando texto="Cargando incidentes…" />}
      {error && <ErrorPanel error={error} onRetry={reload} />}

      {!loading && !error && incidents?.length === 0 && (
        <Vacio
          titulo={scope === 'zona' ? 'Sin incidentes en tu radio operativo.' : 'No hay operaciones abiertas.'}
          ayuda={
            scope === 'zona'
              ? `El alcance de zona solo muestra operaciones con ruta calculada a menos de ${ZONE_RADIUS_KM} km. Cambia a alcance general en /login para ver el resto.`
              : 'Nadie ha disparado todavía una emergencia. Envía un reporte desde /reportar y vuelve aquí.'
          }
        />
      )}

      <div>
        {incidents?.map((i) => {
          const b = bandOf(i.score);
          return (
            <button key={i.id} type="button" className="row-btn" style={{ padding: '14px 0' }} onClick={() => navigate(`/matching/${i.id}`)}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <PriorityMark score={i.score} />
                <span style={{ flex: 1, fontSize: 17 }}>{i.title}</span>
                <span style={{ fontSize: 12, letterSpacing: '.08em', color: b.textColor }}>{b.label}</span>
              </span>
              <span className="note" style={{ display: 'block', marginTop: 4, paddingLeft: 24 }}>
                {i.distanceKm > 0 ? `${formatDistance(i.distanceKm)} · ` : 'sin ruta · '}
                {i.need} · {formatAge(i.ageMinutes)}
                {i.estado ? ` · ${etiquetaEstado(i.estado)}` : ''}
              </span>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}
