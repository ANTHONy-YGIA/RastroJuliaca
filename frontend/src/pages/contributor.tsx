import { useState } from "react";
import { Link, useParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CircleCheck, Crosshair, Download, FileText, HandHeart, Inbox, ShieldCheck } from "lucide-react";
import { Container } from "@/components/layout";
import { FilePicker, FileStatusLine, HashLine, Section, TypeIcon } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/overlay";
import { Alert, Badge, Card, DataRow, EmptyState, Field, Input, PageHeader, Select, Spinner, StatusBadge, Textarea } from "@/components/ui/primitives";
import { api, download, errorMessage } from "@/lib/api";
import { CERTAINTY, CONTRIB_STATUS, CONTRIB_TYPE, cn, fmtDateTime, fromLocalInput, toLocalInput, ROLE_LABEL } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Contribution, Notification, PublicCase } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const TYPES = [
  { v: "VIDEO", accept: ".mp4,.mov,.webm", hint: "MP4, MOV o WEBM" },
  { v: "FOTO", accept: ".jpg,.jpeg,.png,.webp", hint: "JPG, PNG o WEBP" },
  { v: "DOCUMENTO", accept: ".pdf", hint: "PDF sin contenido activo" },
  { v: "TEXTO", accept: "", hint: "" },
] as const;

const schema = z
  .object({
    ctype: z.enum(["VIDEO", "FOTO", "DOCUMENTO", "TEXTO"]),
    description: z.string().trim().min(10, "Describa su aporte con al menos 10 caracteres").max(3000),
    declared_at: z.string().optional(),
    lat: z.string().optional(),
    lon: z.string().optional(),
    location_note: z.string().max(255).optional(),
    certainty: z.enum(["BAJA", "MEDIA", "ALTA"], { error: "Indique su nivel de certeza" }),
    consent: z.literal(true, { error: "Debe confirmar la declaración" }),
  })
  .refine((d) => (!d.lat && !d.lon) || (d.lat && d.lon), { path: ["lat"], message: "Indique latitud y longitud, o ninguna" })
  .refine((d) => !d.declared_at || new Date(fromLocalInput(d.declared_at)).getTime() <= Date.now() + 600000, { path: ["declared_at"], message: "No puede ser futura" });

