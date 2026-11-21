import { expect, test } from "@playwright/test";
import { login, logout, register, reloadUntil, syntheticPng } from "./helpers";

/**
 * Recorrido completo del MVP (puntos 1–13 del objetivo):
 * registro → expediente → documentación → revisión → publicación → aportación → validación →
 * clasificación → ordenamiento/línea de tiempo → informe exportable.
 */
test("recorrido completo del MVP", async ({ page }) => {
  const stamp = Date.now();
  const password = "Prueba-E2E-2026";
  const reporterEmail = `denunciante.e2e.${stamp}@rastrojuliaca.test`;

  // 1–4. Ciudadano se registra, crea expediente, adjunta documentación y lo envía (privado y pendiente)
  await register(page, "Denunciante E2E", reporterEmail, "Denunciante", password);
  await expect(page).toHaveURL(/mis-expedientes/);
  await page.getByRole("link", { name: "Nuevo expediente" }).click();
  await page.getByTestId("cat-objetos-extraviados").click();
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Título breve").fill("Mochila verde extraviada en paradero");
  await page.getByLabel("Descripción objetiva").fill("Se extravió una mochila verde con cuadernos en un paradero de la Zona Sur. Caso ficticio E2E.");
  await page.getByLabel("Fecha y hora del incidente").fill("2026-11-15T10:30");
  await page.getByLabel("Zona general").selectOption("Zona Sur");
  await page.getByRole("button", { name: "Continuar" }).click();
  // Campos específicos dinámicos: validación en frontend
  await page.getByRole("button", { name: "Continuar" }).click();
  await expect(page.getByText("Seleccione una opción").first()).toBeVisible();
  await page.getByLabel("Tipo de objeto").selectOption("Mochila o bolso");
  await page.getByLabel("Características del objeto").fill("Mochila verde con parche de alpaca");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Latitud").fill("-15.5100");
  await page.getByLabel("Longitud").fill("-70.1300");
  await page.getByLabel("Referencia privada").fill("Paradero ficticio secreto");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Crear expediente" }).click();
  await expect(page.getByText("Borrador").first()).toBeVisible();
  const code = (await page.locator("text=/RJ-\\d{4}-\\d{5}/").first().innerText()).match(/RJ-\d{4}-\d{5}/)![0];

  // Envío sin documentación: el backend exige la política de la categoría
  await page.getByRole("button", { name: "Enviar a revisión" }).click();
  await expect(page.getByText(/Documentación insuficiente/)).toBeVisible();
  await page.getByLabel("Tipo de documento").selectOption("FOTOGRAFIA_RESPALDO");
  await page.locator("#doc_file").setInputFiles({ name: "foto-objeto.png", mimeType: "image/png", buffer: syntheticPng(1) });
  await page.getByRole("button", { name: "Adjuntar" }).click();
  await expect(page.getByText(/Documento recibido/)).toBeVisible();
  await page.getByRole("button", { name: "Enviar a revisión" }).click();
  await expect(page.getByText(/enviado a revisión/i).first()).toBeVisible();
  await expect(page.getByText("Pendiente de revisión").first()).toBeVisible();

  // El expediente es privado: no aparece en el explorador público
  await logout(page);
  const priv = await page.request.get(`/api/public/cases/${code}`);
  expect(priv.status()).toBe(404);

  // 5–7. Revisor examina la documentación, aprueba y publica ficha generalizada
  await login(page, "revisor2@rastrojuliaca.test");
  await page.goto("/revisor");
  await page.getByTestId("review-case-row").filter({ hasText: code }).click();
  await reloadUntil(page, "Validado");
  await page.getByRole("button", { name: "Aceptar" }).click();
  await expect(page.getByText("Aceptado").first()).toBeVisible();
  await page.getByLabel("Acción").selectOption("APROBAR");
  await page.getByLabel("Motivo (obligatorio)").fill("Fotografía de respaldo coherente con lo declarado.");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByText("Aprobado").first()).toBeVisible();
  await page.getByRole("tab", { name: "Publicación" }).click();
  await page.getByLabel("Título público").fill("Mochila verde extraviada en la Zona Sur");
  await page.getByLabel("Resumen público").fill("Se busca información sobre una mochila verde extraviada en un paradero de la Zona Sur.");
  await page.getByRole("checkbox", { name: /Tipo de objeto/ }).check();
  await page.getByRole("button", { name: "Publicar ficha" }).click();
  await expect(page.getByText("Ficha vigente")).toBeVisible();
  await page.getByRole("button", { name: "Habilitar aportaciones" }).click();
  await expect(page.getByText("Abiertas")).toBeVisible();

  // La ficha pública muestra solo datos autorizados
  await logout(page);
  await page.goto(`/expedientes/${code}`);
  await expect(page.getByRole("heading", { name: "Mochila verde extraviada en la Zona Sur" })).toBeVisible();
  await expect(page.getByText("Mochila o bolso")).toBeVisible();
  await expect(page.getByText("Paradero ficticio secreto")).toHaveCount(0);
  await expect(page.getByText("parche de alpaca")).toHaveCount(0);

  // 8–9. Otro ciudadano aporta una fotografía; queda privada y en validación
  await register(page, "Colaborador E2E", `colaborador.e2e.${stamp}@rastrojuliaca.test`, "Colaborador", password);
  await page.goto(`/expedientes/${code}`);
  await page.getByRole("link", { name: "Aportar información" }).click();
  await page.locator("#file").setInputFiles({ name: "registro.png", mimeType: "image/png", buffer: syntheticPng(2) });
  await page.getByLabel("Descripción de lo que aporta").fill("Vi a una persona con una mochila verde subir a un colectivo.");
  await page.getByLabel("Fecha y hora del registro").fill("2026-11-15T10:50");
  await page.getByLabel("Nivel de certeza").selectOption("MEDIA");
  await page.getByLabel("Latitud").fill("-15.5110");
  await page.getByLabel("Longitud").fill("-70.1310");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Enviar aportación" }).click();
  const contribCode = await page.getByTestId("contribution-code").innerText();
  expect(contribCode).toMatch(/AP-\d{4}-\d{5}/);
  await page.goto("/mis-aportaciones");
  await expect(page.getByText(contribCode)).toBeVisible();

  // 10–12. Revisor examina, clasifica y ordena por proximidad; línea de tiempo
  await logout(page);
  await login(page, "revisor2@rastrojuliaca.test");
  await page.goto("/revisor");
  await page.getByTestId("review-case-row").filter({ hasText: code }).click();
  await page.getByRole("tab", { name: /Evidencias/ }).click();
  await page.getByTestId("evidence-row").filter({ hasText: contribCode }).click();
  await reloadUntil(page, "Validado");
  await expect(page.getByText(/COL-/).first()).toBeVisible(); // seudónimo, no identidad
  await expect(page.getByText("Colaborador E2E")).toHaveCount(0);
  await page.getByRole("radio", { name: "Relevante", exact: true }).check();
  await page.getByLabel("Observación (obligatoria)").fill("Coincide la descripción del objeto y la hora es cercana.");
  await page.getByRole("button", { name: "Registrar clasificación" }).click();
  await expect(page.getByText("Clasificada").first()).toBeVisible();
  await page.getByRole("link", { name: /Evidencias de/ }).click();
  await expect(page.getByTestId("evidence-row").filter({ hasText: contribCode })).toContainText(/m|km/);
  await page.getByRole("tab", { name: "Línea de tiempo" }).click();
  await expect(page.getByTestId("timeline-item").filter({ hasText: contribCode })).toBeVisible();
  await expect(page.getByText(/no constituyen hechos comprobados/)).toBeVisible();

  // 13. Informe exportable (JSON) con registro de exportación
  await page.getByRole("tab", { name: "Informes" }).click();
  await page.getByLabel("Resumen del revisor").fill("Se identificó una aportación relevante con hora y ubicación cercanas a lo declarado.");
  await page.getByRole("button", { name: "Generar informe" }).click();
  await expect(page).toHaveURL(/revisor\/informes\/\d+/);
  await expect(page.getByTestId("report-evidence").filter({ hasText: contribCode })).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar JSON" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^IN-\d{4}-\d{5}\.json$/);
  await expect(page.getByText(/1 exportación/)).toBeVisible();
});

test("aislamiento: un revisor no accede a expedientes no asignados", async ({ page }) => {
  await login(page, "revisor2@rastrojuliaca.test");
  // RJ-…-00008 es INSTITUCIONAL y está asignado solo a revisor1
  const r = await page.request.get("/api/review/cases/8");
  expect(r.status()).toBe(404);
  await page.goto("/revisor/expedientes/8");
  await expect(page.getByText("Expediente no disponible")).toBeVisible();
});

test("roles: un colaborador no entra al panel del revisor ni a administración", async ({ page }) => {
  await login(page, "colaborador1@rastrojuliaca.test");
  await page.goto("/revisor");
  await expect(page.getByText("Acceso no autorizado")).toBeVisible();
  expect((await page.request.get("/api/admin/overview")).status()).toBe(403);
});

test("persistencia: los datos sembrados siguen disponibles en la API", async ({ request }) => {
  const r = await request.get("/api/public/cases");
  expect(r.ok()).toBeTruthy();
  expect((await r.json()).length).toBeGreaterThanOrEqual(2);
});
