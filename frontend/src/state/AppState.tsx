import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
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
  /** Reportes pendientes de sincronizar. */
  queueSize: number;

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
};

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [offline, setOffline] = useState(false);
  const [gpsDenied, setGpsDenied] = useState(false);
  const [scope, setScope] = useState<CoordinatorScope>('zona');
  const [draft, setDraft] = useState<ReportDraft>(EMPTY_DRAFT);

  const updateDraft = useCallback((patch: Partial<ReportDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  }, []);
  const resetDraft = useCallback(() => setDraft(EMPTY_DRAFT), []);

  const value = useMemo<AppState>(() => ({
    offline, setOffline,
    gpsDenied, setGpsDenied,
    scope, setScope,
    queueSize: offline ? 2 : 0,
    draft, updateDraft, resetDraft,
  }), [offline, gpsDenied, scope, draft, updateDraft, resetDraft]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAppState fuera de <AppStateProvider>');
  return ctx;
}
