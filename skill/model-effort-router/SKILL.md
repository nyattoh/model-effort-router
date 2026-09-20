---
name: model-effort-router
description: Decompose a request into a dependency-aware task graph, use Jev choice questions as an independent routing signal when available, select only supported model and effort combinations, dispatch independent work in parallel, and validate the combined result. Use when a request benefits from multi-agent task decomposition, model routing, effort routing, or evidence-aware fan-in across Codex, Claude, Gemini, or another agent host.
---

# Model Effort Router

Route work by task needs rather than by a fixed model hierarchy. Treat Jev as an
independent decision signal, never as an authority.

This is an unofficial TypeSafe integration. Do not imply endorsement,
certification, or an official relationship with TypeSafe. TypeSafe service terms
may restrict publication of benchmarks or performance information. Do not publish
Jev benchmarks or comparative performance claims unless the user has confirmed
that their agreement permits it.

## Outcome

For one input request, produce and execute a routing plan that:

1. proposes two or three plausible decompositions;
2. selects one decomposition with a typed finite choice;
3. selects a supported `model x effort` option for every task;
4. dispatches dependency-ready tasks in parallel by DAG level; and
5. validates and synthesises all results at fan-in.

Do not create subagents when the host, user, or applicable project instructions
forbid delegation. In that case, return the proposed routing plan and execute it
serially or hand it over, as the host permits.

## Operating modes

### Jev-backed mode

Use this mode only when all of the following are true:

- a Jev adapter is available;
- `TYPESAFE_API_KEY` is configured in the execution environment;
- sending the compact decision state is authorised; and
- an independent signal can materially affect the route.

Ask one `choice` question for decomposition selection, then one `choice` question
per task for model-effort selection. Questions that share the same non-sensitive
state may be bundled if the adapter supports it.

Record the concrete Jev model identifier, selected option, confidence or
probability when supplied, and usage metadata when supplied. Never expose an API
key or authorisation header.

### Framework-only mode

Use this mode whenever Jev-backed mode is unavailable. Apply the same finite
options and routing criteria locally, but state exactly:

`Jev API call: not made`

Set `decision_source` to `framework_only_local`. Do not describe the result as a
Jev answer, Jev recommendation, or Jev choice.

Never ask the user to paste an API key into chat. Never print, persist, or include
the key in routing state, task prompts, logs, or artefacts.

## Required host capabilities

Use the host's equivalent of these abstract operations:

- `get_capabilities()` returns available models, supported effort values,
  concurrency limits, context limits, and delegation restrictions;
- `jev_choice(state, question, options)` returns one typed option in Jev-backed
  mode;
- `dispatch(task, model, effort)` starts one bounded task;
- `await_any(handles)` waits for progress or completion without busy polling;
- `send_follow_up(handle, message)` requests a bounded correction when supported;
- `cancel(handle)` stops work only when cancellation is authorised and safe.

Do not assume operation names, model names, effort values, or concurrency limits.
Discover them at runtime. See [references/adapters.md](references/adapters.md) for
host-specific mapping examples.

## Workflow

### 1. Establish constraints and capability catalogue

Read the input request and applicable project instructions. Identify:

- desired outcome and acceptance criteria;
- authorised write, network, publication, and delegation scope;
- time, cost, latency, and concurrency constraints;
- tasks that require shared mutable state or a human decision; and
- currently supported model-effort pairs from `get_capabilities()`.

Never invent a model or effort setting. Treat a model-effort pair as eligible only
if the current host explicitly reports it. If no capability catalogue is
available, use the current model and default effort and mark routing capability as
`UNVERIFIED`.

### 2. Build compact, safe decision state

Include only facts needed for routing:

- request summary;
- acceptance criteria;
- known constraints;
- relevant evidence and uncertainty;
- supported model-effort pairs; and
- budget and concurrency limits.

Exclude credentials, secrets, private tokens, personal information, raw private
repository contents, and unrelated user data. Prefer summaries and opaque task
identifiers. If necessary evidence cannot be shared with Jev, use framework-only
mode for that decision.

Keep these layers separate throughout:

- `evidence`: measured or inspected facts;
- `decision_signal`: Jev output, or an explicit framework-only local decision;
- `synthesis`: the router's final decision and rationale.

### 3. Generate two or three decomposition candidates

Create two candidates by default and a third only when it represents a materially
different trade-off. Each candidate must contain:

- a stable candidate ID;
- bounded tasks with one primary deliverable each;
- dependencies as task IDs;
- ownership boundaries for shared files or resources;
- acceptance checks;
- expected parallelism and critical path; and
- risks, including merge or evidence risks.

Candidates must be valid DAGs. Reject circular dependencies, hidden hand-offs,
duplicate ownership, or plans that exceed host concurrency or user authority.

Prefer useful differences such as:

- minimal task count versus greater parallelism;
- specialist investigation before implementation versus direct implementation;
- one integrator task versus distributed ownership with an explicit merge task.

Do not manufacture superficial alternatives with renamed tasks.

### 4. Select the decomposition

Ask a finite unordered choice question:

```text
Which decomposition best satisfies the acceptance criteria under the stated
authority, dependency, cost, latency, and evidence constraints?
```

Options are the valid candidate IDs plus `insufficient_evidence`. In Jev-backed
mode, use `jev_choice`. In framework-only mode, use the same options and decide
locally. A Jev signal does not override observed constraints, user authority, or
project instructions.

If `insufficient_evidence` is selected, gather the minimum missing evidence or ask
one focused user question. Do not dispatch an under-specified graph.