export function ContributionFormPage() {
  const { code } = useParams();
  const { meta } = useSession();
  const { data: pc, loading, error } = useApi<PublicCase>(`/public/cases/${code}`);
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<Contribution | null>(null);
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { ctype: "FOTO" as const, description: "", certainty: undefined as unknown as "MEDIA" },
  });
  const ctype = watch("ctype");
  const t = TYPES.find((x) => x.v === ctype)!;

  if (loading) return <Spinner />;
  if (error || !pc) return <Container><Alert kind="error">{error}</Alert></Container>;
  if (!pc.accepts_contributions) return <Container><Alert kind="warning">Este expediente no recibe aportaciones.</Alert></Container>;

  const onSubmit = handleSubmit(async (v) => {
    setErr(null);
    if (v.ctype !== "TEXTO" && !file) return setErr("Adjunte el archivo de su aportación");
    const fd = new FormData();
    fd.append("case_code", pc.code);
    fd.append("ctype", v.ctype);
    fd.append("description", v.description);
    fd.append("certainty", v.certainty);
    if (v.declared_at) fd.append("declared_at", fromLocalInput(v.declared_at));
    if (v.lat) fd.append("declared_lat", v.lat);
    if (v.lon) fd.append("declared_lon", v.lon);
    if (v.location_note) fd.append("location_note", v.location_note);
    if (v.ctype !== "TEXTO" && file) fd.append("file", file);
    try {
      setDone(await api<Contribution>("/contributions", { body: fd }));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setErr(errorMessage(e));
    }
  });

  if (done)
    return (
      <Container className="max-w-2xl">
        <Card className="p-8 text-center animate-fade-in">
          <CircleCheck className="mx-auto size-12 text-brand-600" />
          <h1 className="mt-3 text-2xl font-bold">Aportación recibida</h1>
          <p className="mt-2 text-slate-600">Código de seguimiento: <span className="font-mono font-semibold text-navy-900" data-testid="contribution-code">{done.code}</span></p>
          <div className="mt-4 flex justify-center"><StatusBadge map={CONTRIB_STATUS} value={done.status} /></div>
          {done.file && <div className="mt-4 space-y-1 text-left"><FileStatusLine file={done.file} /><HashLine sha={done.file.sha256} /></div>}
          <p className="mt-4 text-sm text-slate-600">Su archivo permanece privado. Pasa por cuarentena, antivirus y validación antes de que un revisor autorizado lo examine.</p>
          <div className="mt-6 flex justify-center gap-2">
            <Button asChild variant="brand"><Link to="/mis-aportaciones">Ver mis aportaciones</Link></Button>
            <Button asChild variant="outline"><Link to={`/expedientes/${pc.code}`}>Volver a la ficha</Link></Button>
          </div>
        </Card>
      </Container>
    );

  return (
    <Container className="max-w-3xl">
      <PageHeader eyebrow={`Aportar a ${pc.code}`} title={pc.public_title} description="Su aporte es voluntario y privado. Los revisores verán un seudónimo, no su identidad." />
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {err && <Alert kind="error">{err}</Alert>}
        <Card className="p-5">
          <p className="mb-3 text-sm font-medium text-slate-700">Tipo de aportación</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="Tipo de aportación">
            {TYPES.map((o) => (
              <button key={o.v} type="button" role="radio" aria-checked={ctype === o.v} onClick={() => { setValue("ctype", o.v); setFile(null); }}
                className={cn("flex flex-col items-center gap-1.5 rounded-lg border p-3 text-sm font-medium transition",
                  ctype === o.v ? "border-brand-500 bg-brand-50 text-navy-900 ring-2 ring-brand-500/20" : "border-slate-200 text-slate-600 hover:border-slate-300")}>
                <TypeIcon type={o.v} className="size-5" />{CONTRIB_TYPE[o.v]}
              </button>
            ))}
          </div>
          {ctype !== "TEXTO" && (
            <div className="mt-4">
              <FilePicker accept={t.accept} file={file} onChange={setFile}
                hint={`${t.hint} · máx. ${ctype === "VIDEO" ? meta?.limits_mb.video : ctype === "FOTO" ? meta?.limits_mb.image : meta?.limits_mb.document} MB`} />
            </div>
          )}
        </Card>
        <Card className="space-y-4 p-5">
          <Field label="Descripción de lo que aporta" htmlFor="description" required error={errors.description?.message}>
            <Textarea id="description" rows={4} {...register("description")} placeholder="Qué se observa, desde dónde se registró, cualquier detalle útil." />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Fecha y hora del registro (opcional)" htmlFor="declared_at" error={errors.declared_at?.message} help="Hora de Perú. Se mostrará como dato declarado.">
              <Input id="declared_at" type="datetime-local" {...register("declared_at")} />
            </Field>
            <Field label="Nivel de certeza" htmlFor="certainty" required error={errors.certainty?.message}>
              <Select id="certainty" defaultValue="" {...register("certainty")}>
                <option value="" disabled>Seleccione…</option>
                <option value="ALTA">Alta: estoy seguro de lo que aporto</option>
                <option value="MEDIA">Media: probablemente relacionado</option>
                <option value="BAJA">Baja: no estoy seguro</option>
              </Select>
            </Field>
          </div>
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium text-slate-700">Ubicación aproximada del registro (opcional, privada)</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Latitud" htmlFor="lat" error={errors.lat?.message}><Input id="lat" inputMode="decimal" {...register("lat")} /></Field>
              <Field label="Longitud" htmlFor="lon"><Input id="lon" inputMode="decimal" {...register("lon")} /></Field>
              <Field label="Referencia" htmlFor="location_note"><Input id="location_note" {...register("location_note")} /></Field>
            </div>
            <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => navigator.geolocation?.getCurrentPosition((p) => {
              setValue("lat", p.coords.latitude.toFixed(6)); setValue("lon", p.coords.longitude.toFixed(6));
            })}><Crosshair />Usar mi ubicación actual</Button>
          </fieldset>
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" {...register("consent")} />
            <span>Declaro que aporto este material voluntariamente, que lo obtuve legítimamente y que no incluye contenido que vulnere derechos de terceros de forma innecesaria.</span>
          </label>
          {errors.consent && <p className="text-xs font-medium text-red-600" role="alert">{errors.consent.message}</p>}
        </Card>
        <div className="flex items-center justify-between gap-3">
          <p className="flex items-center gap-1.5 text-xs text-slate-500"><ShieldCheck className="size-4 text-brand-600" />Se calcula la huella SHA-256 y se analiza con antivirus.</p>
          <Button type="submit" variant="brand" size="lg" loading={isSubmitting}><HandHeart />Enviar aportación</Button>
        </div>
      </form>
    </Container>
  );
}

