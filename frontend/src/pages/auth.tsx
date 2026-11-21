import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FlaskConical, HandHeart, ClipboardList } from "lucide-react";
import { Logo } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Alert, Card, Field, Input } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api";
import { homeFor, useSession } from "@/lib/session";
import { cn } from "@/lib/format";

const DEMO = [
  { email: "denunciante1@rastrojuliaca.test", label: "Denunciante" },
  { email: "colaborador1@rastrojuliaca.test", label: "Colaborador" },
  { email: "revisor1@rastrojuliaca.test", label: "Revisor 1" },
  { email: "revisor2@rastrojuliaca.test", label: "Revisor 2" },
  { email: "admin@rastrojuliaca.test", label: "Administrador" },
];

const loginSchema = z.object({
  email: z.email("Correo no válido"),
  password: z.string().min(1, "Ingrese su contraseña"),
});

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col px-4 py-12">
      <div className="mb-6 flex justify-center"><Logo /></div>
      <Card className="p-6 sm:p-8 animate-fade-in">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </Card>
    </div>
  );
}

export function LoginPage() {
  const { login, meta } = useSession();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [err, setErr] = useState<string | null>(null);
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(loginSchema) });
  const onSubmit = handleSubmit(async (v) => {
    setErr(null);
    try {
      const u = await login(v.email, v.password);
      const next = params.get("next");
      nav(next && next.startsWith("/") && !next.startsWith("//") ? next : homeFor(u), { replace: true });
    } catch (e) {
      setErr(errorMessage(e));
    }
  });
  return (
    <AuthFrame title="Ingresar" subtitle="Acceda a sus expedientes, aportaciones o panel de trabajo.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="Correo electrónico" htmlFor="email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...register("email")} aria-invalid={!!errors.email || undefined} />
        </Field>
        <Field label="Contraseña" htmlFor="password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" {...register("password")} aria-invalid={!!errors.password || undefined} />
        </Field>
        <Button type="submit" className="w-full" loading={isSubmitting}>Ingresar</Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        ¿No tiene cuenta? <Link to="/registro" className="font-medium text-brand-700 hover:underline">Regístrese</Link>
      </p>
      {meta?.demo_mode && (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-900"><FlaskConical className="size-3.5" />Cuentas ficticias de demostración</p>
          <p className="mt-1 text-xs text-amber-800">Contraseña común: <code className="font-mono">Demo-Juliaca-2026</code></p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {DEMO.map((d) => (
              <button key={d.email} type="button" className="rounded-md border border-amber-300 bg-white px-2 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
                onClick={() => { setValue("email", d.email); setValue("password", "Demo-Juliaca-2026"); }}>
                {d.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </AuthFrame>
  );
}

const registerSchema = z
  .object({
    full_name: z.string().trim().min(3, "Mínimo 3 caracteres").max(120),
    email: z.email("Correo no válido"),
    password: z.string().min(10, "Mínimo 10 caracteres").regex(/[A-Za-z]/, "Incluya al menos una letra").regex(/\d/, "Incluya al menos un número"),
    confirm: z.string(),
    role: z.enum(["DENUNCIANTE", "COLABORADOR"]),
    accept_terms: z.literal(true, { error: "Debe aceptar el aviso de privacidad" }),
  })
  .refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden" });

export function RegisterPage() {
  const { register: signup } = useSession();
  const nav = useNavigate();
  const [err, setErr] = useState<string | null>(null);
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: "DENUNCIANTE" as const },
  });
  const role = watch("role");
  const onSubmit = handleSubmit(async (v) => {
    setErr(null);
    try {
      const u = await signup({ email: v.email, full_name: v.full_name, password: v.password, role: v.role, accept_terms: true });
      nav(homeFor(u), { replace: true });
    } catch (e) {
      setErr(errorMessage(e));
    }
  });
  return (
    <AuthFrame title="Crear cuenta" subtitle="Las cuentas de revisores y administradores se crean por la administración.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {err && <Alert kind="error">{err}</Alert>}
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">¿Cómo participará?</legend>
          <div className="grid grid-cols-2 gap-2">
            {([
              { v: "DENUNCIANTE", t: "Denunciante", d: "Registro incidentes", i: ClipboardList },
              { v: "COLABORADOR", t: "Colaborador", d: "Aporto evidencias", i: HandHeart },
            ] as const).map((o) => (
              <button key={o.v} type="button" aria-pressed={role === o.v} onClick={() => setValue("role", o.v)}
                className={cn("rounded-lg border p-3 text-left transition", role === o.v ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/20" : "border-slate-200 hover:border-slate-300")}>
                <o.i className="size-5 text-navy-700" aria-hidden="true" />
                <p className="mt-1 text-sm font-semibold">{o.t}</p>
                <p className="text-xs text-slate-500">{o.d}</p>
              </button>
            ))}
          </div>
        </fieldset>
        <Field label="Nombre completo" htmlFor="full_name" error={errors.full_name?.message}>
          <Input id="full_name" autoComplete="name" {...register("full_name")} />
        </Field>
        <Field label="Correo electrónico" htmlFor="email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
        </Field>
        <Field label="Contraseña" htmlFor="password" error={errors.password?.message} help="Mínimo 10 caracteres, con letras y números.">
          <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
        </Field>
        <Field label="Confirmar contraseña" htmlFor="confirm" error={errors.confirm?.message}>
          <Input id="confirm" type="password" autoComplete="new-password" {...register("confirm")} />
        </Field>
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" {...register("accept_terms")} />
          <span>He leído el <Link to="/privacidad" className="font-medium text-brand-700 hover:underline" target="_blank">aviso de privacidad</Link> y entiendo que RastroJuliaca no reemplaza a la Policía Nacional del Perú.</span>
        </label>
        {errors.accept_terms && <p className="text-xs font-medium text-red-600" role="alert">{errors.accept_terms.message}</p>}
        <Button type="submit" variant="brand" className="w-full" loading={isSubmitting}>Crear cuenta</Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        ¿Ya tiene cuenta? <Link to="/ingresar" className="font-medium text-brand-700 hover:underline">Ingrese</Link>
      </p>
    </AuthFrame>
  );
}
