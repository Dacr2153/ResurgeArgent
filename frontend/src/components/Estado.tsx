/**
 * Estados de carga, vacio y error. Existen como componente compartido porque en
 * una emergencia una pantalla en blanco es indistinguible de una pantalla que
 * dice "no hay nada": el operador tiene que saber cual de las dos es, y que
 * hacer a continuacion.
 */
import { ApiError, API_BASE, mensajeDeError } from '../api/http';

export function Cargando({ texto }: { texto: string }) {
  return <div className="note" role="status">{texto}</div>;
}

export function Vacio({ titulo, ayuda }: { titulo: string; ayuda?: string }) {
  return (
    <div className="callout callout--info" role="status">
      <div style={{ fontSize: 16 }}>{titulo}</div>
      {ayuda && <div className="note" style={{ marginTop: 6 }}>{ayuda}</div>}
    </div>
  );
}

/** Que hacer, segun por que fallo. Un fallo de red y un 400 del dominio piden
    acciones distintas y no deben compartir texto. */
function queHacer(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Reintenta; si persiste, revisa la consola del navegador.';
  // El 404 no es un fallo del cliente: el recurso no existe todavia, y el texto
  // tiene que decir eso y no "corrige los datos".
  if (error.notFound) return 'El backend no tiene ese recurso. Puede que aún no se haya creado, o que se perdiera al reiniciar el proceso.';
  switch (error.kind) {
    case 'red':
      return `Levanta el backend con: uvicorn main:app --port 8000 · Base configurada: ${API_BASE}`;
    case 'timeout':
      return 'El backend tardo demasiado. Reintenta; si vuelve a pasar, revisa su carga.';
    case 'servidor':
      return 'Fallo del lado del servidor. Revisa el log de uvicorn.';
    case 'peticion':
      return 'La peticion no cumple lo que exige el dominio. Corrige los datos y vuelve a enviar.';
    default:
      return 'La respuesta no tenia la forma esperada.';
  }
}

export function ErrorPanel({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="callout callout--alert" role="alert">
      <div style={{ fontSize: 16 }}>{mensajeDeError(error)}</div>
      <div className="note" style={{ marginTop: 6 }}>{queHacer(error)}</div>
      {onRetry && (
        <button type="button" className="link-btn" style={{ marginTop: 10 }} onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  );
}