const correctionSchema = z.object({
  field: z.enum(["declared_at", "declared_lat", "declared_lon", "description"]),
  new_value: z.string().optional(),
  reason: z.string().trim().min(10, "Justifique la corrección (mínimo 10 caracteres)"),
});

export function CorrectionDialog({ contribution, endpoint, onDone }: { contribution: Contribution; endpoint: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { register, handleSubmit, watch, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(correctionSchema), defaultValues: { field: "declared_at" as const, new_value: "", reason: "" },
  });
  const field = watch("field");
  const submit = handleSubmit(async (v) => {
    setErr(null);
    const nv = v.field === "declared_at" && v.new_value ? fromLocalInput(v.new_value) : v.new_value;
    try {
      await api(endpoint, { body: { field: v.field, new_value: nv || null, reason: v.reason } });
      setOpen(false);
      reset();
      onDone();
    } catch (e) {
      setErr(errorMessage(e));
    }
  });
  return (
    <Dialog open={open} onOpenChange={setOpen} title={`Corregir ${contribution.code}`} description="El dato original se conserva; la corrección queda registrada con su justificación."
      trigger={<Button variant="outline" size="sm">Registrar corrección</Button>}>
      <form onSubmit={submit} className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="Dato a corregir" htmlFor="c-field">
          <Select id="c-field" {...register("field")}>
            <option value="declared_at">Fecha y hora declarada</option>
            <option value="declared_lat">Latitud</option>
            <option value="declared_lon">Longitud</option>
            <option value="description">Descripción</option>
          </Select>
        </Field>
        <Field label="Nuevo valor" htmlFor="c-value">
          {field === "declared_at" ? <Input id="c-value" type="datetime-local" defaultValue={toLocalInput(contribution.effective.declared_at)} {...register("new_value")} />
            : field === "description" ? <Textarea id="c-value" {...register("new_value")} /> : <Input id="c-value" inputMode="decimal" {...register("new_value")} />}
        </Field>
        <Field label="Justificación" htmlFor="c-reason" required error={errors.reason?.message}>
          <Textarea id="c-reason" rows={2} {...register("reason")} />
        </Field>
        <Button type="submit" loading={isSubmitting} className="w-full">Registrar corrección</Button>
      </form>
    </Dialog>
  );
}

