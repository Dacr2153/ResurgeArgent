import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/Screen';
import { PriorityMark } from '../components/PriorityMark';
import { MapView } from '../components/MapView';
import { useAppState } from '../state/AppState';
import { api } from '../api/client';
import { CATEGORIES, SEVERITIES } from '../lib/catalogos';
import { mensajeDeError } from '../api/http';
import type { IncidentCategory, SeverityId, SubmittedReport } from '../api/types';

const MAX_DESC = 140;

export default function Report() {
  const navigate = useNavigate();
  const { offline, gpsDenied, setGpsDenied, draft, updateDraft, resetDraft, refreshQueueSize } = useAppState();
  const [step, setStep] = useState(0);
  const [otpLate, setOtpLate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmittedReport | null>(null);
  const [fallo, setFallo] = useState('');

  // Ubicacion real del navegador. Es la unica forma honesta de saber donde esta
  // quien reporta: una coordenada fija seria un dato inventado viajando al motor
  // de verificacion, que la usaria para agrupar incidentes que no son el mismo.
  useEffect(() => {
    if (!navigator.geolocation) { setGpsDenied(true); return; }
    let vivo = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (!vivo) return;
        updateDraft({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setGpsDenied(false);
      },
      () => { if (vivo) setGpsDenied(true); },
      { enableHighAccuracy: true, timeout: 8000 },
    );
    return () => { vivo = false; };
  }, [setGpsDenied, updateDraft]);

  const next = () => setStep((s) => Math.min(2, s + 1));
  const back = () => (step === 0 ? navigate('/') : setStep((s) => s - 1));

  async function submit(verified: boolean) {
    setSubmitting(true);
    setFallo('');
    try {
      const res = await api.submitReport(draft, { offline, verified });
      setResult(res);
      if (res.status === 'en_cola_local') refreshQueueSize();
    } catch (e) {
      setFallo(mensajeDeError(e));
    } finally {
      setSubmitting(false);
    }
  }

  // ---- Confirmacion (fuera del stepper: ya no hay pasos que retroceder) ----
  if (result) {
    const title = result.status === 'en_cola_local' ? 'Guardado en tu teléfono' : 'Reporte recibido';
    const body =
      result.status === 'en_cola_local'
        ? 'Sin señal: el reporte y la foto quedan en cola local y se envían automáticamente al reconectar.'
        : result.status === 'pendiente_verificacion'
          ? 'Queda como pendiente_verificación: ya está en la cola del coordinador y puedes verificar tu número después.'
          : 'Un coordinador de zona lo está revisando. Recibirás un SMS cuando se asigne una brigada.';

    return (
      <Screen>
        <div className="kicker">Reporte enviado</div>
        <div
          aria-hidden="true"
          style={{
            width: 44, height: 44, borderRadius: '50%', background: 'var(--color-accent)',
            color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, margin: '20px 0 16px',
          }}
        >
          ✓
        </div>
        <h1 className="title" style={{ fontSize: 30, marginBottom: 10 }}>{title}</h1>
        <p className="lede" style={{ marginBottom: 20 }}>{body}</p>
        <div className="kicker">Tu ID de reporte</div>
        <div style={{ fontSize: 30, letterSpacing: '.06em', margin: '4px 0 24px', fontVariantNumeric: 'tabular-nums' }}>
          {result.id}
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => { resetDraft(); navigate(`/seguimiento/${result.id}`); }}
        >
          Ver seguimiento
        </button>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScreenHeader
        kicker={`Reportar · paso ${step + 1} de 3`}
        action={<button type="button" className="link-btn" onClick={back}>Atrás</button>}
      />

      <div style={{ display: 'flex', gap: 4, margin: '6px 0 20px' }} aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              flex: 1, height: 3, borderRadius: 2,
              background: i <= step ? 'var(--color-text)' : 'color-mix(in srgb, var(--color-text) 18%, transparent)',
            }}
          />
        ))}
      </div>

      {step === 0 && <StepWhat next={next} gpsDenied={gpsDenied} draft={draft} updateDraft={updateDraft} />}
      {fallo && <div className="callout callout--alert" style={{ marginTop: 16 }} role="alert">{fallo}</div>}
      {step === 1 && <StepSeverity next={next} draft={draft} updateDraft={updateDraft} />}
      {step === 2 && (
        <StepVerify
          draft={draft}
          updateDraft={updateDraft}
          otpLate={otpLate}
          showLate={() => setOtpLate(true)}
          resend={() => { setOtpLate(false); updateDraft({ otp: '' }); }}
          submitting={submitting}
          onSubmit={submit}
        />
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------------------

type DraftProps = {
  draft: ReturnType<typeof useAppState>['draft'];
  updateDraft: ReturnType<typeof useAppState>['updateDraft'];
};

function StepWhat({ next, gpsDenied, draft, updateDraft }: DraftProps & { next: () => void; gpsDenied: boolean }) {
  // Sin GPS la direccion es obligatoria: un reporte sin ninguna referencia de
  // sitio no se puede despachar, y el backend lo agruparia en el punto (0,0).
  const canContinue = draft.category !== null
    && (!gpsDenied ? draft.lat !== null : draft.address.trim().length > 0);

  return (
    <div>
      <h1 className="subtitle" style={{ marginBottom: 16 }}>¿Qué está pasando?</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {CATEGORIES.map((c) => {
          const active = draft.category === (c.label as IncidentCategory);
          return (
            <button
              key={c.label}
              type="button"
              aria-pressed={active}
              onClick={() => updateDraft({ category: c.label as IncidentCategory })}
              style={{
                textAlign: 'left', padding: '14px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
                background: active ? 'var(--color-accent-200)' : 'var(--color-neutral-100)',
                border: active ? '1px solid var(--color-accent)' : '1px solid color-mix(in srgb, var(--color-text) 22%, transparent)',
              }}
            >
              <span style={{ fontSize: 18 }}>{c.label}</span>
              <span style={{ display: 'block', fontSize: 12, color: 'var(--color-neutral-700)', marginTop: 2 }}>{c.hint}</span>
            </button>
          );
        })}
      </div>

      <div className="kicker" style={{ margin: '24px 0 8px' }}>Ubicación</div>

      {gpsDenied ? (
        <div>
          <div className="callout callout--alert" style={{ marginBottom: 10 }}>
            Sin permiso de ubicación. Escribe la dirección: es obligatoria para enviar.
          </div>
          <input
            className="input"
            value={draft.address}
            onChange={(e) => updateDraft({ address: e.target.value })}
            placeholder="Av. Abancay 490, Cercado"
            aria-label="Dirección de la emergencia"
          />
        </div>
      ) : (
        <div>
          {draft.lat !== null && draft.lng !== null ? (
            <>
              <MapView mode="pick" height={168} center={[draft.lat, draft.lng]} zoom={16} />
              <div className="note" style={{ marginTop: 7 }}>
                Ubicación del dispositivo · {draft.lat.toFixed(5)}, {draft.lng.toFixed(5)}
              </div>
            </>
          ) : (
            <div className="note">Leyendo la ubicación del dispositivo…</div>
          )}
          <label className="field" style={{ marginTop: 12 }}>
            Referencia o dirección (opcional, ayuda a la brigada)
            <input
              className="input"
              value={draft.address}
              onChange={(e) => updateDraft({ address: e.target.value })}
              placeholder="Frente al parque, portón azul"
              aria-label="Referencia de la ubicación"
            />
          </label>
        </div>
      )}

      <button type="button" className="btn btn--primary" style={{ marginTop: 26 }} onClick={next} disabled={!canContinue}>
        Continuar
      </button>
    </div>
  );
}

function StepSeverity({ next, draft, updateDraft }: DraftProps & { next: () => void }) {
  return (
    <div>
      <h1 className="subtitle" style={{ marginBottom: 16 }}>¿Qué tan grave es?</h1>

      <div className="stack" style={{ gap: 6 }}>
        {SEVERITIES.map((v) => {
          const active = draft.severity === (v.id as SeverityId);
          return (
            <button
              key={v.id}
              type="button"
              aria-pressed={active}
              onClick={() => updateDraft({ severity: v.id as SeverityId })}
              style={{
                display: 'flex', alignItems: 'center', gap: 11, minHeight: 50, padding: '0 12px',
                borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: 17, color: 'var(--color-text)',
                background: active ? 'var(--color-accent-200)' : 'var(--color-neutral-100)',
                border: active ? '1px solid var(--color-accent)' : '1px solid color-mix(in srgb, var(--color-text) 22%, transparent)',
              }}
            >
              <PriorityMark score={v.score} size={20} />
              <span style={{ flex: 1, textAlign: 'left' }}>{v.label}</span>
              <span style={{ fontSize: 12, color: 'var(--color-neutral-700)' }}>{v.detail}</span>
            </button>
          );
        })}
      </div>

      <div className="kicker" style={{ margin: '22px 0 8px' }}>Descripción · máx. {MAX_DESC}</div>
      <textarea
        className="textarea"
        rows={3}
        value={draft.description}
        onChange={(e) => updateDraft({ description: e.target.value.slice(0, MAX_DESC) })}
        placeholder="Humo saliendo del segundo piso, dos personas en la ventana."
        aria-label="Descripción de la emergencia"
      />
      <div className="note--quiet note" style={{ marginTop: 4 }}>
        {draft.description.length}/{MAX_DESC} · el texto se sanitiza antes de mostrarse
      </div>

      <button
        type="button"
        onClick={() => updateDraft({ hasPhoto: !draft.hasPhoto })}
        style={{
          width: '100%', minHeight: 48, marginTop: 16, borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: 16,
          background: draft.hasPhoto ? 'var(--color-accent-200)' : 'transparent',
          border: draft.hasPhoto ? '1px solid var(--color-accent)' : '1px dashed color-mix(in srgb, var(--color-text) 40%, transparent)',
          color: draft.hasPhoto ? 'var(--color-accent-800)' : 'var(--color-neutral-800)',
        }}
      >
        {draft.hasPhoto ? 'Foto marcada como adjunta — quitar' : 'Adjuntar foto'}
      </button>
      <div className="note note--quiet" style={{ marginTop: 6 }}>
        Queda constancia de que hay foto. El archivo se adjunta al llegar el reporte al coordinador.
      </div>

      <button type="button" className="btn btn--primary" style={{ marginTop: 26 }} onClick={next}>Continuar</button>
    </div>
  );
}

function StepVerify({
  draft, updateDraft, otpLate, showLate, resend, submitting, onSubmit,
}: DraftProps & {
  otpLate: boolean;
  showLate: () => void;
  resend: () => void;
  submitting: boolean;
  onSubmit: (verified: boolean) => void;
}) {
  return (
    <div>
      <h1 className="title" style={{ marginBottom: 10 }}>Confirma tu número</h1>
      <p className="lede" style={{ fontSize: 15, marginBottom: 18 }}>
        Lo usamos solo para contactarte por este reporte. Nunca es público.
      </p>

      <input
        className="input"
        type="tel"
        value={draft.phone}
        onChange={(e) => updateDraft({ phone: e.target.value })}
        placeholder="+51 987 654 321"
        aria-label="Número de teléfono"
      />

      <div className="kicker" style={{ margin: '16px 0 8px' }}>Código de 4 dígitos</div>
      <input
        className="input"
        inputMode="numeric"
        maxLength={4}
        value={draft.otp}
        onChange={(e) => updateDraft({ otp: e.target.value.replace(/\D/g, '').slice(0, 4) })}
        placeholder="0000"
        aria-label="Código de verificación"
        style={{ width: 140, fontSize: 24, letterSpacing: '.3em' }}
      />

      {otpLate && (
        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--color-divider)' }}>
          <div style={{ fontSize: 14, lineHeight: 1.45, color: 'var(--color-neutral-800)', marginBottom: 10 }}>
            El SMS no llegó en 60 s. Elige otra vía — nunca bloqueamos un reporte por esto.
          </div>
          <div className="stack" style={{ gap: 6 }}>
            <button type="button" className="btn btn--secondary" style={{ minHeight: 48, fontSize: 16 }} onClick={resend}>
              Reintentar SMS
            </button>
            <button type="button" className="btn btn--secondary" style={{ minHeight: 48, fontSize: 16 }} onClick={resend}>
              Llamada con el código
            </button>
            <button type="button" className="link-row" style={{ marginTop: 4 }} onClick={() => onSubmit(false)}>
              Enviar sin verificar (queda pendiente_verificación) →
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        className="btn btn--primary"
        style={{ marginTop: 26 }}
        onClick={() => onSubmit(true)}
        disabled={submitting}
      >
        {submitting ? 'Enviando…' : 'Enviar reporte'}
      </button>

      {!otpLate && (
        <button type="button" className="btn btn--ghost" style={{ marginTop: 8 }} onClick={showLate}>
          No me llega el SMS
        </button>
      )}
    </div>
  );
}
