import { useLocation, useNavigate } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { useAppState } from '../state/AppState';
import { SCREEN_ROUTES } from '../lib/routes';

/**
 * Indice de las 11 pantallas. Existe para recorrer el flujo en la presentacion
 * del hackaton; no es parte del producto.
 */
export default function DemoIndex() {
  const navigate = useNavigate();
  const location = useLocation();
  const { offline, setOffline, gpsDenied, setGpsDenied, scope, setScope } = useAppState();

  const toggleStyle = (active: boolean) => ({
    minHeight: 40,
    padding: '0 12px',
    textAlign: 'left' as const,
    borderRadius: 'var(--radius-md)',
    fontSize: 14,
    cursor: 'pointer',
    background: active ? 'var(--color-accent-2-200)' : 'transparent',
    color: active ? 'var(--color-accent-2-800)' : 'var(--color-neutral-800)',
    border: active ? '1px solid var(--color-accent-2)' : '1px solid var(--color-border)',
  });

  return (
    <Screen>
      <div className="kicker">Prototipo · Lima</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Plataforma de Gestión de Emergencias</h1>
      <p className="lede" style={{ fontSize: 15, marginBottom: 26 }}>
        Once pantallas de los cuatro flujos, con mapa real, prioridad accesible y modo sin red.
      </p>

      <div className="kicker" style={{ marginBottom: 10 }}>Pantallas</div>
      <div className="stack" style={{ gap: 1, marginBottom: 30 }}>
        {SCREEN_ROUTES.map((r, i) => {
          const active = location.pathname === r.path;
          return (
            <button
              key={r.path}
              type="button"
              onClick={() => navigate(r.path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left',
                minHeight: 38, padding: '5px 8px', border: 'none', borderRadius: 'var(--radius-md)',
                cursor: 'pointer', fontSize: 15,
                background: active ? 'var(--color-accent-200)' : 'transparent',
                color: active ? 'var(--color-accent-800)' : 'var(--color-text)',
              }}
            >
              <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--color-neutral-600)', fontSize: 12, width: 20, flex: '0 0 20px' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <span style={{ flex: 1 }}>{r.label}</span>
              <span style={{ fontSize: 11, color: 'var(--color-neutral-600)', letterSpacing: '.04em' }}>{r.role}</span>
            </button>
          );
        })}
      </div>

      <div className="kicker" style={{ marginBottom: 10 }}>Estados transversales</div>
      <div className="stack" style={{ gap: 6 }}>
        <button
          type="button"
          style={toggleStyle(offline)}
          onClick={() => { const next = !offline; setOffline(next); navigate(next ? '/offline' : '/'); }}
        >
          Sin red / cola de sync
        </button>
        <button
          type="button"
          style={toggleStyle(gpsDenied)}
          onClick={() => { setGpsDenied(!gpsDenied); navigate('/reportar'); }}
        >
          GPS denegado
        </button>
        <button
          type="button"
          style={toggleStyle(scope === 'general')}
          onClick={() => setScope(scope === 'zona' ? 'general' : 'zona')}
        >
          {scope === 'general' ? 'RBAC: coordinador general' : 'RBAC: coordinador de zona'}
        </button>
      </div>

      <div className="note" style={{ marginTop: 30 }}>
        Prioridad nunca por color solo:
        <span className="stack" style={{ gap: 5, marginTop: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--color-accent-2-700)' }}>
            <span aria-hidden="true" style={{ width: 17, height: 17, borderRadius: '50%', background: 'var(--color-accent-2)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>!</span>
            CRÍTICO · 80+
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--color-neutral-700)' }}>
            <span aria-hidden="true" style={{ width: 17, height: 17, borderRadius: '50%', background: 'var(--color-process-yellow)', color: 'var(--color-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>▲</span>
            ALTO · 50–80
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--color-accent-700)' }}>
            <span aria-hidden="true" style={{ width: 17, height: 17, borderRadius: '50%', background: 'var(--color-accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>●</span>
            MEDIO · &lt;50
          </span>
        </span>
      </div>
    </Screen>
  );
}
