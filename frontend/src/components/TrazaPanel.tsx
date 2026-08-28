/**
 * Panel de traza del coordinador: que agente hizo que, y cuando.
 *
 * Es lo que responde el "por que se despachó ahí y no allá". Sale entero de
 * `GET /orquestador/auditoria/{correlacion_id}`, el mismo hilo que comparten los
 * cinco agentes; aqui solo se filtra al incidente que se esta mirando y se
 * ordena en el sentido de lectura de una bitacora.
 *
 * Sin librerias nuevas y con los tokens de `styles/tokens.css`, como el resto.
 */
import { useState } from 'react';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { Cargando, ErrorPanel, Vacio } from './Estado';

/** Color de tinta por agente. La traza se lee en diagonal buscando quien actuo,
    asi que el emisor tiene que distinguirse antes que el texto. */
const TINTA: Record<string, string> = {
  Orquestador: 'var(--color-accent-700)',
  Ingesta: 'var(--color-neutral-700)',
  Verificacion: 'var(--color-neutral-700)',
  Geoespacial: 'var(--color-neutral-700)',
  Coordinador: 'var(--color-accent-2-700)',
};

function hora(iso: string): string {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return iso;
  return t.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

interface Props {
  correlationId: string;
  incidentId: string;
}

export function TrazaPanel({ correlationId, incidentId }: Props) {
  const { data: eventos, loading, error, reload } = useAsync(
    () => api.getAuditTrail(correlationId, incidentId),
    [correlationId, incidentId],
  );
  const [abierto, setAbierto] = useState(false);

  const total = eventos?.length ?? 0;
  // Una traza completa son decenas de lineas; la demostracion necesita ver el
  // final (lo ultimo que paso) sin desplegar todo.
  const visibles = abierto ? eventos ?? [] : (eventos ?? []).slice(-6);

  return (
    <section style={{ marginTop: 30, borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div className="kicker">Traza de la operación</div>
        {total > 6 && (
          <button type="button" className="link-btn" onClick={() => setAbierto((v) => !v)}>
            {abierto ? 'Ver solo lo último' : `Ver los ${total} eventos`}
          </button>
        )}
      </div>
      <div className="note note--quiet" style={{ marginTop: 4, marginBottom: 12 }}>
        Hilo {correlationId.slice(0, 8)} · un solo identificador para los cinco agentes
      </div>

      {loading && <Cargando texto="Leyendo la traza…" />}
      {error && <ErrorPanel error={error} onRetry={reload} />}
      {!loading && !error && total === 0 && (
        <Vacio
          titulo="Sin eventos en este hilo."
          ayuda="La auditoría vive en memoria del proceso: si el backend se reinició, la traza anterior se perdió."
        />
      )}

      <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {visibles.map((evento) => (
          <li
            key={evento.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '68px 1fr',
              gap: 12,
              padding: '9px 0',
              borderTop: '1px solid var(--color-divider)',
            }}
          >
            <span
              className="note"
              style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}
            >
              {hora(evento.at)}
            </span>
            <span>
              <span style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span
                  style={{
                    fontSize: 11,
                    letterSpacing: '.1em',
                    textTransform: 'uppercase',
                    color: TINTA[evento.agent] ?? 'var(--color-neutral-700)',
                  }}
                >
                  {evento.agent}
                </span>
                <span style={{ fontSize: 15 }}>{evento.type}</span>
              </span>
              {evento.summary && (
                <span className="note" style={{ display: 'block', marginTop: 2 }}>{evento.summary}</span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
