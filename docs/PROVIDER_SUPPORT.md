# Provider support and authentication boundary

Research snapshot: **2026-08-03**. CrossAudit does not freeze the model list at
this date: the app asks the selected provider for the models visible to the
exact credential and treats the curated rows below only as an offline fallback.

## What “connected” means

An API key, a cloud authorization key, and a consumer chat subscription are
different entitlements. CrossAudit supports a browser subscription login only
when an official runtime publishes a third-party inference flow whose tokens
remain under that runtime's control. It does not import browser cookies, copy
CLI credential stores, or ask users to paste access/refresh tokens.

- **OpenAI**: API key or official ChatGPT sign-in through the bundled Codex App
  Server. CrossAudit receives account state and text output, never the OAuth
  token. Official references: [Codex authentication](https://learn.chatgpt.com/docs/auth),
  [models](https://developers.openai.com/api/docs/models).
- **Google Gemini**: Google AI Studio API/auth key. Google documents OAuth for
  Cloud projects, but a Gemini consumer subscription is not an API entitlement.
  CrossAudit currently uses the documented OpenAI-compatible text route and the
  native `models.list` route. Official references: [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai),
  [API keys](https://ai.google.dev/gemini-api/docs/api-key),
  [models.list](https://ai.google.dev/api/models).
- **Anthropic**: developer API key. Claude consumer subscriptions are separate
  from API billing and are not bridged. Official references: [Models API](https://docs.anthropic.com/en/api/models-list),
  [API billing explanation](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console).
- **DeepSeek**: Platform API key. The 2026-07-24 retirement of
  `deepseek-chat`/`deepseek-reasoner` is reflected in the fallback list; use
  `deepseek-v4-flash` or `deepseek-v4-pro`. Official references: [models and pricing](https://api-docs.deepseek.com/quick_start/pricing),
  [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion).
- **Zhipu GLM**: BigModel or international Z.AI API key and the corresponding
  official OpenAI-compatible v4 route. Choose **China · BigModel** or
  **International · Z.AI** in the project form. Official references:
  [BigModel quick start](https://docs.bigmodel.cn/cn/api/introduction),
  [Z.AI HTTP API](https://docs.z.ai/guides/develop/http/introduction).
- **Moonshot Kimi**: Kimi Platform API key. Global and mainland-platform keys
  are separate and must not be mixed; choose International or China in the
  project form. Official references: [API overview](https://platform.kimi.ai/docs/api/overview),
  [model list](https://platform.kimi.ai/docs/models),
  [List Models](https://platform.kimi.ai/docs/api/list-models).
- **MiniMax**: Open Platform key entered in the same write-only key field, with
  China (`api.minimaxi.com`) and International (`api.minimax.io`) selectable
  per role. Official references: [China List Models](https://platform.minimaxi.com/docs/api-reference/models/openai/list-models),
  [International List Models](https://platform.minimax.io/docs/api-reference/models/openai/list-models),
  [OpenAI compatibility](https://platform.minimax.io/docs/api-reference/text-openai-api).
- **Alibaba Qwen**: Model Studio/DashScope API key. Coding Plan credentials are
  a separate product with explicit permitted-use restrictions, so CrossAudit
  does not silently reuse Qwen Code sessions or treat a consumer login as a
  general API credential. Official references: [Model Studio](https://help.aliyun.com/en/model-studio/what-is-model-studio),
  [Coding Plan restrictions](https://help.aliyun.com/en/model-studio/coding-plan),
  [regional endpoints](https://www.alibabacloud.com/help/en/model-studio/regions/),
  [model pricing and IDs](https://help.aliyun.com/en/model-studio/model-pricing).
- **xAI**: xAI Console inference API key. The API also documents OAuth tokens
  for approved integrations, but an X consumer subscription is not inferred to
  include API usage. Official references: [Models API](https://docs.x.ai/developers/rest-api-reference/inference/models),
  [API overview](https://x.ai/api).
- **Mistral AI**: La Plateforme API key. Official references:
  [Models endpoint](https://docs.mistral.ai/api/endpoint/models),
  [Mistral Medium 3.5](https://docs.mistral.ai/models/model-cards/mistral-medium-3-5-26-04).

## Request-level reasoning effort

The workspace can change model and reasoning effort between calls. CrossAudit
does not assume that one provider's labels or payload field work for another:

- OpenAI API sends `reasoning_effort` only for recognised GPT-5 reasoning
  families. ChatGPT subscription choices are taken from the signed-in Codex
  runtime's live model catalogue and passed as the documented per-turn effort.
- Anthropic sends `output_config.effort` only for Claude models with documented
  adaptive-effort support.
- Gemini thinking models use the OpenAI-compatible `reasoning_effort` mapping.
- xAI reasoning-capable Grok models use their documented low/medium/high field.
- Every other model/provider remains on provider-controlled **Automatic**.

Saving is serialized with the project worker. It is refused while a loop is
running, so one Generator or Auditor call can never start under one setting and
finish under another. The selected effort is recorded with the exchange and
receipt evidence for later review.

Official references: [OpenAI reasoning models](https://developers.openai.com/api/docs/guides/latest-model),
[Anthropic effort](https://platform.claude.com/docs/en/build-with-claude/effort),
[Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), and
[xAI reasoning effort](https://docs.x.ai/developers/model-capabilities/text/reasoning).

## Runtime safety properties

1. Every preset has an allowlisted set of first-party HTTPS origins, exact
   authentication style, model-list endpoint, completion base, and Keychain
   environment name in a single registry. Region-bound keys require an explicit
   region choice; CrossAudit never guesses by retrying a secret against hosts.
2. The app never returns stored keys to JavaScript. Settings can only report
   whether a Keychain item exists, replace it, or delete it.
3. Redirects are refused before credentials can move to another host; TLS
   verification cannot be disabled.
4. Provider-specific 400 responses may trigger one narrowly scoped compatibility
   retry (for example `max_tokens` → `max_completion_tokens`). Authentication,
   permissions, malformed content, and all other errors remain fail-closed.
5. Aggregators are not first-party presets because a different billing endpoint
   does not prove an independent model source. An explicitly trusted custom
   OpenAI-compatible endpoint remains available for controlled CLI deployments,
   but it is never used as evidence of cross-vendor independence. Each preset
   carries a `source_independence` flag (true for every first-party service
   here), and the receipt builder consults `source_independent(vendor, base_url)`
   with the *runtime-actual* origin of each role. When either role ran on — or
   could fall back to — a custom endpoint, an aggregator, a self-hosted gateway,
   or an unknown vendor, the receipt records `isolation.parametric: false` with
   the note "model source independence cannot be asserted for a custom or
   aggregator endpoint", even when the two roles' vendor *names* differ. This is
   fail-open for running the audit (the verdict, deterministic checks, and other
   isolation dimensions are unaffected) but fail-closed for admission: a
   deployment whose `isolation.minimum.parametric` is true refuses a receipt
   whose parametric evidence is false, so an unattestable source cannot be
   admitted where independence is required (North Star §31: required
   independence cannot be silently disabled). Two genuine first-party vendors
   (for example `anthropic` + `openai`) are unaffected and keep
   `parametric: true`.

## Adding another provider

Add one `ProviderSpec` record, a compatibility adapter only if the first-party
request schema differs, and contract tests for the exact completion URL,
authentication header, model-list response shape, error mapping, and usage
fields. Do not add only a model name to the UI: that recreates the failure mode
where a visible option is routed to a different provider's endpoint.
