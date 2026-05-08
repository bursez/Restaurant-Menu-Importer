import { expect, test } from "@playwright/test";

test("renders the import workspace and can reach backend-backed data", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Restaurant Menu Importer" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Pasted text" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create import" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
});
