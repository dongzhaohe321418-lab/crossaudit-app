"""First-party LLM provider capabilities used by every CrossAudit surface.

The catalogue is deliberately data-driven.  A vendor shown in Settings, the
project wizard, live model discovery and the runtime adapter must all refer to
the same record; otherwise a UI can claim support while the request is sent to
the wrong origin.  Only first-party inference services are presets here, and
each carries ``source_independence`` so a receipt can state, per role, whether
the model source was one CrossAudit can attest.  Aggregators and self-hosted
gateways remain available through the explicit custom OpenAI-compatible
configuration, but because they cannot by themselves prove model-source
independence, a receipt records their runtime as ``parametric: False`` rather
than asserting a cross-vendor independence it cannot back — see
:func:`source_independent`, which the receipt builder consults with the
*runtime-actual* vendor and base URL (a fallback may have switched origins).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProviderSpec:
    vendor: str
    label: str
    provider: str
    api_base: str
    models_url: str
    auth: str
    key_env: str
    default_model: str
    models: tuple[tuple[str, str], ...]
    prefixes: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    #: Whether this is a first-party inference service whose model source
    #: CrossAudit can attest.  Every preset here is one, so the default is True.
    #: An aggregator or self-hosted gateway — were one ever added as a preset —
    #: would set this False; a custom OpenAI-compatible endpoint is judged False
    #: at runtime by :func:`source_independent`.  This is what lets the receipt's
    #: ``parametric`` field stay honest: an unattestable source never claims
    #: cross-vendor independence it cannot prove.
    source_independence: bool = True
    console_url: str = ""
    api_docs_url: str = ""
    subscription_detail: str = (
        "This provider has no supported third-party subscription sign-in for "
        "model inference. Use an official developer API key."
    )
    # id, user-facing label, chat-completions base, model-list URL.  Some
    # providers issue region-bound keys; those endpoints must be selectable
    # rather than silently sending the key to a different regional origin.
    endpoints: tuple[tuple[str, str, str, str], ...] = ()


SPECS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        "openai", "OpenAI", "openai_compat", "https://api.openai.com/v1",
        "https://api.openai.com/v1/models", "bearer",
        "CROSSAUDIT_OPENAI_KEY", "gpt-5.6-terra",
        (("gpt-5.6-sol", "highest capability"),
         ("gpt-5.6-terra", "balanced · recommended"),
         ("gpt-5.6-luna", "fastest, lowest cost")),
        prefixes=("gpt-", "o1", "o3", "o4"),
        exclude=("audio", "image", "realtime", "transcribe", "tts",
                 "search", "whisper", "instruct"),
        console_url="https://platform.openai.com/api-keys",
        api_docs_url="https://developers.openai.com/api/docs/models",
        subscription_detail=(
            "Official ChatGPT subscription sign-in is available through the "
            "bundled Codex runtime; CrossAudit never receives its OAuth token."),
    ),
    "anthropic": ProviderSpec(
        "anthropic", "Anthropic", "anthropic", "https://api.anthropic.com/v1",
        "https://api.anthropic.com/v1/models?limit=1000", "anthropic",
        "CROSSAUDIT_ANTHROPIC_KEY", "claude-sonnet-4-6",
        (("claude-sonnet-4-6", "balanced · recommended"),
         ("claude-opus-4-8", "highest capability"),
         ("claude-haiku-4-5-20251001", "fastest, lowest cost")),
        prefixes=("claude-",), console_url="https://console.anthropic.com/settings/keys",
        api_docs_url="https://docs.anthropic.com/en/api/models-list",
        subscription_detail=(
            "Anthropic does not permit Claude consumer subscriptions to be bound to third-party apps. "
            "Use an Anthropic API key or a separately implemented enterprise cloud route."),
    ),
    "google": ProviderSpec(
        "google", "Google Gemini", "google",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
        "google", "CROSSAUDIT_GOOGLE_KEY", "gemini-3.6-flash",
        (("gemini-3.6-flash", "fast, current general model"),
         ("gemini-3.5-pro", "higher capability"),
         ("gemini-3.5-flash", "fast and economical")),
        prefixes=("gemini-",), console_url="https://aistudio.google.com/api-keys",
        api_docs_url="https://ai.google.dev/api/models",
        subscription_detail=(
            "A Gemini consumer subscription is not an API credential. Google AI "
            "Studio API/auth keys are supported; Vertex AI IAM is a separate cloud connection."),
    ),
    "deepseek": ProviderSpec(
        "deepseek", "DeepSeek", "deepseek", "https://api.deepseek.com/v1",
        "https://api.deepseek.com/models", "bearer",
        "CROSSAUDIT_DEEPSEEK_KEY", "deepseek-v4-flash",
        (("deepseek-v4-pro", "current flagship when enabled for the account"),
         ("deepseek-v4-flash", "fast general and thinking modes")),
        prefixes=("deepseek-",), console_url="https://platform.deepseek.com/api_keys",
        api_docs_url="https://api-docs.deepseek.com/",
    ),
    "zhipu": ProviderSpec(
        "zhipu", "Zhipu GLM", "zhipu",
        "https://open.bigmodel.cn/api/paas/v4",
        "https://open.bigmodel.cn/api/paas/v4/models", "bearer",
        "CROSSAUDIT_ZHIPU_KEY", "glm-5.2",
        (("glm-5.2", "current flagship"), ("glm-5", "general reasoning"),
         ("glm-4.7", "stable previous generation")),
        prefixes=("glm-",), console_url="https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        api_docs_url="https://docs.bigmodel.cn/cn/api/introduction",
        endpoints=(
            ("china", "China · BigModel", "https://open.bigmodel.cn/api/paas/v4",
             "https://open.bigmodel.cn/api/paas/v4/models"),
            ("global", "International · Z.AI", "https://api.z.ai/api/paas/v4",
             "https://api.z.ai/api/paas/v4/models"),
        ),
    ),
    "moonshot": ProviderSpec(
        "moonshot", "Moonshot Kimi", "moonshot", "https://api.moonshot.ai/v1",
        "https://api.moonshot.ai/v1/models", "bearer",
        "CROSSAUDIT_MOONSHOT_KEY", "kimi-k2.6",
        (("kimi-k2.6", "current multimodal and agentic flagship"),
         ("kimi-k2.5", "previous multimodal generation"),
         ("kimi-k2-thinking-turbo", "fast long reasoning")),
        prefixes=("kimi-", "moonshot-"),
        console_url="https://platform.kimi.ai/console/api-keys",
        api_docs_url="https://platform.kimi.ai/docs",
        endpoints=(
            ("global", "International", "https://api.moonshot.ai/v1",
             "https://api.moonshot.ai/v1/models"),
            ("china", "China", "https://api.moonshot.cn/v1",
             "https://api.moonshot.cn/v1/models"),
        ),
    ),
    "minimax": ProviderSpec(
        "minimax", "MiniMax", "minimax", "https://api.minimaxi.com/v1",
        "https://api.minimaxi.com/v1/models", "bearer",
        "CROSSAUDIT_MINIMAX_KEY", "MiniMax-M2.7",
        (("MiniMax-M2.7", "current general model"),
         ("MiniMax-M2.7-highspeed", "lower-latency current model"),
         ("MiniMax-M2.5", "stable previous generation")),
        prefixes=("minimax-",), console_url="https://platform.minimaxi.com/user-center/basic-information/interface-key",
        api_docs_url="https://platform.minimaxi.com/document/对话",
        endpoints=(
            ("china", "China", "https://api.minimaxi.com/v1",
             "https://api.minimaxi.com/v1/models"),
            ("global", "International", "https://api.minimax.io/v1",
             "https://api.minimax.io/v1/models"),
        ),
    ),
    "qwen": ProviderSpec(
        "qwen", "Alibaba Qwen", "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/models", "bearer",
        "CROSSAUDIT_QWEN_KEY", "qwen3.7-plus",
        (("qwen3.7-max", "highest capability"),
         ("qwen3.7-plus", "balanced · recommended"),
         ("qwen3-coder-plus", "coding"), ("qwen-plus", "stable alias")),
        prefixes=("qwen",), console_url="https://bailian.console.aliyun.com/",
        api_docs_url="https://help.aliyun.com/en/model-studio/compatibility-of-openai-with-dashscope",
        subscription_detail=(
            "Qwen Code offers its own official Coding Plan login, but CrossAudit "
            "does not reuse CLI session files as general inference credentials. "
            "Use a Model Studio API key here."),
        endpoints=(
            ("beijing", "China · Beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "https://dashscope.aliyuncs.com/compatible-mode/v1/models"),
            ("singapore", "International · Singapore", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
             "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models"),
            ("us", "United States · Virginia", "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
             "https://dashscope-us.aliyuncs.com/compatible-mode/v1/models"),
            ("hongkong", "China · Hong Kong", "https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1",
             "https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1/models"),
        ),
    ),
    "xai": ProviderSpec(
        "xai", "xAI", "xai", "https://api.x.ai/v1",
        "https://api.x.ai/v1/models", "bearer", "CROSSAUDIT_XAI_KEY",
        "grok-4.5", (("grok-4.5", "current flagship"),
                     ("grok-4.3", "stable previous generation"),
                     ("grok-code-fast-1", "fast coding")),
        prefixes=("grok-",), console_url="https://console.x.ai/",
        api_docs_url="https://docs.x.ai/developers/rest-api-reference/inference/models",
        subscription_detail=(
            "xAI's inference API supports API credentials (and documented OAuth "
            "tokens for approved integrations), but an X consumer subscription "
            "is not automatically an inference entitlement. API key is enabled here."),
    ),
    "mistral": ProviderSpec(
        "mistral", "Mistral AI", "mistral", "https://api.mistral.ai/v1",
        "https://api.mistral.ai/v1/models", "bearer",
        "CROSSAUDIT_MISTRAL_KEY", "mistral-medium-3-5",
        (("mistral-medium-3-5", "balanced · recommended"),
         ("mistral-medium-latest", "rolling medium alias"),
         ("devstral-latest", "software engineering")),
        prefixes=("mistral-", "devstral-", "ministral-", "codestral-"),
        console_url="https://console.mistral.ai/api-keys",
        api_docs_url="https://docs.mistral.ai/api/endpoint/models",
    ),
}


def spec(vendor: str) -> ProviderSpec:
    try:
        return SPECS[vendor]
    except KeyError:
        raise ValueError(f"unsupported provider vendor {vendor!r}") from None


def vendors() -> tuple[str, ...]:
    return tuple(SPECS)


def endpoints(vendor: str) -> tuple[tuple[str, str, str, str], ...]:
    item = spec(vendor)
    return item.endpoints or (("default", "Default", item.api_base,
                               item.models_url),)


def endpoint(vendor: str, endpoint_id: str = "") -> tuple[str, str, str, str]:
    rows = endpoints(vendor)
    wanted = endpoint_id or rows[0][0]
    for row in rows:
        if row[0] == wanted:
            return row
    raise ValueError(f"unsupported {vendor} endpoint {endpoint_id!r}")


def _origin(url: str) -> str:
    """scheme://host[:port], case-folded, for comparing endpoints by origin."""
    parsed = urlparse(url if "//" in url else "https://" + url)
    return f"{parsed.scheme}://{parsed.netloc}".casefold()


