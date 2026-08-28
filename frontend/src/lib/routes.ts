/** Catalogo de las 11 pantallas: alimenta el indice de demo y la navegacion. */
export interface ScreenRoute {
  path: string;
  label: string;
  role: 'público' | 'ciudadano' | 'voluntario' | 'coordinador' | 'todos';
}

export const SCREEN_ROUTES: ScreenRoute[] = [
  { path: '/',                          label: 'Landing',              role: 'público' },
  { path: '/reportar',                  label: 'Reporte (stepper)',    role: 'ciudadano' },
  { path: '/seguimiento/INC-2481',      label: 'Seguimiento',          role: 'ciudadano' },
  { path: '/registro',                  label: 'Registro voluntario',  role: 'voluntario' },
  { path: '/voluntario/misiones',       label: 'Muro de misiones',     role: 'voluntario' },
  { path: '/voluntario/mapa/INC-2481',  label: 'Ruta y ejecución',     role: 'voluntario' },
  { path: '/login',                     label: 'Acceso RBAC',          role: 'coordinador' },
  { path: '/dashboard',                 label: 'Dashboard',            role: 'coordinador' },
  { path: '/matching/INC-2481',         label: 'Matching',             role: 'coordinador' },
  { path: '/recuperacion/INC-2481',     label: 'Recuperación',         role: 'ciudadano' },
  { path: '/offline',                   label: 'Sin red / sync',       role: 'todos' },
];
