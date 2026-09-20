# Security policy

## Supported versions

Security fixes are provided for the latest released version on the `main`
branch while the project is in alpha.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or exposed secret.
Contact the repository maintainers privately through the security contact
published by the hosting service. Include affected version, reproduction
steps, impact, and any safe mitigation you found.

Do not include API keys, access tokens, personal data, or private source in a
report. We will acknowledge receipt, assess the report, and coordinate a fix
and disclosure timeline when appropriate.

## Secret handling

`TYPESAFE_API_KEY` is read only from the process environment for an optional
integration. Never commit it, add it to request JSON, or paste it into issues.