def official_origins(vendor: str) -> frozenset[str]:
    """Every first-party origin a built-in vendor's key is allowed to reach.

    An unknown vendor has none: it owns no origin this catalogue can vouch for.
    """
    item = SPECS.get((vendor or "").casefold().strip())
    if item is None:
        return frozenset()
    origins = {_origin(item.api_base)}
    origins.update(_origin(row[2]) for row in item.endpoints)
    return frozenset(origins)


def source_independent(vendor: str, base_url: str | None = None) -> bool:
    """Whether a role's runtime origin can attest an independent model source.

    True only for a first-party built-in vendor reached at one of its own
    official origins.  A custom OpenAI-compatible ``base_url`` (an origin this
    catalogue does not recognise), an aggregator, a self-hosted gateway, or an
    unknown vendor cannot prove who serves the model, so a receipt must not
    assert cross-vendor independence for it.

    A ``human`` generator is not a model source at all — it can never route to
    the auditor model's origin — so it is treated as independent; the parametric
    dimension is about *model* sources reselling one another, which a person is
    categorically outside of.
    """
    key = (vendor or "").casefold().strip()
    if key == "human":
        return True
    item = SPECS.get(key)
    if item is None or not item.source_independence:
        return False
    if not base_url:
        return True
    return _origin(base_url) in official_origins(vendor)


