# Przeniesienie danych pacjenta — Transfer browser extension

Manifest V3 extension that transfers the five Patient Metadata fields
(Badany narząd, Imię i nazwisko, Wiek, PESEL, Opis badania) from the
recording app (`/record-description`) into the form on an open Target Page
(a third-party medical system we do not control). The Transfer only fills
the fields — it **never submits the Target Page form**; a human reviews and
saves there.

Domain terms: `GLOSSARY.md`. Design decisions: `docs/adr/0001`, `docs/adr/0002`.

## How it works

1. The app's **Przenieś do formularza** button broadcasts a versioned
   `transfer-request` over `window.postMessage` on the `rx-transfer` channel
   (`docs/adr/0002`).
2. The app-page content script relays it to the background service worker.
3. The background finds the single open tab matching the active
   **Transfer Profile**'s URL pattern (zero or multiple matches is an error),
   tells the target-page content script to resolve the **Field Mapping**
   (CSS selector candidates, then visible label text) and fill each control
   in a framework-safe way (native value setter + `input`/`change` events).
4. A value-free **Transfer Report** (per-field `filled` / `not_found` /
   `failed`) is routed back to the app tab as a `transfer-result` and shown
   as a Polish toast. The last 20 reports are kept for the options page —
   **transferred values (PESEL, transcript text) are never logged**.

## Install from source

No store publishing is needed.

```
cd extension
bun install
bun run build        # produces dist/ (background + content scripts + options)
```

Then load the unpacked extension:

- **Chrome / Brave / Edge:** open `chrome://extensions`, enable
  *Developer mode*, click *Load unpacked* and select the `extension/`
  directory (the one containing `manifest.json`).
- **Firefox (temporary add-on):** open `about:debugging#/runtime/this-firefox`,
  *Load Temporary Add-on…*, select `extension/manifest.json`.
  Re-load after each browser restart.

The app side (`app/`) requires no changes beyond the Recorder page itself —
the button and result toasts ship inside `app/`.

## Configuration (options page)

Open the extension's *Details → Options* UI:

- **Transfer Profiles:** each is `{ name, urlPattern, appUrlPattern, Field Mapping }`.
  Exactly one profile is active. The built-in **Mock** profile targets
  `http://localhost:3011/*` for development and accepts requests from the app
  at `http://localhost:3010/*` (`appUrlPattern` gates which pages may
  **initiate** a Transfer — a request from any other page is refused).
- **Per-field mapping:** candidate CSS selectors (one per line, tried in
  order) plus a label-text fallback (diacritics/case-insensitive), which
  usually covers third-party forms whose element IDs are brittle.
- **JSON import/export** of the whole configuration.
- **Historia Przeniesień:** last 20 Transfer Reports (statuses only).

## Development

```
bun run mock      # Mock Target Page on http://localhost:3011 (/, /controlled.html)
bun test          # unit tests (mapping-resolver, form-filler, report-builder)
bun run typecheck # tsc --noEmit
bun run test:e2e  # Playwright: real app + loaded extension + mock pages
```

`bun run test:e2e` rebuilds the extension automatically and starts the app
dev server (`localhost:3010`) if not already running.

## Dev → production cutover checklist

- [ ] Learn the real Target Page URL; create a production Transfer Profile
      (name, `urlPattern`, per-field selectors/labels) in the options page —
      or import its JSON. Keep or remove the Mock profile as needed.
- [ ] **Narrow `host_permissions` and `content_scripts.matches` in
      `manifest.json` to the concrete app + Target Page origins.** The broad
      `http://*/*`, `https://*/*` grant is a *deliberate temporary* decision
      while the Target Page URL is unknown — see `docs/adr/0001` (includes a
      pending-action note).
- [ ] Reload the unpacked extension and run one dry Transfer; check the
      options-page history for `not_found` fields and adjust the mapping.

## Guarantees / non-goals

- A Transfer **never** submits a form, clicks `Zapisz`, or touches buttons on
  the Target Page.
- Reports never contain transferred values (error details are value-free by
  construction and unit-tested).
- Only pages matching the active profile's `appUrlPattern` can initiate a
  Transfer; requests from any other origin are refused.
- If the Target Page tab is missing, ambiguous, or unresponsive (5 s), the
  app shows a Polish error toast and fills nothing.
- The real third-party page must be configured manually (Field Mapping);
  this repo intentionally ships only the Mock Target Page.
