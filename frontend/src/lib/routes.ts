/** Catalogo de las 11 pantallas: alimenta el indice de demo y la navegacion. */
export interface ScreenRoute {
  /** Puede llevar `:id`: el indice lo sustituye por un incidente real del
      backend. Fijar aqui un identificador de ejemplo llevaria a una pantalla
      que siempre dice "no existe". */
  path: string;
  label: string;
  role: 'público' | 'ciudadano' | 'voluntario' | 'coordinador' | 'todos';
}

export const SCREEN_ROUTES: ScreenRoute[] = [
  { path: '/',                          label: 'Landing',              role: 'público' },
  { path: '/reportar',                  label: 'Reporte (stepper)',    role: 'ciudadano' },
  { path: '/seguimiento/:id',      label: 'Seguimiento',          role: 'ciudadano' },
  { path: '/registro',                  label: 'Registro voluntario',  role: 'voluntario' },
  { path: '/voluntario/misiones',       label: 'Muro de misiones',     role: 'voluntario' },
  { path: '/voluntario/mapa/:id',  label: 'Ruta y ejecución',     role: 'voluntario' },
  { path: '/login',                     label: 'Acceso RBAC',          role: 'coordinador' },
  { path: '/dashboard',                 label: 'Dashboard',            role: 'coordinador' },
  { path: '/matching/:id',         label: 'Matching',             role: 'coordinador' },
  { path: '/recuperacion/:id',     label: 'Recuperación',         role: 'ciudadano' },
  { path: '/offline',                   label: 'Sin red / sync',       role: 'todos' },
];
