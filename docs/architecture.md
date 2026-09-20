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
