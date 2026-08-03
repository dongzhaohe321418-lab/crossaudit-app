# Constitution — <PROJECT>

Version this file in git. Every audit cites the commit that carried it. Rule
changes take effect only between cycles, so work is never judged against a
target that moved underneath it.

Each rule has a stable ID and a decidable criterion. **BLOCKER** gates the
increment when an objective requirement is not met. **ADVISORY** records
judgement or an improvement opportunity and never gates admission.

---

### CA-TASK-001
**BLOCKER.** When a committed `TASK.md` exists, the delivered work satisfies
every objectively testable requirement it states, including requested scope,
length, format, and number of deliverables. Substituting an unrequested format
or creating extra deliverables that obscure the requested result is a defect.

### CA-CONTENT-001
**BLOCKER.** The primary deliverable is complete, internally consistent, and
contains no unresolved placeholder such as TODO, TBD, or sample text.

### CA-CONTENT-002
**BLOCKER.** Claims presented as facts do not contradict the supplied source
material or other files in the audited increment.

### CA-USABILITY-001
**ADVISORY.** The deliverable should be easy for its intended reader to locate,
open, and use without needing unrelated supporting files.

---

<!-- Add project-specific rules below. Keep the ID scheme CA-<AREA>-<NNN>, one
     heading per rule, severity in the first line, and a decidable criterion. -->