export function MyContributionsPage() {
  const { data, loading, error, reload } = useApi<Contribution[]>("/contributions/mine");
  return (
    <Container className="max-w-5xl">
      <PageHeader eyebrow="Seguimiento privado" title="Mis aportaciones" description="Consulte el estado de validación y revisión de lo que aportó."
        actions={<Button variant="brand" asChild><Link to="/expedientes?open_only=true">Buscar expedientes abiertos</Link></Button>} />
      {loading && !data && <Spinner />}
      {error && <Alert kind="error">{error}</Alert>}
      {data?.length === 0 && <EmptyState icon={Inbox} title="Aún no realizó aportaciones">Explore las fichas públicas que reciben aportaciones.</EmptyState>}
      <div className="space-y-3">
        {data?.map((c) => (
          <Card key={c.id} className="p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <div className="rounded-lg bg-navy-50 p-2.5 text-navy-700 self-start"><TypeIcon type={c.type} className="size-5" /></div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-mono text-xs text-slate-500">{c.code} · Expediente {c.case_code}</p>
                <p className="font-semibold text-navy-900">{c.case_title}</p>
                <p className="text-sm text-slate-600 line-clamp-2">{c.effective.description}</p>
                <p className="text-xs text-slate-500">Enviada {fmtDateTime(c.created_at)} · Hora declarada: {fmtDateTime(c.effective.declared_at)} · Certeza {CERTAINTY[c.certainty]}</p>
                {c.file && <FileStatusLine file={c.file} />}
                {c.corrections.length > 0 && <p className="text-xs text-slate-500">{c.corrections.length} corrección(es) registrada(s)</p>}
              </div>
              <div className="flex flex-col items-start gap-2 sm:items-end">
                <StatusBadge map={CONTRIB_STATUS} value={c.status} />
                {c.status === "CLASIFICADA" && <Badge tone="navy">Examinada por el equipo</Badge>}
                {c.status !== "CLASIFICADA" && <CorrectionDialog contribution={c} endpoint={`/contributions/${c.id}/corrections`} onDone={reload} />}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </Container>
  );
}

export function AccountPage() {
  const { user, refresh } = useSession();
  const notifs = useApi<Notification[]>("/me/notifications");
  const reqs = useApi<{ id: number; rtype: string; detail: string; status: string; response: string | null; created_at: string }[]>("/me/data-requests");
  const [rtype, setRtype] = useState("ACCESO");
  const [detail, setDetail] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  if (!user) return <Spinner />;
  const readAll = async () => { await api("/me/notifications/read-all", { method: "POST" }); notifs.reload(); refresh(); };
  const open = async (n: Notification) => { if (!n.read) { await api(`/me/notifications/${n.id}/read`, { method: "POST" }); refresh(); } };
  const sendReq = async () => {
    setMsg(null);
    try {
      await api("/me/data-requests", { body: { rtype, detail } });
      setDetail("");
      setMsg("Solicitud registrada. La administración la atenderá y recibirá una notificación.");
      reqs.reload();
    } catch (e) { setMsg(errorMessage(e)); }
  };
  return (
    <Container className="max-w-5xl">
      <PageHeader eyebrow="Mi cuenta" title={user.full_name} description={`${ROLE_LABEL[user.role]} · ${user.email}`} />
      <div className="grid gap-6 lg:grid-cols-5">
        <Section className="lg:col-span-3" title="Notificaciones internas" actions={<Button variant="ghost" size="sm" onClick={readAll}>Marcar todas como leídas</Button>}>
          {notifs.data?.length === 0 && <p className="text-sm text-slate-500">Sin notificaciones.</p>}
          <ul className="divide-y divide-slate-100">
            {notifs.data?.map((n) => (
              <li key={n.id} className="py-3">
                <Link to={n.link ?? "#"} onClick={() => open(n)} className="group flex gap-3">
                  <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.read ? "bg-slate-300" : "bg-brand-500")} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className={cn("block text-sm group-hover:text-brand-700", n.read ? "text-slate-700" : "font-semibold text-navy-900")}>{n.title}</span>
                    <span className="block text-sm text-slate-600">{n.body}</span>
                    <span className="block text-xs text-slate-400">{fmtDateTime(n.created_at)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Section>
        <div className="space-y-6 lg:col-span-2">
          <Section title="Mis datos personales">
            <dl className="divide-y divide-slate-100">
              <DataRow label="Seudónimo">{user.alias}</DataRow>
              <DataRow label="Rol">{ROLE_LABEL[user.role]}</DataRow>
            </dl>
            <Button variant="outline" className="mt-3 w-full" onClick={() => download("/me/export", "mis-datos.json")}><Download />Descargar mis datos (JSON)</Button>
          </Section>
          <Section title="Derechos del titular">
            <p className="mb-3 text-xs text-slate-500">Solicitudes de acceso, rectificación, cancelación u oposición sobre sus datos personales.</p>
            {msg && <Alert kind="info" className="mb-3">{msg}</Alert>}
            <div className="space-y-3">
              <Select aria-label="Tipo de solicitud" value={rtype} onChange={(e) => setRtype(e.target.value)}>
                <option value="ACCESO">Acceso</option><option value="RECTIFICACION">Rectificación</option>
                <option value="CANCELACION">Cancelación</option><option value="OPOSICION">Oposición</option>
              </Select>
              <Textarea aria-label="Detalle de la solicitud" placeholder="Detalle su solicitud (mínimo 10 caracteres)" value={detail} onChange={(e) => setDetail(e.target.value)} />
              <Button className="w-full" onClick={sendReq} disabled={detail.trim().length < 10}><FileText />Presentar solicitud</Button>
            </div>
            <ul className="mt-4 space-y-2">
              {reqs.data?.map((r) => (
                <li key={r.id} className="rounded-lg bg-slate-50 p-3 text-xs">
                  <p className="font-semibold">{r.rtype} · {r.status}</p>
                  <p className="text-slate-500">{fmtDateTime(r.created_at)}</p>
                  {r.response && <p className="mt-1 text-slate-700">{r.response}</p>}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </Container>
  );
}
