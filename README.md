# AI Behavior Attestation Layer

**English** · [中文说明 →](./README.zh-CN.md)

> **Your AI can do anything. Can you prove what it did?**

An open-source, independently verifiable evidence layer for AI API calls and research priority.

**Live demo:** [ai-attestation.com](https://ai-attestation.com) · **License:** MIT

---

## The hook

**July 2026.** Elon Musk acknowledged that his AI company uploaded customers’ private code without consent.

**What if he had not admitted it?**

**September 2026.** Tristan Buckmaster and Levent Alpöge had privately worked for nearly a year on a blow-up solution to the Navier–Stokes equations, and uploaded an unpublished draft to OpenAI Codex for assistance. OpenAI then ran a large swarm of AI agents along the same obscure path and claimed the proof.

The fight is not “who is better at math.” It is:

- When did I already have this idea? **There is no evidence.**
- Which model did I talk to, and what did I say? **The vendor’s word.**
- Did I consent to training use? **A memory.**
- How would a journal or institution check? **Screenshots.**

**Today, AI companies’ behavior rests on self-attestation.** They can see your data, call your APIs, and make decisions that hit your business — and no independent third party can audit what they actually did.

We built this. We shipped our first public version in September 2026.

---

## What we built

**A third-party attestation layer that does not depend on any AI vendor.**

| Capability | What it does |
|---|---|
| **API call attestation** | Point your SDK `base_url` at our proxy. Every call appends a SHA-256 hash chain. **Bodies are not stored.** |
| **Research priority deposit** | Before you send a draft to any AI, hash it locally in the browser and write the fingerprint onto the chain. |
| **Offline verify pack** | One-click ZIP with `verify.html`. Works **offline, on another machine, without our servers.** |
| **Public verify link** | A URL a counterparty can open. Chain integrity, no login, no download. |
| **Compliance as code** | Open templates (EU AI Act, China’s Interim Measures for the Management of Generative AI Services, and more), versioned and runnable. |

In one line: customers are not buying “we know AI better.” They are buying **decision insurance** — reconcile, replay, and let a third party verify when something goes wrong.

---

## Why open source

**Attestation only works if it is open.**

A closed audit tool cannot prove it did not tamper with the data. Code, algorithms, and verification methods have to be public, or a third party cannot independently recompute them.

Compliance templates and verification methods are MIT. The hosted product is the batteries-included path. If you do not trust us, fork it, run it, and verify it yourself.

---

## Who this is for

- **Teams that ship AI features** and need a paper trail when a client asks “what did the model do?”
- **Researchers** who want a timestamped fingerprint *before* a draft goes into someone else’s model
- **Buyers, auditors, and counterparties** who should not have to trust a vendor-console screenshot
- **Not** a stand-in for counsel, a notary, or a full GRC suite

---

## Honest boundaries

**This can support:**

- A given hash existed at a given time
- An API call happened and request/response hashes were not rewritten on our chain
- The hash chain is intact

**This cannot prove:**

- A vendor trained on or read your content
- Your paper strictly predates someone else’s
- A substitute for counsel, a notary, or a qualified TSA (trusted timestamp authority)
- That a court will admit it

We would rather draw the line now than have you discover it in a fight.

---

## Quick start

### Hosted (fastest)

1. Open [ai-attestation.com](https://ai-attestation.com) → **Key Management** → create a key → copy `ata_xxxxxx`.
2. Point your SDK at the proxy:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://ai-attestation.com/v1/proxy",
    api_key="sk-your-upstream-key",  # DeepSeek / OpenAI / Anthropic / …
    default_headers={
        "X-Attest-Key": "ata_your_key",
    },
)

resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "hello"}],
)
```

3. Back on the site → **API Call Log** → open a row → inspect the hash chain.
4. Call detail → **Export Verify Pack** → unzip → open `verify.html`.
   No network, no login, no need to trust us.

Without an upstream key, use **Simulate a Call** in the dashboard (`POST /v1/demo/simulate`).

### Self-host

```bash
# API — http://127.0.0.1:8004
cd backend/app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8004

# Dashboard — http://127.0.0.1:3002
cd frontend
npm install && npm run dev
```

Local proxy: `http://127.0.0.1:8004/v1/proxy` with header `X-Attest-Key`.
Optional env: `ATA_HOME`, `ATA_SMTP_*`, `ATA_DASHBOARD_URL`, `ATA_UPSTREAM_*`. See the source and [`SECURITY.md`](./SECURITY.md) — **do not expose an unmodified MVP to the public internet.**

```bash
cd backend && PYTHONPATH=app python -m pytest tests/ -q
```

---

## Relation to SAIR's Open Math Model Initiative

In September 2026, Terence Tao and fellow Fields Medalists launched SAIR Foundation's Open Math Model Initiative, which states three principles:

- Data should not enter training sets without explicit researcher consent
- Model outputs must have traceable provenance
- Results must be reproducible and independently checkable

AI Behavior Attestation Layer provides the technical implementation for all three:

- **Explicit consent**: per-vendor training-consent records, each change appended to the evidence chain
- **Traceable provenance**: research priority deposit and call-to-artifact timeline
- **Reproducible checks**: offline verify packs and public verify links

We are not affiliated with SAIR and do not replace its governance framework — we provide the "verifiable evidence" layer beneath it.

## FAQ

**How is this different from LLMOps tools?**
LLMOps helps you debug and monitor *your* app. We are a vendor-independent third party: not OpenAI’s console, not Anthropic’s, not anyone’s. The hash chain can be recomputed offline by anyone. LLMOps is for your team. This is for customers, auditors, and counterparties.

**Do you store our prompts and completions?**
No. API attestation stores hashes, not bodies. Research deposit is stricter: the browser hashes locally; only a 64-character fingerprint is uploaded.

**Can a customer really verify without you?**
Yes. The ZIP includes `verify.html`. Offline, another laptop, no our servers. Public verify links need no download.

**Is this legally binding?**
We produce technical evidence and a timeline — not a legal opinion, and not a substitute for a notary. See **Honest boundaries**.

**Can you prove OpenAI trained on our data?**
**No, and we will not say that.** We can show that you possessed some content at a point in time (fingerprint + timestamp), and that a call to a vendor happened (hash chain). Whether the vendor trained on it is a question for *their* logs and legal process.

**If it is open source, why not just fork?**
You can. Templates and verification are MIT. Hosting is the “give a customer a link” path: no server, no verify page, no share-token ops. Fork to learn; use hosted when a counterparty needs a URL today.

**Pricing?**
Open source is free. Hosted is trial / subscription. We are in a pilot.

---

## Architecture

```text
Your SDK
   │
   ▼
/v1/proxy  ──►  upstream (OpenAI / Anthropic / DeepSeek / Zhipu / …)
   │
   ├─ hash only; no bodies
   ├─ SHA-256 chain: prev_hash → chain_hash
   └─ unified evidence chain
         │
         ▼
    dashboard · compliance · offline pack · public verify URL
```

- Backend: FastAPI + SQLite
- Frontend: Next.js 14
- Crypto: SHA-256 chain, local timestamp; optional OpenTimestamps / on-chain anchor
- License: MIT

---

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). We especially want:

- Compliance YAML templates
- Vendor adapters
- Security review of the verify path

---

## Contact

- Issues: GitHub Issues
- Demo: [ai-attestation.com](https://ai-attestation.com)
- ICP: 粤ICP备2026110101号 · 粤公网安备44195302000214号

**Vulnerabilities:** email, do not file a public issue. See [`SECURITY.md`](./SECURITY.md).

## License

MIT © 2026 liao-zhizhi
