import {
  expect,
  test,
  chromium,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EXTENSION_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const APP_URL = "http://localhost:3010/record-description";
const MOCK_URL = "http://localhost:3011/";
const MOCK_CONTROLLED_URL = "http://localhost:3011/controlled.html";

const PATIENT = {
  organ: "Wątroba",
  name: "Jan Kowalski",
  age: "45",
  pesel: "75010101234",
  description: "Biópsja gruboigłowa, rozpoznanie: stłuszczenie.",
};

async function launchContext(): Promise<BrowserContext> {
  return chromium.launchPersistentContext("", {
    // Extensions require full Chromium; Playwright's default headless uses headless shell.
    channel: "chromium",
    args: [
      `--disable-extensions-except=${EXTENSION_ROOT}`,
      `--load-extension=${EXTENSION_ROOT}`,
    ],
  });
}

async function openAppTab(context: BrowserContext): Promise<Page> {
  const app = await context.newPage();
  await app.goto(APP_URL);
  await app.getByPlaceholder("Imię i nazwisko pacjenta").waitFor();

  await app.getByPlaceholder("Nazwa narządu").fill(PATIENT.organ);
  await app.getByPlaceholder("Imię i nazwisko pacjenta").fill(PATIENT.name);
  await app.getByPlaceholder("Wiek").fill(PATIENT.age);
  await app.getByPlaceholder("PESEL").fill(PATIENT.pesel);
  await app.getByPlaceholder(/^Transkrypcja pojawi się/).fill(PATIENT.description);
  return app;
}

function transferButton(app: Page) {
  return app.getByRole("button", { name: "Przenieś do formularza" });
}

test.describe("Transfer to Mock Target Page", () => {
  let context: BrowserContext;

  test.beforeEach(async () => {
    context = await launchContext();
  });

  test.afterEach(async () => {
    await context.close();
  });

  test("fills the plain target form and never submits it", async () => {
    const app = await openAppTab(context);
    const mock = await context.newPage();
    await mock.goto(MOCK_URL);

    await transferButton(app).click();

    await expect(app.getByText("Przeniesiono dane do formularza (5/5)")).toBeVisible({
      timeout: 15_000,
    });

    await expect(mock.locator("#field-organ")).toHaveValue(PATIENT.organ);
    await expect(mock.locator("#field-name")).toHaveValue(PATIENT.name);
    await expect(mock.locator("#field-age")).toHaveValue(PATIENT.age);
    await expect(mock.locator("#field-pesel")).toHaveValue(PATIENT.pesel);
    await expect(mock.locator("#field-description")).toHaveValue(PATIENT.description);

    // The transfer never presses the target page's Zapisz / submits the form.
    await expect(mock.locator("#submit-marker")).toBeHidden();
    expect(mock.url()).toBe(MOCK_URL);
  });

  test("fills a JS-controlled form so framework state stays in sync", async () => {
    const app = await openAppTab(context);
    const mock = await context.newPage();
    await mock.goto(MOCK_CONTROLLED_URL);

    await transferButton(app).click();

    await expect(app.getByText("Przeniesiono dane do formularza (5/5)")).toBeVisible({
      timeout: 15_000,
    });

    const debug = mock.locator("#state-debug");
    await expect(debug).toContainText(PATIENT.organ);
    await expect(debug).toContainText(PATIENT.name);
    await expect(debug).toContainText(PATIENT.pesel);
    await expect(mock.locator("#field-description")).toHaveValue(PATIENT.description);
    await expect(mock.locator("#submit-marker")).toBeHidden();
  });

  test("reports an error toast when the target page is not open", async () => {
    const app = await openAppTab(context);

    await transferButton(app).click();

    await expect(app.getByText(/Strona docelowa nie jest otwarta/)).toBeVisible({
      timeout: 15_000,
    });
    await expect(transferButton(app)).toBeEnabled();
  });

  test("refuses to guess when several target tabs match", async () => {
    const app = await openAppTab(context);
    const mockA = await context.newPage();
    await mockA.goto(MOCK_URL);
    const mockB = await context.newPage();
    await mockB.goto(MOCK_CONTROLLED_URL);

    await transferButton(app).click();

    await expect(app.getByText(/wiele kart strony docelowej/)).toBeVisible({
      timeout: 15_000,
    });
    await expect(mockA.locator("#field-organ")).toHaveValue("");
  });

  test("reports a Polish error when the target tab stops answering (5 s timeout)", async () => {
    const app = await openAppTab(context);
    const mock = await context.newPage();
    await mock.goto(MOCK_URL);

    // Freeze the target page's main thread (isolated content scripts stall with it).
    // Keep the busy loop close to the 5 s transfer timeout so teardown isn't blocked on it;
    // the "never submits" assertion lives in the fill tests, which can actually read the page.
    mock
      .evaluate(() => {
        const end = Date.now() + 8_000;
        while (Date.now() < end) {
          // busy block
        }
      })
      .catch(() => {}); // never resolves; discarded with the context

    await transferButton(app).click();

    await expect(app.getByText(/Strona docelowa nie odpowiada/)).toBeVisible({
      timeout: 15_000,
    });
  });

  test("ignores a transfer requested by a page outside the profile's app URL pattern", async () => {
    await context.route("http://localhost:3012/*", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: "<html><body>Obca strona</body></html>",
      }),
    );

    const target = await context.newPage();
    await target.goto(MOCK_URL);

    const outsider = await context.newPage();
    await outsider.goto("http://localhost:3012/evil");
    await outsider.evaluate(() => {
      window.postMessage(
        {
          channel: "rx-transfer",
          version: 1,
          type: "transfer-request",
          transferId: "outsider-1",
          metadata: { organ: "Sfałszowane", name: "x", age: "1", pesel: "2", description: "y" },
        },
        window.location.origin,
      );
    });

    // No request is ever made against the target form and nothing is filled.
    await expect(target.locator("#field-organ")).toHaveValue("", { timeout: 3_000 });
  });
});
