# Host adapter guide

The core skill uses abstract operations so its policy stays portable. This guide
shows how to map those operations to a host. These are illustrative mappings, not
promises that a tool exists in every version or environment. Inspect the live tool
definitions before use.

## Adapter contract

An adapter should expose these logical operations:

| Operation | Required behaviour |
| --- | --- |
| `get_capabilities()` | Return supported model-effort pairs, concurrency, context, tools, permissions, and delegation restrictions. |
| `jev_choice(...)` | Submit only a compact non-sensitive state and a finite unordered choice; return the selected option and available metadata. |
| `dispatch(...)` | Start one bounded task with exact model and effort keys, or fail without substitution. |
| `await_any(...)` | Wait for completion or attention across active tasks without busy polling. |
| `send_follow_up(...)` | Send a bounded correction or clarification to one task. |
| `cancel(...)` | Stop a task only when authorised; report whether state may be partial. |

Adapters must never translate an unsupported model-effort pair into a different
pair silently. They should return a typed capability error to the router.

## Codex-style hosts

Typical mapping:

- capability catalogue: inspect the live agent/thread tool schema and applicable
  project instructions;
- dispatch: spawn a bounded subagent, or create a user-visible task only when the
  user explicitly requested a separate task;
- wait: use the host's multi-agent wait primitive;
- follow-up: send a task-scoped message or follow-up;
- cancellation: use the host's interrupt operation.

Illustrative pseudocode:

```text
catalogue = inspect_live_agent_capabilities()
handle = spawn_subagent(
  task=bounded_prompt,
  model=catalogue[selection].model,
  effort=catalogue[selection].effort
)
event = wait_for_agents(handles)
```

Do not assume that a visible task/thread creator is the same as an internal
subagent dispatcher. Respect the host's distinction.

## Claude-style hosts

Typical mapping:

- capability catalogue: inspect the current Task/Agent tool definition, enabled
  model aliases, permissions, and team limits;
- dispatch: invoke a task/agent tool with one bounded prompt and explicit model
  only when the live schema supports it;
- wait: use the host's task status or blocking result mechanism;
- follow-up: resume or message the same task when supported;
- cancellation: stop through the task control interface.

Illustrative pseudocode:

```text
catalogue = inspect_live_task_tool()
handle = task_agent(
  prompt=bounded_prompt,
  model=catalogue[selection].model,
  effort=catalogue[selection].effort_if_supported
)
result = task_result(handle)
```

Some Claude environments do not expose a separate effort control. Represent that
as one supported pair using the host default; do not invent an effort parameter.

## Gemini-style hosts

Typical mapping:

- capability catalogue: inspect the current agent/tool configuration and provider
  model list;
- dispatch: use the available subagent or task primitive if one exists;
- wait and follow-up: use its task lifecycle operations;
- otherwise: execute the DAG serially in the current agent while retaining the
  routing record.

Illustrative pseudocode:

```text
catalogue = inspect_live_gemini_capabilities()
if catalogue.supports_subagents:
  handle = dispatch_agent(bounded_prompt, catalogue[selection])
else:
  result = execute_serially(bounded_prompt)
```

Do not infer subagent support from a model name or provider brand.

## Generic CLI or API hosts

Wrap the provider with a small adapter that:

1. loads an allow-listed capability catalogue from current configuration;
2. validates the exact model-effort pair before each request;
3. carries a task ID and dependency IDs in request metadata;
4. bounds parallelism with a semaphore or worker pool;
5. captures exit status, provider model ID, usage, and validation evidence; and
6. redacts credentials and personal information before logs are written.

The adapter may use provider APIs, a local process runner, or a queue. The routing
policy must not depend on which transport it uses.

## Jev adapter

The Jev adapter is separate from the worker host adapter. It should:

- read `TYPESAFE_API_KEY` only from the process environment;
- accept JSON-serialisable, non-sensitive state;
- validate that every choice answer matches an option ID;
- return the concrete Jev model identifier and confidence/probability when the
  service supplies them;
- redact request headers and never log the key; and
- return an error or `human_review` when a live call fails; framework-only mode
  may be selected explicitly after inspection.

Do not label framework-only local output as Jev output. Network failure after an
attempt is also not a Jev decision unless a valid typed answer was received.

### Credential contract

- Read only TYPESAFE_API_KEY from the host process environment.
- Never depend on a particular vault product, item name, user profile, or path.
- Let CI, containers, desktop launchers, and secret managers inject the same
  environment variable.
- Treat a missing key as framework-only mode; never invent or persist a value.
- A skill or plugin installation does not configure the key. The host process
  must inherit it before Jev-backed execution starts.
- Check presence without revealing the value with
  python -m model_effort_router --check-api-key.

## Capability catalogue example

```json
{
  "source": "live_host_introspection",
  "concurrency_limit": 3,
  "pairs": [
    {
      "key": "capability:model_a:low",
      "model": "model_a",
      "effort": "low",
      "tools": ["read", "search"],
      "writes": false
    },
    {
      "key": "capability:model_b:high",
      "model": "model_b",
      "effort": "high",
      "tools": ["read", "search", "edit", "test"],
      "writes": true
    }
  ]
}
```

The names above are placeholders. Replace them only with values reported by the
current host.
