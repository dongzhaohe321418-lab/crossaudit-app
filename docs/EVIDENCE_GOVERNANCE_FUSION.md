# Evidence–Governance Fusion

This design combines the Evidence Lab admission architecture with the original
Git-native CrossAudit protocol. The product remains a black box at the normal
interaction surface, while its receipts and ledger remain inspectable.

## The authority split

```text
untrusted proposal plane
  Generator artifact
       ├── registered deterministic checks
       └── cross-vendor semantic Auditor
                         |
                         v
trusted admission plane
  normalized evidence -> authority policy -> receipt
                              |
          +-------------------+------------------+
          |                   |                  |
        PASS               BLOCK             ESCALATE
          |                   |                  |
      one-time           guarded repair      Git governance
      admission          of verified fault   dispute / human ruling
```

The model Auditor is still important: it finds semantic defects for which no
checker exists. It is not the component that decides how much authority its own
claim receives.

## Admission rule

An automatic `BLOCK` requires at least one of:

1. a verified deterministic failure, executable counterexample, or reproducible
   observation; or
2. the same finding supported by at least two distinct producers and at least
   two distinct mechanism families.

Repeating a claim with another model using the same semantic-review mechanism
does not satisfy the second rule. Confidence scores and vendor names are
metadata, not proof.

If planned semantic coverage is missing, an Auditor reply is invalid, the
artifact/prompt boundary is incomplete, or a blocker remains only a textual
judgment, the result is `ESCALATE`. The existing CrossAudit state machine then
prevents later commits from routing around that decision.

## Workflow mapping

| Authority status | Workflow verdict | Route |
|---|---|---|
| `PASS` | `PASS` | one-time receipt admission |
| `ADVISORY` | `PASS` | admission with findings retained |
| `BLOCK` | `BLOCKED` | automatic repair, subject to guard |
| `ESCALATE` | `ESCALATE` | dispute or human resolution |
| missing model coverage | `DCL_ONLY` | obtain a semantic audit |

The two status vocabularies are intentionally separate. Authority describes
what evidence may do; workflow verdict describes how the existing controller
must proceed.

## Defensive-programming control

Only verified machine blockers are returned to the Generator automatically.
Before a repair commit, the guard checks the staged diff for:

- files outside the verified finding scope;
- change size above the configured automatic budget;
- broad `Exception`/bare catches and silent `pass`;
- newly introduced retry, fallback, suppression, ignored type/lint errors, or
  disabled-test patterns; and
- binary patches not produced by the trusted local document renderer.

A guard refusal does not delete the working bytes. It removes them from the
admission candidate, records the reason in live run events, and gives the next
bounded Generator turn a chance to make a smaller causal repair. At the round
limit, the case enters human governance.

This is deliberately not a ban on defensive code. A human can approve a broader
behavior when the task actually requires it. The point is that a model cannot
add such behavior merely to make an audit finding disappear.

## Receipt and verification bindings

New receipts include an `authority` block containing:

- policy version and deterministic decision ID;
- authority status and workflow route;
- normalized evidence records;
- blocking/advisory evidence IDs;
- evidence digest and rationale.

The verifier checks the evidence digest, status/verdict mapping, and the
authority status/route printed in the immutable report. The entire authority
block is also covered by the receipt digest. Older schema-v2 receipts remain
verifiable but do not retroactively claim the new evidence policy.

## Trusted computing base and limits

The fused system improves authority semantics; it does not remove all trust.
The registered checks, evidence normalization, authority policy, repair guard,
receipt verifier, controller store, and local renderer are in the trusted
computing base. Mechanism-family registration must eventually be backed by a
signed registry rather than adapter self-description. The present semantic
Auditor is a single proposal source, and real-world efficacy still requires a
multi-domain benchmark with human adjudication.

## Code map

- `crossaudit.authority`: evidence normalization, policy and receipt validation
- `crossaudit.auditor.run`: invokes the policy after checks/model review
- `crossaudit.repair_guard`: scopes and screens automatic repair diffs
- `crossaudit.cli.build`: applies the guard and returns only verified blockers
- `crossaudit.receipt`: binds and verifies the authority object
- `crossaudit.dispute` / `crossaudit.controller`: bounded governance and rulings
