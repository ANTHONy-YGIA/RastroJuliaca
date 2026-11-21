import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import {
  ArrowRight, BadgeCheck, CircleCheck, ClipboardList, Clock, Download, Eye, FileBraces, FileText, FolderOpen, Globe, Inbox, Lock, MapPin,
  Printer, Search, Send, ShieldCheck, Timer, TriangleExclamationPoint,
} from "lucide-react";
import { Container } from "@/components/layout";
import { CaseStatusBadges, FileStatusLine, HashLine, HistoryList, MediaViewer, Section, SensitivityBadge, TypeIcon } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, TabPanel, Tabs } from "@/components/ui/overlay";
import { Alert, Badge, Card, DataRow, EmptyState, Field, Input, PageHeader, Select, Spinner, StatCard, StatusBadge, Textarea } from "@/components/ui/primitives";
import { api, download, errorMessage, fileUrl } from "@/lib/api";
import {
  CASE_STATUS, CERTAINTY, CLASSIFICATION, CONTRIB_STATUS, CONTRIB_TYPE, DOC_REVIEW, EVENT_LABEL, PUBLICATION_STATUS, cn, fmtBytes, fmtDateTime, fmtHours, fmtKm, fmtRelative,
} from "@/lib/format";
import { CategoryIcon } from "@/lib/icons";
import { useSession } from "@/lib/session";
import type { CaseDetail, CaseSummary, Contribution, ReportFull, ReportSummary } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { CorrectionDialog } from "./contributor";

interface Dashboard {
  counts: Record<string, number>;
  recent: { case_id: number; case_code: string; event: string; detail: string; created_at: string; actor: string }[];
  pending_contributions: { id: number; code: string; case_code: string; type: string; created_at: string }[];
  clearance: { restricted: boolean; institutional: boolean };
}

