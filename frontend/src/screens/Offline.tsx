import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { useAppState } from '../state/AppState';

export default function Offline() {
  const navigate = useNavigate();
  const { setOffline } = useAppState();
  const { data: queue, loading } = useAsync(() => api.getSyncQueue(), []);
  const [sending, setSending] = useState(false);

  async function retry() {
    setSending(true);
    await api.flushSyncQueue();
    setOffline(false);
    navigate('/seguimiento/INC-2481');
  }

  return (
    <Screen back="/">
      <div className="kicker">Sin conexión</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Tu reporte está a salvo</h1>
      <p className="lede" style={{ marginBottom: 24 }}>
        Guardado en este dispositivo (IndexedDB, con la foto). Se envía solo al recuperar señal,
        incluso si cierras la app.
      </p>

      {loading && <div className="note">Leyendo la cola local…</div>}

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

      <button type="button" className="btn btn--secondary" style={{ marginTop: 24 }} onClick={retry} disabled={sending}>
        {sending ? 'Enviando…' : 'Intentar enviar ahora'}
      </button>

      <div className="note note--quiet" style={{ marginTop: 12 }}>
        Modo alto contraste y lector de pantalla activos en este flujo.
      </div>
    </Screen>
  );
}
