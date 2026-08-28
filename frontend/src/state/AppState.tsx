import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import type { CoordinatorScope, ReportDraft } from '../api/types';

interface AppState {
  /** Sin red: los reportes se guardan en cola local. */
  offline: boolean;
  setOffline: (v: boolean) => void;
  /** El usuario nego el permiso de ubicacion: la direccion pasa a obligatoria. */
  gpsDenied: boolean;
  setGpsDenied: (v: boolean) => void;
  /** Alcance RBAC del coordinador autenticado. */
  scope: CoordinatorScope;
  setScope: (v: CoordinatorScope) => void;
  /**
   * Identificador del coordinador que firma. No es autenticacion: es
   * responsabilidad. `POST /orquestador/decisiones` rechaza toda decision sin
   * `coordinador_id`, porque una firma sin firmante no es una firma.
   */
  coordinatorId: string;
  setCoordinatorId: (v: string) => void;
  /** Reportes realmente pendientes de sincronizar, leidos del backend. */
  queueSize: number;
  /** Refresca la cuenta de la cola tras encolar o vaciar. */
  refreshQueueSize: () => void;

  draft: ReportDraft;
  updateDraft: (patch: Partial<ReportDraft>) => void;
  resetDraft: () => void;
}

const EMPTY_DRAFT: ReportDraft = {
  category: null,
  severity: 'critical',
  description: '',
  hasPhoto: false,
  address: '',
  phone: '',
  otp: '',
  lat: null,
  lng: null,
};

/** Sobrevive al refresco para que el coordinador no tenga que reidentificarse
    cada vez que recarga el tablero en mitad de una operacion. */
const COORD_KEY = 'resurge-coordinador';

function coordinadorGuardado(): string {
  try {
    return localStorage.getItem(COORD_KEY) ?? '';
  } catch {
    return '';
  }
}

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [offline, setOffline] = useState(false);
  const [gpsDenied, setGpsDenied] = useState(false);
  const [scope, setScope] = useState<CoordinatorScope>('zona');
  const [coordinatorId, setCoordinatorIdState] = useState<string>(coordinadorGuardado);
  const [draft, setDraft] = useState<ReportDraft>(EMPTY_DRAFT);
  const [queueSize, setQueueSize] = useState(0);
  const [queueTick, setQueueTick] = useState(0);

  const refreshQueueSize = useCallback(() => setQueueTick((n) => n + 1), []);

  // La banda "N reporte(s) en cola local" cuenta lo que hay de verdad en
  // `/plataforma/sincronizacion`. Si el backend no responde, la cuenta se queda
  // en cero: es preferible no decir nada a decir un numero inventado.
  useEffect(() => {
    let vivo = true;
    api.getSyncQueue().then(
      (cola) => { if (vivo) setQueueSize(cola.length); },
      () => { if (vivo) setQueueSize(0); },
    );
    return () => { vivo = false; };
  }, [queueTick]);

  const setCoordinatorId = useCallback((valor: string) => {
    setCoordinatorIdState(valor);
    try { localStorage.setItem(COORD_KEY, valor); } catch { /* modo privado */ }
  }, []);

  const updateDraft = useCallback((patch: Partial<ReportDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  }, []);
  const resetDraft = useCallback(() => setDraft(EMPTY_DRAFT), []);

  const value = useMemo<AppState>(() => ({
    offline, setOffline,
    gpsDenied, setGpsDenied,
    scope, setScope,
    coordinatorId, setCoordinatorId,
    queueSize, refreshQueueSize,
    draft, updateDraft, resetDraft,
  }), [offline, gpsDenied, scope, coordinatorId, setCoordinatorId, queueSize, refreshQueueSize,
    draft, updateDraft, resetDraft]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAppState fuera de <AppStateProvider>');
  return ctx;
}
