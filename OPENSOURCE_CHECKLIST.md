# Open-source packaging checklist

Confirm each row before publishing this repo (`ai-attestation`) as a standalone OSS tree.

## File classes

| Class | Status | Notes |
|-------|--------|-------|
| Python backend (`.py`) | Done | Docstrings/comments/env cleaned; `paths.py` uses `ATA_HOME` / `.ai_attestation/` |
| Frontend (`.ts` / `.tsx` / `.js`) | Done | Brand: ai-attestation |
| Marketing website | Done | Brand + neutral evidence-chain copy |
| Config / YAML / JSON templates | Done | Shared/standard descriptions neutralized |
| Markdown docs / README / CONTRIBUTING | Done | Root `CONTRIBUTING.md` + `SECURITY.md` |
| Tests + CI | Done | `backend/tests/` + `.github/workflows/ci.yml` |
| LICENSE | Done | MIT |
| `.gitignore` | Done | Ignores `.next/`, `node_modules/`, `data/`, `.env` |

## Sensitive categories

| Category | Cleared |
|----------|---------|
| Non-product methodology jargon | Yes (evidence chain / audit proxy) |
| Obsolete / alternate product names | Yes (brand is **ai-attestation** only) |
| Absolute personal machine paths in source | Yes |
| Secrets / credentials in tree | Yes |
| Branded env vars / data dirs | Keep product `ATA_HOME` / `.ai_attestation/` |

## Pre-publish smoke checks

```bash
cd backend/app
PYTHONPATH=. python -c "from paths import product_data_root; from main import app; print(product_data_root(), app.title)"
cd ..
PYTHONPATH=app python -m pytest tests/ -q
```

Optional grep gate: expect zero matches for obsolete brands / internal status labels
(exclude `node_modules` / `.next` / `.venv`). Maintain a private forbidden-token list locally;
do not commit third-party product names into this repository.
## Sign-off

- [x] Maintainer reviewed `SENSITIVE_CLEANUP_LOG.md`
- [x] Maintainer ran pytest smoke
- [x] Maintainer confirmed no secrets in tree
- [x] Ready to publish (MVP caveats documented in README + SECURITY.md)
