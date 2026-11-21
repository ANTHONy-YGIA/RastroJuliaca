import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft, ArrowRight, Check, Crosshair, FileText, FolderOpen, MapPin, Pencil, Plus, Send, ShieldCheck, TriangleExclamationPoint,
} from "lucide-react";
import { Container } from "@/components/layout";
import { CaseStatusBadges, DynamicFields, FilePicker, FileStatusLine, HistoryList, Section, SensitivityBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Alert, Badge, Card, DataRow, EmptyState, Field, Input, PageHeader, Select, Spinner, StatusBadge, Textarea } from "@/components/ui/primitives";
import { api, errorMessage, fileUrl, ApiError } from "@/lib/api";
import { buildFieldsSchema, cleanFields } from "@/lib/dynamicSchema";
import { CASE_STATUS, DOC_REVIEW, cn, fmtDateTime, fromLocalInput, toLocalInput } from "@/lib/format";
import { CategoryIcon } from "@/lib/icons";
import { flatCategories, useSession } from "@/lib/session";
import type { CaseDetail, CaseSummary, Category, Sensitivity } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export function ReporterDashboard() {
  const { data, loading, error } = useApi<CaseSummary[]>("/cases/mine");
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    data?.forEach((x) => (c[x.status] = (c[x.status] ?? 0) + 1));
    return c;
  }, [data]);
  return (
    <Container>
      <PageHeader eyebrow="Panel del denunciante" title="Mis expedientes" description="Sus expedientes son privados. Solo usted y el equipo de revisión asignado pueden verlos."
        actions={<Button variant="brand" asChild><Link to="/mis-expedientes/nuevo"><Plus />Nuevo expediente</Link></Button>} />
      {data && data.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {Object.entries(counts).map(([s, n]) => <Badge key={s} tone={CASE_STATUS[s]?.tone}>{CASE_STATUS[s]?.label ?? s}: {n}</Badge>)}
        </div>
      )}
      {loading && <Spinner />}
      {error && <Alert kind="error">{error}</Alert>}
      {data?.length === 0 && (
        <EmptyState icon={FolderOpen} title="Aún no registró expedientes">
          <Button variant="brand" className="mt-3" asChild><Link to="/mis-expedientes/nuevo"><Plus />Registrar incidente</Link></Button>
        </EmptyState>
      )}
      <div className="grid gap-3">
        {data?.map((c) => (
          <Link key={c.id} to={`/mis-expedientes/${c.id}`} className="group">
            <Card className="flex flex-col gap-3 p-4 transition group-hover:border-brand-400 sm:flex-row sm:items-center">
              <div className="rounded-lg bg-navy-50 p-2.5 text-navy-700 self-start"><CategoryIcon name={c.category.icon} className="size-5" /></div>
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-slate-500">{c.code} · {c.category.parent_name ? `${c.category.parent_name} / ` : ""}{c.category.name}</p>
                <p className="truncate font-semibold text-navy-900 group-hover:text-brand-700">{c.title}</p>
                <p className="text-xs text-slate-500">Incidente: {fmtDateTime(c.incident_at)} · {c.zone}</p>
              </div>
              <CaseStatusBadges c={c} />
            </Card>
          </Link>
        ))}
      </div>
    </Container>
  );
}

const generalSchema = z.object({
  title: z.string().trim().min(5, "Mínimo 5 caracteres").max(160),
  description: z.string().trim().min(20, "Describa el incidente con al menos 20 caracteres").max(5000),
  incident_at: z.string().min(1, "Indique fecha y hora").refine((v) => new Date(fromLocalInput(v)).getTime() <= Date.now() + 600000, "No puede ser futura"),
  zone: z.string().min(1, "Seleccione una zona"),
  flags: z.array(z.string()).optional(),
});

const locationSchema = z
  .object({ lat: z.string().optional(), lon: z.string().optional(), note: z.string().max(255).optional() })
  .refine((d) => (!d.lat && !d.lon) || (d.lat && d.lon && Math.abs(+d.lat) <= 90 && Math.abs(+d.lon) <= 180), { message: "Coordenadas incompletas o fuera de rango", path: ["lat"] });

