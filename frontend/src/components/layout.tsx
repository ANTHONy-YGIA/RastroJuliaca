import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { Bell, FlaskConical, LogOut, Menu, ShieldCheck, UserRound, X } from "lucide-react";
import { useSession, homeFor } from "@/lib/session";
import { cn, ROLE_LABEL } from "@/lib/format";
import type { Role } from "@/lib/types";
import { Button } from "./ui/button";
import { Spinner } from "./ui/primitives";

const NAV: Record<Role | "PUBLIC", { to: string; label: string }[]> = {
  PUBLIC: [
    { to: "/", label: "Inicio" },
    { to: "/expedientes", label: "Explorar expedientes" },
    { to: "/privacidad", label: "Privacidad" },
  ],
  DENUNCIANTE: [
    { to: "/expedientes", label: "Explorar" },
    { to: "/mis-expedientes", label: "Mis expedientes" },
    { to: "/mis-aportaciones", label: "Mis aportaciones" },
  ],
  COLABORADOR: [
    { to: "/expedientes", label: "Explorar" },
    { to: "/mis-aportaciones", label: "Mis aportaciones" },
  ],
  REVISOR: [
    { to: "/revisor", label: "Panel de revisión" },
    { to: "/revisor/informes", label: "Informes" },
  ],
  ADMIN: [{ to: "/admin", label: "Administración" }],
};

export function Logo({ light }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg viewBox="0 0 64 64" className="size-8 shrink-0" aria-hidden="true">
        <rect width="64" height="64" rx="14" fill={light ? "#ffffff1a" : "#0B2545"} />
        <path d="M18 44V20h14a8 8 0 0 1 0 16h-6l10 8" fill="none" stroke="#2DD4BF" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="46" cy="20" r="4" fill="#2DD4BF" />
      </svg>
      <span className={cn("text-lg font-bold tracking-tight", light ? "text-white" : "text-navy-900")}>
        Rastro<span className="text-brand-500">Juliaca</span>
      </span>
    </span>
  );
}

export function DemoBanner() {
  const { meta } = useSession();
  if (!meta?.demo_mode) return null;
  return (
    <div className="no-print bg-amber-400 px-4 py-1.5 text-center text-xs font-semibold text-amber-950" role="note">
      <FlaskConical className="mr-1 inline size-3.5" aria-hidden="true" />
      MODO DEMOSTRACIÓN — Todos los datos son ficticios. No registre incidentes reales.
    </div>
  );
}

export function AppShell() {
  const { user, unread, logout } = useSession();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  useEffect(() => setOpen(false), [loc.pathname]);
  const links = NAV[user?.role ?? "PUBLIC"];

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Saltar al contenido
      </a>
      <DemoBanner />
      <header className="no-print sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <Link to={user ? homeFor(user) : "/"} aria-label="RastroJuliaca, inicio"><Logo /></Link>
          <nav className="ml-6 hidden items-center gap-1 lg:flex" aria-label="Principal">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.to === "/" || l.to === "/revisor"}
                className={({ isActive }) => cn("whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition", isActive ? "bg-navy-50 text-navy-900" : "text-slate-600 hover:text-navy-900")}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <>
                <Link to="/cuenta" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label={`Notificaciones: ${unread} sin leer`}>
                  <Bell className="size-5" />
                  {unread > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex min-w-5 items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-bold text-white" data-testid="unread-count">
                      {unread > 99 ? "99+" : unread}
                    </span>
                  )}
                </Link>
                <Link to="/cuenta" className="hidden items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 sm:flex">
                  <span className="flex size-8 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white">
                    {user.full_name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden text-left leading-tight lg:block">
                    <span className="block max-w-40 truncate text-sm font-medium text-navy-900">{user.full_name}</span>
                    <span className="block text-xs text-slate-500">{ROLE_LABEL[user.role]}</span>
                  </span>
                </Link>
                <Button variant="ghost" size="icon" aria-label="Cerrar sesión" className="hidden lg:inline-flex" onClick={async () => { await logout(); nav("/"); }}>
                  <LogOut />
                </Button>
              </>
            ) : (
              <div className="hidden gap-2 sm:flex">
                <Button variant="ghost" asChild><Link to="/ingresar">Ingresar</Link></Button>
                <Button variant="brand" asChild><Link to="/registro">Crear cuenta</Link></Button>
              </div>
            )}
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label={open ? "Cerrar menú" : "Abrir menú"} aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? <X /> : <Menu />}
            </Button>
          </div>
        </div>
        {open && (
          <nav className="border-t border-slate-200 bg-white px-4 py-3 lg:hidden animate-fade-in" aria-label="Menú móvil">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end className={({ isActive }) => cn("block rounded-lg px-3 py-2.5 text-sm font-medium", isActive ? "bg-navy-50 text-navy-900" : "text-slate-700")}>
                {l.label}
              </NavLink>
            ))}
            {user ? (
              <>
                <NavLink to="/cuenta" className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-700">Mi cuenta</NavLink>
                <button className="block w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium text-red-700" onClick={async () => { await logout(); nav("/"); }}>
                  Cerrar sesión
                </button>
              </>
            ) : (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button variant="outline" asChild><Link to="/ingresar">Ingresar</Link></Button>
                <Button variant="brand" asChild><Link to="/registro">Crear cuenta</Link></Button>
              </div>
            )}
          </nav>
        )}
      </header>
      <main id="contenido" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

function Footer() {
  const { meta } = useSession();
  return (
    <footer className="no-print mt-16 border-t border-slate-200 bg-white">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 text-sm text-slate-500 sm:px-6 md:grid-cols-3">
        <div className="space-y-2">
          <Logo />
          <p>Sistema colaborativo de gestión y revisión de evidencias digitales para incidentes ciudadanos. Juliaca, Puno, Perú.</p>
        </div>
        <p className="md:col-span-2 flex gap-2 leading-relaxed">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden="true" />
          <span>
            {meta?.disclaimer ?? "RastroJuliaca no reemplaza a la Policía Nacional del Perú."} Prototipo académico: no está autorizado para procesar incidentes reales.{" "}
            <Link to="/privacidad" className="font-medium text-brand-700 hover:underline">Aviso de privacidad</Link>
          </span>
        </p>
      </div>
    </footer>
  );
}

export function RequireRole({ roles, children }: { roles: Role[]; children?: ReactNode }) {
  const { user, loading } = useSession();
  const loc = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to={`/ingresar?next=${encodeURIComponent(loc.pathname)}`} replace />;
  if (!roles.includes(user.role))
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <UserRound className="mx-auto mb-3 size-10 text-slate-400" />
        <h1 className="text-xl font-semibold">Acceso no autorizado</h1>
        <p className="mt-2 text-sm text-slate-600">Su rol ({ROLE_LABEL[user.role]}) no tiene permiso para esta sección.</p>
        <Button className="mt-4" asChild><Link to={homeFor(user)}>Ir a mi panel</Link></Button>
      </div>
    );
  return <>{children ?? <Outlet />}</>;
}

export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto max-w-7xl px-4 py-8 sm:px-6", className)}>{children}</div>;
}
