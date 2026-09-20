# Architecture

`model-effort-router` separates generative work from bounded decisions:

1. The host AI proposes two or three explicit task-decomposition candidates.
2. Jev selects one candidate with a typed `choice` question.
3. The router derives the finite `model x effort` choices allowed for each task.
4. Jev answers those independent routing questions in one request.
5. Ordinary code validates the answers, preserves confidence and probabilities,
   and groups the selected tasks into dependency-safe parallel levels.

Jev does not generate task text, execute tasks, or grant authority. The host AI
creates candidates; the caller remains responsible for permissions and dispatch.

## Why two Jev decisions

Routing questions depend on the selected decomposition. Sending routing questions
for every candidate would ask irrelevant questions and make the result ambiguous,
so the workflow uses one call to choose a decomposition and one call to route all
tasks in that decomposition.

## Failure boundaries

- Missing `TYPESAFE_API_KEY`: emit framework-only request payloads; never claim
  Jev participated.
- Unknown or malformed API response: stop before dispatch.
- Low-confidence answer: surface the task for human review.
- Invalid dependency graph or unavailable model/effort pair: reject the input.
- Secrets or personal data: callers must remove them before creating Jev state.

This is an unofficial integration. Jev is a TypeSafe AI service and is not part
of this repository.

## Checkpoint gate

Workers can emit a compact checkpoint before dependent work or external effects.
The checkpoint contains the task's understanding, acceptance checks, completed
work, evidence references, uncertainties, blockers, and proposed action. It does
not contain chain-of-thought.

The router sends two independent Choice questions to Jev:

- next_action: continue, revise, human_review, or stop;
- risk_class: no_known_risk, input, implementation, integration, or evaluation
  failure.

Only continue plus no_known_risk, with both answers above the configured
confidence threshold, produces pre_dispatch_guard: pass. Every other result
produces human_review and prevents automatic release of dependent work.

Use the CLI with --checkpoint or call review_checkpoint directly. This is a
direct Jev integration; an MCP facade can be added later without changing the
checkpoint contract.