const STEPS = ["Categoría", "Datos generales", "Campos específicos", "Ubicación privada", "Confirmar"];

function Stepper({ step }: { step: number }) {
  return (
    <ol className="mb-6 flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" aria-label="Pasos del formulario">
      {STEPS.map((s, i) => (
        <li key={s} className="flex shrink-0 items-center gap-2" aria-current={i === step ? "step" : undefined}>
          <span className={cn("flex size-7 items-center justify-center rounded-full text-xs font-bold",
            i < step ? "bg-brand-600 text-white" : i === step ? "bg-navy-900 text-white" : "bg-slate-200 text-slate-600")}>
            {i < step ? <Check className="size-4" /> : i + 1}
          </span>
          <span className={cn("text-sm", i === step ? "font-semibold text-navy-900" : "text-slate-500 hidden sm:inline")}>{s}</span>
          {i < STEPS.length - 1 && <span className="h-px w-6 bg-slate-300" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}

const LEVEL: Record<Sensitivity, number> = { GENERAL: 0, RESTRINGIDO: 1, INSTITUCIONAL: 2 };

export function CaseWizard() {
  const { id } = useParams();
  const editing = !!id;
  const { data: existing, loading } = useApi<CaseDetail>(editing ? `/cases/${id}` : null);
  if (editing && loading) return <Spinner />;
  if (editing && existing && !["BORRADOR", "CORRECCION_SOLICITADA"].includes(existing.status))
    return <Container><Alert kind="warning">Este expediente ya no puede editarse.</Alert></Container>;
  return <WizardInner existing={existing ?? null} />;
}

function WizardInner({ existing }: { existing: CaseDetail | null }) {
  const { categories, meta } = useSession();
  const nav = useNavigate();
  const all = flatCategories(categories);
  const [step, setStep] = useState(existing ? 1 : 0);
  const [parentId, setParentId] = useState<number | null>(() => {
    if (!existing) return null;
    const c = all.find((x) => x.id === existing.category.id);
    return c?.parent_id ?? c?.id ?? null;
  });
  const [categoryId, setCategoryId] = useState<number | null>(existing?.category.id ?? null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const category = all.find((c) => c.id === categoryId) ?? null;
  const parent = categories.find((c) => c.id === parentId) ?? null;

  const general = useForm({
    resolver: zodResolver(generalSchema),
    defaultValues: existing
      ? { title: existing.title, description: existing.description, incident_at: toLocalInput(existing.incident_at), zone: existing.zone, flags: existing.sensitive_flags.map((f) => f.key) }
      : { title: "", description: "", incident_at: "", zone: "", flags: [] },
  });
  const fieldsSchema = useMemo(() => z.object({ fields: buildFieldsSchema(category?.field_schema ?? []) }), [category]);
  const specific = useForm({ resolver: zodResolver(fieldsSchema), defaultValues: { fields: (existing?.specific_fields ?? {}) as Record<string, unknown> } });
  const location = useForm({
    resolver: zodResolver(locationSchema),
    defaultValues: { lat: existing?.private_lat?.toString() ?? "", lon: existing?.private_lon?.toString() ?? "", note: existing?.private_location_note ?? "" },
  });
  const flags = general.watch("flags") ?? [];
  const effective: Sensitivity = flags.length ? "INSTITUCIONAL" : category?.sensitivity ?? "GENERAL";

  const next = async () => {
    setErr(null);
    if (step === 0 && !category) return setErr("Seleccione una categoría");
    if (step === 1 && !(await general.trigger())) return;
    if (step === 2 && !(await specific.trigger())) return;
    if (step === 3 && !(await location.trigger())) return;
    setStep(step + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const useMyLocation = () => {
    navigator.geolocation?.getCurrentPosition(
      (p) => { location.setValue("lat", p.coords.latitude.toFixed(6)); location.setValue("lon", p.coords.longitude.toFixed(6)); },
      () => setErr("No se pudo obtener la ubicación del dispositivo"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    const g = general.getValues();
    const l = location.getValues();
    const body = {
      title: g.title, description: g.description, incident_at: fromLocalInput(g.incident_at), zone: g.zone,
      private_lat: l.lat ? +l.lat : null, private_lon: l.lon ? +l.lon : null, private_location_note: l.note || null,
      specific_fields: cleanFields(specific.getValues().fields ?? {}), sensitive_flags: g.flags ?? [],
    };
    try {
      const res = existing
        ? await api<CaseDetail>(`/cases/${existing.id}`, { method: "PATCH", body })
        : await api<CaseDetail>("/cases", { body: { ...body, category_id: categoryId } });
      nav(`/mis-expedientes/${res.id}`, { replace: true });
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fields).length) setErr(`${e.message}: ${Object.entries(e.fields).map(([k, v]) => `${k}: ${v}`).join("; ")}`);
      else setErr(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Container className="max-w-4xl">
      <PageHeader eyebrow={existing ? existing.code : "Nuevo expediente"} title={existing ? "Editar expediente" : "Registrar incidente"}
        description="El expediente permanecerá privado y pendiente hasta su revisión. Use datos objetivos; no incluya datos de terceros innecesarios." />
      <Stepper step={step} />
      {err && <Alert kind="error" className="mb-4">{err}</Alert>}

      {step === 0 && (
        <div className="space-y-6 animate-fade-in">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="radiogroup" aria-label="Categoría">
            {categories.map((c) => (
              <button key={c.id} type="button" role="radio" aria-checked={parentId === c.id} data-testid={`cat-${c.slug}`}
                onClick={() => { setParentId(c.id); setCategoryId(c.id); }}
                className={cn("flex items-start gap-3 rounded-xl border bg-white p-4 text-left transition hover:border-brand-400",
                  parentId === c.id ? "border-brand-500 ring-2 ring-brand-500/20" : "border-slate-200")}>
                <div className="rounded-lg bg-navy-50 p-2 text-navy-700"><CategoryIcon name={c.icon} className="size-5" /></div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-navy-900">{c.name}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{c.description}</p>
                  <div className="mt-1.5"><SensitivityBadge value={c.sensitivity} /></div>
                </div>
              </button>
            ))}
          </div>
          {parent && parent.children && parent.children.length > 0 && (
            <Card className="p-4">
              <p className="text-sm font-medium text-slate-700">Subcategoría (opcional)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[parent, ...parent.children].map((s) => (
                  <button key={s.id} type="button" onClick={() => setCategoryId(s.id)} aria-pressed={categoryId === s.id}
                    className={cn("rounded-full border px-3 py-1.5 text-sm", categoryId === s.id ? "border-navy-900 bg-navy-900 text-white" : "border-slate-300 bg-white hover:bg-slate-50")}>
                    {s.id === parent.id ? "General" : s.name}
                  </button>
                ))}
              </div>
            </Card>
          )}
          {category && <PolicyNote category={category} />}
        </div>
      )}

      {step === 1 && (
        <Card className="space-y-4 p-5 animate-fade-in">
          <Field label="Título breve" htmlFor="title" required error={general.formState.errors.title?.message}>
            <Input id="title" {...general.register("title")} placeholder="Ej.: Robo de mototaxi estacionada" />
          </Field>
          <Field label="Descripción objetiva" htmlFor="description" required error={general.formState.errors.description?.message}
            help="Describa hechos observables. Evite acusaciones o datos personales de terceros.">
            <Textarea id="description" rows={5} {...general.register("description")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Fecha y hora del incidente (hora de Perú)" htmlFor="incident_at" required error={general.formState.errors.incident_at?.message}>
              <Input id="incident_at" type="datetime-local" {...general.register("incident_at")} />
            </Field>
            <Field label="Zona general" htmlFor="zone" required error={general.formState.errors.zone?.message} help="Se usa en la ficha pública en lugar de la ubicación exacta.">
              <Select id="zone" {...general.register("zone")}>
                <option value="">Seleccione…</option>
                {meta?.zones.map((z) => <option key={z} value={z}>{z}</option>)}
              </Select>
            </Field>
          </div>
          <fieldset className="rounded-lg border border-violet-200 bg-violet-50/50 p-4">
            <legend className="px-1 text-sm font-semibold text-violet-900">Protecciones reforzadas</legend>
            <p className="mb-2 text-xs text-violet-800">Si el incidente involucra alguna de estas situaciones, el expediente será INSTITUCIONAL: privado, sin publicación ni aportaciones abiertas.</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(meta?.protected_flags ?? {}).map(([k, v]) => {
                const locked = !!existing?.sensitive_flags.some((f) => f.key === k);
                return (
                  <label key={k} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" value={k} disabled={locked} className="size-4 accent-violet-600" {...general.register("flags")} />
                    {v}{locked && <span className="text-xs text-violet-700">(no puede retirarse)</span>}
                  </label>
                );
              })}
            </div>
          </fieldset>
        </Card>
      )}

      {step === 2 && category && (
        <Card className="p-5 animate-fade-in">
          <p className="mb-4 flex items-center gap-2 text-sm text-slate-600"><CategoryIcon name={category.icon} className="size-4" />Campos de <strong>{category.name}</strong></p>
          <DynamicFields fields={category.field_schema} register={specific.register} errors={specific.formState.errors} />
        </Card>
      )}

      {step === 3 && (
        <Card className="space-y-4 p-5 animate-fade-in">
          <Alert kind="info" title="Ubicación privada (opcional)">
            Nunca se publica. Permite al revisor ordenar las aportaciones por cercanía aproximada. Si no la indica, el sistema mostrará que los datos son insuficientes.
          </Alert>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Latitud" htmlFor="lat" error={location.formState.errors.lat?.message}>
              <Input id="lat" inputMode="decimal" placeholder="-15.4990" {...location.register("lat")} />
            </Field>
            <Field label="Longitud" htmlFor="lon">
              <Input id="lon" inputMode="decimal" placeholder="-70.1330" {...location.register("lon")} />
            </Field>
            <Field label="Referencia privada" htmlFor="note" className="sm:col-span-2">
              <Input id="note" maxLength={255} {...location.register("note")} placeholder="Ej.: frente a la vivienda" />
            </Field>
          </div>
          <Button type="button" variant="outline" onClick={useMyLocation}><Crosshair />Usar la ubicación de este dispositivo</Button>
        </Card>
      )}

      {step === 4 && category && (
        <Card className="p-5 animate-fade-in">
          <dl className="divide-y divide-slate-100">
            <DataRow label="Categoría">{category.name}</DataRow>
            <DataRow label="Sensibilidad"><SensitivityBadge value={LEVEL[effective] >= LEVEL[category.sensitivity] ? effective : category.sensitivity} /></DataRow>
            <DataRow label="Título">{general.getValues("title")}</DataRow>
            <DataRow label="Fecha y hora">{general.getValues("incident_at").replace("T", " ")}</DataRow>
            <DataRow label="Zona">{general.getValues("zone")}</DataRow>
            {category.field_schema.map((f) => {
              const v = (specific.getValues().fields as Record<string, unknown>)?.[f.key];
              return v === undefined || v === "" ? null : <DataRow key={f.key} label={f.label}>{typeof v === "boolean" ? (v ? "Sí" : "No") : String(v)}</DataRow>;
            })}
            <DataRow label="Ubicación privada">{location.getValues("lat") ? `${location.getValues("lat")}, ${location.getValues("lon")}` : "No indicada"}</DataRow>
          </dl>
          <Alert kind="info" className="mt-4">Después de guardar podrá adjuntar la documentación de respaldo y enviar el expediente a revisión.</Alert>
        </Card>
      )}

      <div className="mt-6 flex justify-between gap-2">
        <Button variant="outline" onClick={() => (step === 0 || (existing && step === 1) ? nav(-1) : setStep(step - 1))}><ArrowLeft />Atrás</Button>
        {step < 4 ? (
          <Button onClick={next}>Continuar<ArrowRight /></Button>
        ) : (
          <Button variant="brand" onClick={save} loading={saving}><Check />{existing ? "Guardar cambios" : "Crear expediente"}</Button>
        )}
      </div>
    </Container>
  );
}

function PolicyNote({ category }: { category: Category }) {
  const { meta } = useSession();
  const p = category.document_policy;
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2"><ShieldCheck className="size-4 text-brand-600" /><p className="text-sm font-semibold">Política de esta categoría</p><SensitivityBadge value={category.sensitivity} /></div>
      <p className="mt-1 text-sm text-slate-600">{category.policy_text}</p>
      <p className="mt-2 text-sm text-slate-600">Documentación requerida: mínimo {p.min_documents ?? 1} documento(s).{p.note ? ` ${p.note}` : ""}</p>
      {p.required_any?.map((g, i) => (
        <p key={i} className="text-xs text-slate-500">• Uno de: {g.map((t) => meta?.doc_types[t] ?? t).join(", ")}</p>
      ))}
    </Card>
  );
}

export function OwnerCasePage() {
  const { id } = useParams();
  const { meta, categories } = useSession();
  const { data: c, loading, error, reload } = useApi<CaseDetail>(`/cases/${id}`);
  const [docType, setDocType] = useState("");
  const [desc, setDesc] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  if (loading && !c) return <Spinner />;
  if (error || !c) return <Container><Alert kind="error">{error}</Alert></Container>;
  const editable = ["BORRADOR", "CORRECCION_SOLICITADA"].includes(c.status);
  const canUpload = editable || c.status === "PENDIENTE_REVISION";
  const cat = flatCategories(categories).find((x) => x.id === c.category.id);

  const upload = async () => {
    if (!file || !docType) return setMsg({ kind: "error", text: "Seleccione el tipo de documento y el archivo" });
    setBusy(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("doc_type", docType);
    fd.append("description", desc);
    try {
      await api(`/cases/${c.id}/documents`, { body: fd });
      setFile(null); setDesc(""); setDocType("");
      setMsg({ kind: "success", text: "Documento recibido. Pasa por cuarentena y análisis antivirus antes de estar disponible para el revisor." });
      setTimeout(reload, 1500);
      reload();
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const submit = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api(`/cases/${c.id}/submit`, { method: "POST" });
      setMsg({ kind: "success", text: "Expediente enviado a revisión. Recibirá una notificación con el resultado." });
      reload();
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Container className="max-w-5xl">
      <Link to="/mis-expedientes" className="text-sm font-medium text-brand-700 hover:underline">← Mis expedientes</Link>
      <PageHeader eyebrow={<span className="font-mono">{c.code}</span>} title={c.title}
        description={<span className="flex items-center gap-1.5"><CategoryIcon name={c.category.icon} className="size-4" />{c.category.parent_name ? `${c.category.parent_name} / ` : ""}{c.category.name}</span>}
        actions={editable ? <Button variant="outline" asChild><Link to={`/mis-expedientes/${c.id}/editar`}><Pencil />Editar datos</Link></Button> : undefined} />
      <div className="mb-4"><CaseStatusBadges c={c} /></div>
      {msg && <Alert kind={msg.kind} className="mb-4">{msg.text}</Alert>}
      {c.status === "CORRECCION_SOLICITADA" && <Alert kind="warning" title="El revisor solicitó correcciones" className="mb-4">{c.status_reason}</Alert>}
      {c.status === "RECHAZADO" && <Alert kind="error" title="Expediente rechazado" className="mb-4">{c.status_reason}</Alert>}
      {c.status === "APROBADO" && <Alert kind="success" title="Expediente aprobado" className="mb-4">{c.status_reason}</Alert>}
      {c.sensitivity === "INSTITUCIONAL" && <Alert kind="info" title="Tratamiento institucional" className="mb-4">{c.policy_text}</Alert>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Documentación de respaldo (privada)">
            {c.documents.length === 0 && <p className="text-sm text-slate-500">Aún no adjuntó documentos.</p>}
            <ul className="divide-y divide-slate-100">
              {c.documents.map((d) => (
                <li key={d.id} className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-2 text-sm font-medium"><FileText className="size-4 text-navy-700" />{meta?.doc_types[d.doc_type] ?? d.doc_type}</p>
                    <StatusBadge map={DOC_REVIEW} value={d.review_status} />
                  </div>
                  <div className="mt-1"><FileStatusLine file={d.file} /></div>
                  {d.review_note && <p className="mt-1 text-xs text-orange-700">Observación: {d.review_note}</p>}
                  {d.file.status === "DISPONIBLE" && (
                    <a className="mt-1 inline-block text-xs font-medium text-brand-700 hover:underline" href={fileUrl(d.file.id, "original")}>Descargar mi documento</a>
                  )}
                </li>
              ))}
            </ul>
            {cat && editable && <div className="mt-3"><PolicyNote category={cat} /></div>}
            {canUpload && (
              <div className="mt-4 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold">Adjuntar documento</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Tipo de documento" htmlFor="doc_type">
                    <Select id="doc_type" value={docType} onChange={(e) => setDocType(e.target.value)}>
                      <option value="">Seleccione…</option>
                      {Object.entries(meta?.doc_types ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                  </Field>
                  <Field label="Descripción (opcional)" htmlFor="doc_desc">
                    <Input id="doc_desc" value={desc} maxLength={500} onChange={(e) => setDesc(e.target.value)} />
                  </Field>
                </div>
                <FilePicker id="doc_file" accept=".pdf,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm" file={file} onChange={setFile}
                  hint={`PDF o imagen (máx. ${meta?.limits_mb.document ?? 20} MB) · video de respaldo (máx. ${meta?.limits_mb.video ?? 200} MB)`} />
                <Button onClick={upload} loading={busy} variant="outline">Adjuntar</Button>
              </div>
            )}
            {editable && (
              <div className="mt-4 flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">Cuando la documentación esté completa, envíe el expediente a revisión.</p>
                <Button variant="brand" onClick={submit} loading={busy}><Send />{c.status === "CORRECCION_SOLICITADA" ? "Reenviar a revisión" : "Enviar a revisión"}</Button>
              </div>
            )}
          </Section>
          <Section title="Datos del expediente">
            <dl className="divide-y divide-slate-100">
              <DataRow label="Descripción"><span className="whitespace-pre-line">{c.description}</span></DataRow>
              <DataRow label="Fecha y hora declarada">{fmtDateTime(c.incident_at)}</DataRow>
              <DataRow label="Zona">{c.zone}</DataRow>
              {Object.entries(c.specific_fields).map(([k, v]) => (
                <DataRow key={k} label={c.field_labels[k] ?? k}>{typeof v === "boolean" ? (v ? "Sí" : "No") : String(v)}</DataRow>
              ))}
              <DataRow label="Ubicación privada">{c.private_lat !== null ? <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" />{c.private_lat}, {c.private_lon}</span> : "No indicada"}</DataRow>
              {c.sensitive_flags.length > 0 && <DataRow label="Protecciones">{c.sensitive_flags.map((f) => f.label).join(", ")}</DataRow>}
            </dl>
          </Section>
        </div>
        <div className="space-y-6">
          <Section title="Seguimiento">
            <dl className="mb-4 divide-y divide-slate-100">
              <DataRow label="Estado"><StatusBadge map={CASE_STATUS} value={c.status} /></DataRow>
              <DataRow label="Responsable">{c.responsible}</DataRow>
              <DataRow label="Sensibilidad"><SensitivityBadge value={c.sensitivity} /></DataRow>
            </dl>
            <HistoryList events={[...c.history].reverse()} />
          </Section>
          {c.public_card && c.publication_status === "PUBLICADO" && (
            <Section title="Ficha pública">
              <p className="text-sm font-semibold">{c.public_card.public_title}</p>
              <p className="mt-1 text-sm text-slate-600">{c.public_card.public_summary}</p>
              <Button variant="link" asChild><Link to={`/expedientes/${c.code}`}>Ver ficha pública<ArrowRight /></Link></Button>
            </Section>
          )}
          <div className="flex gap-2 rounded-xl bg-amber-50 p-4 text-xs text-amber-900">
            <TriangleExclamationPoint className="size-4 shrink-0" />
            La aprobación de un expediente es una revisión documental del sistema y no equivale a una certificación de los hechos por una autoridad.
          </div>
        </div>
      </div>
    </Container>
  );
}