EFFORT_HINTS = {
    "none": "fastest · reasoning disabled where supported",
    "minimal": "very light reasoning",
    "low": "lower latency and token use",
    "medium": "balanced",
    "high": "deeper reasoning",
    "xhigh": "extended reasoning",
    "max": "maximum supported reasoning",
    "ultra": "maximum reasoning with runtime delegation",
}


# ── Model capability cards ──────────────────────────────────────────────────
#
# One declaration per (vendor, model family) of what that model actually
# accepts.  This is the single source the rest of the system reads instead of
# keeping its own copy: adapters send only the parameters a model supports
# (never "send it and see"), the usage ledger takes its list price from here,
# and the model selector shows only the controls the model exposes.  Adding a
# capability means editing one row below, not five call sites.

PRICE_SNAPSHOT = "2026-08-03"

_MAX_TOKENS = "max_tokens"
_MAX_COMPLETION_TOKENS = "max_completion_tokens"
_MODERN_OPENAI_PREFIXES = ("gpt-5", "o1", "o3", "o4")


@dataclass(frozen=True)
class Rates:
    """USD per one million tokens, as published at ``PRICE_SNAPSHOT``."""

    input: float
    output: float
    cache_write: float
    cache_read: float


@dataclass(frozen=True)
class CapabilityCard:
    """What a concrete (vendor, model) accepts, and how it is billed.

    ``known`` is True only when a declared family matched.  An unrecognised
    model, or any custom OpenAI-compatible endpoint, receives a conservative
    card that advertises no optional control it cannot vouch for and keeps a
    single compatibility retry (``compat_retry``) as its safety net.  A built-in
    provider's recognised model sets ``compat_retry`` False: it sends exactly
    the parameters this record names and never gambles a request that would come
    back as an unsupported-parameter HTTP 400.

    ``context_window``/``vision``/``structured_output`` are the model-selector
    fields named in North Star §4.  They are populated only from authoritative
    provider documentation; where a value has not yet been verified the card
    stays conservative (``None``/``False``) rather than assert an unproven fact.
    """

    token_param: str = _MAX_TOKENS
    temperature: bool = False
    reasoning_efforts: tuple[str, ...] | None = None
    context_window: int | None = None
    vision: bool = False
    structured_output: bool = False
    price: Rates | None = None
    price_snapshot: str = PRICE_SNAPSHOT
    known: bool = False
    compat_retry: bool = True


