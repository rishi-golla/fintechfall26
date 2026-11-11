# PRD: ClaimForge, Autonomous Claims Investigation and Revenue Recovery for Diagnostic Labs

**Version 1.0 · Fall 2026 · Team of 4 · Status: accepted for build**

> This document is the single source of truth for the project. If code, a chat message or a slide
> disagrees with it, this document wins until someone changes it. To change it: edit this file, bump
> the version in the change log at the bottom, and post one line in the team chat. Section 9
> (interface contracts) freezes at the end of Week 1. After that, a contract change needs agreement
> from the owners on both sides of that interface.

---

## 1. Summary

**One line:** a multi-agent back office for a diagnostic laboratory's billing team. It watches every
claim the lab submits, flags denials and underpayments, investigates why they happened, reconstructs
what should have been paid, and prepares a corrected claim or an evidence-backed appeal for a human
to approve. Every financial number is recomputed deterministically, every finding cites its source,
an independent Validator and an adversarial Critic check the work, and a Learning agent improves the
system from confirmed outcomes.

**The problem.** Diagnostic labs submit thousands of claims a month. Many come back denied, delayed or
underpaid. Billing teams have to read remittance codes, check payer policies, find the requisition,
the prior authorization and the ordering physician's diagnosis, recompute the contracted rate, and
then write a corrected claim or an appeal before the payer's deadline. Most of that money is never
chased. Public data shows the scale: insurers on HealthCare.gov denied 19% of in-network claims in
2024, fewer than 1% of denied claims were appealed, and about a third of the appeals that were filed
succeeded (KFF, *Claims Denials and Appeals in ACA Marketplace Plans in 2024*, Mar 2026). A quarter
of in-network denials were for administrative reasons and 9% for missing prior authorization or
referral, which are exactly the kinds of denials an agent can investigate from records.

**Our solution.** Seven specialist agents, each running as its own A2A service, coordinate on a
shared case. Investigation agents (Coverage, Audit, Evidence) work the case under a Resolution agent.
Verification agents (Validator, Critic) independently check the proposal. A Learning agent turns
validated mistakes and payer outcomes into scoped memory and versioned, benchmark-gated instruction
updates. A human approves every outbound action.

**The buyer.** The diagnostic lab, or the revenue-cycle management (RCM) firm that bills on its
behalf. The insurer is not our customer. Every legitimate denied or underpaid claim we resolve is
money the lab would otherwise never collect.

**Seats it fills:** *"The denials analyst, payment-variance analyst and appeals writer on a lab's
billing team, reporting to the billing manager."*

**Inspiration and lineage.** The agent runtime, delegation guards, controls engine, validator loop
and audit model are adapted from FreightLine (Cal Hacks 13.0,
`github.com/rishi-golla/calhacks-26`). We reuse its patterns: one A2A service per agent with an Agent
Card, frozen Pydantic contracts, bounded delegation, park/resume on `INPUT_REQUIRED`, deterministic
policy checks before every state change, a hash-chained audit trail, scoped agent memory and
versioned instruction patches with revert. We replace its SpacetimeDB system of record with
PostgreSQL plus pgvector, and its freight domain with lab billing.

---

## 2. Decisions resolved from the source brief

The original planning document contained conflicting statements. These decisions settle them.

| # | Topic | Conflict in the brief | Decision |
|---|---|---|---|
| D1 | Customer | One section says the lab is the buyer; the "ClaimForge Integrity" section says the system helps insurers process claims. | **The diagnostic lab (or its RCM firm) is the buyer.** All wording about "insurance analysts" means the lab's billing analysts. Payer behavior is simulated. |
| D2 | Agent roster | An 8-step appeal pipeline and a 7-agent team breakdown. | **The 7 agents from the team breakdown.** Appeal strategy and drafting from the 8-step list become skills of the Resolution agent. |
| D3 | Orchestration | The brief lists LangGraph. | **Pure A2A, FreightLine-style runtime.** No LangGraph. Each agent is an independent A2A service built on a shared runtime with its own bounded tool loop. |
| D4 | System of record | FreightLine used SpacetimeDB. | **PostgreSQL** is the system of record (claims, cases, findings, audit, memory with pgvector, A2A task store). **Redis Streams** carries intake events. |
| D5 | Live UI updates | Not specified beyond "SSE / WebSockets". | **Server-Sent Events** from the FastAPI backend. TanStack Query invalidates on events. |
| D6 | Timeline | Not specified. | **Multi-week semester build**, six one-week milestones (section 17). |

---

## 3. Users and personas

| Persona | Role in the lab | What they do in ClaimForge | Permissions |
|---|---|---|---|
| **Denials analyst** (primary user) | Works the denial and underpayment queue | Reviews agent proposals, edits drafts, approves routine actions, flags mistakes | `biller` |
| **Billing manager** | Owns collections targets | Approves high-value or sensitive actions, reviews learning changes, rolls back instructions | `manager` |
| **Compliance officer** | Guards against improper billing | Reads the audit trail, checks that no code change lacks documentation | `auditor` (read-only) |
| **Lab finance lead** | Tracks revenue leakage | Reads the overview dashboard: dollars at risk, recovered, by payer and reason | `viewer` |

Auth for the semester build is a simple role switcher with signed session tokens; no SSO.

---

## 4. Goals and non-goals

**Goals (must ship):**

- **G1 End-to-end case.** A denied or underpaid claim from the synthetic stream is screened, routed to
  Resolution over real A2A, investigated by the specialists it needs, verified by Validator and
  Critic, approved by a human, submitted to the payer simulator, and closed with a payer decision.
  Every step lands in the audit trail.
- **G2 Scale.** Generate and ingest 10,000 to 50,000 claims. Screening of 50,000 claims completes in
  under 5 minutes on a team laptop. The claims queue stays responsive at that volume.
- **G3 Concurrency.** At least 20 cases investigate concurrently while one waits on a documentation
  request.
- **G4 Recovery.** Kill any agent mid-case, restart it, and the case finishes with no duplicate work.
- **G5 Deterministic money.** No dollar figure that reaches a human comes from a model. Expected
  allowed amounts, variances and recovery totals are computed in code and recomputed by the
  Validator.
- **G6 Evidence-backed.** Every finding cites source records (document and span) and, where relevant,
  a policy provision. The Validator rejects any citation that does not resolve.
- **G7 Independent verification.** Every proposal receives a Validator verdict (Verified, Rejected,
  Needs Review) and a Critic review before a human sees it.
- **G8 Human in the loop.** No appeal, corrected claim or write-off recommendation leaves the system
  without human approval. The person who edits a proposal cannot also approve it.
- **G9 Learning that is measurable.** The Learning agent's instruction changes are benchmark-gated,
  versioned and revertible, and their effect is shown as a before/after score on a held-out set.
- **G10 Accuracy scoreboard.** Precision, recall, dollars identified, false appeal rate and validator
  catch rate against the simulator's answer key, shown live.
- **G11 Auditable.** For any number on screen, show the source record, the agent that read it, the
  calculation, the policy rule, the instruction version and memories used, and who approved it.

**Non-goals:** real patient data or PHI of any kind; real payer portals, clearinghouses or EDI
transmission; real money movement; multi-tenant deployment; mobile; SSO; model fine-tuning; pre-bill
claim scrubbing (stretch only, see section 19); payer-side fraud detection.

---

## 5. Domain primer (read this first)

**How a lab gets paid.** A physician orders tests on a requisition with diagnosis codes. The lab runs
the tests and submits a claim (professional claim format, equivalent to X12 837P / CMS-1500) with one
line per test: CPT/HCPCS code, modifiers, units, charge and diagnosis pointers. The payer adjudicates
and returns a remittance (equivalent to X12 835 / ERA) with the allowed amount, paid amount, patient
responsibility and adjustment reason codes per line. If a line is denied or underpaid, the lab can
send a corrected claim (replacement, frequency code 7) when the lab made the error, or file an appeal
when the payer made the error. Appeals have deadlines.

