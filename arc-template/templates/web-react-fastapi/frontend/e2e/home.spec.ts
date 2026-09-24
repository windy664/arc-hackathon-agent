import { expect, test } from "@playwright/test";


test("renders the starter website shell", async ({ page }) => {
  await page.route("**/api/modules", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "orders", name: "Orders", status: "ready" }]),
    });
  });

  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Generated Application" }),
  ).toBeVisible();
  await expect(page.getByText("Orders")).toBeVisible();
  await expect(page.getByText("Implementation Area")).toBeVisible();
});

