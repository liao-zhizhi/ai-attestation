# Security Policy

## Supported versions

This repository ships an **open-source MVP**. Security fixes are accepted on the default branch (`main`) when practical.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Prefer one of:

1. GitHub **Private vulnerability reporting** on this repository (Security tab), if enabled.
2. Contact the maintainer via the GitHub profile linked from the repository.

Include: affected component, reproduction steps, impact, and any suggested fix.

We will acknowledge reports when we can and coordinate disclosure after a fix or mitigation is available.

## Deployment warnings (MVP)

- Bind the API to **localhost** or a trusted network by default (`127.0.0.1`). Do not expose an unmodified MVP to the public internet.
- Unknown dashboard/proxy keys are **rejected** (fail-closed). Provision via `POST /v1/keys` or the local demo bootstrap key; treat demo keys as **dev-only**.
- Proxy upstream override (`X-Upstream-Base`) is constrained, but operators should still set `ATA_UPSTREAM_ALLOWLIST` / avoid forwarding secrets to untrusted hosts.
- Default demo keys are for local development only. Set your own keys via `POST /v1/keys`. Do not enable `ATA_EXPOSE_DEMO_KEY` in shared environments.
- Request/response bodies are hashed and not persisted by design; still avoid sending unnecessary secrets through the proxy.

## Cryptographic claims

Local timestamp receipts and mock chain anchors are **MVP stand-ins**, not independent third-party proofs. See `docs/` and in-product notes before relying on them for high-assurance audit.
