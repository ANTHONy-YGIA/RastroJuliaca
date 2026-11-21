import { useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { CalendarClock, FileText, Hash, ImageIcon, Lock, MapPin, ShieldCheck, Upload, Video } from "lucide-react";
import type { CaseSummary, FieldDef, FileInfo, HistoryEvent, PublicCase } from "@/lib/types";
import {
  CASE_STATUS, EVENT_LABEL, FILE_STATUS, PUBLICATION_STATUS, SENSITIVITY, cn, fmtBytes, fmtDate, fmtDateTime,
} from "@/lib/format";
import { CategoryIcon } from "@/lib/icons";
import { fileUrl } from "@/lib/api";
import { Badge, Card, Field, Input, Select, StatusBadge, Textarea } from "./ui/primitives";

export function SensitivityBadge({ value }: { value: string }) {
  return <StatusBadge map={SENSITIVITY} value={value} />;
}

/** Renderiza campos específicos a partir del esquema configurable de la categoría. */
export function DynamicFields({ fields, register, errors, prefix = "fields" }: {
  fields: FieldDef[]; register: UseFormRegister<any>; errors?: FieldErrors<any>; prefix?: string; // eslint-disable-line
}) {
  if (!fields.length) return <p className="text-sm text-slate-500">Esta categoría no requiere campos adicionales.</p>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {fields.map((f) => {
        const id = `f-${f.key}`;
        const err = (errors?.[prefix] as Record<string, { message?: string }> | undefined)?.[f.key]?.message;
        const name = `${prefix}.${f.key}`;
        const common = { id, "aria-invalid": !!err || undefined, ...register(name) };
        const wide = f.type === "textarea" ? "sm:col-span-2" : "";
        if (f.type === "boolean")
          return (
            <label key={f.key} htmlFor={id} className={cn("flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm", wide)}>
              <input type="checkbox" className="size-4 accent-brand-600" {...common} />
              <span>{f.label}</span>
              {f.public && <PublicHint />}
            </label>
          );
        return (
          <Field key={f.key} label={f.label} htmlFor={id} required={f.required} error={err} help={f.help} className={wide}>
            {f.type === "textarea" ? (
              <Textarea maxLength={f.max_length} {...common} />
            ) : f.type === "select" ? (
              <Select {...common} defaultValue="">
                <option value="">Seleccione…</option>
                {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
              </Select>
            ) : (
              <Input type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} min={f.min} max={f.max} maxLength={f.max_length} step="any" {...common} />
            )}
          </Field>
        );
      })}
    </div>
  );
}

function PublicHint() {
  return <span className="ml-auto text-[11px] text-slate-400">publicable</span>;
}

export function FilePicker({ accept, onChange, file, hint, id = "file" }: { accept: string; onChange: (f: File | null) => void; file: File | null; hint?: string; id?: string }) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); onChange(e.dataTransfer.files?.[0] ?? null); }}
      className={cn("flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center transition", drag ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50")}
    >
      <Upload className="size-6 text-navy-700" aria-hidden="true" />
      {file ? (
        <p className="text-sm font-medium text-navy-900 break-all">{file.name} <span className="text-slate-500">({fmtBytes(file.size)})</span></p>
      ) : (
        <p className="text-sm text-slate-600">Arrastre un archivo aquí o</p>
      )}
      <label htmlFor={id} className="cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-100">
        {file ? "Cambiar archivo" : "Seleccionar archivo"}
      </label>
      <input ref={ref} id={id} type="file" accept={accept} className="sr-only" onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function FileStatusLine({ file }: { file: FileInfo }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <StatusBadge map={FILE_STATUS} value={file.status} />
      <span>{file.detected_type?.toUpperCase()} · {fmtBytes(file.size_bytes)}</span>
      {file.scan_engine && <span className="inline-flex items-center gap-1"><ShieldCheck className="size-3.5" />{file.scan_engine}</span>}
    </div>
  );
}

export function HashLine({ sha }: { sha: string }) {
  return (
    <p className="flex items-start gap-1.5 font-mono text-[11px] text-slate-500 break-all" title="Huella SHA-256">
      <Hash className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
      {sha}
    </p>
  );
}

/** Visor de copia segura de reproducción (nunca el original). */
export function MediaViewer({ file }: { file: FileInfo }) {
  if (file.status !== "DISPONIBLE")
    return (
      <div className="flex aspect-video flex-col items-center justify-center gap-2 rounded-lg bg-slate-100 p-4 text-center text-sm text-slate-600">
        <Lock className="size-6 text-slate-400" />
        <p className="font-medium">Archivo no disponible</p>
        <p className="text-xs">{file.status_detail}</p>
      </div>
    );
  if (file.media_class === "video" && file.has_playback)
    return <video controls preload="metadata" className="aspect-video w-full rounded-lg bg-black" src={fileUrl(file.id)} aria-label="Copia segura de reproducción" />;
  if (file.media_class === "image" && file.has_playback)
    return <img src={fileUrl(file.id)} alt="Copia segura de la imagen aportada" className="w-full rounded-lg border border-slate-200 bg-slate-100 object-contain max-h-[480px]" />;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
      <FileText className="size-6 text-navy-700" />
      <span>Documento PDF validado. Descárguelo para examinarlo (la descarga queda registrada).</span>
    </div>
  );
}

