"""First-party LLM provider capabilities used by every CrossAudit surface.

The catalogue is deliberately data-driven.  A vendor shown in Settings, the
project wizard, live model discovery and the runtime adapter must all refer to
the same record; otherwise a UI can claim support while the request is sent to
the wrong origin.  Only first-party inference services are presets here.
Aggregators and self-hosted gateways remain available through the explicit
custom OpenAI-compatible configuration because they cannot, by themselves,
prove model-source independence.
"""
from __future__ import annotations

from dataclasses import dataclass


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
