import { z } from "zod";
import type { FieldDef } from "./types";

/**
 * Construye un esquema Zod a partir de la definición de campos de la categoría.
 * Es la misma definición que valida el backend (validación en ambas capas).
 */
export function buildFieldsSchema(fields: FieldDef[]) {
  const shape: Record<string, z.ZodType> = {};
  for (const f of fields) {
    let s: z.ZodType;
    switch (f.type) {
      case "number": {
        let n = z.coerce.number({ error: "Debe ser numérico" });
        if (f.min !== undefined) n = n.min(f.min, `Mínimo ${f.min}`);
        if (f.max !== undefined) n = n.max(f.max, `Máximo ${f.max}`);
        s = f.required
          ? z.preprocess((v) => (v === "" || v === null ? undefined : v), n)
          : z.preprocess((v) => (v === "" || v === null ? undefined : v), n.optional());
        break;
      }
      case "boolean":
        s = z.boolean().optional();
        break;
      case "select": {
        const opts = (f.options ?? []) as [string, ...string[]];
        const e = z.enum(opts, { error: "Seleccione una opción" });
        s = f.required ? e : z.preprocess((v) => (v === "" ? undefined : v), e.optional());
        break;
      }
      case "date": {
        const d = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Fecha no válida");
        s = f.required ? d : z.preprocess((v) => (v === "" ? undefined : v), d.optional());
        break;
      }
      default: {
        let t = z.string().trim().max(f.max_length ?? (f.type === "textarea" ? 2000 : 200), "Texto demasiado largo");
        if (f.pattern) t = t.regex(new RegExp(`^(?:${f.pattern.replace(/^\^|\$$/g, "")})$`), "Formato no válido");
        s = f.required ? t.min(1, "Campo obligatorio") : z.preprocess((v) => (v === "" ? undefined : v), t.optional());
      }
    }
    shape[f.key] = s;
  }
  return z.object(shape);
}

/** Elimina valores vacíos antes de enviar al backend. */
export function cleanFields(values: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(values)) {
    if (v === "" || v === undefined || v === null || (typeof v === "number" && Number.isNaN(v))) continue;
    out[k] = v;
  }
  return out;
}
