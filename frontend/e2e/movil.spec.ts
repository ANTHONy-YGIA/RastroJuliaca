import { expect, test, type Page } from "@playwright/test";
import { login } from "./helpers";

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("portada y menú en móvil", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await noHorizontalScroll(page);
  const menu = page.getByRole("button", { name: "Abrir menú" });
  await expect(menu).toBeVisible();
  await menu.click();
  await page.getByRole("navigation", { name: "Menú móvil" }).getByRole("link", { name: "Explorar expedientes" }).click();
  await expect(page).toHaveURL(/expedientes/);
  await expect(page.getByText(/RJ-\d{4}-\d{5}/).first()).toBeVisible();
  await noHorizontalScroll(page);
});

test("ficha pública y formulario de ingreso en móvil", async ({ page }) => {
  await page.goto("/expedientes");
  await page.getByText(/RJ-\d{4}-\d{5}/).first().click();
  await expect(page.getByText("Información no verificada por una autoridad")).toBeVisible();
  await noHorizontalScroll(page);
  await page.goto("/ingresar");
  await noHorizontalScroll(page);
});

test("panel del revisor y del denunciante en móvil", async ({ page }) => {
  await login(page, "revisor1@rastrojuliaca.test");
  await expect(page.getByText("Revisión de expedientes y evidencias")).toBeVisible();
  await noHorizontalScroll(page);
  await page.getByTestId("review-case-row").first().click();
  await expect(page.getByRole("tab", { name: /Evidencias/ })).toBeVisible();
  await noHorizontalScroll(page);
  await page.context().clearCookies();
  await login(page, "denunciante1@rastrojuliaca.test");
  await page.getByRole("link", { name: "Nuevo expediente" }).click();
  await expect(page.getByTestId("cat-robo-vehiculos")).toBeVisible();
  await noHorizontalScroll(page);
});
