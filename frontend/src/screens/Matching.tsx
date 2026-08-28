import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityTag } from '../components/PriorityMark';
import { MapView } from '../components/MapView';
import { TrazaPanel } from '../components/TrazaPanel';
import { Cargando, ErrorPanel } from '../components/Estado';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { mensajeDeError } from '../api/http';
import { etiquetaEstado } from '../api/mapeo';
import { useAppState } from '../state/AppState';
import type { MatchDecision } from '../api/types';

/** Las tres firmas posibles y lo que significan en la maquina de estados del
    Orquestador. Reasignar manualmente no esta: no hay agente de matching
    montado y ofrecer un boton que no despacha a nadie seria mentir. */
const ACCIONES: { id: MatchDecision; label: string; clase: string; ayuda: string }[] = [
  { id: 'assign', label: 'Asignar', clase: 'btn btn--primary', ayuda: 'Aprueba la operación: el incidente pasa a asignado.' },
  { id: 'suspend', label: 'Suspender · pedir más información', clase: 'btn btn--secondary', ayuda: 'No lo aprueba todavía, sin declarar que el reporte sea falso.' },
  { id: 'reject', label: 'Rechazar', clase: 'btn btn--ghost', ayuda: 'Descarta el incidente. Queda firmado y auditado.' },
];

