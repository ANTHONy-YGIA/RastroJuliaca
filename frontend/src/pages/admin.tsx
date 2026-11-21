import { useState } from "react";
import { useSearchParams } from "react-router";
import { Activity, Database, FolderOpen, KeyRound, RefreshCw, ShieldCheck, UserCog, Users } from "lucide-react";
import { Container } from "@/components/layout";
import { Section, SensitivityBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, TabPanel, Tabs } from "@/components/ui/overlay";
import { Alert, Badge, Card, Field, Input, PageHeader, Select, Spinner, StatCard, StatusBadge, Textarea } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { CASE_STATUS, FILE_STATUS, PUBLICATION_STATUS, ROLE_LABEL, fmtBytes, fmtDateTime } from "@/lib/format";
import type { Category, User } from "@/lib/types";
import { useApi } from "@/lib/useApi";

interface Overview {
  cases_by_status: Record<string, number>;
  files_by_status: Record<string, number>;
  users_by_role: Record<string, number>;
  unassigned_cases: number;
  pending_rights_requests: number;
  system: { antivirus_engine: string; antivirus_available: boolean; ffmpeg: boolean; ffprobe: boolean; demo_mode: boolean; env: string };
}

export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "resumen";
  return (
    <Container>
      <PageHeader eyebrow="Administración técnica" title="Panel administrativo"
        description="Gestión de usuarios, asignaciones y configuración. La administración no otorga acceso al contenido de expedientes ni evidencias." />
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })} tabs={[
        { value: "resumen", label: "Resumen" }, { value: "usuarios", label: "Usuarios" }, { value: "expedientes", label: "Asignaciones" },
        { value: "categorias", label: "Categorías" }, { value: "auditoria", label: "Auditoría" }, { value: "conservacion", label: "Conservación" },
        { value: "derechos", label: "Derechos del titular" },
      ]}>
        <TabPanel value="resumen"><OverviewTab /></TabPanel>
        <TabPanel value="usuarios"><UsersTab /></TabPanel>
        <TabPanel value="expedientes"><AssignmentsTab /></TabPanel>
        <TabPanel value="categorias"><CategoriesTab /></TabPanel>
        <TabPanel value="auditoria"><AuditTab /></TabPanel>
        <TabPanel value="conservacion"><RetentionTab /></TabPanel>
        <TabPanel value="derechos"><RightsTab /></TabPanel>
      </Tabs>
    </Container>
  );
}

