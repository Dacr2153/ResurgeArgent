import { useState } from 'react';
import { Screen } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { Cargando, ErrorPanel, Vacio } from '../components/Estado';
import { mensajeDeError } from '../api/http';
import { useAppState } from '../state/AppState';

export default function Offline() {
  const { setOffline, refreshQueueSize } = useAppState();
  const { data: queue, loading, error, reload } = useAsync(() => api.getSyncQueue(), []);
  const [sending, setSending] = useState(false);
  const [fallo, setFallo] = useState('');
  const [enviados, setEnviados] = useState<number | null>(null);

  async function retry() {
    setSending(true);
    setFallo('');
    try {
      const res = await api.flushSyncQueue();
      setEnviados(res.sent);
      setOffline(false);
      refreshQueueSize();
      reload();
    } catch (e) {
      setFallo(mensajeDeError(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <Screen back="/">
      <div className="kicker">Sin conexión</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Tu reporte está a salvo</h1>
      <p className="lede" style={{ marginBottom: 24 }}>
        Los reportes que se crearon sin cobertura esperan turno en la cola de plataforma
        (<code>/plataforma/sincronizacion</code>) y salen en cuanto se pulsa enviar.
      </p>

      {loading && <Cargando texto="Leyendo la cola…" />}
      {error && <ErrorPanel error={error} onRetry={reload} />}
      {!loading && !error && queue?.length === 0 && (
        <Vacio titulo="No hay nada pendiente de enviar." ayuda="Todo lo que se reportó sin cobertura ya salió." />
      )}

      <div>
        {queue?.map((q) => (
          <div key={q.id} style={{ borderTop: '1px solid var(--color-divider)', padding: '14px 0', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <span style={{ marginTop: 3 }}><PriorityMark score={q.score} /></span>
            <span style={{ flex: 1 }}>
              <span style={{ display: 'block', fontSize: 17 }}>{q.title}</span>
              <span className="note" style={{ display: 'block', marginTop: 2 }}>{q.meta}</span>
            </span>
          </div>
        ))}
      </div>

      <button
        type="button"
        className="btn btn--secondary"
        style={{ marginTop: 24 }}
        onClick={retry}
        disabled={sending || !queue?.length}
      >
        {sending ? 'Enviando…' : 'Intentar enviar ahora'}
      </button>

      {enviados !== null && (
        <div className="callout callout--info" style={{ marginTop: 14 }} role="status">
          {enviados} reporte(s) marcados como enviados.
        </div>
      )}
      {fallo && <div className="callout callout--alert" style={{ marginTop: 14 }} role="alert">{fallo}</div>}
    </Screen>
  );
}