export default function Matching() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { coordinatorId } = useAppState();
  const { data: match, loading, error, reload } = useAsync(() => api.getMatchSuggestion(id), [id]);

  const [justificacion, setJustificacion] = useState('');
  const [busy, setBusy] = useState(false);
  const [nota, setNota] = useState('');
  const [fallo, setFallo] = useState('');

  async function firmar(accion: MatchDecision) {
    setBusy(true);
    setFallo('');
    setNota('');
    try {
      const res = await api.assignMatch(id, accion, {
        coordinatorId,
        justification: justificacion.trim(),
      });
      setNota(res.message);
      setJustificacion('');
      reload();
    } catch (e) {
      // El texto del backend es el del dominio ("un rechazo debe justificarse"):
      // sustituirlo por uno generico le quitaria al coordinador la unica pista
      // de que tiene que corregir.
      setFallo(mensajeDeError(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Screen back="/dashboard"><Cargando texto="Leyendo la operación…" /></Screen>;
  if (error || !match) {
    return (
      <Screen back="/dashboard">
        <ErrorPanel error={error ?? new Error(`No hay operación abierta para ${id}.`)} onRetry={reload} />
      </Screen>
    );
  }

  const sinIdentidad = coordinatorId.trim().length === 0;
  // El dominio solo obliga a justificar cuando no se aprueba, pero la caja se
  // muestra siempre: una aprobacion motivada es lo que hace util el post-mortem.
  const yaFirmado = match.signature !== null;

  return (
    <Screen back="/dashboard">
      <ScreenHeader
        kicker="Decisión del coordinador"
        action={<span className="note">{etiquetaEstado(match.estado)}</span>}
      />

      <h1 style={{ fontSize: 26, lineHeight: 1.15, margin: '8px 0 6px' }}>{match.incidentTitle}</h1>
      <div style={{ marginBottom: 18, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12 }}>
        <PriorityTag score={match.score} size={16} />
        {match.triagePosition !== null && (
          <span style={{ color: 'var(--color-neutral-700)', letterSpacing: '.1em' }}>
            · POSICIÓN {match.triagePosition} DEL LOTE
          </span>
        )}
      </div>

      {match.geoDegraded && (
        <div className="callout callout--alert" style={{ marginBottom: 16 }} role="status">
          Operación degradada: el agente geoespacial no respondió. No hay ruta ni distancia;
          la prioridad se calculó con lo que sí había.
        </div>
      )}

      {(match.route.length > 1 || match.lat !== null) && (
        <div style={{ marginBottom: 16 }}>
          <MapView
            mode="route"
            height={210}
            route={match.route}
            zones={match.zones}
            destination={
              match.lat !== null && match.lng !== null
                ? { lat: match.lat, lng: match.lng, score: match.score, title: match.incidentTitle }
                : undefined
            }
          />
          <div className="note note--quiet" style={{ marginTop: 6 }}>
            {match.route.length > 1
              ? 'Geometría real de la ruta del agente geoespacial · OpenStreetMap'
              : 'Ubicación verificada del incidente · sin ruta calculada'}
          </div>
        </div>
      )}

      <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Lo que sabe el sistema</div>
        {match.summary && <p className="lede" style={{ fontSize: 16, marginBottom: 12 }}>{match.summary}</p>}
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <Dato titulo="Distancia" valor={match.routeKm !== null ? `${match.routeKm.toFixed(2)} km` : '—'} />
          <Dato titulo="Duración" valor={match.routeMinutes !== null ? `${Math.round(match.routeMinutes)} min` : '—'} />
          <Dato titulo="Personas" valor={match.affectedPeople !== null ? String(match.affectedPeople) : '—'} />
          <Dato titulo="Confianza" valor={match.confidence !== null ? match.confidence.toFixed(2) : '—'} />
        </div>

        <div className="kicker" style={{ margin: '20px 0 6px' }}>Necesidades declaradas</div>
        <div className="note">
          {match.needs.length ? match.needs.join(' · ').replace(/_/g, ' ') : 'ninguna declarada'}
        </div>

        {match.triageComponents.length > 0 && (
          <>
            <div className="kicker" style={{ margin: '20px 0 6px' }}>Desglose del triage</div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {match.triageComponents.map((c) => (
                <li
                  key={c.label}
                  style={{
                    display: 'flex', justifyContent: 'space-between', gap: 12,
                    padding: '6px 0', borderTop: '1px solid var(--color-divider)', fontSize: 14,
                  }}
                >
                  <span>{c.label}</span>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>{c.value.toFixed(4)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {match.signature && (
        <div className="callout callout--info" style={{ marginTop: 22 }} role="status">
          Firmado por {match.signature.coordinatorId} · {match.signature.approved ? 'aprobada' : 'no aprobada'}
          {match.signature.justification ? ` · ${match.signature.justification}` : ''}
        </div>
      )}

      <div style={{ marginTop: 26, borderTop: '1px solid var(--color-divider)', paddingTop: 18 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Firma</div>
        {sinIdentidad ? (
          <div className="callout callout--alert" role="alert">
            No hay coordinador identificado en esta sesión. El backend rechaza toda decisión sin
            responsable.
            <button type="button" className="link-btn" style={{ marginTop: 8 }} onClick={() => navigate('/login')}>
              Identificarme
            </button>
          </div>
        ) : (
          <div className="note" style={{ marginBottom: 10 }}>Firmas como <strong>{coordinatorId}</strong></div>
        )}

        <textarea
          className="textarea"
          rows={2}
          value={justificacion}
          onChange={(e) => setJustificacion(e.target.value)}
          placeholder="Motivo de la decisión (obligatorio para rechazar o suspender)"
          aria-label="Justificación de la decisión"
        />

        <div className="stack" style={{ gap: 8, marginTop: 14 }}>
          {ACCIONES.map((accion) => (
            <div key={accion.id}>
              <button
                type="button"
                className={accion.clase}
                style={accion.id === 'reject' ? { color: 'var(--color-accent-2-700)', minHeight: 48 } : undefined}
                disabled={busy || sinIdentidad || yaFirmado}
                onClick={() => firmar(accion.id)}
              >
                {busy ? 'Firmando…' : accion.label}
              </button>
              <div className="note note--quiet" style={{ marginTop: 3 }}>{accion.ayuda}</div>
            </div>
          ))}
        </div>

        {yaFirmado && (
          <div className="note" style={{ marginTop: 10 }}>
            Esta operación ya está firmada: la máquina de estados no admite una segunda decisión.
          </div>
        )}
      </div>

      {nota && <div className="callout callout--info" style={{ marginTop: 16 }} role="status">{nota}</div>}
      {fallo && <div className="callout callout--alert" style={{ marginTop: 16 }} role="alert">{fallo}</div>}

      <TrazaPanel correlationId={match.correlationId} incidentId={match.incidentId} />
    </Screen>
  );
}

function Dato({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <span className="note">
      {titulo}
      <span style={{ display: 'block', fontSize: 22, color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
        {valor}
      </span>
    </span>
  );
}
