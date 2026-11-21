import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));

/** Intérprete del backend: RJ_PYTHON (lo define scripts/test.ps1) o el primer entorno que realmente se ejecute. */
function findPython(): string {
  if (process.env.RJ_PYTHON) return process.env.RJ_PYTHON;
  for (const name of [".venv", ".venv_alt", ".venv-rj"]) {
    const candidate = path.resolve(here, "../backend", name, "Scripts/python.exe");
    if (!existsSync(candidate)) continue;
    const r = spawnSync(candidate, ["-c", "import fastapi, uvicorn"], { stdio: "ignore" });
    if (r.status === 0) return candidate;
  }
  throw new Error("No se encontró un entorno Python funcional en backend/. Ejecute scripts/setup.ps1 o defina RJ_PYTHON.");
}

const python = findPython();
const server = path.resolve(here, "../backend/e2e_server.py");

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "../docs/evidencias/playwright-results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:8001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "es-PE",
    timezoneId: "America/Lima",
  },
  projects: [
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 } }, testIgnore: /movil/ },
    { name: "movil", use: { ...devices["Pixel 7"] }, testMatch: /movil/ },
  ],
  webServer: {
    command: `"${python}" "${server}"`,
    url: "http://127.0.0.1:8001/api/health",
    timeout: 180_000,
    reuseExistingServer: false,
  },
});
