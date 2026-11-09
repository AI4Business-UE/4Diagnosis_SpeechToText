# Broad host permissions as a temporary gate for the unknown Target Page

The Transfer extension needs its content script injected into both our app page and a third-party Target Page whose production URL is not yet known. We decided to declare broad host permissions (`http://*/*`, `https://*/*`) in the manifest and let the runtime Field Mapping configuration act as the real gate for which page participates in a Transfer.

This is **deliberate but temporary**. Because Patient Metadata contains PESEL and health data, broad-grant permissions are a poor long-term fit on medical workstations. Once the production Target Page URL is known, the manifest match patterns must be narrowed to the concrete host(s) — a one-line change plus reload. Until then, treat the broad grant as a flagged deviation, not a pattern to copy.

## Consequences

- The extension can technically observe every HTTP(S) page; only the configured URL pattern ever causes it to act.
- Anyone reviewing "from source" installs should see this ADR and the note in the extension README.

## Pending action

- [ ] Narrow manifest host permissions to the known production Target Page URL.
