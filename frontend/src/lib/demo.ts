/**
 * La barra y el indice de demo existen para recorrer el flujo en la
 * presentacion. Se apagan con VITE_DEMO_BAR=0 y no deben llegar a produccion.
 */
export function demoEnabled(): boolean {
  return import.meta.env.VITE_DEMO_BAR !== '0';
}
