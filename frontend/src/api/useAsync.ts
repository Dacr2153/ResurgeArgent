import { useCallback, useEffect, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  /** Vuelve a lanzar la carga. Con backend real hace falta: un fallo de red no
      se arregla recargando la pagina entera. */
  reload: () => void;
}

/**
 * Hook minimo para consumir `api.*`. Cancela el set de estado si el
 * componente se desmonta antes de que resuelva la promesa.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>({
    data: null, loading: true, error: null,
  });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    load().then(
      (data) => { if (alive) setState({ data, loading: false, error: null }); },
      (error: Error) => { if (alive) setState({ data: null, loading: false, error }); },
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload };
}
