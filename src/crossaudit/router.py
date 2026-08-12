"""The router: deciding which lane a sentence belongs to (P1).

The user speaks as they normally would. This module decides whether that
sentence is about the work (generator), the standards (amendment), a contested
finding (dispute), a pending escalation (resolve), or a question (query).

Three properties, each of which is a pillar in DESIGN.md made executable:

* **The decision is a ledger entry, not a hidden judgement.** Every routing goes
  to `routing.jsonl` with the utterance, the lane, the confidence and what was
  executed. A router whose choices are invisible is a third unaudited agent.
* **Unsure means ask.** Below the confidence threshold the box briefly stops
  being a box and asks one clarifying question. Guessing the direction of a
  change contaminates either the rulebook or the work.
* **The router forwards the user, never the generator.** Nothing the generator
  says can reach the auditor through this path (P2).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .constitution import parse_json_reply
from .errors import ProviderDenial

# "auditor" is the seventh lane: a direct read-only auditor reply, produced by
# an explicit @Auditor mention in route_addressed. A mention selects a
# recipient, not a privilege — mutations still require a certain
# amendment/dispute/resolve classification.
LANES = ("project", "generator", "amendment", "dispute", "resolve", "query",
         "auditor")
CONFIDENCE_FLOOR = 0.75

ROUTER_SYSTEM = """You sort one sentence from a project owner into exactly one \
lane of a supervision system. You are a switchboard, not an assistant: you do not \
answer the person, you decide where their words go.

The lanes:
- project: describing what the project is, or its goals, for the first time.
- generator: asking for the work itself to change (add, cut, rewrite, fix).
- amendment: asking for the audit standards to change (stricter, looser, a new \
thing to watch for). The tell is that it is about how work is judged, not about \
this particular piece of work.
- dispute: contesting a specific audit finding as wrong or unfair.
- resolve: ruling on something the loop escalated — letting it through, or \
abandoning it.
- query: asking about state. Answerable from records; changes nothing.

Judge intent, not vocabulary. "This section is too long" is generator: it asks \
for a change to the work. "Sections should never exceed a page" is amendment: it \
sets a standard for all future work. When a sentence carries both, choose the one \
that would be lost if you chose the other, and say so in your reasoning.

Confidence is your genuine probability that the lane is right. Below 0.75 the \
system will ask the person instead of acting, so a low number is useful, not a \
failure — use it whenever a sentence is genuinely ambiguous.

Reply with exactly one JSON object and nothing else:
{"lane": "...", "confidence": 0.0-1.0,
 "reasoning": "one sentence: what made this that lane",
 "restated": "the person's request as an instruction for that lane",
 "clarify": "if confidence is low, the single question to ask them; else empty"}"""


@dataclass
class Routing:
    utterance: str
    lane: str
    confidence: float
    reasoning: str
    restated: str
    clarify: str = ""
    executed: str = "pending"
    t: int = 0
    addressed_to: str = "auto"
    routing_mode: str = "automatic"
    chat_id: str = ""

    @property
    def certain(self) -> bool:
        return (self.confidence >= CONFIDENCE_FLOOR
                or self.routing_mode == "automatic_safe_default")

    def as_dict(self) -> dict:
        return asdict(self)


def route(utterance: str, *, complete, context: str = "") -> Routing:
    """Classify one utterance. The classification is data; the caller executes."""
    reply = complete(
        system=ROUTER_SYSTEM,
        prompt=(f"{context}\n\n" if context else "")
               + f"THE PERSON SAYS:\n{utterance.strip()}")
    raw = parse_json_reply(reply.text)
    lane = str(raw.get("lane", "")).strip().lower()
    if lane not in LANES:
        raise ProviderDenial(f"router returned an unknown lane {lane!r}")
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    return Routing(utterance=utterance.strip(), lane=lane,
                   confidence=max(0.0, min(1.0, confidence)),
                   reasoning=str(raw.get("reasoning", "")).strip(),
                   restated=str(raw.get("restated", utterance)).strip(),
                   clarify=str(raw.get("clarify", "")).strip(),
                   t=int(time.time()))


MENTION_RE = re.compile(
    r"^\s*@(?P<who>generator|executor|生成端|执行端|auditor|audit|审计端|审计)"
    r"(?=\s|[,:：-]|$)[\s,:：-]*", re.IGNORECASE)
GENERATOR_NAMES = {"generator", "executor", "生成端", "执行端"}
AUDITOR_MUTATIONS = {"amendment", "dispute", "resolve"}


def route_addressed(utterance: str, *, complete, context: str = "") -> Routing:
    """Route ordinary speech automatically, or honour an explicit @recipient.

    A mention chooses a recipient, not a privilege escalation. ``@Generator``
    can ask for work through the normal supervised build loop. ``@Auditor`` may
    trigger an auditor-owned mutation only when the auditor-side router is
    confident it is an amendment, dispute or human resolution; everything else
    becomes a read-only direct auditor reply.
    """
    original = utterance.strip()
    match = MENTION_RE.match(original)
    if not match:
        return route(original, complete=complete, context=context)
    body = original[match.end():].strip()
    if not body:
        raise ProviderDenial("name a recipient and include the instruction after it")
    who = match.group("who").lower()
    if who in GENERATOR_NAMES:
        return Routing(
            utterance=original, lane="generator", confidence=1.0,
            reasoning="the project owner explicitly addressed the Generator",
            restated=body, t=int(time.time()), addressed_to="generator",
            routing_mode="explicit")

    # Recipient selection must not silently widen disclosure. The addressed
    # message alone is enough to distinguish a clear amendment/dispute/ruling;
    # project rule ids and controller state stay out of this classifier call.
    classified = route(body, complete=complete, context="")
    lane = (classified.lane if classified.certain and
            classified.lane in AUDITOR_MUTATIONS else "auditor")
    detail = (f"; auditor-side intent classified as {classified.lane}"
              if lane != "auditor" else "")
    return Routing(
        utterance=original, lane=lane, confidence=1.0,
        reasoning="the project owner explicitly addressed the Auditor" + detail,
        restated=classified.restated or body, t=int(time.time()),
        addressed_to="auditor", routing_mode="explicit")


def apply_safe_default(routing: Routing) -> Routing:
    """Continue low-risk ambiguous speech without interrupting the owner.

    Work requests and project descriptions both safely enter the supervised
    Generator loop; queries are read-only.  Rule changes, disputes and human
    resolutions can alter the control plane, so ambiguity there still asks.
    The original model confidence remains in the ledger for observability.
    """
    if routing.certain:
        return routing
    if routing.lane not in {"generator", "project", "query"}:
        return routing
    lane = "generator" if routing.lane in {"generator", "project"} else "query"
    reason = routing.reasoning.rstrip(".; ")
    suffix = ("safe autonomy sent this reversible request through the supervised "
              "Generator loop" if lane == "generator"
              else "safe autonomy kept this request read-only")
    return replace(
        routing, lane=lane, clarify="", routing_mode="automatic_safe_default",
        reasoning=f"{reason}; {suffix}" if reason else suffix)


def record(path: Path, routing: Routing, executed: str) -> Path:
    """Append the decision to the routing ledger. Called for every utterance,
    including the ones that were only clarified and never acted on."""
    routing.executed = executed
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(routing.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return path


def history(path: Path, limit: int = 50) -> list[dict]:
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]