export function TypeIcon({ type, className }: { type: string; className?: string }) {
  const I = type === "VIDEO" ? Video : type === "FOTO" ? ImageIcon : FileText;
  return <I className={className} aria-hidden="true" />;
}

export function HistoryList({ events }: { events: HistoryEvent[] }) {
  if (!events.length) return <p className="text-sm text-slate-500">Sin eventos registrados.</p>;
  return (
    <ol className="relative space-y-4 border-l-2 border-slate-200 pl-5">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span className="absolute -left-[27px] top-1 size-3 rounded-full border-2 border-white bg-brand-500 ring-2 ring-brand-100" aria-hidden="true" />
          <p className="text-sm font-medium text-navy-900">{EVENT_LABEL[e.event] ?? e.event}</p>
          <p className="text-sm text-slate-600">{e.detail}</p>
          <p className="text-xs text-slate-400">{fmtDateTime(e.created_at)}{e.actor ? ` · ${e.actor}` : ""}</p>
        </li>
      ))}
    </ol>
  );
}

export function CaseStatusBadges({ c }: { c: CaseSummary }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <StatusBadge map={CASE_STATUS} value={c.status} />
      <StatusBadge map={PUBLICATION_STATUS} value={c.publication_status} />
      <SensitivityBadge value={c.sensitivity} />
    </div>
  );
}

export function PublicCaseCard({ c }: { c: PublicCase }) {
  return (
    <Link to={`/expedientes/${c.code}`} className="group block focus-visible:outline-none">
      <Card className="flex h-full flex-col gap-3 p-5 transition group-hover:-translate-y-0.5 group-hover:border-brand-400 group-hover:shadow-md group-focus-visible:ring-2 group-focus-visible:ring-brand-500">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-navy-50 p-2 text-navy-700"><CategoryIcon name={c.category.icon} className="size-5" /></div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-slate-500">{c.category.parent_name ? `${c.category.parent_name} · ` : ""}{c.category.name}</p>
            <h3 className="font-semibold leading-snug text-navy-900 group-hover:text-brand-700">{c.public_title}</h3>
          </div>
        </div>
        <p className="line-clamp-3 text-sm text-slate-600">{c.public_summary}</p>
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" />{c.zone}</span>
          <span className="inline-flex items-center gap-1"><CalendarClock className="size-3.5" />{fmtDate(c.incident_date)}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {c.accepts_contributions ? <Badge tone="teal">Recibe aportaciones</Badge> : <Badge>Aportaciones cerradas</Badge>}
          <span className="font-mono text-[11px] text-slate-400 self-center">{c.code}</span>
        </div>
      </Card>
    </Link>
  );
}

export function Section({ title, children, actions, className }: { title: string; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3.5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-800">{title}</h2>
        {actions}
      </div>
      <div className="px-5 py-4">{children}</div>
    </Card>
  );
}
