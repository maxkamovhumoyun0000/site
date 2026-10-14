import { expect, test } from "@playwright/test";

test("home page renders", async ({ page }) => {
  const response = await page.goto("/");

  expect(response?.status()).toBe(200);
  await expect(page.locator("body")).toBeVisible();
  await expect(page.locator("body")).not.toBeEmpty();
});

test("public course page renders", async ({ page }) => {
  await page.route("**/api/public/courses**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  const response = await page.goto("/courses");

  expect(response?.status()).toBe(200);
  await expect(page.locator("body")).toBeVisible();
  await expect(page.locator("body")).not.toBeEmpty();
});