| Term | Meaning | Why it matters to us |
|---|---|---|
| CPT / HCPCS | Procedure codes for each test (lab codes are mostly 80000-89999 plus molecular 81xxx) | Drives price and coverage |
| ICD-10-CM | Diagnosis codes from the order | Drives medical necessity |
| Modifier | Two-character qualifiers, e.g. 91 (repeat test), 59 (distinct service), QW (CLIA-waived) | Wrong or missing modifiers cause bundling and duplicate denials |
| CARC | Claim Adjustment Reason Code on the remittance, e.g. 16 missing info, 18 duplicate, 27 coverage terminated, 29 timely filing, 45 exceeds fee schedule, 50 not medically necessary, 97 bundled, 197 no authorization | The primary signal for screening |
| RARC | Remark codes that refine a CARC | Extra signal |
| Group code | CO contractual, PR patient responsibility, OA other, PI payer-initiated | Who owes the money |
| Fee schedule / contract | The lab's contracted rate with each payer, often a percent of the Medicare Clinical Laboratory Fee Schedule (CLFS) | Basis for underpayment math |
| NCCI edits | Medicare code-pair (PTP) and units-per-day (MUE) edits | Explains bundling and units denials |
| LCD / NCD | Medicare coverage determinations listing covered diagnoses for a test | Basis for medical necessity analysis |
| Prior authorization | Payer approval required before some tests, especially molecular | Common denial cause |
| Timely filing / appeal window | Deadlines to submit claims and appeals | Drives case priority |
| ABN | Advance Beneficiary Notice signed by a Medicare patient | Shifts liability to the patient |

**Real reference data (public, used to make the synthetic world realistic):** CMS CLFS rates, NCCI PTP
and MUE edit tables, the ICD-10-CM code set, lab-relevant LCD/NCD policies from the Medicare
Coverage Database, and the published CARC/RARC lists. Licensing of CPT descriptors and the X12 code
lists is an open question (section 20); until resolved, we store codes and our own short labels, not
AMA descriptors.

---

## 6. The demo story

The lab is fictional: **Bayview Diagnostics**. Payers are fictional: **Golden State Health Plan**
(commercial), **Pacific Shield** (commercial), **Medicare (simulated MAC)** and **CalCare Medicaid
(simulated)**. Patients are fully synthetic. Values below are fixture values, not real rates.

1. **The month.** Bayview performs $100,000 of billable tests across about 2,000 claims. Payers deny
   or short-pay $15,000. The overview page shows dollars at risk by payer and reason, and the appeal
   deadlines coming due.
2. **Screening.** The rules engine flags 312 claims. The queue sorts them by dollars at risk,
   likelihood of recovery and deadline.
3. **The hero case (`CASE-0042`, claim `CLM-10423`).** A $5,420 genetic panel line was denied
   CARC 197 (no prior authorization). A metabolic panel line on the same claim was paid below contract. Resolution
   fans out: Coverage finds the payer's policy requires authorization for this test; Evidence finds
   an authorization letter on file, issued before the date of service, that the claim omitted; Audit
   recomputes the metabolic panel's contracted rate and finds a $38.12 underpayment.
4. **Verification.** Resolution proposes an appeal with the authorization letter attached and a
   payment-variance dispute. The Critic challenges it: "the authorization covers a different CPT
   code." The Validator checks that concern against the letter and confirms the code matches under
   the payer's code-family rule. Verdict: **Verified**. The trace view shows every delegation.
5. **Human approval.** The analyst reads the draft appeal, sees each citation highlighted in the
   source documents, and approves. Because the case total is above $5,000 (P-003), the billing
   manager gives the required second approval.
6. **Payer decision and learning.** The payer simulator overturns the denial. The Learning agent
   notices that 14 other open cases for Golden State share the same missing-authorization pattern and
   records a scoped memory: "Golden State: when CARC 197 is on a molecular line, check the
   authorization store before drafting." The next similar case cites that memory id.
7. **A caught mistake.** On a corrupted benchmark case, Audit uses the wrong year's fee schedule.
   The Validator's recomputation disagrees; verdict **Rejected**; a bounded reinvestigation fixes it.
   The learning dashboard shows the lesson and the instruction diff, with a rollback button.
8. **The scoreboard.** Precision, recall, dollars identified, false appeal rate, validator catch rate
   and the before/after benchmark scores of the latest instruction version.

---

## 7. System architecture

```text
 sim/ (synthetic lab, payers, answer key)          web/ (Next.js dashboard)
      | raw claims, remits, documents                    ^  REST + SSE
      v                                                  |
 Redis Streams  claims.raw  ->  ingest/  ->  PostgreSQL  <-  api/ (FastAPI, policy-enforcing)
                                              |      ^              ^
                                   screening/ |      | tool calls   | tool calls, writes
                                              v      | (service     |
                                   routing_outbox    |  tokens)     |
                                              |      |              |
                                   router/ dispatch  |              |
                                              v      |              |
   A2A mesh (one process per agent, Agent Card at /.well-known/agent-card.json)
   resolution :9104 --> coverage :9101 --> evidence :9103
                    --> audit    :9102 --> evidence
                    --> evidence :9103
   review_outbox --> validator :9105 <-- critic :9106
   learning_outbox --> learning :9107
              |
              +--> model provider adapters (per agent), Langfuse traces
   evaluator/ + benchmarks/ --> metrics, benchmark_runs
```

**Execution boundary.** The router only does first-hop dispatch of a case to Resolution. After that,
each agent owns its model calls and tool loop and delegates directly to other agents over A2A.
Verification and learning are triggered by durable outbox rows written in the same database
transaction as the state change that requires them, so they can never be skipped by an agent.

