/**
 * Transporte HTTP contra el backend de ResurgeAgent.
 *
 * Todo lo que sale de aqui es `unknown`: el tipado real se hace en `mapeo.ts`,
 * que es el unico sitio que conoce la forma del backend. Asi la frontera queda
 * en un archivo y no repartida por catorce metodos.
 */

/** Base configurable. En desarrollo el backend vive en el 8000 y Vite en el 5173. */
export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') ?? 'http://localhost:8000';

/** Techo de espera por peticion. En una emergencia una espera infinita es peor
    que un error: el coordinador necesita saber que el sistema no responde. */
const TIMEOUT_MS = 12000;

/** Motivo del fallo. Determina el texto que se le ensena a quien opera. */
export type FailureKind = 'red' | 'timeout' | 'servidor' | 'peticion' | 'formato';

export class ApiError extends Error {
  readonly kind: FailureKind;
  readonly status: number | null;
  /** Ruta relativa pedida, util para el aviso al usuario y para el log. */
  readonly path: string;

  constructor(kind: FailureKind, path: string, message: string, status: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.path = path;
    this.status = status;
  }

  /** Un 404 no siempre es un error: hay pantallas que lo tratan como "no existe". */
  get notFound(): boolean {
    return this.status === 404;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  /** Query string ya resuelto, sin la interrogacion. */
  query?: Record<string, string | number | undefined>;
  timeoutMs?: number;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(API_BASE + path);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Extrae el mensaje del error de dominio. FastAPI responde `{"detail": "..."}`
 * y ese texto es el que escribio el dominio (por ejemplo "un rechazo debe
 * justificarse"): mostrarlo tal cual le dice al coordinador que corregir.
 * Un `detail` de validacion de Pydantic llega como lista de objetos.
 */
function detailOf(payload: unknown, fallback: string): string {
  if (typeof payload === 'string' && payload.trim()) return payload;
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const partes = detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : null,
        )
        .filter((m): m is string => m !== null);
      if (partes.length) return partes.join(' · ');
    }
  }
  return fallback;
}

export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, timeoutMs = TIMEOUT_MS } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (cause) {
    // `fetch` rechaza igual por aborto que por red caida; el usuario necesita
    // distinguirlos, porque la accion que le toca es distinta en cada caso.
    if (controller.signal.aborted) {
      throw new ApiError(
        'timeout',
        path,
        `El servidor no respondio en ${Math.round(timeoutMs / 1000)} s (${API_BASE}${path}). Reintenta o revisa si esta saturado.`,
      );
    }
    throw new ApiError(
      'red',
      path,
      `No se pudo contactar con el backend en ${API_BASE}. Comprueba que este levantado y que permita este origen (CORS).`,
    );
  } finally {
    clearTimeout(timer);
  }

  const texto = await response.text();
  let payload: unknown = null;
  if (texto) {
    try {
      payload = JSON.parse(texto) as unknown;
    } catch {
      payload = texto;
    }
  }

  if (!response.ok) {
    const kind: FailureKind = response.status >= 500 ? 'servidor' : 'peticion';
    throw new ApiError(
      kind,
      path,
      detailOf(payload, `El backend respondio ${response.status} en ${path}.`),
      response.status,
    );
  }

  return payload as T;
}

/** Igual que `request`, pero un 404 se traduce a `null` en vez de lanzar. */
export async function requestOrNull<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T | null> {
  try {
    return await request<T>(path, options);
  } catch (error) {
    if (error instanceof ApiError && error.notFound) return null;
    throw error;
  }
}

/** Texto corto para pintar en pantalla cuando algo falla. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return 'Fallo inesperado al hablar con el backend.';
}