_EFFORTS_566 = ("none", "low", "medium", "high", "xhigh", "max")
_EFFORTS_55 = ("low", "medium", "high", "xhigh")
_EFFORTS_5 = ("low", "medium", "high")
_EFFORTS_GEN5 = ("low", "medium", "high", "xhigh", "max")
_EFFORTS_GEN4 = ("low", "medium", "high", "max")
_EFFORTS_GEMINI = ("minimal", "low", "medium", "high")

_OPUS_RATES = Rates(5.0, 25.0, 6.25, 0.50)
_SONNET_RATES = Rates(3.0, 15.0, 3.75, 0.30)
_HAIKU_RATES = Rates(1.0, 5.0, 1.25, 0.10)
_CREATIVE_RATES = Rates(10.0, 50.0, 12.50, 1.00)

# Ordered most-specific prefix first: the first prefix the (case-folded) model id
# starts with wins.  Prefixes may end mid-version (a dot follows) so the match is
# a plain ``startswith``, exactly as the retired per-call tables matched.
_CAPABILITIES: dict[str, tuple[tuple[str, CapabilityCard], ...]] = {
    "openai": (
        ("gpt-5.6-sol", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_566, context_window=1_050_000,
            vision=True, structured_output=True,
            price=Rates(5.0, 30.0, 6.25, 0.50))),
        ("gpt-5.6-terra", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_566, context_window=1_050_000,
            vision=True, structured_output=True,
            price=Rates(2.5, 15.0, 3.125, 0.25))),
        ("gpt-5.6-luna", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_566, context_window=1_050_000,
            vision=True, structured_output=True,
            price=Rates(1.0, 6.0, 1.25, 0.10))),
        ("gpt-5.6", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_566)),
        ("gpt-5.5", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_55)),
        ("gpt-5.4", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_55)),
        ("gpt-5.3-codex", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_55)),
        ("gpt-5.2-codex", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_55)),
        ("gpt-5", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_5)),
        ("o1", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_5)),
        ("o3", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_5)),
        ("o4", CapabilityCard(
            token_param=_MAX_COMPLETION_TOKENS, temperature=False,
            reasoning_efforts=_EFFORTS_5)),
    ),
    "anthropic": (
        ("claude-fable-5", CapabilityCard(
            temperature=False, reasoning_efforts=_EFFORTS_GEN5,
            price=_CREATIVE_RATES)),
        ("claude-mythos-preview", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEN4)),
        ("claude-mythos-5", CapabilityCard(
            temperature=False, reasoning_efforts=_EFFORTS_GEN5,
            price=_CREATIVE_RATES)),
        ("claude-opus-5", CapabilityCard(
            temperature=False, reasoning_efforts=_EFFORTS_GEN5,
            price=_OPUS_RATES)),
        ("claude-sonnet-5", CapabilityCard(
            temperature=False, reasoning_efforts=_EFFORTS_GEN5,
            price=_SONNET_RATES)),
        ("claude-opus-4-8", CapabilityCard(
            temperature=False, reasoning_efforts=_EFFORTS_GEN5,
            context_window=1_000_000, vision=True, structured_output=True,
            price=_OPUS_RATES)),
        ("claude-opus-4-7", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEN5,
            price=_OPUS_RATES)),
        ("claude-opus-4-6", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEN4,
            price=_OPUS_RATES)),
        ("claude-opus-4-5", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEN4,
            price=_OPUS_RATES)),
        ("claude-sonnet-4-6", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEN4,
            context_window=1_000_000, vision=True, structured_output=True,
            price=_SONNET_RATES)),
        ("claude-sonnet-4-5", CapabilityCard(
            temperature=True, price=_SONNET_RATES)),
        ("claude-haiku-4-5", CapabilityCard(
            temperature=True, context_window=200_000,
            vision=True, structured_output=True, price=_HAIKU_RATES)),
    ),
    "google": (
        ("gemini-3", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEMINI,
            context_window=1_000_000, vision=True, structured_output=True)),
        ("gemini-2.5", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_GEMINI)),
    ),
    "xai": (
        ("grok-4.20-multi-agent", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_55)),
        ("grok-4.5", CapabilityCard(
            temperature=True, reasoning_efforts=_EFFORTS_5,
            context_window=500_000, vision=True, structured_output=True)),
    ),
}


