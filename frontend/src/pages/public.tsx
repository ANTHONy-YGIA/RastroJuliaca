import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import {
  ArrowRight, CalendarClock, ClipboardList, FileSearch, FolderOpen, Info, Lock, MapPin, ScanSearch, Search, ShieldCheck, Upload, Users,
} from "lucide-react";
import { Container } from "@/components/layout";
import { PublicCaseCard, SensitivityBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Alert, Badge, Card, DataRow, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui/primitives";
import { useApi } from "@/lib/useApi";
import { useSession } from "@/lib/session";
import { CategoryIcon } from "@/lib/icons";
import { fmtDate, fmtDateTime } from "@/lib/format";
import type { PublicCase } from "@/lib/types";

export function HomePage() {
  const { categories, user } = useSession();
  const { data: stats } = useApi<{ published_cases: number; open_for_contributions: number; categories: number }>("/public/stats");
  const { data: recent } = useApi<PublicCase[]>("/public/cases");
  return (
    <>
      <section className="relative overflow-hidden bg-navy-900 text-white">
        <div className="absolute inset-0 opacity-[0.07]" aria-hidden="true"
          style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "24px 24px" }} />
        <div className="absolute -right-24 -top-24 size-96 rounded-full bg-brand-500/20 blur-3xl" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-5 lg:py-24">
          <div className="lg:col-span-3 animate-fade-in">
            <Badge tone="teal" className="mb-4 bg-brand-500/15 text-brand-100 ring-brand-400/30">Juliaca · Puno · Perú</Badge>
            <h1 className="text-4xl font-bold leading-tight text-white sm:text-5xl">
              Evidencias ciudadanas organizadas, protegidas y <span className="text-brand-400">revisadas</span>.
            </h1>
            <p className="mt-5 max-w-2xl text-lg text-navy-100">
              RastroJuliaca centraliza voluntariamente fotografías, videos e información sobre incidentes, los mantiene privados
              y los organiza por expediente para su revisión por operadores autorizados.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" variant="brand" asChild><Link to="/expedientes"><Search />Explorar expedientes</Link></Button>
              {!user && <Button size="lg" variant="light" asChild><Link to="/registro">Registrar un incidente<ArrowRight /></Link></Button>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 self-center lg:col-span-2">
            {[
              { v: stats?.published_cases ?? "—", l: "Fichas públicas" },
              { v: stats?.open_for_contributions ?? "—", l: "Reciben aportaciones" },
              { v: stats?.categories ?? "—", l: "Categorías de incidente" },
              { v: "SHA-256", l: "Integridad de cada archivo" },
            ].map((s) => (
              <div key={s.l} className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur">
                <p className="text-2xl font-bold tabular-nums text-white">{s.v}</p>
                <p className="text-xs text-navy-100">{s.l}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Container>
        <h2 className="text-2xl font-bold">¿Cómo funciona?</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { i: ClipboardList, t: "1. Registro privado", d: "El denunciante crea un expediente y adjunta documentación de respaldo. Todo permanece privado." },
            { i: FileSearch, t: "2. Revisión documental", d: "Un revisor asignado examina la documentación y aprueba, rechaza o solicita correcciones." },
            { i: Upload, t: "3. Aportaciones", d: "Si corresponde, se publica una ficha generalizada y la ciudadanía aporta videos, fotos o información." },
            { i: ScanSearch, t: "4. Validación y análisis", d: "Cada archivo pasa por cuarentena, antivirus y hash; el revisor clasifica y genera un informe." },
          ].map((s) => (
            <Card key={s.t} className="p-5">
              <s.i className="size-6 text-brand-600" aria-hidden="true" />
              <h3 className="mt-3 font-semibold">{s.t}</h3>
              <p className="mt-1 text-sm text-slate-600">{s.d}</p>
            </Card>
          ))}
        </div>

        {recent && recent.length > 0 && (
          <div className="mt-14">
            <div className="flex items-end justify-between">
              <h2 className="text-2xl font-bold">Fichas públicas recientes</h2>
              <Link to="/expedientes" className="text-sm font-medium text-brand-700 hover:underline">Ver todas</Link>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {recent.slice(0, 3).map((c) => <PublicCaseCard key={c.code} c={c} />)}
            </div>
          </div>
        )}

        <div className="mt-14">
          <h2 className="text-2xl font-bold">Categorías de incidente</h2>
          <p className="mt-1 text-sm text-slate-600">Cada categoría tiene campos específicos y una política de sensibilidad.</p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {categories.map((c) => (
              <div key={c.id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4">
                <div className="rounded-lg bg-navy-50 p-2 text-navy-700"><CategoryIcon name={c.icon} className="size-5" /></div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-navy-900">{c.name}</p>
                  <div className="mt-1"><SensitivityBadge value={c.sensitivity} /></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-14 grid gap-4 lg:grid-cols-3">
          {[
            { i: Lock, t: "Privacidad por defecto", d: "Los documentos de respaldo nunca son públicos. Las fichas solo muestran datos generalizados autorizados por la revisión." },
            { i: ShieldCheck, t: "Archivos protegidos", d: "Cuarentena, antivirus real, validación de formato, nombres internos aleatorios y registro de cada acceso." },
            { i: Users, t: "Colaboradores protegidos", d: "Los revisores ven un seudónimo, no la identidad de quien aporta. Los casos sensibles tienen restricciones reforzadas." },
          ].map((s) => (
            <div key={s.t} className="flex gap-4 rounded-xl bg-navy-50 p-5">
              <s.i className="size-6 shrink-0 text-navy-700" aria-hidden="true" />
              <div><h3 className="font-semibold">{s.t}</h3><p className="mt-1 text-sm text-slate-600">{s.d}</p></div>
            </div>
          ))}
        </div>
      </Container>
    </>
  );
}

export function ExplorerPage() {
  const { categories, meta } = useSession();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const qs = new URLSearchParams();
  for (const k of ["q", "category", "zone", "open_only"]) {
    const v = params.get(k);
    if (v) qs.set(k, v);
  }
  const { data, loading, error } = useApi<PublicCase[]>(`/public/cases?${qs.toString()}`);
  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p, { replace: true });
  };
  useEffect(() => {
    const t = setTimeout(() => set("q", q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Container>
      <PageHeader eyebrow="Explorador" title="Expedientes con ficha pública" description="Solo se muestran fichas generalizadas aprobadas por revisión. La publicación no implica verificación por una autoridad." />
      <Card className="mb-6 grid gap-3 p-4 md:grid-cols-4">
        <div className="relative md:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <Input aria-label="Buscar" placeholder="Buscar por título, resumen o código" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
        <Select aria-label="Categoría" value={params.get("category") ?? ""} onChange={(e) => set("category", e.target.value)}>
          <option value="">Todas las categorías</option>
          {categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </Select>
        <Select aria-label="Zona" value={params.get("zone") ?? ""} onChange={(e) => set("zone", e.target.value)}>
          <option value="">Todas las zonas</option>
          {meta?.zones.map((z) => <option key={z} value={z}>{z}</option>)}
        </Select>
        <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-4">
          <input type="checkbox" className="size-4 accent-brand-600" checked={params.get("open_only") === "true"} onChange={(e) => set("open_only", e.target.checked ? "true" : "")} />
          Solo expedientes que reciben aportaciones
        </label>
      </Card>
      {loading && <Spinner />}
      {error && <Alert kind="error">{error}</Alert>}
      {data && data.length === 0 && <EmptyState icon={FolderOpen} title="No hay fichas que coincidan">Pruebe con otros filtros.</EmptyState>}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((c) => <PublicCaseCard key={c.code} c={c} />)}
      </div>
    </Container>
  );
}

export function PublicCasePage() {
  const { code } = useParams();
  const { meta, user } = useSession();
  const { data: c, loading, error } = useApi<PublicCase>(`/public/cases/${code}`);
  if (loading) return <Spinner />;
  if (error || !c) return <Container><Alert kind="error" title="Ficha no disponible">{error}</Alert></Container>;
  const canContribute = c.accepts_contributions && (!user || user.role === "COLABORADOR" || user.role === "DENUNCIANTE");
  return (
    <Container className="max-w-4xl">
      <Link to="/expedientes" className="text-sm font-medium text-brand-700 hover:underline">← Volver al explorador</Link>
      <div className="mt-4 flex flex-col gap-6 lg:flex-row">
        <div className="min-w-0 flex-1 space-y-6">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <CategoryIcon name={c.category.icon} className="size-4" />
              {c.category.parent_name ? `${c.category.parent_name} · ` : ""}{c.category.name}
              <span className="font-mono text-xs">· {c.code}</span>
            </div>
            <h1 className="mt-2 text-3xl font-bold">{c.public_title}</h1>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
              <span className="inline-flex items-center gap-1"><MapPin className="size-4" />{c.zone}</span>
              <span className="inline-flex items-center gap-1"><CalendarClock className="size-4" />{fmtDate(c.incident_date)}</span>
            </div>
          </div>
          <Card className="p-5">
            <p className="whitespace-pre-line leading-relaxed text-slate-700">{c.public_summary}</p>
            {Object.keys(c.public_fields).length > 0 && (
              <dl className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
                {Object.entries(c.public_fields).map(([k, v]) => (
                  <DataRow key={k} label={k}>{typeof v === "boolean" ? (v ? "Sí" : "No") : String(v)}</DataRow>
                ))}
              </dl>
            )}
          </Card>
          <Alert kind="info" title="Información no verificada por una autoridad">{meta?.disclaimer}</Alert>
        </div>
        <aside className="w-full space-y-4 lg:w-72">
          <Card className="p-5">
            <h2 className="font-semibold">¿Tiene información?</h2>
            {c.accepts_contributions ? (
              <>
                <p className="mt-1 text-sm text-slate-600">Puede aportar un video, fotografía, documento o descripción. Su aporte será privado y revisado.</p>
                {canContribute ? (
                  <Button variant="brand" className="mt-4 w-full" asChild>
                    <Link to={user ? `/expedientes/${c.code}/aportar` : `/ingresar?next=/expedientes/${c.code}/aportar`}><Upload />Aportar información</Link>
                  </Button>
                ) : (
                  <p className="mt-3 text-xs text-slate-500">Las cuentas del personal no realizan aportaciones ciudadanas.</p>
                )}
              </>
            ) : (
              <p className="mt-1 text-sm text-slate-600">Este expediente no recibe aportaciones en este momento.</p>
            )}
            <p className="mt-4 text-xs text-slate-500">Aportaciones recibidas: {c.contributions_received ?? 0}</p>
            <p className="text-xs text-slate-500">Publicado: {fmtDateTime(c.published_at)}</p>
          </Card>
          <div className="flex gap-2 rounded-xl bg-navy-50 p-4 text-xs text-navy-800">
            <Info className="size-4 shrink-0" aria-hidden="true" />
            Los videos originales, documentos de respaldo y ubicaciones exactas nunca se publican.
          </div>
        </aside>
      </div>
    </Container>
  );
}

export function PrivacyPage() {
  return (
    <Container className="max-w-3xl">
      <PageHeader eyebrow="Privacidad" title="Aviso de privacidad y uso responsable" />
      <Card className="space-y-4 p-6 text-sm leading-relaxed text-slate-700">
        <Alert kind="warning" title="Prototipo académico">
          Este sistema es un MVP para demostraciones controladas. No está autorizado para procesar incidentes reales ni declara cumplimiento legal certificado.
        </Alert>
        <p>
          El diseño considera los principios de la Ley N.° 29733, Ley de Protección de Datos Personales, y su Reglamento aprobado mediante
          D. S. N.° 016-2024-JUS, así como las disposiciones aplicables al tratamiento de imágenes y videovigilancia. Su aplicación en un
          contexto real requeriría evaluación legal, inscripción de bancos de datos y procedimientos institucionales autorizados.
        </p>
        <h2 className="text-base font-semibold">Qué datos se tratan</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Datos de cuenta: nombre, correo y contraseña (almacenada con hash Argon2id).</li>
          <li>Expedientes: descripción del incidente, fecha, zona general, ubicación privada opcional y documentación de respaldo.</li>
          <li>Aportaciones: archivos, descripción, fecha y ubicación declaradas y nivel de certeza.</li>
          <li>Registros de auditoría: accesos, descargas, decisiones y exportaciones.</li>
        </ul>
        <h2 className="text-base font-semibold">Medidas aplicadas</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Minimización: las fichas públicas solo contienen datos generalizados autorizados.</li>
          <li>Seudonimización de colaboradores frente a revisores.</li>
          <li>Acceso por rol y por asignación; registro de cada descarga.</li>
          <li>Políticas configurables de conservación y eliminación.</li>
        </ul>
        <h2 className="text-base font-semibold">Derechos del titular</h2>
        <p>
          Desde <Link to="/cuenta" className="font-medium text-brand-700 hover:underline">Mi cuenta</Link> puede descargar sus datos y presentar solicitudes de acceso,
          rectificación, cancelación u oposición, que la administración atiende y registra.
        </p>
      </Card>
    </Container>
  );
}
