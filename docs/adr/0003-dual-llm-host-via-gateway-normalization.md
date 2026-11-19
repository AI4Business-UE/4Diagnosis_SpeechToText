# Dual LLM Host (OpenRouter / OpenAI) via gateway normalization of Model references

The pipeline must run against either OpenRouter or direct OpenAI, chosen at deployment time via an explicit `LLM_HOST` env var (default: OpenRouter) rather than by API-key precedence. We decided to keep the widespread `vendor/model` Model-reference notation as the single canonical form across config, stages and eval, and to normalize it at one deep gateway module (`app_stt/pipeline/utils/llm/`): on the OpenRouter Host the reference passes through untouched; on the OpenAI Host a `openai/*` reference is prefix-stripped to the native id, and any other vendor fails fast with a Polish configuration error. The gateway also owns per-Host request shaping (OpenRouter's JSON + base64 `input_audio` + `provider.options` envelope vs OpenAI's multipart flat `keywords`/`languages`/`prompt`), so no stage ever branches on the Host.

## Considered Options

- Native model ids per Host in config — rejected: would duplicate every model setting per Host and scatter `openai/gpt-transcribe`-style references across the app.
- Host inferred from which API key is present — rejected: the footgun that motivated this refactor (silent behavior switches, plus `docker-compose` `:-null` making the inference lie).
- Alias/translation table per model — rejected as unnecessary: `gpt-transcribe` is served natively by OpenAI with `keywords`, `languages` and `prompt` support, so both Hosts serve the same models and only the wire shape differs.

## Consequences

- HuggingFace-only references (`msxksm/whisper-medium-medical-pl`, `openai/whisper-large-v3`) cannot be served by either Host; the hosted-whisper config was pruned to Host-servable references (`whisper_local` keeps HF ids — it never touches the gateway).
- Model-reference validation is lazy (at request time) while Host+key validation is eager (at gateway construction), so a stale reference in an unselected stage never blocks startup.
- Eval results record the explicit Host (`llm_host`) instead of inferring `llm_api_provider` from key presence.
