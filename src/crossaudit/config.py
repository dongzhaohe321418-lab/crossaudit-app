"""`crossaudit.yml`: the one configuration file, schema-validated on load.

Credentials never appear here. The file names the *environment variable* that
carries a key; the value is read at call time and never echoed, never logged,
never written into a receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import ConfigDenial
from .providers.specs import EFFORT_HINTS

CONFIG_NAME = "crossaudit.yml"

#: Isolation dimensions, in the paper's own terms (I1). Recorded as evidence
#: per deployment, and compared against `isolation.minimum` before admission.
ISOLATION_DIMS = ("parametric", "contextual", "permissive")

_ALLOWED_TOP = {"version", "science_repo", "audit_repo", "constitution", "max_rounds",
                "auditor", "generator", "isolation", "state", "ledger", "scope",
                "checks", "plugins", "resilience", "budgets", "repair"}
_ALLOWED_ROLE = {"provider", "model", "base_url", "key_env", "vendor",
                 "reasoning_effort", "fallbacks"}
#: Valid ``reasoning_effort`` strings for YAML validation, derived from the one
#: provider effort catalogue so this schema and the model cards cannot drift.
#: ``EFFORT_HINTS`` is the single vocabulary of effort levels the system knows:
#: it is a superset of every CapabilityCard's efforts and additionally documents
#: reserved levels (e.g. "ultra") no shipping card emits yet, so validation stays
#: deliberately as wide as the catalogue. Adding a level in specs.EFFORT_HINTS
#: makes it both describable in the UI and acceptable here, in one edit.
_EFFORT_VALUES = frozenset(EFFORT_HINTS)


@dataclass(frozen=True)
class Role:
    provider: str
    model: str
    vendor: str
    key_env: str
    base_url: str | None = None
    reasoning_effort: str | None = None
    fallbacks: tuple["Role", ...] = ()


@dataclass(frozen=True)
class Resilience:
    """Provider-call recovery policy; retries never spend audit rounds."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 20.0
    retry_after_cap_seconds: float = 120.0
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown_seconds: float = 60.0


@dataclass(frozen=True)
class Budgets:
    """Local guardrails. None means visible metering without a limit."""

    daily_token_warning: int | None = None
    daily_token_limit: int | None = None
    monthly_cost_warning_usd: float | None = None
    monthly_cost_limit_usd: float | None = None


@dataclass(frozen=True)
class RepairPolicy:
    """Bounds for automatic revisions after verified failures."""

    enabled: bool = True
    max_changed_lines: int = 200


@dataclass(frozen=True)
class Config:
    path: Path
    science_repo: str
    audit_repo: str | None
    constitution: str
    max_rounds: int
    auditor: Role
    generator_vendor: str | None
    generator_provider: str | None
    generator_model: str | None
    generator_key_env: str | None
    generator_base_url: str | None
    generator_reasoning_effort: str | None
    isolation_minimum: dict
    state_dir: str
    ledger_dir: str
    scope_dirs: list[str] | None
    checks: list[str]
    plugins: list[str] = field(default_factory=list)
    generator_fallbacks: tuple[Role, ...] = ()
    resilience: Resilience = field(default_factory=Resilience)
    budgets: Budgets = field(default_factory=Budgets)
    repair: RepairPolicy = field(default_factory=RepairPolicy)

    @property
    def root(self) -> Path:
        return self.path.parent


