import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { Cargando, ErrorPanel } from '../components/Estado';
import { mensajeDeError } from '../api/http';
import type { RecoveryPlanStep } from '../api/types';

/** El cuestionario se contesta en momentos malos: el progreso sobrevive al cierre. */
const STORAGE_KEY = 'em-rec-progress';

interface Progress { step: number; answers: Record<string, string> }

function loadProgress(): Progress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as Progress;
  } catch { /* storage no disponible */ }
  return { step: 0, answers: {} };
}

function saveProgress(p: Progress) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(p)); } catch { /* ignore */ }
}

export default function Recovery() {
  const { id = 'INC-2481' } = useParams();
  const { data: questions, loading, error, reload } = useAsync(() => api.getRecoveryQuestions(), []);
  const [fallo, setFallo] = useState('');
  const [progress, setProgress] = useState<Progress>(loadProgress);
  const [plan, setPlan] = useState<RecoveryPlanStep[] | null>(null);
  const [building, setBuilding] = useState(false);

  useEffect(() => { saveProgress(progress); }, [progress]);

  const total = questions?.length ?? 0;
  const done = plan !== null;

  async function answer(questionId: string, option: string) {
    const answers = { ...progress.answers, [questionId]: option };
    const step = progress.step + 1;
    setProgress({ step, answers });
    if (step >= total) {
      setBuilding(true);
      setFallo('');
      try {
        setPlan(await api.getRecoveryPlan(answers));
      } catch (e) {
        // Se retrocede un paso: dejar el contador al final sin plan dejaria la
        // pantalla en un estado del que no se puede salir.
        setProgress({ step: step - 1, answers });
        setFallo(mensajeDeError(e));
      } finally {
        setBuilding(false);
      }
    }
  }

  function restart() {
    setProgress({ step: 0, answers: {} });
    setPlan(null);
  }

  const current = questions?.[Math.min(progress.step, total - 1)];

  return (
    <Screen back={true}>
      <div className="kicker">Recuperación · {id}</div>
      <h1 className="subtitle" style={{ margin: '10px 0 6px' }}>{done ? 'Hoja de ruta' : 'Evaluación de daños'}</h1>
      <div className="note" style={{ marginBottom: 20 }}>
        {done ? `${total} de ${total} respondidas` : `Pregunta ${Math.min(progress.step + 1, total)} de ${total} · progreso guardado`}
      </div>

      {loading && <Cargando texto="Cargando el cuestionario…" />}
      {error && <ErrorPanel error={error} onRetry={reload} />}
      {fallo && <div className="callout callout--alert" role="alert" style={{ marginBottom: 14 }}>{fallo}</div>}
      {building && <Cargando texto="Armando tu hoja de ruta…" />}

      {!done && !building && current && (
        <div>
          <div style={{ fontSize: 19, lineHeight: 1.35, marginBottom: 16 }}>{current.question}</div>
          <div className="stack" style={{ gap: 6 }}>
            {current.options.map((o) => (
              <button
                key={o}
                type="button"
                className="option-row"
                onClick={() => answer(current.id, o)}
              >
                {o}
              </button>
            ))}
          </div>
          <div className="note note--quiet" style={{ marginTop: 16 }}>
            Progreso guardado automáticamente · puedes cerrar y volver
          </div>
        </div>
      )}

      {done && plan && (
        <div>
          <div className="kicker" style={{ marginBottom: 10 }}>Tu hoja de ruta</div>
          <div className="stack">
            {plan.map((p) => (
              <div key={p.tag} style={{ borderTop: '1px solid var(--color-divider)', padding: '14px 0' }}>
                <div style={{ fontSize: 12, letterSpacing: '.1em', color: 'var(--color-accent-700)' }}>{p.tag}</div>
                <div style={{ fontSize: 18, marginTop: 4 }}>{p.title}</div>
                <div className="note" style={{ marginTop: 3 }}>{p.body}</div>
              </div>
            ))}
          </div>
          <button type="button" className="btn btn--ghost" style={{ marginTop: 6, fontSize: 14 }} onClick={restart}>
            Rehacer cuestionario
          </button>
        </div>
      )}
    </Screen>
  );
}
