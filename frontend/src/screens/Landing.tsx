import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen } from '../components/Screen';

export default function Landing() {
  const navigate = useNavigate();
  const [trackId, setTrackId] = useState('');

  const track = () => {
    const id = trackId.trim();
    if (id) navigate(`/seguimiento/${encodeURIComponent(id)}`);
  };

  return (
    <Screen>
      <div className="kicker">Emergencias · Lima Centro</div>
      <h1 className="display" style={{ margin: '12px 0 14px' }}>¿Necesitas ayuda ahora?</h1>
      <p className="lede" style={{ marginBottom: 26 }}>
        Tres pasos y confirmamos. Funciona sin señal: guardamos tu reporte y lo enviamos al recuperar red.
      </p>

      <button type="button" className="btn btn--danger" onClick={() => navigate('/reportar')}>
        Reportar emergencia
      </button>

      <div className="kicker" style={{ margin: '32px 0 10px' }}>Ya reporté</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          className="input"
          style={{ flex: 1 }}
          value={trackId}
          onChange={(e) => setTrackId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && track()}
          placeholder="ID de reporte"
          aria-label="ID de reporte"
        />
        <button type="button" className="btn btn--secondary" style={{ width: 'auto', minHeight: 48 }} onClick={track}>
          Seguir
        </button>
      </div>

      <div className="stack" style={{ gap: 10, marginTop: 38 }}>
        <button type="button" className="link-row" onClick={() => navigate('/registro')}>Soy voluntario →</button>
        <button type="button" className="link-row" onClick={() => navigate('/login')}>Soy coordinador →</button>
      </div>
    </Screen>
  );
}