function OverviewTab() {
  const { data: o } = useApi<Overview>("/admin/overview");
  const blocked = useApi<{ id: string; status: string; status_detail: string; size_bytes: number; detected_type: string; uploaded_at: string }[]>("/admin/files/blocked");
  if (!o) return <Spinner />;
  const total = (m: Record<string, number>) => Object.values(m).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={FolderOpen} label="Expedientes" value={total(o.cases_by_status)} />
        <StatCard icon={UserCog} label="Sin revisor asignado" value={o.unassigned_cases} tone="amber" />
        <StatCard icon={Users} label="Usuarios" value={total(o.users_by_role)} tone="teal" />
        <StatCard icon={KeyRound} label="Solicitudes de derechos pendientes" value={o.pending_rights_requests} tone="amber" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Estado del sistema">
          <ul className="space-y-2 text-sm">
            <li className="flex items-center justify-between gap-2">Antivirus <Badge tone={o.system.antivirus_available ? "green" : "red"}>{o.system.antivirus_available ? o.system.antivirus_engine : "No disponible"}</Badge></li>
            <li className="flex items-center justify-between gap-2">FFmpeg / FFprobe <Badge tone={o.system.ffmpeg && o.system.ffprobe ? "green" : "red"}>{o.system.ffmpeg && o.system.ffprobe ? "Disponibles" : "No disponibles"}</Badge></li>
            <li className="flex items-center justify-between gap-2">Modo demostración <Badge tone={o.system.demo_mode ? "amber" : "slate"}>{o.system.demo_mode ? "Activo" : "No"}</Badge></li>
            <li className="flex items-center justify-between gap-2">Entorno <Badge>{o.system.env}</Badge></li>
          </ul>
          {!o.system.antivirus_available && <Alert kind="warning" className="mt-3">Sin antivirus operativo, los archivos permanecen bloqueados en cuarentena.</Alert>}
        </Section>
        <Section title="Expedientes por estado">
          <ul className="space-y-2">{Object.entries(o.cases_by_status).map(([k, v]) => <li key={k} className="flex justify-between text-sm"><StatusBadge map={CASE_STATUS} value={k} /><span className="tabular-nums">{v}</span></li>)}</ul>
        </Section>
        <Section title="Archivos por estado">
          <ul className="space-y-2">{Object.entries(o.files_by_status).map(([k, v]) => <li key={k} className="flex justify-between text-sm"><StatusBadge map={FILE_STATUS} value={k} /><span className="tabular-nums">{v}</span></li>)}</ul>
        </Section>
      </div>
      {blocked.data && blocked.data.length > 0 && (
        <Section title="Archivos bloqueados o en cuarentena (solo metadatos)">
          <ul className="divide-y divide-slate-100">
            {blocked.data.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span className="font-mono text-xs">{f.id.slice(0, 12)}… · {f.detected_type} · {fmtBytes(f.size_bytes)}</span>
                <StatusBadge map={FILE_STATUS} value={f.status} />
                <Button size="sm" variant="outline" disabled={f.status === "CUARENTENA" && Date.now() - new Date(f.uploaded_at).getTime() < 600_000}
                  onClick={async () => { await api(`/admin/files/${f.id}/rescan`, { method: "POST" }).catch(() => undefined); setTimeout(blocked.reload, 1500); }}><RefreshCw />Reanalizar</Button>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function UsersTab() {
  const { data, reload } = useApi<User[]>("/admin/users");
  const [err, setErr] = useState<string | null>(null);
  const patch = async (u: User, body: Partial<User>) => {
    setErr(null);
    try { await api(`/admin/users/${u.id}`, { method: "PATCH", body }); reload(); } catch (e) { setErr(errorMessage(e)); }
  };
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><NewStaffDialog onDone={reload} /></div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Usuario</th><th className="px-4 py-3">Rol</th><th className="px-4 py-3">Habilitación sensible</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3">Acciones</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3"><p className="font-medium text-navy-900">{u.full_name}</p><p className="text-xs text-slate-500">{u.email}</p></td>
                <td className="px-4 py-3">{ROLE_LABEL[u.role]}{u.active_assignments !== undefined && <span className="block text-xs text-slate-500">{u.active_assignments} asignación(es)</span>}</td>
                <td className="px-4 py-3">
                  {u.role === "REVISOR" ? (
                    <div className="flex flex-col gap-1">
                      <label className="flex items-center gap-2 text-xs"><input type="checkbox" className="accent-brand-600" checked={u.can_review_restricted} onChange={(e) => patch(u, { can_review_restricted: e.target.checked })} />Restringido</label>
                      <label className="flex items-center gap-2 text-xs"><input type="checkbox" className="accent-brand-600" checked={u.can_review_institutional} onChange={(e) => patch(u, { can_review_institutional: e.target.checked })} />Institucional</label>
                    </div>
                  ) : <span className="text-xs text-slate-400">No aplica</span>}
                </td>
                <td className="px-4 py-3"><Badge tone={u.is_active ? "green" : "slate"}>{u.is_active ? "Activo" : "Inactivo"}</Badge></td>
                <td className="px-4 py-3"><Button size="sm" variant="outline" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? "Desactivar" : "Activar"}</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function NewStaffDialog({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", full_name: "", password: "", role: "REVISOR", can_review_restricted: false, can_review_institutional: false });
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setErr(null);
    try { await api("/admin/users", { body: f }); setOpen(false); onDone(); } catch (e) { setErr(errorMessage(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen} title="Nueva cuenta del personal" trigger={<Button><UserCog />Crear cuenta del personal</Button>}>
      <div className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="Nombre" htmlFor="sn"><Input id="sn" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Correo" htmlFor="se"><Input id="se" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Contraseña inicial" htmlFor="sp" help="Mínimo 10 caracteres con letras y números."><Input id="sp" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
        <Field label="Rol" htmlFor="sr"><Select id="sr" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="REVISOR">Revisor</option><option value="ADMIN">Administrador</option></Select></Field>
        {f.role === "REVISOR" && (
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={f.can_review_restricted} onChange={(e) => setF({ ...f, can_review_restricted: e.target.checked })} />Restringido</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={f.can_review_institutional} onChange={(e) => setF({ ...f, can_review_institutional: e.target.checked })} />Institucional</label>
          </div>
        )}
        <Button className="w-full" onClick={save}>Crear</Button>
      </div>
    </Dialog>
  );
}

function AssignmentsTab() {
  const cases = useApi<{ id: number; code: string; category: string; sensitivity: string; status: string; publication_status: string; created_at: string; assigned: { id: number; full_name: string }[] }[]>("/admin/cases");
  const reviewers = useApi<User[]>("/admin/users?role=REVISOR");
  const [err, setErr] = useState<string | null>(null);
  const assign = async (caseId: number, rid: string) => {
    if (!rid) return;
    setErr(null);
    try { await api(`/admin/cases/${caseId}/assignments`, { body: { reviewer_id: +rid } }); cases.reload(); } catch (e) { setErr(errorMessage(e)); }
  };
  const unassign = async (caseId: number, rid: number) => {
    try { await api(`/admin/cases/${caseId}/assignments/${rid}`, { method: "DELETE" }); cases.reload(); } catch (e) { setErr(errorMessage(e)); }
  };
  return (
    <div className="space-y-4">
      <Alert kind="info">Se muestran solo metadatos. El contenido de los expedientes es accesible únicamente para revisores asignados y habilitados.</Alert>
      {err && <Alert kind="error">{err}</Alert>}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Expediente</th><th className="px-4 py-3">Sensibilidad</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3">Revisores</th><th className="px-4 py-3">Asignar</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cases.data?.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-3"><p className="font-mono font-medium">{c.code}</p><p className="text-xs text-slate-500">{c.category} · {fmtDateTime(c.created_at)}</p></td>
                <td className="px-4 py-3"><SensitivityBadge value={c.sensitivity} /></td>
                <td className="px-4 py-3"><div className="flex flex-col gap-1"><StatusBadge map={CASE_STATUS} value={c.status} /><StatusBadge map={PUBLICATION_STATUS} value={c.publication_status} /></div></td>
                <td className="px-4 py-3">
                  {c.assigned.length === 0 && <Badge tone="amber">Sin asignar</Badge>}
                  {c.assigned.map((a) => (
                    <span key={a.id} className="mb-1 mr-1 inline-flex items-center gap-1 rounded-full bg-navy-50 px-2 py-0.5 text-xs">
                      {a.full_name}<button className="text-slate-500 hover:text-red-600" aria-label={`Quitar a ${a.full_name}`} onClick={() => unassign(c.id, a.id)}>×</button>
                    </span>
                  ))}
                </td>
                <td className="px-4 py-3">
                  <Select aria-label={`Asignar revisor a ${c.code}`} defaultValue="" onChange={(e) => { assign(c.id, e.target.value); e.target.value = ""; }}>
                    <option value="">Agregar revisor…</option>
                    {reviewers.data?.filter((r) => r.is_active && !c.assigned.some((a) => a.id === r.id)).map((r) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
                  </Select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function CategoriesTab() {
  const { data, reload } = useApi<Category[]>("/admin/categories");
  const [msg, setMsg] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [editing, setEditing] = useState<Category | null>(null);
  const [schema, setSchema] = useState("");
  const patch = async (c: Category, body: Record<string, unknown>) => {
    setMsg(null);
    try {
      const r = await api<{ upgraded_cases?: number }>(`/admin/categories/${c.id}`, { method: "PATCH", body });
      setMsg({ kind: "success", text: `Categoría actualizada${r.upgraded_cases ? `; ${r.upgraded_cases} expediente(s) elevados de sensibilidad` : ""}.` });
      reload();
      return true;
    } catch (e) { setMsg({ kind: "error", text: errorMessage(e) }); return false; }
  };
  const all = data?.flatMap((c) => [c, ...(c.children ?? [])]) ?? [];
  return (
    <div className="space-y-4">
      <Alert kind="info" title="Protecciones reforzadas">La sensibilidad no puede reducirse por debajo del mínimo protegido definido en el código (secuestro, violencia sexual, menores vulnerables y desapariciones de alto riesgo).</Alert>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Categoría</th><th className="px-4 py-3">Efectiva</th><th className="px-4 py-3">Configurada</th><th className="px-4 py-3">Mínimo protegido</th><th className="px-4 py-3">Campos</th><th className="px-4 py-3" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {all.map((c) => (
              <tr key={c.id} className={c.parent_id ? "bg-slate-50/50" : ""}>
                <td className="px-4 py-3"><span className={c.parent_id ? "pl-4 text-slate-600" : "font-medium text-navy-900"}>{c.parent_id ? "↳ " : ""}{c.name}</span></td>
                <td className="px-4 py-3"><SensitivityBadge value={c.sensitivity} /></td>
                <td className="px-4 py-3">
                  <Select aria-label={`Sensibilidad de ${c.name}`} className="h-8 w-40 text-xs" value={c.configured_sensitivity} onChange={(e) => patch(c, { sensitivity: e.target.value })}>
                    <option value="GENERAL">General</option><option value="RESTRINGIDO">Restringido</option><option value="INSTITUCIONAL">Institucional</option>
                  </Select>
                </td>
                <td className="px-4 py-3"><SensitivityBadge value={c.code_floor === "GENERAL" ? c.min_sensitivity : c.code_floor} /></td>
                <td className="px-4 py-3 text-xs text-slate-500">{c.own_field_schema.length} propios</td>
                <td className="px-4 py-3"><Button size="sm" variant="ghost" onClick={() => { setEditing(c); setSchema(JSON.stringify(c.own_field_schema, null, 2)); }}>Editar esquema</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Dialog wide open={!!editing} onOpenChange={(v) => !v && setEditing(null)} title={`Esquema de campos: ${editing?.name ?? ""}`}
        description="JSON validado en el servidor. Tipos: text, textarea, number, select, date, boolean. Use public: true solo para datos generalizables.">
        <Textarea className="min-h-80 font-mono text-xs" value={schema} onChange={(e) => setSchema(e.target.value)} aria-label="Esquema JSON" />
        <Button className="mt-3 w-full" onClick={async () => {
          try { const parsed = JSON.parse(schema); if (editing && (await patch(editing, { field_schema: parsed }))) setEditing(null); }
          catch { setMsg({ kind: "error", text: "JSON no válido" }); }
        }}>Guardar esquema</Button>
      </Dialog>
    </div>
  );
}

function AuditTab() {
  const [action, setAction] = useState("");
  const { data, loading } = useApi<{ id: number; at: string; action: string; actor: string; actor_role: string | null; entity_type: string | null; entity_id: string | null; ip: string | null; details: Record<string, unknown> }[]>(`/admin/audit?limit=200${action ? `&action=${action}` : ""}`);
  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Activity className="size-4 text-navy-700" />
        <Select aria-label="Filtrar por acción" className="w-auto" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">Todas las acciones</option>
          {["LOGIN", "LOGIN_FAILED", "CASE_CREATED", "CASE_SUBMITTED", "CASE_DECISION", "PUBLICATION_REQUESTED", "CONTRIBUTION_CREATED", "FILE_SCANNED", "FILE_VIEWED", "FILE_DOWNLOADED", "CONTRIBUTION_CLASSIFIED", "REPORT_CREATED", "REPORT_EXPORTED", "CASE_ASSIGNED", "CATEGORY_UPDATED", "RETENTION_RUN", "DATA_RIGHTS_RESOLVED"].map((a) => <option key={a}>{a}</option>)}
        </Select>
      </Card>
      {loading && !data && <Spinner />}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead className="border-b border-slate-200 bg-slate-50 text-left uppercase tracking-wide text-slate-500">
            <tr><th className="px-3 py-2">Fecha</th><th className="px-3 py-2">Acción</th><th className="px-3 py-2">Actor</th><th className="px-3 py-2">Entidad</th><th className="px-3 py-2">Detalle</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono">
            {data?.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap px-3 py-2">{fmtDateTime(r.at)}</td>
                <td className="px-3 py-2 font-semibold text-navy-900">{r.action}</td>
                <td className="px-3 py-2">{r.actor}{r.actor_role && <span className="text-slate-400"> ({r.actor_role})</span>}</td>
                <td className="px-3 py-2">{r.entity_type}{r.entity_id && `#${r.entity_id.slice(0, 10)}`}</td>
                <td className="max-w-xs truncate px-3 py-2 text-slate-500" title={JSON.stringify(r.details)}>{JSON.stringify(r.details)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function RetentionTab() {
  const { data, reload } = useApi<Record<string, number>>("/admin/settings");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{ dry_run: boolean; cases: string[]; blocked_files: number; files_deleted: number } | null>(null);
  const [msg, setMsg] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  if (!data) return <Spinner />;
  const labels: Record<string, string> = {
    retention_days_rejected: "Días de conservación de expedientes rechazados",
    retention_days_closed: "Días de conservación de expedientes cerrados",
    retention_days_blocked_files: "Días de conservación de archivos no validados",
  };
  const save = async () => {
    setMsg(null);
    const body: Record<string, number> = {};
    Object.entries(vals).forEach(([k, v]) => v && (body[k] = +v));
    try { await api("/admin/settings", { method: "PUT", body }); setVals({}); reload(); setMsg({ kind: "success", text: "Configuración guardada" }); }
    catch (e) { setMsg({ kind: "error", text: errorMessage(e) }); }
  };
  const run = async (dry: boolean) => {
    try { setResult(await api("/admin/retention/run", { body: { dry_run: dry } })); } catch (e) { setMsg({ kind: "error", text: errorMessage(e) }); }
  };
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Section title="Políticas de conservación">
        {msg && <Alert kind={msg.kind} className="mb-3">{msg.text}</Alert>}
        <div className="space-y-3">
          {Object.entries(data).map(([k, v]) => (
            <Field key={k} label={labels[k] ?? k} htmlFor={k}><Input id={k} type="number" placeholder={String(v)} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} /></Field>
          ))}
          <Button onClick={save}><Database />Guardar</Button>
        </div>
      </Section>
      <Section title="Ejecutar política">
        <p className="text-sm text-slate-600">Elimina archivos y datos personales de expedientes rechazados o cerrados que superaron el plazo, y archivos que nunca superaron la validación. Se conserva un registro mínimo y la auditoría.</p>
        <div className="mt-3 flex gap-2">
          <Button variant="outline" onClick={() => run(true)}>Simular</Button>
          <Dialog title="Confirmar eliminación" description="Esta acción elimina archivos de forma permanente." trigger={<Button variant="danger">Ejecutar</Button>}>
            <Button variant="danger" className="w-full" onClick={() => run(false)}>Sí, ejecutar política de conservación</Button>
          </Dialog>
        </div>
        {result && (
          <Alert kind="info" className="mt-4" title={result.dry_run ? "Simulación" : "Ejecución completada"}>
            Expedientes afectados: {result.cases.length ? result.cases.join(", ") : "ninguno"}. Archivos no validados vencidos: {result.blocked_files}. Archivos eliminados: {result.files_deleted}.
          </Alert>
        )}
      </Section>
    </div>
  );
}

function RightsTab() {
  const { data, reload } = useApi<{ id: number; user: { id: number; full_name: string; email: string }; rtype: string; detail: string; status: string; response: string | null; created_at: string }[]>("/admin/data-requests");
  const [resp, setResp] = useState<Record<number, string>>({});
  const [anon, setAnon] = useState<Record<number, boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const resolve = async (id: number, status: string) => {
    setErr(null);
    try { await api(`/admin/data-requests/${id}/resolve`, { body: { status, response: resp[id] ?? "", anonymize_account: !!anon[id] } }); reload(); }
    catch (e) { setErr(errorMessage(e)); }
  };
  if (!data) return <Spinner />;
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      {data.length === 0 && <p className="text-sm text-slate-500">No hay solicitudes.</p>}
      {data.map((r) => (
        <Card key={r.id} className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">#{r.id} · {r.rtype} · {r.user.full_name}</p>
            <Badge tone={r.status === "PENDIENTE" ? "amber" : r.status === "ATENDIDA" ? "green" : "red"}>{r.status}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600">{r.detail}</p>
          <p className="text-xs text-slate-400">{fmtDateTime(r.created_at)} · {r.user.email}</p>
          {r.status === "PENDIENTE" ? (
            <div className="mt-3 space-y-2">
              <Textarea aria-label="Respuesta" placeholder="Respuesta al titular (mínimo 10 caracteres)" value={resp[r.id] ?? ""} onChange={(e) => setResp({ ...resp, [r.id]: e.target.value })} />
              {(r.rtype === "CANCELACION" || r.rtype === "OPOSICION") && (
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-red-600" checked={!!anon[r.id]} onChange={(e) => setAnon({ ...anon, [r.id]: e.target.checked })} />Anonimizar y desactivar la cuenta</label>
              )}
              <div className="flex gap-2">
                <Button size="sm" onClick={() => resolve(r.id, "ATENDIDA")}><ShieldCheck />Atender</Button>
                <Button size="sm" variant="outline" onClick={() => resolve(r.id, "DENEGADA")}>Denegar</Button>
              </div>
            </div>
          ) : <p className="mt-2 text-sm text-slate-700">Respuesta: {r.response}</p>}
        </Card>
      ))}
    </div>
  );
}
