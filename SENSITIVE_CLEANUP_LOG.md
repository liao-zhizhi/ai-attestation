# Sensitive cleanup log (open-source packaging)

Scope: `ai-attestation` open-source repository.  
Date: 2026-07-22 (updated 2026-07-27)  
Goal: ship **ai-attestation** as a standalone MIT project with neutral product language only.

## Summary

| Batch | Change |
|-------|--------|
| Brand | README, package.json, pyproject.toml, FastAPI title, UI/website → **ai-attestation** |
| Paths | Repo-relative paths; data dir → `.ai_attestation/` / `ATA_HOME` |
| Copy | Neutral language: evidence chain / audit proxy / compliance check templates |
| Artifacts | Removed local build caches and generated email samples that carried old branding |
| Hardening | Auth fail-closed on unknown keys; write-buffer / full-chain verify fixes |

## Keep as product identifiers

- `ATA_HOME`, `.ai_attestation/` data layout via `backend/app/paths.py`
- Product brand **ai-attestation**
- Public vendor names (OpenAI, etc.) and regulations (EU AI Act, ISO 42001, …)

## Deliverables

- `README.md`, `LICENSE`, `pyproject.toml`, `CONTRIBUTING.md`, `SECURITY.md`
- This log + `OPENSOURCE_CHECKLIST.md`
