import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { useAppState } from '../state/AppState';
import type { CoordinatorScope } from '../api/types';

const ROLES: { id: CoordinatorScope; label: string }[] = [
  { id: 'zona', label: 'Coordinador de zona' },
  { id: 'general', label: 'Coordinador general' },
];

export default function Login() {
  const navigate = useNavigate();
  const { scope, setScope, coordinatorId, setCoordinatorId } = useAppState();
  const [password, setPassword] = useState('');

  // El identificador no es un adorno del formulario: viaja como `coordinador_id`
  // en cada POST /orquestador/decisiones. Sin el, el dominio rechaza la firma.
  const puedeEntrar = coordinatorId.trim().length > 0;

  return (
    <Screen back="/">
      <div className="kicker">Acceso institucional</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Coordinación</h1>
      <p className="lede" style={{ fontSize: 15, marginBottom: 22 }}>
        El identificador que escribas queda adherido a cada decisión que firmes.
        No es autenticación: es el responsable de la orden.
      </p>

      <input
        className="input"
        type="text"
        value={coordinatorId}
        onChange={(e) => setCoordinatorId(e.target.value)}
        placeholder="coordinador@defensacivil.gob.co"
        aria-label="Identificador del coordinador"
        style={{ marginBottom: 10 }}
      />
      <input
        className="input"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Contraseña"
        aria-label="Contraseña"
      />

      <div className="kicker" style={{ margin: '22px 0 8px' }}>Rol (RBAC)</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {ROLES.map((r) => (
          <button key={r.id} type="button" className="chip" aria-pressed={scope === r.id} onClick={() => setScope(r.id)}>
            {r.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        className="btn btn--primary"
        style={{ marginTop: 26 }}
        disabled={!puedeEntrar}
        onClick={() => navigate('/dashboard')}
      >
        Entrar
      </button>
      {!puedeEntrar && (
        <div className="note" style={{ marginTop: 8 }}>
          Escribe tu identificador: sin él no se puede firmar ninguna asignación.
        </div>
      )}
    </Screen>
  );
}