When the signal conflicts with evidence, inspect the assumptions causing the
disagreement. Prefer a minimum discriminating check over voting or averaging.

### 5. Build model-effort options per task

For each task, filter the live capability catalogue by hard constraints first:

- tool and modality access;
- context capacity;
- write or network permissions;
- model-effort compatibility;
- latency, cost, and concurrency budget; and
- any user-mandated model or effort.

From the remaining pairs, create a small finite option set. Do not rank by model
name alone. Evaluate task-specific needs:

- ambiguity and reasoning depth;
- coding or domain specialisation;
- blast radius and reversibility;
- amount of evidence to reconcile;
- verification burden; and
- urgency and cost sensitivity.

Always include `insufficient_capability` unless only one valid pair exists and the
host requires direct use of it.

Use one choice question per task:

```text
Which supported model-effort pair is the least costly option likely to satisfy
this task's deliverable and acceptance checks within its constraints?
```

The options must encode exact catalogue keys, for example
`capability:model_a:medium`; examples are identifiers only, not recommendations.

In Jev-backed mode, call `jev_choice`. In framework-only mode, select locally and
record `framework_only_local`. If `insufficient_capability` is selected, revise
the task boundary, run it on the current agent if feasible, or request a human
decision. Never silently substitute an unsupported pair.

### 6. Dispatch by DAG level

Compute DAG levels so every task at level `n` depends only on completed tasks from
earlier levels. Then:

1. dispatch dependency-ready tasks at the same level concurrently, up to the
   discovered concurrency limit;
2. give each worker a bounded prompt containing its task, inputs, ownership,
   acceptance checks, selected model-effort pair, and required result contract;
3. tell workers that other workers share the workspace and that they must not
   revert others' edits;
4. wait efficiently using `await_any`, collecting progress without busy polling;
5. validate every result before releasing dependent tasks; and
6. stop the level on an unsafe conflict, missing authority, or failed prerequisite.

Do not parallelise tasks that mutate the same files or external resource unless
the plan defines non-overlapping ownership and a deterministic integration step.

Each worker result must contain:

```yaml
task_id: string
status: complete | partial | blocked | failed
deliverables: []
evidence: []
validation_run: []
unverified: []
risks: []
hand_over: string
```

### 7. Fan-in and validate

After every terminal task has returned, run an explicit integrator pass. The
integrator must:

- verify all task IDs and expected deliverables are present;
- distinguish completed, partial, blocked, failed, and unverified work;
- check interface, schema, terminology, and ownership consistency;
- resolve contradictions against primary evidence, not majority vote;
- run acceptance checks proportionate to the combined change;
- check that no secret or personal information entered state or artefacts;
- confirm actual model-effort selections were supported at dispatch time; and
- compare the integrated result with the original request, not just subtask
  completion claims.

Request a bounded correction only when its target and acceptance check are clear.
Do not repeatedly retry an unchanged failure. If a correction cannot be made
within scope, preserve the failure and report the exact blocker.

### 8. Report

Return a concise routing record containing:

- operating mode and whether a Jev API call was made;
- considered decomposition candidates and selected candidate;
- each task's selected model-effort pair and decision source;
- DAG levels and actual dispatch outcome;
- fan-in validation performed and its result;
- failures, unverified claims, and remaining user decisions; and
- Jev disagreement with evidence, if any.

Do not claim that routing quality, model superiority, cost savings, or speed-up was
proved unless a separately authorised and methodologically valid evaluation did
so. Do not publish Jev service benchmarks without confirmed permission.

## Invariants

- User and project authority outrank any routing signal.
- Jev is a signal, not proof or an authority.
- Framework-only mode never impersonates a Jev call.
- Capability discovery precedes model-effort selection.
- Only dependency-ready, non-conflicting tasks run in parallel.
- Evidence and failures survive fan-in; they are not averaged away.
- Secrets and personal information never enter decision state.
- Completion means original acceptance criteria passed or remaining gaps were
  reported explicitly.

## Jev choice response and dispatch guard

Assign a stable `qid` to each decomposition and task-routing question. Keep each
task as an independent `choice` decision: confidence for one task must never raise
or replace confidence for another. When several independent questions share the
same non-sensitive state, prefer sending them in one Jev call.

Each `choice` question may contain at most 255 choices. Keep normal routing sets
much smaller and include `other` when the listed choices may not cover a valid
answer. Keep `insufficient_evidence` and `insufficient_capability` as explicit
options when they trigger distinct control flow.

For Jev-backed decisions, parse and retain:

- `model`;
- `answers[qid].type`;
- `answers[qid].choice`;
- `answers[qid].confidence`;
- `answers[qid].probabilities`; and
- `usage`.

Before dispatching each task, run a pre-dispatch guard. Dispatch automatically
only when `answers[qid].type` is `choice`, the selected value is one of the offered
model-effort options, and the answer satisfies the deployment's configured
confidence policy.

An `other`, `insufficient_evidence`, or `insufficient_capability` selection, or a
missing, malformed, error, out-of-set, or low-confidence answer, produces
`human_review` and must not trigger automatic dispatch. The adapter must not
invent a confidence threshold.

Preserve each task's confidence and probability distribution independently in the
audit record. Do not interpret confidence or probabilities as proof.

Do not copy third-party speed or accuracy figures into public documentation.
TypeSafe/Jev performance information remains subject to the publication guardrail
above.

## Resources

- [references/adapters.md](references/adapters.md): map abstract operations to
  Codex, Claude, Gemini, and other hosts.
- [examples/routing-plan.json](examples/routing-plan.json): minimal portable
  routing record showing framework-only mode.