def _role(raw: dict, name: str, where: Path, *, allow_fallbacks: bool = True) -> Role:
    unknown = set(raw) - _ALLOWED_ROLE
    if unknown:
        raise ConfigDenial(f"{name}: unknown keys {sorted(unknown)}", file=str(where))
    for req in ("provider", "model", "vendor", "key_env"):
        if not raw.get(req):
            raise ConfigDenial(f"{name}.{req} is required", file=str(where))
    effort = raw.get("reasoning_effort")
    if effort is not None and effort not in _EFFORT_VALUES:
        raise ConfigDenial(
            f"{name}.reasoning_effort must be one of {sorted(_EFFORT_VALUES)}",
            file=str(where))
    fallback_rows = raw.get("fallbacks") or []
    if not allow_fallbacks and fallback_rows:
        raise ConfigDenial(f"{name}.fallbacks cannot contain nested fallbacks", file=str(where))
    if not isinstance(fallback_rows, list):
        raise ConfigDenial(f"{name}.fallbacks must be a list", file=str(where))
    fallbacks = tuple(_role(item, f"{name}.fallbacks[{i}]", where,
                            allow_fallbacks=False)
                      for i, item in enumerate(fallback_rows)
                      if isinstance(item, dict))
    if len(fallbacks) != len(fallback_rows):
        raise ConfigDenial(f"{name}.fallbacks entries must be mappings", file=str(where))
    return Role(provider=raw["provider"], model=raw["model"], vendor=raw["vendor"],
                key_env=raw["key_env"], base_url=raw.get("base_url"),
                reasoning_effort=effort, fallbacks=fallbacks)


def _number(raw: dict, key: str, default: float, low: float, high: float,
            where: Path) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ConfigDenial(f"{key} must be between {low:g} and {high:g}", file=str(where))
    return float(value)


def _positive_optional(raw: dict, key: str, where: Path, *, integer: bool = False):
    value = raw.get(key)
    if value is None:
        return None
    valid_type = isinstance(value, int) if integer else isinstance(value, (int, float))
    if isinstance(value, bool) or not valid_type or value <= 0:
        raise ConfigDenial(f"budgets.{key} must be a positive number or null", file=str(where))
    return int(value) if integer else float(value)


