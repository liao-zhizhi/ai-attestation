# Contributing to ai-attestation

Thanks for helping improve this open-source AI API audit proxy.

## Ways to contribute

1. **Compliance check templates** — add or refine YAML under `compliance-templates/` (see that folder’s `CONTRIBUTING.md`).
2. **Core proxy / evidence chain** — bug fixes and small, reviewable improvements in `backend/app/`.
3. **Dashboard / website** — UX clarity and docs in `frontend/` and `website/`.
4. **Tests** — extend coverage under `backend/tests/`.

## Development setup

```bash
# Backend
cd backend/app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
uvicorn main:app --host 127.0.0.1 --port 8004

# Dashboard (another terminal)
cd frontend && npm install && npm run dev

# Optional marketing site
cd website && npm install && npm run dev
```

## Tests

```bash
cd backend
PYTHONPATH=app python -m pytest tests/ -q
```

## Pull requests

- Keep PRs focused; prefer small diffs over large refactors.
- Do not commit secrets, `.env`, local `data/*.db`, or build caches (`.next/`, `node_modules/`).
- Match existing naming: product brand is **ai-attestation**; prefer neutral terms (evidence chain, audit proxy).
- Describe *why* the change matters in the PR body.

## Scope reminders

This project is an **MVP technical tool**. It does not define industry standards or provide legal certification advice. Template wording should stay factual and evidence-oriented.