**Agents never write to the database directly.** Agent tools are thin HTTP clients for the Claims
API. The API authenticates each agent's service token, checks its role, and runs the same policy
checks again before writing (defense in depth, mirroring FreightLine's reducers).

**Where state lives:**

| Data | Store | Why |
|---|---|---|
| Claims, lines, remits, documents, policies, contracts, eligibility, authorizations | PostgreSQL `core` schema | The "source systems" agents read |
| Cases, tasks projection, findings, proposals, verifications, critiques, reviews, flags | PostgreSQL `ops` schema | Operational truth |
| Audit events (hash-chained, append-only) | PostgreSQL `audit` schema | Tamper-evident trail |
| Agent memory (with pgvector embeddings), lessons, instruction versions, benchmark runs | PostgreSQL `learning` schema | Learning loop |
| A2A task store (history, status, artifacts, checkpoints) | PostgreSQL `a2a` schema via the SDK's database task store | Survives restarts |
| Answer key | PostgreSQL `answer_key` schema, **no grant to any agent or API agent role** | Prevents leakage into agent behavior |
| Intake events | Redis Streams | Buffer, consumer groups, replay |
| LLM traces | Langfuse | Debugging, cost and latency |

---

## 8. Agent roster

Seven independently running A2A services. Every agent folder contains `card.py`, `instructions.md`,
`knowledge/`, `tools.py` and `main.py`. The registry (ports, skills, delegation allowlist) lives in
`common/config.py`.

| Agent (service ID) | Port | Owner | Skills (Agent Card) | Work it owns | May delegate to | Hard limits |
|---|---|---|---|---|---|---|
| **Coverage** (`coverage`) | 9101 | Person 2 | `check_eligibility`, `check_authorization`, `check_medical_necessity`, `retrieve_policy` | Eligibility on the date of service, coordination of benefits, authorization requirements, diagnosis-to-test coverage against payer policy and LCD/NCD rules; evidence-backed explanation of any coverage inconsistency | `evidence` | Read-only; cites policy ids and sections; never decides the final action |
| **Audit** (`audit`) | 9102 | Person 2 | `recalculate_reimbursement`, `check_duplicates`, `check_coding_edits`, `reconcile_remittance` | Contracted-rate recomputation, patient responsibility and contractual adjustments, duplicate billing, NCCI PTP/MUE edits, overpayment and underpayment detection | `evidence` | All math in deterministic tools; the model only selects tools and explains results |
| **Evidence** (`evidence`) | 9103 | Person 2 | `gather_evidence`, `check_documentation`, `request_documentation` | Retrieves requisitions, results, authorization letters, ABNs, submission receipts; identifies missing or inconsistent documentation; cross-references claim, remit and policy; requests missing documents through the approved workflow | none | Requests go only to the simulated document desk; parks the task while waiting |
| **Resolution** (`resolution`) | 9104 | Person 2 | `investigate_case`, `reinvestigate_case`, `propose_resolution`, `draft_appeal`, `draft_corrected_claim` | Case owner. Plans the investigation, fans out to specialists, consolidates findings, identifies unresolved questions, recommends an action and drafts the appeal or corrected claim with citations | `coverage`, `audit`, `evidence` | Proposes only; cannot submit, approve or trigger its own verification |
| **Validator** (`validator`) | 9105 | Person 3 | `verify_proposal`, `verify_concerns`, `review_flag` | Independent deterministic recomputation, citation resolution, policy-interpretation checks, deadline and compliance checks; assigns Verified, Rejected or Needs Review | none | Read-only on source data; cannot edit proposals or findings |
| **Critic** (`critic`) | 9106 | Person 3 | `challenge_proposal` | Adversarial review: contradictory evidence, overlooked provisions, hallucinations, unsupported assumptions, reasoning errors; requests more investigation | `validator` | Cannot change verdicts; concerns go to the Validator for independent checking |
| **Learning** (`learning`) | 9107 | Person 3 | `analyze_outcome`, `propose_lesson`, `propose_instruction_patch`, `run_benchmark` | Analyzes rejections, human corrections and payer outcomes; finds recurring mistakes; stores validated scoped memory; proposes benchmark-gated instruction patches with rollback | none | Cannot change policy code, limits, tool permissions or delegation allowlists (P-012) |

**Delegation guards (from FreightLine):** depth at most 3, fan-out at most 3, no cycles (the
`visited` list), allowlisted targets only, an idempotency key per delegation, per-skill timeouts,
retries with backoff, and a reconciler loop every 5 seconds. Modes are `await`, `park` and `fanout`.
A parked task resumes with a follow-up message on the same task id.

**Case flow:**

1. `screening/` flags a claim and opens a case. In the same transaction it writes a `routing_outbox`
   row.
2. `router/` claims the row and sends `investigate_case` to Resolution with idempotency key
   `case_id:screen_version`.
3. Resolution fans out to Coverage, Audit and Evidence (only the ones the screen reasons call for).
   Coverage or Audit may delegate to Evidence. If documents are missing, Evidence parks with
   `awaiting_documentation`; the simulated document desk replies after a configurable delay and the
   task resumes.
4. Resolution writes a `ProposedResolution` through the API. The API writes a `review_outbox` row in
   the same transaction.
5. The review worker sends `verify_proposal` to the Validator and `challenge_proposal` to the Critic
   in parallel. The Critic delegates its concerns to the Validator (`verify_concerns`). The Validator
   issues one final verdict after both its own checks and the Critic's concerns are resolved.
6. **Rejected:** the review worker sends `reinvestigate_case` to Resolution with the failed checks and
   open concerns. At most 2 corrective attempts; after that the case goes to human review as Needs
   Review.
7. **Verified or Needs Review:** the case enters the human review queue.
8. A human approves, edits or rejects. Approval submits to the payer simulator. The payer decision
   arrives as an event and closes the case.
9. Every Rejected verdict, human edit or rejection, and payer decision writes a `learning_outbox` row.
   The Learning agent analyzes it.

---

## 9. Interface contracts (frozen at end of Week 1)

Contracts live in `common/envelope.py` (Pydantic v2) and `db/` migrations. Field lists below are the
contract; types follow Pydantic conventions.

### 9.1 Intake events (Redis Streams; Person 1 produces and consumes)

Streams: `claims.raw` (simulator to ingest), `claims.events` (normalized, ingest to screening), with
consumer groups `ingest` and `screening`. Dead letters go to `claims.dead_letter` after 3 failed
attempts.

| Field | Type | Notes |
|---|---|---|
| `event_id` | str | `EVT-` prefix, stable, used for dedupe |
| `type` | enum | `claim.submitted`, `remit.received`, `document.received`, `authorization.recorded`, `eligibility.updated`, `appeal.decided`, `corrected_claim.decided`, `scenario.injected` |
| `ts`, `sim_ts` | ISO datetime | Wall clock and simulated clock |
| `claim_id` | str or null | `CLM-` prefix |
| `payload` | object | Type-specific body |
| `source` | enum | `sim`, `demo`, `payer_sim`, `human` |
| `history` | bool | True for back-filled history; never routed as live work |

### 9.2 A2A envelope (Person 2 owns; everyone uses)

- Case maps to A2A `context_id`. A delegated work item is a `Task`. The payload is a data part
  (`new_data_part` / `new_data_message` in `a2a-sdk` 1.x). The result is a named artifact with a data
  part.
- **`TaskEnvelope`:** `task_type`, `case_id`, `claim_id`, `display_id`, `subject` (claim line ids,
  payer id, CPT, CARC, amounts), `evidence_refs[]`, `requested_output`, `priority` (P0 to P3),
  `deadline_s`.
- **`DelegationMeta`** (in `Message.metadata`): `case_id`, `from_agent`, `parent_task_id`,
  `correlation_id`, `causation_id`, `delegation_depth`, `visited[]`, `idempotency_key`, `priority`.
- **`ResultArtifact`:** `outcome`, `confidence`, `findings` (list of `Finding`), `evidence_refs[]`,
  `policy_ids[]`, `model_used`, `instr_version`, `memory_ids[]`, `recommended_next[]`.
- **`outcome` values:** `covered`, `not_covered`, `auth_required`, `auth_on_file`, `underpaid`,
  `overpaid`, `paid_correctly`, `duplicate`, `coding_edit`, `documented`, `missing_documentation`,
  `proposed`, `verified`, `rejected`, `needs_review`, `concerns_found`, `no_concerns`,
  `lesson_recorded`, `not_implemented`.
- **Business status** (case and task): `screened`, `queued`, `investigating`,
  `awaiting_other_agent`, `awaiting_documentation`, `proposed`, `verifying`, `reinvestigating`,
  `awaiting_human_review`, `approved`, `submitted`, `payer_decided`, `closed_recovered`,
  `closed_unrecoverable`, `rejected`, `failed`. All `awaiting_*` map to A2A `INPUT_REQUIRED`.

### 9.3 Domain payloads (shared; changes need Person 2 and Person 3)

| Model | Fields |
|---|---|
| **`Finding`** | `finding_id`, `case_id`, `claim_line_id`, `agent`, `kind` (`improper_denial`, `underpayment`, `overpayment`, `lab_billing_error`, `correct_denial`, `missing_documentation`, `coding_edit`, `eligibility_issue`, `auth_issue`), `amount_usd`, `expected`, `actual`, `workings` (structured calculation inputs and steps, produced by a tool), `evidence_refs[]` (format `DOC-id#p<page>:<start>-<end>`), `policy_refs[]` (format `POL-id#<section>`), `confidence`, `rationale` (short structured text, never chain of thought) |
| **`ProposedResolution`** | `proposal_id`, `case_id`, `action` (`appeal`, `corrected_claim`, `payment_dispute`, `accept_denial`, `bill_secondary`, `bill_patient`, `escalate`, `request_more_info`), `claim_line_ids[]`, `expected_recovery_usd`, `finding_ids[]`, `draft` (`type`: `appeal_letter` or `corrected_claim`; `content` or line-level `delta`), `filing_deadline`, `open_questions[]`, `confidence`, `attempt` (1 to 3) |
| **`VerificationResult`** | `verification_id`, `proposal_id`, `verdict` (`verified`, `rejected`, `needs_review`), `checks[]` (`check_id`, `name`, `ok`, `expected`, `actual`, `severity` hard/soft), `concerns_checked[]` (`concern_id`, `upheld`, `reason`), `notes` |
| **`Critique`** | `critique_id`, `proposal_id`, `concerns[]` (`concern_id`, `type`: `hallucination`, `unsupported_assumption`, `overlooked_policy`, `contradictory_evidence`, `calculation_error`, `compliance_risk`, `deadline_risk`; `severity` low/medium/high; `claim`; `counter_evidence_refs[]`; `requested_investigation`) |
| **`Lesson`** | `lesson_id`, `agent`, `type` (`memory`, `instruction`), `scope` (`payer_id?`, `cpt?`, `carc?`, `skill?`), `text_or_diff`, `confidence`, `source` (`validator`, `human`, `payer_outcome`), `evidence_refs[]`, `benchmark_run_id?` |
| **`Friction`** | `kind` (`retry`, `reject`, `policy_deny`, `timeout`, `missing_doc`, `redelegation`, `human_override`, `flag`), `detail`, `cost_s` |

### 9.4 Claims API (Person 1 owns; FastAPI, OpenAPI published at `/docs`)

Every write endpoint calls `common/policy.check()` and writes an audit event in the same transaction.

| Group | Endpoints | Caller |
|---|---|---|
| Claims and source data | `GET /claims` (filters: status, payer, CARC, CPT, flagged, date range, amount range; sort; cursor pagination), `GET /claims/{id}`, `GET /claims/{id}/remits`, `GET /documents/{id}`, `GET /documents/{id}/content`, `GET /policies`, `GET /policies/{id}` | UI, agents |
| Cases and traces | `GET /cases`, `GET /cases/{id}`, `GET /cases/{id}/trace` (task tree and delegations), `GET /cases/{id}/audit`, `GET /audit/verify?case_id=` | UI |
| Agent tools | `GET /tools/eligibility`, `GET /tools/authorizations`, `GET /tools/contract-rate`, `GET /tools/ncci-ptp`, `GET /tools/mue`, `GET /tools/policy-search`, `GET /tools/claim-history`, `POST /tools/documentation-requests` | Agents (service token) |
| Agent writes | `POST /tasks` (projection), `POST /findings`, `POST /proposals`, `POST /verifications`, `POST /critiques`, `POST /lessons`, `POST /instruction-versions`, `POST /agents/heartbeat` | Role-checked per agent |
| Human actions | `GET /reviews/queue`, `POST /reviews/{proposal_id}/decision` (approve, reject, edit), `POST /flags`, `POST /instruction-versions/{agent}/{version}/rollback`, `POST /cases/{id}/take-over` | Role-checked per human role |
| Metrics and learning | `GET /metrics/overview`, `GET /metrics/scoreboard`, `GET /agents`, `GET /learning/lessons`, `GET /learning/memory`, `GET /learning/instructions/{agent}`, `GET /learning/benchmarks` | UI |
| Demo and simulator | `POST /demo/scenarios`, `POST /payer-sim/submissions` | UI (demo), API internal |
| Live updates | `GET /stream` (SSE) | UI |

**SSE event types:** `case.updated`, `task.updated`, `delegation.created`, `finding.created`,
`proposal.created`, `verification.completed`, `critique.created`, `review.decided`,
`lesson.created`, `instruction.published`, `metric.updated`, `agent.heartbeat`. Each event carries
`id`, `ts`, `case_id?` and a minimal body; the UI refetches details through REST.

### 9.5 Database tables (Person 1 owns migrations; Person 3 co-owns `audit` and `learning`)

- `core`: `payer`, `payer_contract` (payer, CPT, rate or percent of CLFS, effective dates),
  `payer_policy` (structured rules: auth-required CPTs, covered ICD lists, frequency limits, appeal
  windows; plus policy text sections), `patient` (synthetic), `coverage` (member, payer, plan,
  effective dates, primary/secondary), `ordering_provider`, `requisition` (ordered tests, ICD codes),
  `authorization`, `claim`, `claim_line`, `remit`, `remit_adjustment` (group, CARC, RARC, amount),
  `document` (kind, text, page map, content hash), `reference_clfs`, `reference_ncci_ptp`,
  `reference_mue`, `reference_icd10`, `reference_carc`.
- `ops`: `case`, `screen_result`, `task`, `delegation_edge`, `finding`, `proposal`,
  `verification`, `critique`, `review_decision`, `flag`, `documentation_request`, `submission`,
  `payer_decision`, `routing_outbox`, `review_outbox`, `learning_outbox`, `agent_status`.
- `audit`: `audit_event` (`id`, `ts`, `case_id`, `task_id`, `actor`, `kind`, `summary`,
  `evidence_refs`, `policy_ids`, `instr_version`, `memory_ids`, `model_used`, `prev_hash`, `hash`).
  UPDATE and DELETE are revoked and blocked by trigger.
- `learning`: `agent_memory` (scope columns, text, embedding `vector`, source, source_ref, version,
  active), `lesson`, `instruction_version` (agent, version, diff, reason, author, benchmark_run_id,
  active, reverts_version), `benchmark_run`, `benchmark_case_result`, `metric`.
- `answer_key`: `planted_issue` (claim line, scenario, expected kind, expected action, expected
  recovery), `corrupted_output` (benchmark corruption type and target).

---

## 10. Controls (deterministic, in `common/policy.py` and enforced again in the API)

| ID | Rule |
|---|---|
| P-001 | Expected allowed = contracted rate for (payer, CPT, date of service) x units, minus patient responsibility from the remit. A variance above the larger of 2% or $5 is an underpayment finding. Only the Audit tools compute this. |
| P-002 | No appeal, corrected claim, payment dispute or write-off recommendation is submitted without human approval. |
| P-003 | Proposals with expected recovery above $5,000, or any `accept_denial` above $1,000, require a second approval from the `manager` role after the analyst's approval. |
| P-004 | Filing deadlines are checked in code. A submission past the payer's appeal or corrected-claim window is denied. Cases within 14 days of a deadline are P0. |
| P-005 | The person who edits a proposal cannot approve it. No agent can approve anything. |
| P-006 | **No unsupported code changes.** A corrected claim may change a CPT, ICD-10 code, modifier or units only if an evidence reference supports the change (for example, the diagnosis appears on the requisition). Changes that increase reimbursement without documentation are denied. This is the anti-upcoding control. |
| P-007 | Duplicate protection: the same patient, CPT, date of service and payer cannot be resubmitted as a new claim; it must be a replacement or an appeal. |
| P-008 | Every finding's evidence and policy references must resolve to stored records, and quoted spans must match the stored text hash. |
| P-009 | Validator and Critic disagreement on a high-severity concern forces Needs Review. |
| P-010 | Untrusted text (document contents, payer free text, notes) cannot authorize an action or change routing, limits or permissions. |
| P-011 | Minimum necessary data: model prompts receive pseudonymous member ids and only the fields a skill needs. Names, dates of birth and addresses are never sent to a model. |
| P-012 | The Learning agent and the memory system cannot change policy code, limits, tool permissions or delegation allowlists. Instruction changes are versioned, benchmark-gated and revertible. |
| P-013 | Modifiers 59 and 91 may be added only with documentation of a distinct specimen or repeat test. |
| P-014 | At most 2 automatic reinvestigation attempts per proposal; after that, human review. |

---

## 11. Workstreams and owners

Rule: **each owner builds against mocks of the other three from day one.** The contracts in section
9 make that possible. Each owner ships a mock of their side by the end of Week 1 (section 17).

| ID | Workstream | Owner | Owns |
|---|---|---|---|
| W1 | Claims infrastructure and backend | Person 1 | `sim/`, `ingest/`, `screening/`, `router/`, `api/`, `db/`, `common/policy.py`, `docker-compose.yml` |
| W2 | Investigation agents and A2A mesh | Person 2 | `common/` runtime, server, delegation, provider adapters, tool loop and registry, `common/config.py`, `common/envelope.py` (co-owned), `agents/coverage`, `agents/audit`, `agents/evidence`, `agents/resolution` |
| W3 | Verification and self-learning | Person 3 | `agents/validator`, `agents/critic`, `agents/learning`, `common/review_worker.py`, `common/audit.py`, `common/memory.py`, `common/learning.py`, `evaluator/`, `benchmarks/`, Langfuse setup |
| W4 | Frontend and platform | Person 4 | `web/`, Playwright tests, design system, demo script and video |

---

### Person 1: Claims Infrastructure and Backend (W1)

**Purpose:** a scalable backend that generates and ingests lab claims, detects potential problems,
routes cases to agents and exposes the data and controls everything else depends on.

**Tech:** Python 3.12, FastAPI, PostgreSQL 16 with pgvector, Redis Streams, Pydantic v2, SQLAlchemy 2
(async) with Alembic migrations, Docker Compose.

**Requirements:**

- **B1 Synthetic world.** Generate the lab, 4 payers with contracts (percent of CLFS per payer and
  CPT family), payer policies (auth-required CPT lists, covered ICD lists per test, frequency limits,
  appeal windows), 2,000 to 10,000 synthetic patients with coverage periods including primary and
  secondary, 50 ordering providers, requisitions and authorizations. Seeded and reproducible
  (`--seed`).
- **B2 Claims generator.** Produce 10,000 to 50,000 claims with realistic lab test mixes (routine
  chemistry and hematology, infectious disease, molecular), dates spread over 90 days, and matching
  remits. Render key documents (requisition, authorization letter, ABN, result report, submission
  receipt) as text with a page map and as PDF with a "SYNTHETIC" footer.
- **B3 Planted scenarios and answer key.** Inject the scenario taxonomy in section 13 at configurable
  rates (default about 15% of dollars), with clean decoys and correct denials mixed in. Write the
  answer key only to the `answer_key` schema.
- **B4 Payer simulator.** Adjudicates submitted appeals and corrected claims from the answer key with
  realistic delays and noise (for example, 85% overturn when the appeal includes the required
  evidence, 10% when it does not), and emits `appeal.decided` or `corrected_claim.decided`.
- **B5 Document desk simulator.** Answers `documentation_request` rows: returns the document after a
  delay if it exists in the world, or "not available" if the scenario says it is missing.
- **B6 Ingest pipeline.** Consume `claims.raw` with consumer group `ingest`, validate against
  Pydantic schemas, normalize (codes uppercase, amounts as `Decimal`, dates as UTC), dedupe on
  `event_id` and content hash, upsert into `core`, and publish to `claims.events`. Poison messages
  retry 3 times then go to `claims.dead_letter`. History events are marked and never routed.
- **B7 Rule-based screening (the highest-priority item in this workstream).** A versioned rules
  engine over claim lines and remits. Each rule returns a reason code, dollars at risk and evidence
  pointers:
  - R-01 denied line (paid 0 with a denial CARC)
  - R-02 underpayment versus contract (P-001)
  - R-03 partial denial on a multi-line claim
  - R-04 bundling denial (CARC 97 or similar) where a modifier may apply
  - R-05 authorization denial (CARC 197 or 15) where an authorization record exists
  - R-06 medical necessity denial (CARC 50) where the requisition has an additional diagnosis
  - R-07 duplicate denial (CARC 18) on a possible repeat test
  - R-08 timely filing denial (CARC 29) with a submission receipt on file
  - R-09 eligibility denial (CARC 27 or 31) where secondary coverage exists
  - R-10 no remit 30 days after submission
  - R-11 deadline within 14 days
  Priority score = dollars at risk x recovery likelihood prior (per rule, later fed by Learning
  outcomes) x deadline urgency. Screening 50,000 claims must finish in under 5 minutes.
- **B8 Case creation and routing.** One case per claim with all screen reasons. Write `case`,
  `screen_result` and `routing_outbox` in one transaction. `router/` claims outbox rows with
  `SELECT ... FOR UPDATE SKIP LOCKED`, sends A2A `investigate_case` to Resolution with a stable
  idempotency key, records the task mapping, and retries with backoff. Bounded in-flight per
  destination; P0 cases jump the queue.
- **B9 Claims API.** All endpoints in section 9.4, with OpenAPI docs, cursor pagination, indexed
  filters, p95 under 200 ms for queue queries on 50,000 claims. Service tokens per agent and session
  tokens per human role; role checks on every write.
- **B10 Controls.** Implement `common/policy.py` (`check(action, actor, payload) -> allow | deny |
  needs_approval(rule_id)`) for P-001 to P-007, P-010 and P-014, and call it inside every write
  endpoint. Unit tests per rule.
- **B11 Outboxes and SSE.** `review_outbox` and `learning_outbox` rows are written in the same
  transaction as the triggering write. `GET /stream` publishes the SSE events in section 9.4 using
  Postgres `LISTEN/NOTIFY`.
- **B12 Demo scenario injection.** `POST /demo/scenarios` accepts a preset (missing authorization,
  medical necessity, underpayment, bundling, correct denial) or a free-form description that is
  normalized into a claim and remit, then flows through ingest like any other event.
- **B13 Developer experience.** `docker compose up` brings up Postgres (pgvector image), Redis and
  optionally Langfuse. Make targets (section 18) work on Windows, macOS and Linux; launchers are
  Python scripts, not bash.

**Week 1 mock to ship:** migrations for every table, a seed of 500 claims with 10 fixed scenarios,
the API returning seeded data for all read endpoints, write endpoints that store without validation,
and a router stub that dispatches seeded cases.

**Done when:** 50,000 claims generate, ingest and screen in under 5 minutes; replaying the same raw
stream creates no duplicate claims or cases; a router restart loses no queued case; every planted
scenario that should be flagged is flagged (screening recall 100% on the answer key) and screening
precision is reported; API p95 targets are met; T1, T2, T3, T4, T11 and T19 pass.

**Depends on:** Person 2 for the A2A client helper used by the router; Person 3 for the audit writer
and the `learning` table design; Person 4 for read endpoint shapes.

---

### Person 2: Autonomous Claims Investigation Agents (W2)

**Purpose:** the A2A mesh and the four investigation agents that turn a flagged claim into an
evidence-backed proposal.

**Tech:** Python 3.12, `a2a-sdk` 1.x (pin the version FreightLine used, `1.2.3`, and confirm it is
still current before starting; many online examples target 0.x and are wrong), Pydantic v2, httpx,
uvicorn/Starlette, a provider adapter layer for model APIs with tool calling, pgvector (through the
API) for memory recall.

**Requirements: shared runtime (port from FreightLine):**

- **I1 Agent services.** Each agent is its own process with an Agent Card at
  `/.well-known/agent-card.json` and a JSON-RPC endpoint. Skills and ports come from
  `common/config.py`.
- **I2 Runtime base class.** `ClaimAgent` (adapted from FreightLine's `FreightAgent`) with
  `handle(env, meta, task_id, updater) -> ResultArtifact`, durable checkpointed `step()` stages,
  admission deduplication by idempotency key, and lease-based recovery so a killed agent resumes on
  restart without duplicate work.
- **I3 Delegation.** `delegate(skill, envelope, mode)` with `await`, `park` and `fanout`; guards from
  section 8; refusals and child failures surfaced as structured errors; every delegation posts a
  `delegation_edge` for the UI.
- **I4 Provider adapters.** One interface over at least one model provider with tool calling,
  structured outputs validated against Pydantic, retry and backoff, per-agent model configuration,
  and Langfuse tracing (trace per task, span per model and tool call, tagged with `case_id`, `agent`,
  `instr_version`).
- **I5 Tool loop and registry.** A bounded model-selected tool loop (max steps, max tokens, deadline)
  with a per-agent tool allowlist. Tools are typed functions that call the Claims API. Models cannot
  pass arbitrary SQL, URLs, amounts or code changes; amounts come only from deterministic tools.
- **I6 Context assembly.** Each task loads `instructions.md` at the active version and the top-k
  scoped memories (scope match on payer, CPT, CARC, skill first, then vector similarity), and records
  `instr_version` and `memory_ids` on the task and on every finding.
- **I7 Fixture mode.** With `CLAIMFORGE_MODE=fixture`, every agent runs a deterministic workflow with
  no model calls so tests and CI run offline.

**Requirements: the four agents:**

- **I8 Coverage agent.** Tools: `get_eligibility(member, dos)`, `get_coverage_order(member, dos)`,
  `get_authorizations(member, cpt, dos)`, `get_payer_policy(payer, cpt)`, `search_policy_text(q,
  payer)`, `check_dx_coverage(payer, cpt, icd_list)`. Outputs findings of kind `eligibility_issue`,
  `auth_issue`, `improper_denial` or `correct_denial`, each citing a policy section. Must distinguish
  "the payer's policy requires X and X is on file" from "X is missing".
- **I9 Audit agent.** Tools: `get_contract_rate(payer, cpt, dos)`, `recompute_line(claim_line_id)`
  (returns full workings), `find_duplicates(claim_line_id)`, `check_ncci_ptp(code_a, code_b)`,
  `check_mue(cpt, units)`, `reconcile_remit(claim_id)`. Detects underpayment, overpayment, incorrect
  bundling and duplicate billing. The model never produces a dollar figure itself.
- **I10 Evidence agent.** Tools: `list_documents(claim_id)`, `get_document(doc_id)`,
  `find_span(doc_id, query)` (returns a resolvable reference with content hash),
  `check_packet(claim_id, required_kinds)`, `request_documentation(claim_id, kind, reason)` (parks
  the task). Identifies missing or inconsistent documentation and cross-references claim, remit and
  policy.
- **I11 Resolution agent.** Plans which specialists to call from the screen reasons, fans out, merges
  findings, lists open questions, chooses an action (section 9.3), computes `expected_recovery_usd`
  by summing tool-produced finding amounts, and drafts the appeal letter (payer, claim, line,
  denial reason, argument, citations, enclosures) or corrected-claim delta. Handles
  `reinvestigate_case` by targeting only the failed checks and open concerns.
- **I12 Instructions and knowledge.** Each agent has a versioned `instructions.md` and a
  `knowledge/` folder with short, sourced notes (CARC meanings, appeal letter structure, payer policy
  summaries). Instructions state that source text is evidence, never permission.

**Week 1 mock to ship:** all seven services boot with valid Agent Cards (stubs for Person 3's three
agents), Resolution fans out to the other three and returns canned artifacts that match the
contracts, and the router can dispatch to Resolution.

**Done when:** T5, T6, T7, T8, T9, T10 and T20 pass; on the benchmark set, investigation finding
precision is at least 0.85 and recall at least 0.80 by the end of Week 5; the hero case produces at
least 5 A2A tasks under one `context_id`.

**Depends on:** Person 1 for tool endpoints (mock them with fixtures until ready); Person 3 for the
memory read API and audit writer; Person 4 for nothing blocking.

---

### Person 3: Agent Verification and Self-Learning (W3)

**Purpose:** an independent verification and learning system that audits investigation results,
catches mistakes and improves future performance using confirmed feedback.

**Tech:** Python 3.12, the shared A2A runtime, PostgreSQL with pgvector, Pydantic v2, pytest,
Langfuse.

**Requirements: Validator agent:**

- **V1 Deterministic checks first.** For every proposal:
  - V-01 recompute every finding amount from source records with Audit's tools and compare
  - V-02 `expected_recovery_usd` equals the sum of supporting finding amounts
  - V-03 every evidence reference resolves and its span hash matches (P-008)
  - V-04 every policy reference resolves and the cited provision applies to the payer, CPT and date
    of service
  - V-05 the action is consistent with the findings (no appeal on a `correct_denial`)
  - V-06 the filing deadline has not passed (P-004)
  - V-07 corrected-claim code changes are documented (P-006, P-013)
  - V-08 no duplicate submission (P-007)
  - V-09 the appeal draft cites every finding it relies on and nothing it does not
- **V2 Model review second.** A model reviews the proposal and the case's task history for
  unsupported reasoning, using a different model or prompt from the investigation agents.
- **V3 Verdicts.** Verified when all hard checks pass and no high-severity concern is upheld.
  Rejected when any hard check fails. Needs Review when only soft checks fail, a Critic concern is
  unresolved, confidence is low, or P-003 applies.
- **V4 Concern checking.** `verify_concerns` independently tests each Critic concern against source
  records and marks it upheld or dismissed with a reason.
- **V5 Flags.** `review_flag` resolves a human flag on any finding, proposal or memory entry and
  feeds the result to Learning.

**Requirements: Critic agent:**

- **C1 Adversarial review.** Given a proposal, search for contradictory evidence, overlooked policy
  provisions (for example, a frequency limit or an exclusion), hallucinated facts, unsupported
  assumptions and reasoning errors, using read-only tools.
- **C2 Structured concerns.** Output a `Critique` with typed, severity-rated concerns and counter
  evidence references. Never output a verdict.
- **C3 Hand-off.** Delegate concerns to the Validator (`verify_concerns`) and set
  `recommended_next: ["resolution.reinvestigate_case"]` when findings are incomplete. The review
  worker decides whether to act, within P-014.

**Requirements: Learning agent:**

- **L1 Triggers.** Runs on `learning_outbox` rows: Validator rejections, human edits and rejections,
  flags, and payer decisions.
- **L2 Analysis.** Classify the root cause (wrong rate table, missed document, misread policy,
  wrong action, missing modifier logic, and so on) and look for recurrence across cases with the same
  scope.
- **L3 Scoped memory.** Store a lesson only when it is validated by a Validator recheck, a human
  decision or a payer outcome. Lessons about one payer or code stay scoped to it; lessons about
  procedure are skill-wide. Embeddings are stored for similarity recall; scope filters apply first.
- **L4 Instruction patches.** Propose a unified diff against the agent's `instructions.md`. Patches
  may only target `instructions.md` (port FreightLine's patch applier and version reconstruction).
- **L5 Benchmark gate.** A patch is published only if, on the held-out benchmark split, it fixes the
  target failure class and does not lower precision by more than 1 point or raise the false appeal
  rate. The run id is stored on the instruction version.
- **L6 Rollback.** Any version can be reverted by a human with one action; a revert is a new version,
  never an edit.
- **L7 Prior updates.** Feed overturn rates by payer and rule back to screening's recovery likelihood
  priors (data only, never rule logic, per P-012).

**Requirements: platform pieces:**

- **V6 Review worker.** `common/review_worker.py` claims `review_outbox` and `learning_outbox` rows,
  dispatches Validator and Critic in parallel, collects the final verdict, triggers bounded
  reinvestigation (P-014), and moves the case to human review.
- **V7 Audit writer.** `common/audit.py` writes hash-chained `audit_event` rows per case
  (`hash = sha256(prev_hash + canonical_json(event))`), with `instr_version` and `memory_ids`. A
  verify function walks the chain. Works with Person 1's API transaction.
- **V8 Benchmarks.** Two datasets in `benchmarks/`:
  - corrupted claims (planted scenarios from section 13, with train and held-out splits)
  - corrupted outputs (valid proposals with injected errors: wrong math, wrong fee schedule year,
    fabricated evidence reference, misquoted policy, wrong action, past deadline, undocumented code
    change) to measure the Validator and Critic
- **V9 Evaluator.** `evaluator/` joins outcomes to the answer key and writes `metric` rows on a loop:
  the metrics in section 14.
- **V10 Langfuse.** Project setup, trace conventions shared with Person 2, and a cost-per-case
  report.

**Week 1 mock to ship:** Validator returns Verified for any proposal that has evidence references and
Rejected otherwise; Critic returns one canned concern; Learning logs its trigger; the audit writer and
chain verifier work against a test database.

**Done when:** T12 to T18 pass; the Validator catches at least 90% of corrupted outputs with a false
rejection rate under 10%; at least one instruction version shows a measured held-out improvement and
can be rolled back.

**Depends on:** Person 2 for the runtime and Audit tools (reused for recomputation); Person 1 for
outbox rows and tables; Person 4 for the learning dashboard.

---

### Person 4: Frontend and Platform (W4)

**Purpose:** a claims operations platform where the lab's analysts monitor autonomous
investigations, review verified findings and approve actions.

**Tech:** Next.js (App Router), React, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, TanStack
Table with virtualization, Server-Sent Events, React Flow for the agent graph (addition to the
brief's stack), Playwright for end-to-end tests, MSW for API mocks during Week 1 and 2.

**Requirements:**

- **F1 Design system.** Tokens, typography, color for status and severity, money formatting,
  empty/loading/error states and an accessible component set on shadcn/ui. Document it in
  `web/README.md`.
- **F2 Overview (`/`).** Billed, denied, underpaid, at risk, recovered; denial rate by payer and by
  CARC; upcoming deadlines; agent activity summary; live updates.
- **F3 Claims queue (`/claims`).** Server-side filtered, sorted, cursor-paginated table that stays
  smooth at 50,000 claims: filters for status, payer, CARC, CPT, screen reason, amount, deadline;
  saved views; bulk select to open cases.
- **F4 Claim and case detail (`/cases/[id]`).** Claim header and lines, remits with adjustment codes,
  screen reasons, findings with workings, the proposal and draft, a document viewer that highlights
  each cited span, and the policy provisions referenced.
- **F5 Agent trace (`/cases/[id]/trace`).** The A2A task tree and a live React Flow graph of
  delegations, with each task's status, artifact, model used, instruction version, memory ids,
  duration and cost; links to Langfuse traces.
- **F6 Verification view.** Validator checks (pass/fail, expected vs actual), Critic concerns with
  upheld or dismissed status, rejected findings and the corrective attempts between them.
- **F7 Human review inbox (`/review`).** Queue of Verified and Needs Review proposals; approve,
  reject or edit with a required reason; enforce P-003 and P-005 in the UI and show the API's denial
  when they apply; a role switcher for demos.
- **F8 Audit trail (`/audit`).** Per-case event log, chain verification status, filters by actor and
  kind, and a "why is this number here" panel for any amount (source, calculation, rule, agent,
  approver).
- **F9 Learning dashboard (`/learning`).** Lessons and memory by agent and scope, instruction version
  history with diffs and rollback, benchmark scores per version, recurring error classes over time.
- **F10 Agents page (`/agents`).** Seven agents with status, throughput, active and queued tasks,
  error rate, p50 latency and cost.
- **F11 Scoreboard.** Section 14 metrics, live.
- **F12 Demo console (`/demo`).** Inject preset or free-form scenarios, start a fresh run, and jump to
  the case.
- **F13 Flags.** A flag button on findings, proposals, tasks and memory entries that calls
  `POST /flags`.
- **F14 Real-time.** One SSE connection, mapped to TanStack Query invalidations; reconnect with
  backoff; fall back to polling when SSE is unavailable.
- **F15 Quality.** Playwright tests for the hero flow, review approval, rollback and queue filtering;
  Lighthouse accessibility score at least 90 on the main pages.
- **F16 Demo deliverables.** Demo script, 3-minute video and the README section on what is real,
  simulated and synthetic.

**Week 1 mock to ship:** app shell with navigation, the claims queue and case detail running on MSW
mocks generated from the section 9 contracts.

**Done when:** every page in F2 to F12 runs on the live API with SSE updates; T21 and T22 pass;
Playwright suite is green.

**Depends on:** Person 1 for API and SSE; Person 2 for trace data; Person 3 for verification,
learning and metrics data.

---

## 12. Repository layout and ownership

| Top-level path | Purpose | Owner |
|---|---|---|
| `agents/<service_id>/` | One A2A service per agent | Person 2 (coverage, audit, evidence, resolution), Person 3 (validator, critic, learning) |
| `common/` | Contracts, runtime, server, delegation, providers, tool loop, policy, audit, memory, learning, review worker | Person 2 (runtime), Person 1 (policy), Person 3 (audit, memory, learning, review worker) |
| `api/` | FastAPI Claims API and SSE | Person 1 |
| `db/` | Alembic migrations and seed | Person 1 (Person 3 co-owns `audit` and `learning`) |
| `sim/` | Synthetic lab, payers, document desk, payer simulator, answer key | Person 1 |
| `ingest/`, `screening/`, `router/` | Intake, rules engine, first-hop dispatch | Person 1 |
| `evaluator/`, `benchmarks/` | Scoring and benchmark datasets | Person 3 |
| `web/` | Next.js dashboard | Person 4 |
| `scripts/` | Cross-platform launchers and admin tasks | Shared, each owner for their scripts |
| `tests/` | Python tests by area | Each owner for their area |
| `docs/` | This PRD, runbooks, architecture notes | Shared |

---

## 13. Synthetic scenarios and answer key

Each scenario is planted at the claim-line level with an expected finding kind, expected action and
expected recovery. Decoys ensure the system is scored on what it should **not** do.

| Scenario | Who made the error | Signals | Expected action |
|---|---|---|---|
| S-01 Authorization on file but not on claim | Lab (omitted) or payer (ignored) | CARC 197; authorization exists before DOS | Appeal with authorization letter, or corrected claim with auth number |
| S-02 Missing supporting diagnosis | Lab | CARC 50; requisition has a covered ICD not on the claim | Corrected claim adding the documented diagnosis |
| S-03 Underpayment versus contract | Payer | Paid below contracted rate beyond tolerance | Payment dispute with workings |
| S-04 Incorrect bundling | Payer | CARC 97; distinct specimen documented | Corrected claim with modifier 59, or appeal |
| S-05 Legitimate repeat test denied as duplicate | Lab (no 91) or payer | CARC 18; two results with different collection times | Corrected claim with modifier 91 |
| S-06 Timely filing with proof | Payer | CARC 29; submission receipt within window | Appeal with receipt |
| S-07 Wrong payer order | Lab | CARC 27 or 22; secondary or other primary coverage on DOS | Bill the correct payer |
| S-08 Units above MUE without support | Lab | MUE exceeded, no documentation | Accept denial (decoy) |
| D-01 Coverage truly terminated | Correct denial | CARC 27; no other coverage | Accept denial or bill patient |
| D-02 True duplicate | Correct denial | CARC 18; same specimen | Accept denial |
| D-03 Not covered, no supporting diagnosis anywhere | Correct denial | CARC 50; no covered ICD in any record | Accept denial; bill patient only if an ABN is on file |
| D-04 Past appeal window | Correct denial | Deadline passed | Accept denial |
| D-05 Clean paid claim | None | Paid at contract | No case |

A planted mistake to appeal a correct denial counts against the false appeal rate. Any proposal that
adds an undocumented code (P-006) counts as a compliance failure and is reported separately.

---

## 14. Evaluation metrics

| Area | Metric | Definition |
|---|---|---|
| Screening | Recall, precision | Planted issues flagged / all planted issues; flagged cases with a real issue / all flagged |
| Investigation | Finding precision and recall | Per finding kind, against the answer key |
| Investigation | Correct action rate | Proposals whose action matches the expected action |
| Investigation | Dollars identified | Sum of correct expected recovery vs answer-key total |
| Safety | False appeal rate | Appeals or corrections proposed on correct denials / all correct denials investigated |
| Safety | Compliance failures | Proposals that violate P-006 or P-013, before verification |
| Verification | Validator catch rate | Corrupted outputs rejected or sent to review / all corrupted outputs |
| Verification | False rejection rate | Correct proposals rejected / all correct proposals |
| Verification | Critic concern precision | Concerns upheld by the Validator / all concerns raised |
| Learning | Held-out delta per version | Change in precision, recall and false appeal rate on the held-out split |
| Learning | Recurrence | Repeat rate of the same root-cause class per 100 cases over time |
| Outcome | Overturn rate, dollars recovered | From the payer simulator |
| System | Throughput, latency, cost | Claims screened per minute; p50 and p95 case resolution time; model cost per case |

---

## 15. Acceptance tests (shared definition of done)

| ID | Test | Owner |
|---|---|---|
| T1 | Generate, ingest and screen 50,000 claims in under 5 minutes; counts reconcile | P1 |
| T2 | Replaying the raw stream twice creates no duplicate claims, cases or tasks | P1 |
| T3 | Screening flags every planted issue and reports precision | P1 |
| T4 | Router restart with queued cases loses nothing and duplicates nothing | P1 |
| T5 | All seven Agent Cards resolve and validate | P2 |
| T6 | The hero case produces at least 5 A2A tasks under one `context_id`, each with an artifact | P2 |
| T7 | A delegation outside the allowlist, a cycle (forged `visited` list) and a depth-4 delegation are each refused and logged | P2 |
| T8 | Kill Audit mid-case, restart it, and the case finishes with no duplicate tasks | P2 |
| T9 | 20 concurrent cases plus one parked on documentation all finish | P2 |
| T10 | A model attempt to state a dollar amount not produced by a tool is rejected by schema | P2 |
| T11 | A corrected claim adding an undocumented diagnosis is denied by policy (P-006) in both the agent and the API | P1 + P2 |
| T12 | Every proposal gets a Validator verdict and a Critic review within 60 seconds of creation | P3 |
| T13 | A fabricated evidence reference is rejected (P-008) | P3 |
| T14 | A wrong fee schedule year is rejected and a bounded reinvestigation fixes it; a third failure goes to human review | P3 |
| T15 | The audit chain verifies; tampering with one row is detected | P3 |
| T16 | A seeded recurring mistake produces a scoped memory, and the next similar case cites its memory id | P3 |
| T17 | An instruction patch that regresses the held-out benchmark is blocked; one that improves it is published and can be rolled back | P3 |
| T18 | A human flag on a finding is resolved by the Validator and recorded as a lesson | P3 |
| T19 | A proposal above $5,000 is not submitted until a `manager` gives the second approval; an editor cannot approve their own edit | P1 + P4 |
| T20 | No prompt sent to a model contains patient names, birth dates or addresses (P-011) | P2 |
| T21 | The hero flow runs end to end in the UI with live updates and no page reload | P4 |
| T22 | The claims queue filters and sorts 50,000 claims with p95 interaction under 300 ms | P4 |

---

## 16. Compliance, privacy and responsible design

- Synthetic data only. No real PHI enters the repository, the database or any model prompt.
- The system is designed as if PHI were present: minimum-necessary prompts (P-011), redaction at the
  tool boundary, pseudonymous member ids, and no PHI in logs or Langfuse traces.
- Anti-upcoding is a hard control (P-006, P-013). The product recovers money the lab is owed; it
  never invents billable work.
- Humans approve every outbound action (P-002). The audit trail shows who approved what and why.
- Model output is evidence for a human, not a decision. Final amounts come from code.

---

## 17. Milestones (one week each; Week 1 starts when this PRD is accepted)

Every Friday the team stops for 30 minutes and runs the hero case together on `main`.

| Week | Milestone | Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|---|---|
| 1 | **M0: contracts frozen, mocks up** | Compose stack, migrations, 500-claim seed, read API on seed data, router stub | Runtime ported, seven services boot with cards, Resolution fan-out with canned artifacts | Audit writer and chain verify, Validator and Critic stubs, benchmark format | App shell, design tokens, queue and case detail on MSW mocks |
| 2 | **M1: spine end to end** | 10k-claim generator, ingest with dedupe and dead letter, rules R-01 to R-06, routing outbox | Real A2A dispatch from router; Coverage and Evidence with real tools; fixture mode | Validator checks V-01 to V-05; review worker; Langfuse | Queue and case detail on the live API; SSE wiring |
| 3 | **M2: investigation complete** | Rules R-07 to R-11; all tool endpoints; document desk simulator; policy P-001 to P-007 | Audit agent; Resolution consolidation and drafts; park/resume on documentation | Validator V-06 to V-09 and verdicts; Critic; corrupted-output benchmark | Trace view with React Flow; verification view; document span highlighting |
| 4 | **M3: verification and human loop** | Payer simulator; review decision endpoints with P-003 and P-005; demo scenario injection | Reinvestigation path; memory recall in context; crash recovery (T8) | Reinvestigation policy P-014; evaluator metrics; corrupted-claims benchmark splits | Review inbox; audit trail page; agents page; flags |
| 5 | **M4: learning and scale** | 50k-claim scale and performance tuning (T1, T22 support) | Precision and recall tuning against benchmarks; cost tuning | Learning agent, scoped memory, instruction patches, benchmark gate, rollback | Learning dashboard; scoreboard; demo console |
| 6 | **M5: hardening and demo** | Load test; bug fixes | All T5 to T10 green; bug fixes | All T12 to T18 green; final benchmark report | Playwright suite; demo script; video; README |

After Week 1, contract changes need both owners' agreement and a change-log entry here.

---

## 18. Conventions

- Python 3.12, Pydantic v2, ruff (line length 110), pytest with `pytest-asyncio`. Node LTS for `web/`.
- Make targets (each backed by a Python launcher so they work on Windows): `setup`, `infra`, `api`,
  `agents`, `sim`, `ingest`, `screen`, `router`, `review-worker`, `evaluator`, `web`, `test`, `lint`,
  `demo` (fixture hero case across the real A2A mesh), `bench`.
- `.env.example` lists every variable; never commit keys. `CLAIMFORGE_MODE=fixture|live`.
- IDs: `CLM-#####`, `LINE-#####`, `CASE-####`, `DOC-#####`, `POL-###`, `PAY-##`, `TASK-###`
  (display), `EVT-…`.
- Agent rules (mirroring FreightLine): subclass the runtime base class and implement `handle()`;
  delegation only through `delegate()`; every state-changing tool calls `policy.check()` first;
  contracts change only with both owners.
- Git: one branch per workstream (`p1/...`, `p2/...`, `p3/...`, `p4/...`), atomic Conventional
  Commits, PRs into `main` reviewed by one other person, `main` must always pass `make lint test` and
  run `make demo`.

---

## 19. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Model provider rate limits or cost | Fixture mode for development; per-agent model config; cache tool results; cost per case on the scoreboard |
| A2A SDK version differences | Pin the version; port FreightLine's runtime and tests first; keep the transport behind one helper module |
| Synthetic data looks unrealistic | Base rates, codes and coverage rules on public CMS reference files; review a sample with someone who has done medical billing |
| CPT or X12 code licensing | Use code numbers and our own labels; avoid redistributing licensed descriptors (open question 2) |
| The Validator rubber-stamps | Measure catch rate on corrupted outputs every week; different model or prompt from investigators |
| Learning writes bad memory or instructions | Validated-only lessons, scopes, benchmark gate, one-click rollback, P-012 |
| Performance at 50k claims | Indexes from day one, cursor pagination, server-side filtering, load test in Week 5 |
| Scope creep | Section 4 non-goals; pre-bill scrubbing is stretch only and starts after M4 |

**Stretch (only after M4):** pre-bill scrubbing that runs the same agents before submission; an
email-style documentation request to a team inbox; multi-provider model comparison for the Critic.

---

## 20. Open questions (owner resolves, then updates this document)

1. Which model provider and models per agent, and the budget. Owner: Person 2, with Person 3 for
   Validator and Critic.
2. Licensing terms for CPT descriptors and the CARC/RARC lists; what we can store and display.
   Owner: Person 1.
3. Langfuse cloud or self-hosted in Docker Compose. Owner: Person 3.
4. Final demo date, so Week 6 can be pinned to a calendar date. Owner: team.
5. Names for Person 1 to Person 4 in this document. Owner: team.

---

## Change log

- v1.0 (Nov 10, 2026): initial PRD built from the team brief. Resolved conflicts D1 to D6 (diagnostic
  lab buyer, 7-agent roster with appeal drafting under Resolution, pure A2A runtime adapted from
  FreightLine, PostgreSQL plus pgvector and Redis Streams, SSE, six-week semester plan).