def _anthropic_default_temperature(lowered: str) -> bool:
    """Whether an unrecognised Claude model is known to accept a temperature.

    Opus 4.8 returns a 400 stating temperature is deprecated; generation 5 and
    later drop it too, while 4.x still accepts it.  A generation-number check
    alone is therefore not sufficient, so the 4.8 special case stays explicit.
    """
    if lowered.startswith("claude-opus-4-8"):
        return False
    match = re.match(r"^claude-[a-z0-9]+-(\d+)(?:-|$)", lowered)
    return not match or int(match.group(1)) < 5


def _default_card(vendor: str, lowered: str, *, official: bool) -> CapabilityCard:
    """The conservative card for a model no declared family matched.

    It sends no reasoning effort and keeps the compatibility retry.  The token
    field and whether a temperature is sent are inferred the same way the
    adapters used to infer them inline, so an unknown or custom-endpoint model
    behaves exactly as before this catalogue existed."""
    if vendor == "anthropic":
        return CapabilityCard(token_param=_MAX_TOKENS,
                              temperature=_anthropic_default_temperature(lowered),
                              compat_retry=True)
    modern = lowered.startswith(_MODERN_OPENAI_PREFIXES)
    if vendor == "openai" and official:
        token_param = _MAX_COMPLETION_TOKENS
    else:
        token_param = _MAX_COMPLETION_TOKENS if modern else _MAX_TOKENS
    return CapabilityCard(token_param=token_param, temperature=not modern,
                          compat_retry=True)


def capability_card(vendor: str, model: str, provider: str = "", *,
                    official: bool = True) -> CapabilityCard:
    """The single capability record for one concrete (vendor, model).

    ``official`` is True for a first-party built-in origin and False for a
    custom OpenAI-compatible endpoint.  A recognised model on a built-in origin
    is the only case that disables the compatibility retry: everything else
    keeps it, so proxies and brand-new model ids remain fail-safe.
    """
    vendor = vendor.casefold().strip()
    lowered = model.casefold().strip()
    for prefix, card in _CAPABILITIES.get(vendor, ()):
        if lowered.startswith(prefix):
            return replace(card, known=True, compat_retry=not official)
    return _default_card(vendor, lowered, official=official)


def reasoning_efforts(vendor: str, model: str, provider: str = "") -> tuple[str, ...]:
    """Request-level effort controls a concrete model documents, or none.

    A thin read over :func:`capability_card`; the effort table now lives there
    with the rest of the model's capabilities.  Unknown and custom models return
    no efforts, so the selector hides the control and no optimistic parameter can
    turn a valid run into an HTTP 400.
    """
    return capability_card(vendor, model, provider).reasoning_efforts or ()
