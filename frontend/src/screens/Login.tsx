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
  const { scope, setScope } = useAppState();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <Screen back="/">
      <div className="kicker">Acceso institucional</div>
      <h1 className="title" style={{ margin: '10px 0 8px' }}>Coordinación</h1>
      <p className="lede" style={{ fontSize: 15, marginBottom: 22 }}>
        Token de corta duración con refresh silencioso. El alcance lo define tu rol.
      </p>

      <input
        className="input"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="usuario@defensacivil.gob.pe"
        aria-label="Correo institucional"
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

      <button type="button" className="btn btn--primary" style={{ marginTop: 26 }} onClick={() => navigate('/dashboard')}>
        Entrar
      </button>
    </Screen>
  );
}
