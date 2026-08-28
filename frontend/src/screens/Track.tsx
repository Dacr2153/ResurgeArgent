import { useParams } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { PriorityTag } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';

export default function Track() {
  const { id = 'INC-2481' } = useParams();
  const { data: report, loading } = useAsync(() => api.getTrackedReport(id), [id]);

  if (loading) return <Screen back="/"><div className="note">Cargando seguimiento…</div></Screen>;
  if (!report) return <Screen back="/"><div className="callout callout--alert">No encontramos el reporte {id}.</div></Screen>;

  return (
    <Screen back="/">
      <div className="kicker">Seguimiento · {report.id}</div>
      <h1 className="title" style={{ margin: '10px 0 6px' }}>{report.title}</h1>
      <div style={{ marginBottom: 26 }}><PriorityTag score={report.score} /></div>

      <ol className="stack" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {report.steps.map((step) => (
          <li key={step.label} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', paddingBottom: 22 }}>
            <span
              aria-hidden="true"
              style={{
                width: 13, height: 13, borderRadius: '50%', flex: '0 0 13px', marginTop: 4,
                background: step.done ? 'var(--color-accent)' : 'transparent',
                border: step.done ? 'none' : '1.5px solid var(--color-border-strong)',
              }}
            />
            <span style={{ flex: 1, marginTop: -3 }}>
              <span style={{ display: 'block', fontSize: 17 }}>
                {step.label}
                <span hidden> — {step.done ? 'completado' : 'pendiente'}</span>
              </span>
              <span className="note" style={{ display: 'block', marginTop: 2 }}>{step.meta}</span>
            </span>
          </li>
        ))}
      </ol>

      <div style={{ marginTop: 6, paddingTop: 20, borderTop: '1px solid var(--color-divider)' }}>
        <p className="lede" style={{ fontSize: 15, marginBottom: 12 }}>
          Chat con el coordinador asignado. Se borra 30 días después de “Resuelto”.
        </p>
        <button type="button" className="btn btn--secondary" style={{ minHeight: 48, fontSize: 16 }}>
          Abrir chat · {report.unreadMessages} mensaje nuevo
        </button>
      </div>
    </Screen>
  );
}