export function ReviewerDashboard() {
  const { categories } = useSession();
  const [params, setParams] = useSearchParams();
  const dash = useApi<Dashboard>("/review/dashboard");
  const qs = new URLSearchParams();
  ["status", "category", "sensitivity", "q", "sort"].forEach((k) => params.get(k) && qs.set(k, params.get(k)!));
  const cases = useApi<CaseSummary[]>(`/review/cases?${qs}`);
  const [q, setQ] = useState(params.get("q") ?? "");
  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p, { replace: true });
  };
  useEffect(() => {
    const t = setTimeout(() => set("q", q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const c = dash.data?.counts;
  return (
    <Container>
      <PageHeader eyebrow="Panel del operador" title="Revisión de expedientes y evidencias"
        description={dash.data && <>Habilitación: General{dash.data.clearance.restricted && " · Restringido"}{dash.data.clearance.institutional && " · Institucional"}. Solo ve expedientes asignados.</>}
        actions={<Button variant="outline" asChild><Link to="/revisor/informes"><FileText />Informes</Link></Button>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard icon={Inbox} label="Expedientes pendientes" value={c?.cases_pending ?? "—"} tone="amber" />
        <StatCard icon={BadgeCheck} label="Expedientes aprobados" value={c?.cases_approved ?? "—"} tone="green" />
        <StatCard icon={Eye} label="Evidencias por revisar" value={c?.evidence_pending ?? "—"} tone="teal" />
        <StatCard icon={Lock} label="En validación / bloqueadas" value={c?.evidence_validating ?? "—"} />
        <StatCard icon={Globe} label="Publicación por confirmar" value={c?.publication_pending ?? "—"} tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
            <div className="relative sm:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input aria-label="Buscar expedientes" placeholder="Código, título o descripción" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <Select aria-label="Estado" value={params.get("status") ?? ""} onChange={(e) => set("status", e.target.value)}>
              <option value="">Todos los estados</option>
              {Object.entries(CASE_STATUS).filter(([k]) => k !== "BORRADOR").map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </Select>
            <Select aria-label="Categoría" value={params.get("category") ?? ""} onChange={(e) => set("category", e.target.value)}>
              <option value="">Todas las categorías</option>
              {categories.map((x) => <option key={x.slug} value={x.slug}>{x.name}</option>)}
            </Select>
            <Select aria-label="Ordenar" value={params.get("sort") ?? "received"} onChange={(e) => set("sort", e.target.value)}>
              <option value="received">Recepción (recientes)</option>
              <option value="incident">Fecha del incidente</option>
              <option value="category">Categoría</option>
              <option value="status">Estado</option>
            </Select>
          </Card>
          {cases.loading && !cases.data && <Spinner />}
          {cases.error && <Alert kind="error">{cases.error}</Alert>}
          {cases.data?.length === 0 && <EmptyState icon={FolderOpen} title="Sin expedientes con estos filtros" />}
          <div className="space-y-2">
            {cases.data?.map((x) => (
              <Link key={x.id} to={`/revisor/expedientes/${x.id}`} className="group block" data-testid="review-case-row">
                <Card className="flex flex-col gap-3 p-4 transition group-hover:border-brand-400 xl:flex-row xl:items-center">
                  <div className="rounded-lg bg-navy-50 p-2.5 text-navy-700 self-start"><CategoryIcon name={x.category.icon} className="size-5" /></div>
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs text-slate-500">{x.code} · {x.category.name} · {x.zone}</p>
                    <p className="truncate font-semibold text-navy-900 group-hover:text-brand-700">{x.title}</p>
                    <p className="text-xs text-slate-500">Recibido {fmtRelative(x.submitted_at ?? x.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {!!x.pending_contributions && <Badge tone="blue">{x.pending_contributions} evidencia(s) por revisar</Badge>}
                    <CaseStatusBadges c={x} />
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          <Section title="Evidencias pendientes">
            {dash.data?.pending_contributions.length === 0 && <p className="text-sm text-slate-500">No hay evidencias pendientes.</p>}
            <ul className="space-y-2">
              {dash.data?.pending_contributions.map((p) => (
                <li key={p.id}>
                  <Link to={`/revisor/aportaciones/${p.id}`} className="flex items-center gap-3 rounded-lg p-2 hover:bg-slate-50">
                    <TypeIcon type={p.type} className="size-4 text-navy-700" />
                    <span className="min-w-0 flex-1 text-sm"><span className="font-mono font-medium">{p.code}</span><span className="block text-xs text-slate-500">{p.case_code} · {fmtRelative(p.created_at)}</span></span>
                    <ArrowRight className="size-4 text-slate-400" />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Revisiones recientes">
            {dash.data?.recent.length === 0 && <p className="text-sm text-slate-500">Sin actividad.</p>}
            <ul className="space-y-3">
              {dash.data?.recent.map((r, i) => (
                <li key={i} className="text-sm">
                  <Link to={`/revisor/expedientes/${r.case_id}`} className="font-medium text-navy-900 hover:text-brand-700">{EVENT_LABEL[r.event] ?? r.event} · {r.case_code}</Link>
                  <p className="text-xs text-slate-600 line-clamp-2">{r.detail}</p>
                  <p className="text-[11px] text-slate-400">{fmtRelative(r.created_at)} · {r.actor}</p>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </Container>
  );
}

export function ReviewerCasePage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "resumen";
  const { data: c, loading, error, reload, setData } = useApi<CaseDetail>(`/review/cases/${id}`);
  if (loading && !c) return <Spinner />;
  if (error || !c) return <Container><Alert kind="error" title="Expediente no disponible">{error}</Alert></Container>;
  const total = Object.values(c.contribution_counts ?? {}).reduce((a, b) => a + b, 0);
  return (
    <Container>
      <Link to="/revisor" className="text-sm font-medium text-brand-700 hover:underline">← Panel de revisión</Link>
      <PageHeader eyebrow={<span className="font-mono">{c.code}</span>} title={c.title}
        description={<span className="flex items-center gap-1.5"><CategoryIcon name={c.category.icon} className="size-4" />{c.category.parent_name ? `${c.category.parent_name} / ` : ""}{c.category.name} · Responsable: {c.responsible}</span>} />
      <div className="mb-5"><CaseStatusBadges c={c} /></div>
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })}
        tabs={[{ value: "resumen", label: "Revisión documental" }, { value: "publicacion", label: "Publicación" }, { value: "evidencias", label: "Evidencias", count: total },
          { value: "linea", label: "Línea de tiempo" }, { value: "informes", label: "Informes" }]}>
        <TabPanel value="resumen"><SummaryTab c={c} onChange={(d) => (d ? setData(d) : reload())} /></TabPanel>
        <TabPanel value="publicacion"><PublicationTab c={c} onChange={(d) => (d ? setData(d) : reload())} /></TabPanel>
        <TabPanel value="evidencias"><EvidenceTab c={c} /></TabPanel>
        <TabPanel value="linea"><TimelineTab caseId={c.id} /></TabPanel>
        <TabPanel value="informes"><ReportsTab c={c} /></TabPanel>
      </Tabs>
    </Container>
  );
}

function SummaryTab({ c, onChange }: { c: CaseDetail; onChange: (d?: CaseDetail) => void }) {
  const { meta } = useSession();
  const [decision, setDecision] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const decide = async () => {
    setBusy(true); setErr(null);
    try { onChange(await api<CaseDetail>(`/review/cases/${c.id}/decision`, { body: { decision, reason } })); setReason(""); setDecision(""); }
    catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  const assess = async (docId: number, status: string, note = "") => {
    setErr(null);
    try { await api(`/review/documents/${docId}/assessment`, { body: { status, note } }); onChange(); }
    catch (e) { setErr(errorMessage(e)); }
  };
  const options = c.status === "PENDIENTE_REVISION"
    ? [["APROBAR", "Aprobar"], ["SOLICITAR_CORRECCION", "Solicitar corrección"], ["RECHAZAR", "Rechazar"]]
    : c.status === "APROBADO" ? [["CERRAR", "Cerrar expediente"]] : [];
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        {err && <Alert kind="error">{err}</Alert>}
        <Section title="Documentación de respaldo">
          {c.documents.length === 0 && <p className="text-sm text-slate-500">Sin documentos.</p>}
          <ul className="space-y-4">
            {c.documents.map((d) => (
              <li key={d.id} className="rounded-lg border border-slate-200 p-4" data-testid="doc-item">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-2 font-medium"><FileText className="size-4 text-navy-700" />{meta?.doc_types[d.doc_type] ?? d.doc_type}</p>
                  <StatusBadge map={DOC_REVIEW} value={d.review_status} />
                </div>
                {d.description && <p className="mt-1 text-sm text-slate-600">{d.description}</p>}
                <div className="mt-2"><FileStatusLine file={d.file} /></div>
                <HashLine sha={d.file.sha256} />
                {d.review_note && <p className="mt-1 text-xs text-orange-700">Nota: {d.review_note}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  {d.file.status === "DISPONIBLE" && (
                    <>
                      {d.file.has_playback && <Button size="sm" variant="ghost" asChild><a href={fileUrl(d.file.id)} target="_blank" rel="noopener"><Eye />Ver copia segura</a></Button>}
                      <Button size="sm" variant="ghost" asChild><a href={fileUrl(d.file.id, "original")}><Download />Descargar (registrado)</a></Button>
                    </>
                  )}
                  {c.status === "PENDIENTE_REVISION" && (
                    <>
                      <Button size="sm" variant="outline" disabled={d.file.status !== "DISPONIBLE"} onClick={() => assess(d.id, "ACEPTADO")}><CircleCheck />Aceptar</Button>
                      <ObserveButton onObserve={(note) => assess(d.id, "OBSERVADO", note)} />
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Datos declarados">
          <dl className="divide-y divide-slate-100">
            <DataRow label="Descripción"><span className="whitespace-pre-line">{c.description}</span></DataRow>
            <DataRow label="Fecha y hora declarada">{fmtDateTime(c.incident_at)}</DataRow>
            <DataRow label="Zona">{c.zone}</DataRow>
            {Object.entries(c.specific_fields).map(([k, v]) => <DataRow key={k} label={c.field_labels[k] ?? k}>{typeof v === "boolean" ? (v ? "Sí" : "No") : String(v)}</DataRow>)}
            <DataRow label="Ubicación privada">{c.private_lat !== null ? `${c.private_lat}, ${c.private_lon}${c.private_location_note ? ` · ${c.private_location_note}` : ""}` : "No indicada (datos insuficientes para proximidad)"}</DataRow>
            <DataRow label="Denunciante (seudónimo)">{c.reporter_alias}</DataRow>
            <DataRow label="Sensibilidad"><SensitivityBadge value={c.sensitivity} /> <span className="ml-1 text-xs text-slate-500">{c.policy_text}</span></DataRow>
            {c.sensitive_flags.length > 0 && <DataRow label="Protecciones">{c.sensitive_flags.map((f) => f.label).join(", ")}</DataRow>}
          </dl>
        </Section>
      </div>
      <div className="space-y-6">
        <Section title="Decisión">
          {options.length === 0 ? <p className="text-sm text-slate-600">Estado actual: {CASE_STATUS[c.status]?.label}. {c.status_reason}</p> : (
            <div className="space-y-3">
              <Field label="Acción" htmlFor="decision">
                <Select id="decision" value={decision} onChange={(e) => setDecision(e.target.value)}>
                  <option value="">Seleccione…</option>
                  {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </Select>
              </Field>
              <Field label="Motivo (obligatorio)" htmlFor="reason">
                <Textarea id="reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
              </Field>
              <Button className="w-full" onClick={decide} loading={busy} disabled={!decision || reason.trim().length < 5}><Send />Registrar decisión</Button>
              <p className="text-xs text-slate-500">Para aprobar debe aceptar al menos un documento validado.</p>
            </div>
          )}
        </Section>
        {c.decisions && c.decisions.length > 0 && (
          <Section title="Decisiones registradas">
            <ul className="space-y-3">
              {c.decisions.map((d, i) => (
                <li key={i} className="text-sm"><p className="font-medium">{d.decision.replace("_", " ")} · {d.reviewer}</p><p className="text-slate-600">{d.reason}</p><p className="text-xs text-slate-400">{fmtDateTime(d.created_at)}</p></li>
              ))}
            </ul>
          </Section>
        )}
        <Section title="Historial"><HistoryList events={[...c.history].reverse()} /></Section>
      </div>
    </div>
  );
}

function ObserveButton({ onObserve }: { onObserve: (note: string) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  return (
    <Dialog open={open} onOpenChange={setOpen} title="Observar documento" trigger={<Button size="sm" variant="outline"><TriangleExclamationPoint />Observar</Button>}>
      <Textarea aria-label="Motivo de la observación" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Explique qué falta o qué debe corregirse" />
      <Button className="mt-3 w-full" disabled={note.trim().length < 5} onClick={() => { onObserve(note); setOpen(false); }}>Registrar observación</Button>
    </Dialog>
  );
}

function PublicationTab({ c, onChange }: { c: CaseDetail; onChange: (d?: CaseDetail) => void }) {
  const { user } = useSession();
  const [title, setTitle] = useState(c.public_card?.public_title ?? "");
  const [summary, setSummary] = useState(c.public_card?.public_summary ?? "");
  const [keys, setKeys] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const publicable = c.field_schema.filter((f) => f.public && c.specific_fields[f.key] !== undefined);
  const run = async (fn: () => Promise<CaseDetail | unknown>) => {
    setBusy(true); setErr(null);
    try { const r = await fn(); onChange(r && typeof r === "object" && "code" in (r as object) ? (r as CaseDetail) : undefined); }
    catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  const pending = c.publication_status === "PENDIENTE_SEGUNDA_APROBACION";
  const isRequester = c.public_card?.requested_by === user?.id;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {err && <Alert kind="error">{err}</Alert>}
        <Alert kind="info" title="Política de sensibilidad">{c.policy_text}</Alert>
        {pending && (
          <Alert kind="warning" title="Pendiente de segunda aprobación">
            {isRequester ? "Usted solicitó la publicación. Otro revisor habilitado debe confirmarla." : "Revise la ficha propuesta y confirme si cumple con la minimización de datos."}
            {!isRequester && <div className="mt-2"><Button size="sm" onClick={() => run(() => api(`/review/cases/${c.id}/publication/confirm`, { method: "POST" }))} loading={busy}><CircleCheck />Confirmar publicación</Button></div>}
          </Alert>
        )}
        {c.can_publish ? (
          <Section title="Ficha pública generalizada">
            <div className="space-y-4">
              <Field label="Título público" htmlFor="pt"><Input id="pt" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Sin nombres, direcciones exactas ni datos de contacto" /></Field>
              <Field label="Resumen público" htmlFor="ps" help="Se rechazarán DNI, teléfonos, correos, coordenadas, nombre del denunciante o ubicación privada.">
                <Textarea id="ps" rows={4} value={summary} onChange={(e) => setSummary(e.target.value)} />
              </Field>
              {c.sensitivity === "GENERAL" && publicable.length > 0 && (
                <fieldset>
                  <legend className="mb-2 text-sm font-medium text-slate-700">Campos autorizados para publicar</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {publicable.map((f) => (
                      <label key={f.key} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                        <input type="checkbox" className="size-4 accent-brand-600" checked={keys.includes(f.key)} onChange={(e) => setKeys(e.target.checked ? [...keys, f.key] : keys.filter((k) => k !== f.key))} />
                        <span><span className="font-medium">{f.label}:</span> {String(c.specific_fields[f.key])}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
              {c.sensitivity === "RESTRINGIDO" && <p className="text-sm text-orange-700">Expediente RESTRINGIDO: ficha mínima sin campos específicos y con segunda aprobación de otro revisor.</p>}
              <Button variant="brand" loading={busy} disabled={title.trim().length < 5 || summary.trim().length < 20}
                onClick={() => run(() => api(`/review/cases/${c.id}/publication`, { body: { public_title: title, public_summary: summary, public_field_keys: keys } }))}>
                <Globe />{c.sensitivity === "RESTRINGIDO" ? "Solicitar publicación" : "Publicar ficha"}
              </Button>
            </div>
          </Section>
        ) : !pending && c.publication_status !== "PUBLICADO" && (
          <Alert kind="warning" title="Publicación no disponible">{c.publish_block_reason}</Alert>
        )}
        {c.public_card && c.publication_status === "PUBLICADO" && (
          <Section title="Ficha vigente" actions={<Button variant="link" asChild><Link to={`/expedientes/${c.code}`} target="_blank">Ver pública</Link></Button>}>
            <p className="font-semibold">{c.public_card.public_title}</p>
            <p className="mt-1 text-sm text-slate-600">{c.public_card.public_summary}</p>
            {Object.entries(c.public_card.public_fields).map(([k, v]) => <p key={k} className="text-sm"><span className="font-medium">{k}:</span> {String(v)}</p>)}
            <WithdrawButton onWithdraw={(reason) => run(() => api(`/review/cases/${c.id}/publication/withdraw`, { body: { reason } }))} />
          </Section>
        )}
      </div>
      <Section title="Aportaciones ciudadanas">
        <p className="text-sm text-slate-600">Estado: {c.contributions_open ? <Badge tone="teal">Abiertas</Badge> : <Badge>Cerradas</Badge>}</p>
        <p className="mt-1 text-xs text-slate-500">{PUBLICATION_STATUS[c.publication_status]?.label}</p>
        {c.contributions_open ? (
          <Button variant="outline" className="mt-3 w-full" loading={busy} onClick={() => run(() => api(`/review/cases/${c.id}/contributions-open`, { body: { open: false } }))}>Cerrar aportaciones</Button>
        ) : c.can_open_contributions ? (
          <Button variant="brand" className="mt-3 w-full" loading={busy} onClick={() => run(() => api(`/review/cases/${c.id}/contributions-open`, { body: { open: true } }))}>Habilitar aportaciones</Button>
        ) : <p className="mt-3 text-xs text-slate-500">{c.contributions_block_reason}</p>}
      </Section>
    </div>
  );
}

function WithdrawButton({ onWithdraw }: { onWithdraw: (r: string) => void }) {
  const [open, setOpen] = useState(false);
  const [r, setR] = useState("");
  return (
    <Dialog open={open} onOpenChange={setOpen} title="Retirar ficha pública" trigger={<Button variant="outline" size="sm" className="mt-3">Retirar ficha</Button>}>
      <Textarea aria-label="Motivo del retiro" value={r} onChange={(e) => setR(e.target.value)} placeholder="Motivo del retiro" />
      <Button variant="danger" className="mt-3 w-full" disabled={r.trim().length < 5} onClick={() => { onWithdraw(r); setOpen(false); }}>Retirar</Button>
    </Dialog>
  );
}

interface ContribList { case_reference: { has_location: boolean; incident_at: string }; items: Contribution[]; hidden_by_filters: number }

function EvidenceTab({ c }: { c: CaseDetail }) {
  const [sort, setSort] = useState("distance");
  const [status, setStatus] = useState("");
  const [ctype, setCtype] = useState("");
  const [cls, setCls] = useState("");
  const [maxKm, setMaxKm] = useState("");
  const [maxH, setMaxH] = useState("");
  const qs = new URLSearchParams({ sort });
  if (status) qs.set("status", status);
  if (ctype) qs.set("ctype", ctype);
  if (cls) qs.set("classification", cls);
  if (maxKm) qs.set("max_km", maxKm);
  if (maxH) qs.set("max_hours", maxH);
  const { data, loading, error } = useApi<ContribList>(`/review/cases/${c.id}/contributions?${qs}`);
  return (
    <div className="space-y-4">
      <Card className="grid gap-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Ordenar por" htmlFor="sort">
          <Select id="sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="distance">Cercanía geográfica</option><option value="time">Cercanía temporal</option>
            <option value="received">Fecha de recepción</option><option value="status">Estado de revisión</option>
          </Select>
        </Field>
        <Field label="Estado" htmlFor="fstatus">
          <Select id="fstatus" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos</option>{Object.entries(CONTRIB_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </Select>
        </Field>
        <Field label="Tipo" htmlFor="ftype">
          <Select id="ftype" value={ctype} onChange={(e) => setCtype(e.target.value)}>
            <option value="">Todos</option>{Object.entries(CONTRIB_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Clasificación" htmlFor="fcls">
          <Select id="fcls" value={cls} onChange={(e) => setCls(e.target.value)}>
            <option value="">Todas</option>{Object.entries(CLASSIFICATION).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </Select>
        </Field>
        <Field label="Radio máx. (km)" htmlFor="fkm"><Input id="fkm" type="number" min="0.1" step="0.1" value={maxKm} onChange={(e) => setMaxKm(e.target.value)} /></Field>
        <Field label="Ventana máx. (h)" htmlFor="fh"><Input id="fh" type="number" min="0.5" step="0.5" value={maxH} onChange={(e) => setMaxH(e.target.value)} /></Field>
      </Card>
      {data && !data.case_reference.has_location && <Alert kind="warning">El expediente no tiene ubicación privada: la cercanía geográfica no puede calcularse (datos insuficientes).</Alert>}
      {data && data.hidden_by_filters > 0 && <Alert kind="info">{data.hidden_by_filters} aportación(es) fuera del radio o ventana elegidos están ocultas. Las aportaciones sin datos nunca se ocultan.</Alert>}
      {loading && !data && <Spinner />}
      {error && <Alert kind="error">{error}</Alert>}
      {data?.items.length === 0 && <EmptyState icon={Inbox} title="Sin aportaciones con estos filtros" />}
      <div className="space-y-2">
        {data?.items.map((x) => (
          <Link key={x.id} to={`/revisor/aportaciones/${x.id}`} className="group block" data-testid="evidence-row">
            <Card className="flex flex-col gap-3 p-4 transition group-hover:border-brand-400 xl:flex-row xl:items-center">
              <div className="rounded-lg bg-navy-50 p-2.5 text-navy-700 self-start"><TypeIcon type={x.type} className="size-5" /></div>
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-slate-500">{x.code} · {CONTRIB_TYPE[x.type]} · {x.contributor_alias} · certeza {CERTAINTY[x.certainty]}</p>
                <p className="text-sm text-slate-800 line-clamp-2">{x.effective.description}</p>
                <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" />{fmtKm(x.distance_km)}</span>
                  <span className="inline-flex items-center gap-1"><Timer className="size-3.5" />Δt {fmtHours(x.time_diff_h)}</span>
                  <span className="inline-flex items-center gap-1"><Clock className="size-3.5" />Declarada: {fmtDateTime(x.effective.declared_at)}</span>
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {x.file?.duplicate_of_id && <Badge tone="orange">Duplicado exacto</Badge>}
                <StatusBadge map={CONTRIB_STATUS} value={x.status} />
                {x.classification && <StatusBadge map={CLASSIFICATION} value={x.classification} />}
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

interface TimelineData {
  notice: string;
  entries: { kind: string; code?: string; contribution_id?: number; at: string; original_at?: string; label: string; type: string | null; description: string; status: string; classification: string | null; certainty?: string; observations: string[]; corrected: boolean; distance_km?: number | null }[];
  undated: TimelineData["entries"];
}

function TimelineTab({ caseId }: { caseId: number }) {
  const [cls, setCls] = useState("");
  const [onlyClassified, setOnlyClassified] = useState(false);
  const qs = new URLSearchParams();
  if (cls) qs.set("classification", cls);
  if (onlyClassified) qs.set("include_unclassified", "false");
  const { data, loading } = useApi<TimelineData>(`/review/cases/${caseId}/timeline?${qs}`);
  if (loading && !data) return <Spinner />;
  if (!data) return null;
  const Item = ({ e }: { e: TimelineData["entries"][number] }) => (
    <li className="relative pb-6" data-testid="timeline-item">
      <span className={cn("absolute -left-[33px] flex size-6 items-center justify-center rounded-full ring-4 ring-slate-50", e.kind === "INCIDENTE" ? "bg-red-600 text-white" : "bg-navy-900 text-white")}>
        {e.kind === "INCIDENTE" ? <TriangleExclamationPoint className="size-3.5" /> : <TypeIcon type={e.type ?? "TEXTO"} className="size-3.5" />}
      </span>
      <Card className={cn("p-4", e.kind === "INCIDENTE" && "border-red-200 bg-red-50/40")}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold text-navy-900">{e.at ? fmtDateTime(e.at) : "Sin hora declarada"} {e.code && <span className="font-mono text-xs text-slate-500">· {e.code}</span>}</p>
          <div className="flex gap-1.5">
            {e.kind !== "INCIDENTE" && <StatusBadge map={CONTRIB_STATUS} value={e.status} />}
            {e.classification && <StatusBadge map={CLASSIFICATION} value={e.classification} />}
          </div>
        </div>
        <p className="text-xs italic text-slate-500">{e.label}{e.corrected && e.original_at && ` · corregida (original: ${fmtDateTime(e.original_at)})`}</p>
        <p className="mt-1 text-sm text-slate-700">{e.type ? `${CONTRIB_TYPE[e.type]}: ` : ""}{e.description}</p>
        {e.distance_km !== undefined && <p className="text-xs text-slate-500">Distancia aprox.: {fmtKm(e.distance_km)}</p>}
        {e.observations.map((o, i) => <p key={i} className="mt-1 rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">Observación: {o}</p>)}
        {e.contribution_id && <Link to={`/revisor/aportaciones/${e.contribution_id}`} className="mt-1 inline-block text-xs font-medium text-brand-700 hover:underline">Abrir evidencia</Link>}
      </Card>
    </li>
  );
  return (
    <div className="space-y-4">
      <Alert kind="warning">{data.notice}</Alert>
      <Card className="flex flex-wrap items-center gap-4 p-4">
        <Select aria-label="Filtrar por clasificación" className="w-auto" value={cls} onChange={(e) => setCls(e.target.value)}>
          <option value="">Todas las clasificaciones</option>{Object.entries(CLASSIFICATION).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </Select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" checked={onlyClassified} onChange={(e) => setOnlyClassified(e.target.checked)} />Solo clasificadas</label>
      </Card>
      <ol className="ml-4 border-l-2 border-slate-200 pl-6">{data.entries.map((e, i) => <Item key={i} e={e} />)}</ol>
      {data.undated.length > 0 && (
        <Section title="Aportaciones sin fecha declarada (datos insuficientes)">
          <ol className="ml-4 border-l-2 border-dashed border-slate-200 pl-6">{data.undated.map((e, i) => <Item key={i} e={e} />)}</ol>
        </Section>
      )}
    </div>
  );
}

function ReportsTab({ c }: { c: CaseDetail }) {
  const nav = useNavigate();
  const list = useApi<ReportSummary[]>(`/review/reports?case_id=${c.id}`);
  const contribs = useApi<ContribList>(`/review/cases/${c.id}/contributions?sort=time`);
  const [sel, setSel] = useState<number[]>([]);
  const [title, setTitle] = useState(`Informe de evidencias — ${c.code}`);
  const [summary, setSummary] = useState("");
  const [loc, setLoc] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (contribs.data) setSel(contribs.data.items.filter((x) => x.classification === "RELEVANTE" || x.classification === "POSIBLEMENTE_RELEVANTE").map((x) => x.id));
  }, [contribs.data]);
  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api<ReportFull>(`/review/cases/${c.id}/reports`, { body: { title, summary, contribution_ids: sel, include_private_locations: loc } });
      nav(`/revisor/informes/${r.id}`);
    } catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Section className="lg:col-span-2" title="Generar informe">
        <div className="space-y-4">
          {err && <Alert kind="error">{err}</Alert>}
          <Field label="Título" htmlFor="rt"><Input id="rt" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
          <Field label="Resumen del revisor" htmlFor="rs" help="Describa objetivamente el contenido; no establezca culpabilidad."><Textarea id="rs" rows={4} value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">Evidencias seleccionadas ({sel.length})</legend>
            <div className="max-h-72 space-y-1.5 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {contribs.data?.items.map((x) => (
                <label key={x.id} className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-slate-50">
                  <input type="checkbox" className="size-4 accent-brand-600" checked={sel.includes(x.id)} onChange={(e) => setSel(e.target.checked ? [...sel, x.id] : sel.filter((i) => i !== x.id))} />
                  <span className="font-mono text-xs">{x.code}</span>
                  <span className="min-w-0 flex-1 truncate text-slate-600">{x.effective.description}</span>
                  {x.classification && <StatusBadge map={CLASSIFICATION} value={x.classification} />}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" checked={loc} onChange={(e) => setLoc(e.target.checked)} />Incluir ubicaciones privadas (solo para uso institucional autorizado)</label>
          <Button variant="brand" onClick={create} loading={busy} disabled={summary.trim().length < 20 || title.trim().length < 5}><ClipboardList />Generar informe</Button>
        </div>
      </Section>
      <Section title="Informes del expediente">
        {list.data?.length === 0 && <p className="text-sm text-slate-500">Aún no hay informes.</p>}
        <ul className="space-y-2">
          {list.data?.map((r) => (
            <li key={r.id}><Link to={`/revisor/informes/${r.id}`} className="block rounded-lg p-2 hover:bg-slate-50"><p className="font-mono text-sm font-medium">{r.code}</p><p className="text-xs text-slate-500">{fmtDateTime(r.created_at)} · {r.export_count} exportación(es)</p></Link></li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

export function EvidenceReviewPage() {
  const { id } = useParams();
  const { data: x, loading, error, reload, setData } = useApi<Contribution>(`/review/contributions/${id}`);
  const [cls, setCls] = useState("");
  const [obs, setObs] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (loading && !x) return <Spinner />;
  if (error || !x) return <Container><Alert kind="error">{error}</Alert></Container>;
  const classify = async () => {
    setBusy(true); setErr(null);
    try { setData(await api<Contribution>(`/review/contributions/${x.id}/classify`, { body: { classification: cls, observation: obs } })); setObs(""); reload(); }
    catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  const addNote = async () => {
    try { await api(`/review/contributions/${x.id}/observations`, { body: { text: note } }); setNote(""); reload(); } catch (e) { setErr(errorMessage(e)); }
  };
  const ready = x.status === "PENDIENTE_REVISION" || x.status === "CLASIFICADA";
  return (
    <Container>
      <Link to={`/revisor/expedientes/${x.case?.id}?tab=evidencias`} className="text-sm font-medium text-brand-700 hover:underline">← Evidencias de {x.case?.code}</Link>
      <PageHeader eyebrow={<span className="font-mono">{x.code}</span>} title={`${CONTRIB_TYPE[x.type]} aportada por ${x.contributor_alias}`} description={x.case?.title} />
      <div className="mb-5 flex flex-wrap gap-1.5">
        <StatusBadge map={CONTRIB_STATUS} value={x.status} />
        {x.classification && <StatusBadge map={CLASSIFICATION} value={x.classification} />}
        {x.duplicate_of_code && <Badge tone="orange">Duplicado exacto de {x.duplicate_of_code}</Badge>}
      </div>
      {err && <Alert kind="error" className="mb-4">{err}</Alert>}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          {x.file && (
            <Section title="Material aportado (copia segura)">
              <MediaViewer file={x.file} />
              <div className="mt-3 space-y-1">
                <FileStatusLine file={x.file} />
                <HashLine sha={x.file.sha256} />
                {x.file.media_info?.duration_s !== undefined && <p className="text-xs text-slate-500">Duración: {String(x.file.media_info.duration_s)} s · {String(x.file.media_info.width)}×{String(x.file.media_info.height)}</p>}
                <p className="text-xs text-slate-500">Analizado: {fmtDateTime(x.file.scanned_at)} · Tamaño original {fmtBytes(x.file.size_bytes)}</p>
              </div>
              {x.file.status === "DISPONIBLE" && <Button variant="ghost" size="sm" className="mt-2" asChild><a href={fileUrl(x.file.id, "original")}><Download />Descargar original (queda registrado)</a></Button>}
            </Section>
          )}
          <Section title="Información declarada" actions={<CorrectionDialog contribution={x} endpoint={`/review/contributions/${x.id}/corrections`} onDone={reload} />}>
            <dl className="divide-y divide-slate-100">
              <DataRow label="Descripción"><span className="whitespace-pre-line">{x.effective.description}</span></DataRow>
              <DataRow label="Hora declarada">{fmtDateTime(x.effective.declared_at)}{x.effective.declared_at !== x.original.declared_at && <span className="block text-xs text-slate-500">Original: {fmtDateTime(x.original.declared_at)}</span>}</DataRow>
              <DataRow label="Ubicación declarada">{x.effective.declared_lat !== null ? `${x.effective.declared_lat}, ${x.effective.declared_lon}` : "No indicada"}{x.original.location_note && ` · ${x.original.location_note}`}</DataRow>
              <DataRow label="Distancia aproximada">{fmtKm(x.distance_km)} <span className="text-xs text-slate-500">(Haversine)</span></DataRow>
              <DataRow label="Diferencia temporal">{fmtHours(x.time_diff_h)}</DataRow>
              <DataRow label="Certeza declarada">{CERTAINTY[x.certainty]}</DataRow>
              <DataRow label="Recibida">{fmtDateTime(x.created_at)}</DataRow>
            </dl>
            {x.data_quality && x.data_quality.length > 0 && <Alert kind="warning" className="mt-3">{x.data_quality.join(". ")}.</Alert>}
            {x.corrections.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-sm font-semibold">Correcciones registradas</p>
                {x.corrections.map((k, i) => (
                  <div key={i} className="rounded-lg bg-slate-50 p-3 text-xs">
                    <p><span className="font-medium">{k.field}</span>: {k.old_value ?? "—"} → {k.new_value ?? "—"}</p>
                    <p className="text-slate-600">Motivo: {k.reason}</p>
                    <p className="text-slate-400">{k.author} · {fmtDateTime(k.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>
        <div className="space-y-6 lg:col-span-2">
          <Section title="Clasificación">
            {!ready ? <Alert kind="warning">La aportación aún no superó la validación de seguridad y no puede clasificarse.</Alert> : (
              <div className="space-y-3">
                <div className="grid grid-cols-1 gap-1.5" role="radiogroup" aria-label="Clasificación">
                  {Object.entries(CLASSIFICATION).map(([k, v]) => (
                    <label key={k} className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-sm", cls === k ? "border-brand-500 bg-brand-50" : "border-slate-200")}>
                      <input type="radio" name="cls" value={k} checked={cls === k} onChange={() => setCls(k)} className="accent-brand-600" />{v.label}
                    </label>
                  ))}
                </div>
                <Field label="Observación (obligatoria)" htmlFor="obs"><Textarea id="obs" rows={3} value={obs} onChange={(e) => setObs(e.target.value)} /></Field>
                <Button className="w-full" onClick={classify} loading={busy} disabled={!cls || obs.trim().length < 5}><ShieldCheck />Registrar clasificación</Button>
              </div>
            )}
          </Section>
          <Section title="Observaciones">
            {x.observations?.length === 0 && <p className="text-sm text-slate-500">Sin observaciones.</p>}
            <ul className="space-y-2">
              {x.observations?.map((o) => <li key={o.id} className="rounded-lg bg-slate-50 p-3 text-sm"><p>{o.text}</p><p className="mt-1 text-xs text-slate-400">{o.author} · {fmtDateTime(o.created_at)}</p></li>)}
            </ul>
            <div className="mt-3 flex gap-2">
              <Input aria-label="Nueva observación" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Agregar observación" />
              <Button variant="outline" onClick={addNote} disabled={note.trim().length < 3}>Agregar</Button>
            </div>
          </Section>
        </div>
      </div>
    </Container>
  );
}

export function ReportsListPage() {
  const { data, loading } = useApi<ReportSummary[]>("/review/reports");
  return (
    <Container className="max-w-5xl">
      <PageHeader eyebrow="Informes" title="Informes generados" description="Instantáneas inmutables con huella SHA-256. Cada exportación queda registrada." />
      {loading && <Spinner />}
      {data?.length === 0 && <EmptyState icon={FileText} title="Aún no hay informes">Genérelos desde la pestaña Informes de cada expediente.</EmptyState>}
      <div className="space-y-2">
        {data?.map((r) => (
          <Link key={r.id} to={`/revisor/informes/${r.id}`} className="group block">
            <Card className="flex flex-col gap-2 p-4 group-hover:border-brand-400 sm:flex-row sm:items-center">
              <FileText className="size-5 text-navy-700" />
              <div className="min-w-0 flex-1"><p className="font-mono text-sm font-semibold">{r.code} · {r.case_code}</p><p className="truncate text-sm text-slate-600">{r.title}</p></div>
              <p className="text-xs text-slate-500">{fmtDateTime(r.created_at)} · {r.export_count} export.</p>
            </Card>
          </Link>
        ))}
      </div>
    </Container>
  );
}

export function ReportViewPage() {
  const { id } = useParams();
  const { data: r, loading, error, reload } = useApi<ReportFull>(`/reports/${id}`);
  const [err, setErr] = useState<string | null>(null);
  if (loading && !r) return <Spinner />;
  if (error || !r) return <Container><Alert kind="error">{error}</Alert></Container>;
  const c = r.content;
  const exp = async (fmt: "json" | "pdf") => {
    setErr(null);
    try { await download(`/reports/${r.id}/export.${fmt}`, `${r.code}.${fmt}`); reload(); } catch (e) { setErr(errorMessage(e)); }
  };
  return (
    <Container className="max-w-4xl">
      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link to="/revisor/informes" className="text-sm font-medium text-brand-700 hover:underline">← Informes</Link>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => exp("json")}><FileBraces />Exportar JSON</Button>
          <Button variant="outline" onClick={() => exp("pdf")}><Download />Exportar PDF</Button>
          <Button variant="ghost" onClick={() => window.print()}><Printer />Imprimir</Button>
        </div>
      </div>
      {err && <Alert kind="error" className="mb-4">{err}</Alert>}
      <Card className="p-6 sm:p-8">
        <div className="flex flex-col gap-2 border-b border-slate-200 pb-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-mono text-xs text-slate-500">{c.report_code} · {c.case.code}</p>
            <h1 className="text-2xl font-bold">{c.title}</h1>
            <p className="text-sm text-slate-500">Generado {fmtDateTime(c.generated_at)} por {c.generated_by.name} · {r.export_count} exportación(es)</p>
          </div>
          {c.demo_mode && <Badge tone="amber">MODO DEMOSTRACIÓN</Badge>}
        </div>
        <section className="mt-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-800">Resumen</h2>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{c.summary}</p>
          <p className="mt-3 text-xs text-slate-500">{c.disclaimer}</p>
        </section>
        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-800">Expediente</h2>
          <dl className="mt-2 divide-y divide-slate-100">
            <DataRow label="Categoría">{c.case.category}{c.case.subcategory ? ` / ${c.case.subcategory}` : ""}</DataRow>
            <DataRow label="Estado">{c.case.status} · Sensibilidad {c.case.sensitivity}</DataRow>
            <DataRow label="Incidente (declarado)">{c.case.incident_local} · {c.case.zone}</DataRow>
            {Object.entries(c.case.specific_fields).map(([k, v]) => <DataRow key={k} label={k}>{String(v)}</DataRow>)}
            {c.case.private_location && <DataRow label="Ubicación privada">{c.case.private_location.lat}, {c.case.private_location.lon}</DataRow>}
          </dl>
          <p className="mt-3 text-xs font-medium text-slate-600">Documentos de respaldo</p>
          {c.case.supporting_documents.map((d, i) => <div key={i} className="mt-1 text-xs"><span>{d.type} · {d.review_status}</span><HashLine sha={d.sha256} /></div>)}
        </section>
        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-800">Evidencias seleccionadas ({c.evidence.length})</h2>
          <div className="mt-3 space-y-3">
            {c.evidence.map((e) => (
              <div key={e.code} className="rounded-lg border border-slate-200 p-4 break-inside-avoid" data-testid="report-evidence">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono text-sm font-semibold">{e.code} · {CONTRIB_TYPE[e.type]}</p>
                  <div className="flex gap-1.5">{e.classification && <StatusBadge map={CLASSIFICATION} value={e.classification} />}<Badge>Certeza {CERTAINTY[e.declared_certainty]}</Badge></div>
                </div>
                <p className="mt-1 text-sm">{e.description}</p>
                <p className="mt-1 text-xs text-slate-500">Hora declarada: {fmtDateTime(e.declared_at)}{e.declared_at !== e.declared_at_original && ` (original ${fmtDateTime(e.declared_at_original)})`} · Distancia: {fmtKm(e.distance_km_approx)} · Δt: {fmtHours(e.time_diff_h)}</p>
                {e.file && <HashLine sha={e.file.sha256} />}
                {e.observations.map((o, i) => <p key={i} className="mt-1 text-xs text-slate-600">Observación ({o.author}): {o.text}</p>)}
                {e.corrections.map((k, i) => <p key={i} className="mt-1 text-xs text-slate-600">Corrección {k.field}: {k.old_value} → {k.new_value} ({k.reason})</p>)}
              </div>
            ))}
          </div>
        </section>
        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-800">Historial pertinente</h2>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {c.history.map((h, i) => <li key={i}>{fmtDateTime(h.at)} · {EVENT_LABEL[h.event] ?? h.event} · {h.detail} ({h.actor})</li>)}
          </ul>
        </section>
        <div className="mt-6 rounded-lg bg-navy-50 p-4">
          <p className="text-xs font-semibold text-navy-900">Integridad del informe (SHA-256 del contenido canónico)</p>
          <HashLine sha={r.content_sha256} />
        </div>
      </Card>
    </Container>
  );
}
