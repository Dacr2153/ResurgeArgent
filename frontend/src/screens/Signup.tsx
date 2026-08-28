import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { api } from '../api/client';
import { RESOURCES } from '../lib/catalogos';
import { mensajeDeError } from '../api/http';

export default function Signup() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [document, setDocument] = useState('');
  const [phone, setPhone] = useState('');
  const [resource, setResource] = useState(RESOURCES[0]);
  const [sending, setSending] = useState(false);
  const [fallo, setFallo] = useState('');

  const completo = fullName.trim() && document.trim() && phone.trim();

  async function submit() {
    setSending(true);
    setFallo('');
    try {
      await api.registerVolunteer({ fullName, document, phone, resource });
      navigate('/voluntario/misiones');
    } catch (e) {
      setFallo(mensajeDeError(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <Screen back="/">
      <div className="kicker">Voluntariado</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Regístrate para ayudar</h1>
      <p className="lede" style={{ fontSize: 15, marginBottom: 22 }}>
        Verificación más estricta que un reporte: vas a zonas de riesgo y ves datos de afectados.
      </p>

      <div className="stack" style={{ gap: 14 }}>
        <label className="field">
          Nombre completo
          <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ana Quispe Rojas" />
        </label>
        <label className="field">
          Documento (se valida contra padrón)
          <input className="input" value={document} onChange={(e) => setDocument(e.target.value)} placeholder="DNI 45872311" />
        </label>
        <label className="field">
          Teléfono
          <input className="input" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+51 987 654 321" />
        </label>
      </div>

      <div className="kicker" style={{ margin: '22px 0 8px' }}>Recurso que aportas</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {RESOURCES.map((r) => (
          <button key={r} type="button" className="chip" aria-pressed={resource === r} onClick={() => setResource(r)}>
            {r}
          </button>
        ))}
      </div>

      <button
        type="button"
        className="btn btn--primary"
        style={{ marginTop: 26 }}
        onClick={submit}
        disabled={sending || !completo}
      >
        {sending ? 'Enviando…' : 'Enviar y verificar'}
      </button>
      {fallo && <div className="callout callout--alert" style={{ marginTop: 14 }} role="alert">{fallo}</div>}
    </Screen>
  );
}
