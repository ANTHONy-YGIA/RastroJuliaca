export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;
  problems: string[];
  constructor(status: number, message: string, fields: Record<string, string> = {}, problems: string[] = []) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.problems = problems;
  }
}

function readCookie(name: string): string {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Error ${res.status}`;
  let fields: Record<string, string> = {};
  let problems: string[] = [];
  try {
    const data = await res.json();
    const d = data?.detail;
    if (typeof d === "string") message = d;
    else if (d && typeof d === "object") {
      message = d.message ?? message;
      fields = d.fields ?? {};
      problems = d.problems ?? [];
    }
  } catch {
    /* respuesta sin JSON */
  }
  if (res.status === 429) message = "Demasiadas solicitudes. Espere unos minutos e intente de nuevo.";
  return new ApiError(res.status, message, fields, problems);
}

type Body = Record<string, unknown> | FormData | undefined;

export async function api<T = unknown>(path: string, opts: { method?: string; body?: Body } = {}): Promise<T> {
  const method = opts.method ?? (opts.body ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) body = opts.body;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (method !== "GET") headers["X-CSRF-Token"] = readCookie("rj_csrf");
  const res = await fetch(`/api${path}`, { method, headers, body, credentials: "same-origin" });
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Descarga autenticada (exportaciones). Devuelve el nombre de archivo sugerido. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`/api${path}`, { credentials: "same-origin" });
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function fileUrl(id: string, variant: "playback" | "original" = "playback") {
  return `/api/files/${id}/content?variant=${variant}`;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.problems.length ? `${e.message}: ${e.problems.join("; ")}` : e.message;
  return "Ocurrió un error inesperado. Intente nuevamente.";
}