def find(start: Path | None = None) -> Path:
    """Nearest crossaudit.yml from `start` upward. Absent = denial, not a default."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / CONFIG_NAME).is_file():
            return d / CONFIG_NAME
    raise ConfigDenial(f"no {CONFIG_NAME} found from {cur} upward — run `crossaudit init`")


def load(path: Path | None = None) -> Config:
    p = path or find()
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigDenial(f"{CONFIG_NAME} is not valid YAML: {exc}", file=str(p)) from exc
    if not isinstance(raw, dict):
        raise ConfigDenial(f"{CONFIG_NAME} must be a mapping", file=str(p))

    unknown = set(raw) - _ALLOWED_TOP
    if unknown:
        raise ConfigDenial(f"unknown top-level keys {sorted(unknown)}", file=str(p))
    if raw.get("version") != 1:
        raise ConfigDenial(f"config version {raw.get('version')!r} unsupported (expected 1)",
                           file=str(p))
    for req in ("science_repo", "constitution", "auditor"):
        if not raw.get(req):
            raise ConfigDenial(f"{req} is required", file=str(p))

    auditor = _role(raw["auditor"] or {}, "auditor", p)
    gen = raw.get("generator") or {}
    if not isinstance(gen, dict):
        raise ConfigDenial("generator must be a mapping", file=str(p))
    gen_unknown = set(gen) - _ALLOWED_ROLE
    if gen_unknown:
        raise ConfigDenial(f"generator: unknown keys {sorted(gen_unknown)}", file=str(p))
    generator_vendor = gen.get("vendor")
    generator_effort = gen.get("reasoning_effort")
    if generator_effort is not None and generator_effort not in _EFFORT_VALUES:
        raise ConfigDenial(
            f"generator.reasoning_effort must be one of {sorted(_EFFORT_VALUES)}",
            file=str(p))
    generator_fallbacks_raw = gen.get("fallbacks") or []
    if not isinstance(generator_fallbacks_raw, list):
        raise ConfigDenial("generator.fallbacks must be a list", file=str(p))
    generator_fallbacks = tuple(
        _role(item, f"generator.fallbacks[{i}]", p, allow_fallbacks=False)
        for i, item in enumerate(generator_fallbacks_raw) if isinstance(item, dict))
    if len(generator_fallbacks) != len(generator_fallbacks_raw):
        raise ConfigDenial("generator.fallbacks entries must be mappings", file=str(p))

    iso_raw = raw.get("isolation") or {}
    minimum = iso_raw.get("minimum") or {}
    if set(minimum) - set(ISOLATION_DIMS):
        raise ConfigDenial(f"isolation.minimum keys must be within {list(ISOLATION_DIMS)}",
                           file=str(p))
    if not all(isinstance(v, bool) for v in minimum.values()):
        raise ConfigDenial("isolation.minimum values must be booleans", file=str(p))

    rounds = raw.get("max_rounds", 3)
    if not isinstance(rounds, int) or rounds < 1:
        raise ConfigDenial("max_rounds must be a positive integer", file=str(p))

    # State is mutable and local (gitignored); the ledger is immutable and
    # committed. They must not share a directory: one has to be ignored and the
    # other has to be committable, and a single path cannot be both.
    state_dir = (raw.get("state") or {}).get("dir", ".crossaudit")
    ledger_dir = (raw.get("ledger") or {}).get("dir", "cycles")
    s, l = Path(state_dir), Path(ledger_dir)
    if s == l or s in l.parents or l in s.parents:
        raise ConfigDenial(
            f"state.dir ({state_dir}) and ledger.dir ({ledger_dir}) overlap: the state "
            f"store is gitignored and the ledger must be committable, so one directory "
            f"cannot serve both", file=str(p))

    scope_dirs = (raw.get("scope") or {}).get("dirs")
    if scope_dirs is not None and (not isinstance(scope_dirs, list)
                                   or not all(isinstance(d, str) and d for d in scope_dirs)):
        raise ConfigDenial("scope.dirs must be a list of directory names", file=str(p))

    # Missing checks use the safe domain-neutral pack. An explicit empty list
    # means exactly that; `or` previously made it impossible to disable checks.
    checks = (raw["checks"] if "checks" in raw else
              ["parseable", "declared", "internal", "complete"])
    if not isinstance(checks, list) or not all(isinstance(c, str) for c in checks):
        raise ConfigDenial("checks must be a list of names", file=str(p))

    resilience_raw = raw.get("resilience") or {}
    if not isinstance(resilience_raw, dict):
        raise ConfigDenial("resilience must be a mapping", file=str(p))
    allowed_resilience = {"max_attempts", "initial_backoff_seconds",
                          "max_backoff_seconds", "retry_after_cap_seconds",
                          "circuit_breaker_failures", "circuit_breaker_cooldown_seconds"}
    if set(resilience_raw) - allowed_resilience:
        raise ConfigDenial(
            f"resilience: unknown keys {sorted(set(resilience_raw) - allowed_resilience)}",
            file=str(p))
    resilience = Resilience(
        max_attempts=int(_number(resilience_raw, "max_attempts", 3, 1, 10, p)),
        initial_backoff_seconds=_number(
            resilience_raw, "initial_backoff_seconds", 1, 0, 60, p),
        max_backoff_seconds=_number(
            resilience_raw, "max_backoff_seconds", 20, 0, 300, p),
        retry_after_cap_seconds=_number(
            resilience_raw, "retry_after_cap_seconds", 120, 0, 900, p),
        circuit_breaker_failures=int(_number(
            resilience_raw, "circuit_breaker_failures", 3, 1, 20, p)),
        circuit_breaker_cooldown_seconds=_number(
            resilience_raw, "circuit_breaker_cooldown_seconds", 60, 1, 3600, p),
    )
    if resilience.max_backoff_seconds < resilience.initial_backoff_seconds:
        raise ConfigDenial(
            "resilience.max_backoff_seconds cannot be below initial_backoff_seconds",
            file=str(p))
    budgets_raw = raw.get("budgets") or {}
    if not isinstance(budgets_raw, dict):
        raise ConfigDenial("budgets must be a mapping", file=str(p))
    allowed_budgets = {"daily_token_warning", "daily_token_limit",
                       "monthly_cost_warning_usd", "monthly_cost_limit_usd"}
    if set(budgets_raw) - allowed_budgets:
        raise ConfigDenial(f"budgets: unknown keys {sorted(set(budgets_raw) - allowed_budgets)}",
                           file=str(p))
    budgets = Budgets(
        daily_token_warning=_positive_optional(
            budgets_raw, "daily_token_warning", p, integer=True),
        daily_token_limit=_positive_optional(
            budgets_raw, "daily_token_limit", p, integer=True),
        monthly_cost_warning_usd=_positive_optional(
            budgets_raw, "monthly_cost_warning_usd", p),
        monthly_cost_limit_usd=_positive_optional(
            budgets_raw, "monthly_cost_limit_usd", p),
    )
    if (budgets.daily_token_warning and budgets.daily_token_limit and
            budgets.daily_token_warning > budgets.daily_token_limit):
        raise ConfigDenial("daily token warning cannot exceed the hard limit", file=str(p))
    if (budgets.monthly_cost_warning_usd and budgets.monthly_cost_limit_usd and
            budgets.monthly_cost_warning_usd > budgets.monthly_cost_limit_usd):
        raise ConfigDenial("monthly cost warning cannot exceed the hard limit", file=str(p))

    repair_raw = raw.get("repair") or {}
    if not isinstance(repair_raw, dict):
        raise ConfigDenial("repair must be a mapping", file=str(p))
    if set(repair_raw) - {"enabled", "max_changed_lines"}:
        raise ConfigDenial(
            f"repair: unknown keys {sorted(set(repair_raw) - {'enabled', 'max_changed_lines'})}",
            file=str(p))
    repair_enabled = repair_raw.get("enabled", True)
    if not isinstance(repair_enabled, bool):
        raise ConfigDenial("repair.enabled must be boolean", file=str(p))
    repair_lines = repair_raw.get("max_changed_lines", 200)
    if (isinstance(repair_lines, bool) or not isinstance(repair_lines, int)
            or not 1 <= repair_lines <= 10000):
        raise ConfigDenial(
            "repair.max_changed_lines must be an integer from 1 to 10000", file=str(p))
    repair = RepairPolicy(enabled=repair_enabled, max_changed_lines=repair_lines)

    return Config(
        path=p,
        science_repo=raw["science_repo"],
        audit_repo=raw.get("audit_repo"),
        constitution=raw["constitution"],
        max_rounds=rounds,
        auditor=auditor,
        generator_vendor=generator_vendor,
        generator_provider=gen.get("provider"),
        generator_model=gen.get("model"),
        generator_key_env=gen.get("key_env"),
        generator_base_url=gen.get("base_url"),
        generator_reasoning_effort=generator_effort,
        isolation_minimum={d: bool(minimum.get(d, False)) for d in ISOLATION_DIMS},
        state_dir=state_dir,
        ledger_dir=ledger_dir,
        scope_dirs=scope_dirs,
        checks=checks,
        plugins=raw.get("plugins") or [],
        generator_fallbacks=generator_fallbacks,
        resilience=resilience,
        budgets=budgets,
        repair=repair,
    )


def heterogeneity(cfg: Config) -> tuple[bool, str]:
    """I1 asserted from configuration. Unknown generator vendor cannot assert it."""
    if not cfg.generator_vendor:
        return False, "generator vendor not declared: I1 cannot be asserted from config"
    generator_vendors = {cfg.generator_vendor.strip().lower(),
                         *(r.vendor.strip().lower() for r in cfg.generator_fallbacks)}
    auditor_vendors = {cfg.auditor.vendor.strip().lower(),
                       *(r.vendor.strip().lower() for r in cfg.auditor.fallbacks)}
    overlap = sorted(generator_vendors & auditor_vendors)
    if overlap:
        return False, ("I1 violated: generator and auditor recovery pools overlap at "
                       + ", ".join(overlap))
    return True, f"{cfg.generator_vendor} -> {cfg.auditor.vendor}"
