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
});
