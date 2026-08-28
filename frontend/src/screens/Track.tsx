import { useParams } from 'react-router-dom';
import { Screen } from '../components/Screen';
import { PriorityTag } from '../components/PriorityMark';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { Cargando, ErrorPanel, Vacio } from '../components/Estado';

export default function Track() {
  const { id = 'INC-2481' } = useParams();
  const { data: report, loading, error, reload } = useAsync(() => api.getTrackedReport(id), [id]);

  if (loading) return <Screen back="/"><Cargando texto="Cargando seguimiento…" /></Screen>;
  if (error) return <Screen back="/"><ErrorPanel error={error} onRetry={reload} /></Screen>;
  if (!report) {
    return (
      <Screen back="/">
        <Vacio
          titulo={`No hay ningún reporte con el identificador ${id}.`}
          ayuda="El seguimiento lee la operación real del Orquestador. Si el backend se reinició, las operaciones en memoria se perdieron: arráncalo con AGENTE1_RUTA_SQLITE y PLATAFORMA_RUTA_SQLITE apuntando al mismo archivo para que sobrevivan."
        />
      </Screen>
    );
  }

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
        <button type="button" className="btn btn--secondary" style={{ minHeight: 48, fontSize: 16 }} disabled>
          Chat · {report.unreadMessages} mensaje(s) · canal aún no expuesto por el backend
        </button>
      </div>
    </Screen>
  );
}
