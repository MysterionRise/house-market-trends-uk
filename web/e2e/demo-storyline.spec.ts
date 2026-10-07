import { type Page, expect, test } from "@playwright/test";

/**
 * The demo storyline (docs/demo.md), for rehearsals against `make demo` or
 * `make demo-offline`: LIX_DEMO=1 npx playwright test demo-storyline
 * Saves a screenshot per step to test-results/demo/.
 */
test.skip(!process.env.LIX_DEMO, "rehearsal only: set LIX_DEMO=1 with make demo running");
test.setTimeout(240_000);

const shots = "test-results/demo";

async function ask(page: Page, text: string) {
  const chat = page.getByTestId("copilot-chat");
  const input = page.getByTestId("chat").locator("textarea").first();
  await input.fill(text);
  await input.press("Enter");
  // The run starts (it can be brief when replaying) and then finishes
  await expect(chat).toHaveAttribute("data-copilot-running", "true", { timeout: 10_000 }).catch(() => {});
  await expect(chat).toHaveAttribute("data-copilot-running", "false", { timeout: 120_000 });
  await page.waitForTimeout(800);
}

async function shot(page: Page, name: string, card?: string) {
  if (card) await page.getByTestId(card).last().scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500); // let the map finish drawing
  await page.screenshot({ path: `${shots}/${name}.png` });
}

test("demo storyline", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("legend")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("onboarding")).toBeVisible();
  await shot(page, "01-open");

  await page.getByTestId("persona-family").click();
  await page.getByTestId("tab-weights").click();
  await page.getByTestId("weight-safety").fill("3");
  await shot(page, "02-03-weights");

  await page.getByTestId("tab-assistant").click();
  await ask(page, "We have two young kids and a budget of £350k. Where should we look around Leeds?");
  await expect(page.getByTestId("ranked-list")).toBeVisible();
  await shot(page, "04-family-leeds", "ranked-list");

  await page.getByTestId("ranked-list").locator("li button").first().click();
  await shot(page, "05-top-result");

  await ask(page, "Compare Far Headingley and Chapel Allerton");
  await expect(page.getByTestId("comparison").last()).toBeVisible();
  await shot(page, "06-compare", "comparison");

  await ask(page, "Show me well-run pubs near LS6 3AA");
  await expect(page.getByTestId("poi-list").last()).toBeVisible();
  await shot(page, "07-pubs", "poi-list");

  await ask(page, "Why does Manchester city centre score low on safety?");
  await expect(page.getByTestId("copilot-assistant-message").last()).toContainText(/estimat/i);
  await shot(page, "08-explain", "copilot-assistant-message");

  const search = page.getByTestId("search").locator("input");
  await search.fill("Hebden Bridge");
  await expect(page.getByRole("option").first()).toContainText("Hebden Bridge", { timeout: 15_000 });
  await search.press("Enter");
  await expect(page.getByTestId("theme-bars")).toBeVisible({ timeout: 30_000 });
  await shot(page, "09-hebden-bridge");

  await page.getByTestId("analyst-toggle").check();
  await page.getByTestId("tab-analyst").click();
  await expect(page.getByTestId("correlations")).toBeVisible();
  await shot(page, "10-analyst");

  await page.goto("/methodology/validation");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Face-validity review");
  await shot(page, "11-validation");
});
