# Contributing

Thank you for improving `model-effort-router`.

## Local checks

Use Python 3.11 or later and only the standard library for runtime code.

```powershell
python -m unittest discover -s tests -v
python -m pip install -e .
python -m model_effort_router examples/request.json
```

## Contribution expectations

- Keep routing deterministic when `TYPESAFE_API_KEY` is absent.
- Validate candidate task graphs and fail closed for unknown external-choice
  responses.
- Do not add telemetry or transmit request state by default.
- Never commit secrets, private prompts, API keys, or provider response logs.
- Add or update focused `unittest` coverage for changed behaviour.
- Keep changes small and describe their validation in the pull request.

By contributing, you agree that your contribution is licensed under Apache-2.0.
