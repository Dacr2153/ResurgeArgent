import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppState } from '../state/AppState';
import { demoEnabled } from '../lib/demo';

interface ScreenProps {
  children: ReactNode;
  /**
   * Destino del boton de volver. Una ruta la fuerza (util cuando se llega a la
   * pantalla en frio, sin historial); `true` retrocede en el historial.
   * Omitir para pantallas raiz que no tienen a donde volver.
   */
  back?: string | true;
}

/**
 * Marco de toda pantalla: barra de navegacion, columna de lectura centrada y,
 * cuando no hay red, la banda persistente de cola local en el borde superior.
 */
export function Screen({ children, back }: ScreenProps) {
  const { offline, queueSize } = useAppState();
  const navigate = useNavigate();
  const location = useLocation();
  const showIndex = demoEnabled() && location.pathname !== '/demo';

  const goBack = () => {
    if (back === true) navigate(-1);
    else if (typeof back === 'string') navigate(back);
  };

  return (
    <div className="screen">
      {offline && (
        <div
          role="status"
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            padding: '9px 22px',
            background: 'var(--color-accent-2-200)',
            color: 'var(--color-accent-2-800)',
            fontSize: 13,
          }}
        >
          <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-accent-2)' }} />
          Sin red · {queueSize} reporte(s) en cola local
        </div>
      )}

      {(back || showIndex) && (
        <nav className="topnav">
          {back ? (
            <button type="button" className="link-btn" onClick={goBack}>← Atrás</button>
          ) : <span />}
          {showIndex && (
            <button type="button" className="link-btn" onClick={() => navigate('/demo')}>
              Pantallas ▸
            </button>
          )}
        </nav>
      )}

      <main className="screen__body">{children}</main>
    </div>
  );
}

/** Encabezado de pantalla: kicker + accion secundaria a la derecha. */
export function ScreenHeader({ kicker, action }: { kicker: string; action?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
      <div className="kicker">{kicker}</div>
      {action}
    </div>
  );
}
