import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const TZ = "America/Lima";

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "Sin dato";
  return new Intl.DateTimeFormat("es-PE", { timeZone: TZ, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "Sin dato";
  const d = iso.length === 10 ? new Date(iso + "T12:00:00-05:00") : new Date(iso);
  return new Intl.DateTimeFormat("es-PE", { timeZone: TZ, dateStyle: "long" }).format(d);
}

export function fmtRelative(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  if (diff < 60) return "hace un momento";
  if (diff < 3600) return rtf.format(-Math.round(diff / 60), "minute");
  if (diff < 86400) return rtf.format(-Math.round(diff / 3600), "hour");
  return rtf.format(-Math.round(diff / 86400), "day");
}

/** Convierte ISO UTC a valor de <input type="datetime-local"> en hora de Perú. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() - 5 * 3600 * 1000);
  return d.toISOString().slice(0, 16);
}

/** Valor de datetime-local (hora de Perú) a ISO con desfase explícito. */
export function fromLocalInput(v: string): string {
  return v ? `${v}:00-05:00` : "";
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function fmtKm(km: number | null | undefined): string {
  if (km === null || km === undefined) return "Datos insuficientes";
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(2)} km`;
}

export function fmtHours(h: number | null | undefined): string {
  if (h === null || h === undefined) return "Datos insuficientes";
  if (h < 1) return `${Math.round(h * 60)} min`;
  return `${h.toFixed(1)} h`;
}

export const CASE_STATUS: Record<string, { label: string; tone: Tone }> = {
  BORRADOR: { label: "Borrador", tone: "slate" },
  PENDIENTE_REVISION: { label: "Pendiente de revisión", tone: "amber" },
  CORRECCION_SOLICITADA: { label: "Corrección solicitada", tone: "orange" },
  APROBADO: { label: "Aprobado", tone: "green" },
  RECHAZADO: { label: "Rechazado", tone: "red" },
  CERRADO: { label: "Cerrado", tone: "slate" },
};

export const PUBLICATION_STATUS: Record<string, { label: string; tone: Tone }> = {
  NO_PUBLICADO: { label: "Privado", tone: "slate" },
  PENDIENTE_SEGUNDA_APROBACION: { label: "Pendiente 2.ª aprobación", tone: "amber" },
  PUBLICADO: { label: "Ficha pública vigente", tone: "teal" },
  RETIRADO: { label: "Ficha retirada", tone: "slate" },
};

export const CONTRIB_STATUS: Record<string, { label: string; tone: Tone }> = {
  EN_VALIDACION: { label: "En validación", tone: "amber" },
  BLOQUEADA: { label: "Bloqueada", tone: "red" },
  PENDIENTE_REVISION: { label: "Pendiente de revisión", tone: "blue" },
  CLASIFICADA: { label: "Clasificada", tone: "green" },
};

export const CLASSIFICATION: Record<string, { label: string; tone: Tone }> = {
  RELEVANTE: { label: "Relevante", tone: "green" },
  POSIBLEMENTE_RELEVANTE: { label: "Posiblemente relevante", tone: "teal" },
  NO_RELEVANTE: { label: "No relevante", tone: "slate" },
  DUPLICADO: { label: "Duplicado", tone: "orange" },
  NO_ADMISIBLE: { label: "No admisible", tone: "red" },
};

export const FILE_STATUS: Record<string, { label: string; tone: Tone }> = {
  CUARENTENA: { label: "En cuarentena", tone: "amber" },
  DISPONIBLE: { label: "Validado", tone: "green" },
  BLOQUEADO_SIN_ANTIVIRUS: { label: "Bloqueado: sin antivirus", tone: "red" },
  INFECTADO: { label: "Amenaza detectada", tone: "red" },
  RECHAZADO_FORMATO: { label: "Formato rechazado", tone: "red" },
  ERROR_PROCESAMIENTO: { label: "Bloqueado: error de validación", tone: "red" },
  ELIMINADO: { label: "Eliminado", tone: "slate" },
};

export const DOC_REVIEW: Record<string, { label: string; tone: Tone }> = {
  PENDIENTE: { label: "Por examinar", tone: "amber" },
  ACEPTADO: { label: "Aceptado", tone: "green" },
  OBSERVADO: { label: "Observado", tone: "orange" },
};

export const SENSITIVITY: Record<string, { label: string; tone: Tone }> = {
  GENERAL: { label: "General", tone: "teal" },
  RESTRINGIDO: { label: "Restringido", tone: "orange" },
  INSTITUCIONAL: { label: "Institucional", tone: "purple" },
};

export const CONTRIB_TYPE: Record<string, string> = { VIDEO: "Video", FOTO: "Fotografía", DOCUMENTO: "Documento", TEXTO: "Información escrita" };
export const CERTAINTY: Record<string, string> = { BAJA: "Baja", MEDIA: "Media", ALTA: "Alta" };
export const ROLE_LABEL: Record<string, string> = { DENUNCIANTE: "Denunciante", COLABORADOR: "Colaborador", REVISOR: "Revisor", ADMIN: "Administrador" };

export const EVENT_LABEL: Record<string, string> = {
  CREADO: "Creación",
  EDITADO: "Edición",
  DOCUMENTO_ADJUNTO: "Documento adjunto",
  ENVIADO: "Envío a revisión",
  ASIGNADO: "Asignación",
  DESASIGNADO: "Desasignación",
  DECISION: "Decisión",
  DOCUMENTO_REVISADO: "Documento examinado",
  PUBLICACION: "Publicación",
  APORTACIONES: "Aportaciones",
  APORTACION_RECIBIDA: "Aportación recibida",
  APORTACION_VALIDADA: "Aportación validada",
  APORTACION_BLOQUEADA: "Aportación bloqueada",
  CLASIFICACION: "Clasificación",
  CORRECCION: "Corrección",
  INFORME: "Informe",
  SENSIBILIDAD: "Sensibilidad",
  CONSERVACION: "Conservación",
};

export type Tone = "slate" | "amber" | "orange" | "green" | "red" | "teal" | "blue" | "purple" | "navy";

export function label(map: Record<string, { label: string }>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key]?.label ?? key;
}
