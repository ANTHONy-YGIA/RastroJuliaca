import type { HTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { CircleCheck, CircleX, Info, LoaderCircle, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import { cn, type Tone } from "@/lib/format";

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...p} />;
}
export function CardHeader({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 border-b border-slate-100 px-5 py-4", className)} {...p} />;
}
export function CardTitle({ className, ...p }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-base font-semibold text-navy-900", className)} {...p} />;
}
export function CardDescription({ className, ...p }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-slate-500", className)} {...p} />;
}
export function CardContent({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...p} />;
}

const fieldBase =
  "w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-xs transition placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-3 focus:ring-brand-500/20 disabled:bg-slate-100 aria-invalid:border-red-500 aria-invalid:ring-red-500/20";

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldBase, "h-10", className)} {...p} />;
}
export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldBase, "min-h-24 py-2", className)} {...p} />;
}
export function Select({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(fieldBase, "h-10 pr-8", className)} {...p}>
      {children}
    </select>
  );
}
export function Label({ className, ...p }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium text-slate-700", className)} {...p} />;
}

export function Field({ label, htmlFor, error, help, required, children, className }: {
  label: string; htmlFor?: string; error?: string; help?: string; required?: boolean; children: ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor}>
        {label} {required && <span className="text-red-600" aria-hidden="true">*</span>}
      </Label>
      {children}
      {help && !error && <p className="text-xs text-slate-500">{help}</p>}
      {error && <p className="text-xs font-medium text-red-600" role="alert">{error}</p>}
    </div>
  );
}

const TONES: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  orange: "bg-orange-50 text-orange-800 ring-orange-200",
  green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  teal: "bg-brand-50 text-brand-700 ring-brand-100",
  blue: "bg-sky-50 text-sky-800 ring-sky-200",
  purple: "bg-violet-50 text-violet-800 ring-violet-200",
  navy: "bg-navy-100 text-navy-900 ring-navy-100",
};

export function Badge({ tone = "slate", className, children, icon: Icon }: { tone?: Tone; className?: string; children: ReactNode; icon?: LucideIcon }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap", TONES[tone], className)}>
      {Icon && <Icon className="size-3.5" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function StatusBadge({ map, value }: { map: Record<string, { label: string; tone: Tone }>; value: string | null | undefined }) {
  if (!value) return <Badge>—</Badge>;
  const m = map[value] ?? { label: value, tone: "slate" as Tone };
  return <Badge tone={m.tone}>{m.label}</Badge>;
}

const ALERT = {
  info: { cls: "border-sky-200 bg-sky-50 text-sky-900", icon: Info },
  warning: { cls: "border-amber-200 bg-amber-50 text-amber-900", icon: TriangleExclamationPoint },
  error: { cls: "border-red-200 bg-red-50 text-red-800", icon: CircleX },
  success: { cls: "border-emerald-200 bg-emerald-50 text-emerald-900", icon: CircleCheck },
};

export function Alert({ kind = "info", title, children, className }: { kind?: keyof typeof ALERT; title?: string; children?: ReactNode; className?: string }) {
  const a = ALERT[kind];
  const Icon = a.icon;
  return (
    <div role={kind === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border px-4 py-3 text-sm", a.cls, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="leading-relaxed">{children}</div>}
      </div>
    </div>
  );
}

export function Spinner({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500" role="status">
      <LoaderCircle className="size-5 animate-spin text-brand-600" aria-hidden="true" /> {label}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <div className="rounded-full bg-navy-50 p-3 text-navy-700"><Icon className="size-6" aria-hidden="true" /></div>
      <p className="font-medium text-navy-900">{title}</p>
      {children && <div className="max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between animate-fade-in">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-brand-700">{eyebrow}</div>}
        <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
        {description && <div className="mt-1 text-sm text-slate-600">{description}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ icon: Icon, label, value, tone = "navy", hint }: { icon: LucideIcon; label: string; value: ReactNode; tone?: "navy" | "teal" | "amber" | "green"; hint?: string }) {
  const tones = { navy: "bg-navy-50 text-navy-700", teal: "bg-brand-50 text-brand-700", amber: "bg-amber-50 text-amber-700", green: "bg-emerald-50 text-emerald-700" };
  return (
    <Card className="flex items-center gap-4 p-4">
      <div className={cn("rounded-lg p-2.5", tones[tone])}><Icon className="size-5" aria-hidden="true" /></div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-navy-900 tabular-nums">{value}</p>
        <p className="text-xs font-medium leading-tight text-slate-500">{label}</p>
        {hint && <p className="text-[11px] text-slate-400">{hint}</p>}
      </div>
    </Card>
  );
}

export function DataRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-0.5 py-2 sm:grid-cols-3 sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 sm:text-sm sm:normal-case sm:tracking-normal">{label}</dt>
      <dd className="text-sm text-slate-900 sm:col-span-2 break-words">{children}</dd>
    </div>
  );
}

export function InlineLoader() {
  return <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />;
}
