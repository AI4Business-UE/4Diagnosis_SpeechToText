# App and extension communicate via a versioned window.postMessage channel

The extension obtains Patient Metadata from our app page through an explicit, versioned `postMessage` contract: the app broadcasts a `transfer-request` on the `rx-transfer` channel when the user clicks "Przenieś do formularza", and the extension answers on the same channel with a `transfer-result` carrying the Transfer Report. Both sides ship together; app and extension versions can otherwise evolve independently, and an unknown `version` is surfaced as an error rather than guessed at.

We rejected the alternatives: DOM scraping by the content script (silently breaks on UI refactors, fights React-controlled inputs) and re-enabling the localStorage `selectedPatient` writes (the mechanism the team deliberately parked, and only as fresh as the last field change). The contract is duplicated in types in `extension/src/shared/` and documented in both READMEs rather than extracted into a shared package.

## Consequences

- An app build without this code has no Transfer feature at all — no degraded fallback. Acceptable while app and extension ship together.
- The `Zapisz` button is deliberately renamed: it does not save and does not submit the Target Page form; it initiates a Transfer only.
