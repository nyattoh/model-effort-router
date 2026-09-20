# model-effort-router

[Japanese README](README.ja.md) | English

`model-effort-router` decomposes an incoming request by selecting one supplied
task-DAG candidate, then assigns a supplied `(model, effort)` pair to each
selected task. It is an offline-first Python 3.11+ library and CLI with no
runtime dependencies.

The routing policy is designed to be usable by any AI orchestrator: callers
provide their own model catalogue, effort levels, capabilities, task
requirements, and execution layer. This project selects a plan; it does not
invoke a model provider or execute the resulting tasks.

## Status and scope

- **Alpha:** the public input/output contract is intentionally small and may
  change before 1.0.
- **No benchmark claims:** this repository does not publish Jev or TypeSafe
  performance comparisons or benchmarks.
- **TypeSafe is an unofficial optional integration:** it is not affiliated
  with, endorsed by, or supported by TypeSafe.
- The TypeSafe Choice primitive response shape is based on the
  [official Choice documentation](https://docs.typesafe.ai/primitives/choice).
  Live compatibility has been verified with a public synthetic fixture. Actual
  host dispatch and provider capability discovery remain caller responsibilities.

## Input contract

Pass JSON on standard input to the CLI:

```json
{
  "request": "Add audit logging to the service",
  "constraints": {
    "language": "Python",
    "public_api": "stable"
  },
  "candidates": [
    {
      "id": "small-change",
      "description": "Implement and test the isolated change",
      "tasks": [
        {
          "id": "implement",
          "description": "Implement audit logging",
          "depends_on": [],
          "requirements": ["python"],
          "allowed_pairs": [
            {"model": "gpt-5.6-terra", "effort": "high"}
          ]
        }
      ]
    }
  ],
  "models": [
    {
      "id": "gpt-5.6-terra",
      "provider": "openai",
      "efforts": ["low", "medium", "high"],
      "capabilities": ["python"],
      "description": "General implementation model"
    }
  ],
  "max_parallel": 1
}
```

`constraints`, task `requirements`, task `allowed_pairs`, model
`capabilities`, and model `description` are optional. `constraints` is a JSON
object. A candidate's tasks form
a DAG through `depends_on`; every dependency must name another task in that
candidate. `allowed_pairs` uses `{ "model": "...", "effort": "..." }`
objects when supplied.

Run:

```powershell
python -m pip install -e .
python -m model_effort_router examples/request.json
```

The router performs two choices:

1. Select a decomposition candidate.
2. For every task in that candidate, select a permitted model-and-effort pair.

It returns JSON suitable for an external scheduler. The scheduler remains
responsible for enforcing `depends_on` and `max_parallel`.

## Portable agent skill

The provider-neutral skill is in
[`skill/model-effort-router/SKILL.md`](skill/model-effort-router/SKILL.md).
An agent host can read it directly or copy the complete
`skill/model-effort-router` directory into its local skills directory. Keep the
directory intact so the relative links to `references/` and `examples/` work.

Host-specific operation mappings for Codex, Claude, Gemini, and generic
orchestrators are isolated in
[`references/adapters.md`](skill/model-effort-router/references/adapters.md).
The core workflow and JSON contract do not depend on any one provider.

## Token reduction measurement

The reproducible fixture measures per-worker dispatch context, not provider
billing, latency, quality, or model performance:

~~~powershell
python scripts/measure_token_reduction.py examples/request.json --json-out docs/token-reduction-results.json --svg-out docs/token-reduction.svg
~~~

![Estimated dispatch-context token reduction](docs/token-reduction.svg)

For the supplied fixture, the full-context baseline is **1,720 estimated tokens**
and the task handoff is **377 estimated tokens**: **1,343 fewer tokens
(78.08%)**. This uses a transparent four-characters-per-token estimate and
should not be read as a provider tokenizer or a performance claim.

## Checkpoint gate

Workers can submit a compact, evidence-backed checkpoint before dependent work
or external effects. The router asks Jev for a next action and a risk class,
then releases work only when both answers pass the configured confidence policy.
Otherwise it returns human_review.

~~~powershell
python -m model_effort_router examples/checkpoint.json --checkpoint --dry-run
~~~

Use review_checkpoint from the Python API for an integrated host adapter.
Checkpoints contain evidence and uncertainty, not chain-of-thought.

## Jev modes and privacy

When `TYPESAFE_API_KEY` is absent, this is **framework-only / dry-run mode**:
the router emits the decomposition and assignment Choice payloads for local or
human resolution and makes **no external network request**. It does not invent
a selected plan and does not imply that Jev was called.

When a trusted environment supplies `TYPESAFE_API_KEY` and `--dry-run` is not
set, the CLI automatically sends the compact routing state to TypeSafe: one call
selects the decomposition and, if that passes the confidence policy, a second
call selects model-effort pairs for its tasks. Use `--dry-run` to guarantee no
Jev network call even when the key is present. Keep the key in the environment
or a secret manager; never put it in input JSON, source control, or logs.

Only compact, non-secret decision state belongs in any optional external
request. Do **not** send credentials, tokens, personal data, private source
code, raw repository contents, or other secret state to TypeSafe. The CLI is
safe by default: without the key it performs no external communication.

Unknown, malformed, or incomplete provider responses are **fail closed**.
They must not be converted into a guessed selection; callers receive an error
and can retry in framework-only mode after inspection.

The default confidence threshold of `0.5` is a conservative, configurable
dispatch policy, not an empirically calibrated accuracy claim. A selection
below the configured threshold produces `needs_review` and no assignments.

## Development

```powershell
python -m unittest discover -s tests -v
```

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Security
reports belong in [SECURITY.md](SECURITY.md).

## Licence

Licensed under [Apache-2.0](LICENSE).
