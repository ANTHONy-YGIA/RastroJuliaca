import { expect, type Page } from "@playwright/test";
import { deflateSync } from "node:zlib";

/** PNG sintético válido (generado en memoria, sin contenido real). */
export function syntheticPng(seed: number, w = 32, h = 24): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc32 = (b: Buffer) => {
    let c = 0xffffffff;
    for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    for (let x = 0; x < w; x++) {
      const o = y * (w * 3 + 1) + 1 + x * 3;
      raw[o] = (seed * 40 + x * 4) % 256; raw[o + 1] = (y * 8) % 256; raw[o + 2] = (seed * 90) % 256;
    }
  }
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

export const DEMO_PASSWORD = "Demo-Juliaca-2026";

export async function login(page: Page, email: string, password = DEMO_PASSWORD) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

export async function logout(page: Page) {
  await page.context().clearCookies();
}

export async function register(page: Page, name: string, email: string, role: "Denunciante" | "Colaborador", password: string) {
  await page.goto("/registro");
  await page.getByRole("button", { name: new RegExp(role) }).click();
  await page.getByLabel("Nombre completo").fill(name);
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByLabel("Confirmar contraseña").fill(password);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Crear cuenta" }).last().click();
  await expect(page).not.toHaveURL(/registro/);
}

/** Recarga hasta que aparezca el texto (p. ej. tras el análisis antivirus en segundo plano). */
export async function reloadUntil(page: Page, text: string | RegExp, tries = 20) {
  for (let i = 0; i < tries; i++) {
    if (await page.getByText(text).first().isVisible().catch(() => false)) return;
    await page.waitForTimeout(1500);
    await page.reload();
  }
  await expect(page.getByText(text).first()).toBeVisible();
}
