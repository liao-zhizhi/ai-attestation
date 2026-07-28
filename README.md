# ai-attestation — Open-Source AI Behavior Audit Proxy

**产品名：ai-attestation**

> Open-source AI API audit proxy with a tamper-proof SHA-256 evidence chain.  
> 开源 AI API 行为审计代理：多厂商转发、费用计量、合规检查、可独立验证的防篡改证据链。  
> 状态：开源 MVP（技术验证工具，不构成法律意见或认证审计）。

## Disclaimer / 安全提示

- This is **not** a certified audit, legal opinion, or compliance certification product.  
- 本工具**不构成**法律意见、认证审计或行业标准定义。  
- **Do not expose an unmodified MVP to the public internet.** Bind the API to `127.0.0.1` for local use; provision keys via `POST /v1/keys` (demo bootstrap may seed one local key). See [`SECURITY.md`](./SECURITY.md).

## License

MIT — see [`LICENSE`](./LICENSE).

## Demo

| Surface | URL (local defaults) |
|---------|----------------------|
| Dashboard | http://127.0.0.1:3002 |
| Marketing site | http://127.0.0.1:3003 |
| API health | http://127.0.0.1:8004/health |
| API docs | http://127.0.0.1:8004/docs |

Public demo / GitHub URLs can be set via `NEXT_PUBLIC_DASHBOARD_URL`, `NEXT_PUBLIC_GITHUB_URL`, `NEXT_PUBLIC_PROXY_URL`.

## 🎯 这东西是干什么的？ / What is this?

就像给 AI 调用装上 **行车记录仪 + 计价器 + 可公证黑匣子**：

- **不是替你开车**（我们不做模型，不拼算力）
- **而是留下不可随意篡改的行程与费用证据**
- 需要时给交警、保险公司或甲方查

👉 一句话：客户买的不是「我们更懂 AI」，而是 **出事时能对账、能重放、能给第三方验** 的决策保险。

Like a **dashcam + meter + notarizable black box** for AI API calls:

- **We don’t drive for you** (no models, no GPUs)
- **We leave tamper-evident trip and cost evidence**
- So police, insurers, or your customer can check when needed

👉 One line: buyers are not paying for “we know AI better” — they pay for **decision insurance**: reconcile, replay, and third-party verify when something goes wrong.

## 功能清单 / What it does / does not

**Does:** multi-vendor API proxy · SHA-256 tamper-evident hash chain · cost metering · query-as-audit · compliance-as-code (multi-standard YAML) · custom template editor · check evidence drill-down · independent timestamp · chain-head blockchain anchor (Sepolia mock by default) · shareable verify page · offline verify pack · OSCAL-style export · behavior baseline / drift marks · enterprise dashboard · async DB writes · report email · API key roles · CSV/JSON export  

**Does not:** claim to define industry standards · private opaque evidence formats · full blockchain node · production TEE · ZKP · multi-stage RBAC · real-time WebSocket · mobile apps · Stripe billing

## Quick start

### Backend (`:8004`)

```bash
cd backend/app
# optional: export ATA_HOME=/path/to/data-home
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8004
```

Optional env: `ATA_TEE_MODE=exploratory`, `ATA_ANCHOR_RPC` + `ATA_ANCHOR_PRIVATE_KEY`, per-vendor `ATA_UPSTREAM_*`, SMTP `ATA_SMTP_*`, `ATA_DASHBOARD_URL` (default `http://localhost:3002`).

### Dashboard frontend (`:3002`)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3002
```

Verify page: `http://localhost:3002/verify/{report_hash}?p={pack_token}`

### Marketing website (`:3003`)

```bash
cd website
npm install
npm run dev
# → http://localhost:3003
```

## Integration

```text
SDK base_url     →  http://127.0.0.1:8004/v1/proxy
Header           →  X-Attest-Key: <your_ata_key>
Authorization    →  Bearer <upstream_vendor_key>
Optional         →  X-Attest-Vendor / X-Upstream-Base
```

Without an upstream key, use **Simulate one call** in the dashboard (`POST /v1/demo/simulate`).

## Modules

| Capability | Location |
|------------|----------|
| Cost metering | `backend/app/metering.py` |
| Hash chain | `backend/app/attestation.py` |
| Query-as-audit | `backend/app/query_audit.py` |
| Compliance | `compliance_catalog.py` + `compliance.py` + `compliance-templates/` |
| Behavior baseline / drift | `backend/app/behavior.py` |

## Compliance templates

Open tree: `compliance-templates/` (`checks/shared.yaml` + `standards/*.yaml`).

| ID | Notes |
|----|-------|
| `eu_ai_act_transparency` | EU AI Act transparency |
| `us_ai_executive_order` | US AI EO (assessment / red team) |
| `cn_genai_measures` | China GenAI measures |
| `iso_iec_42001` | ISO/IEC 42001 |
| `soc2_type_ii_ai` | SOC 2 Type II (AI services) |

Override root with `ATA_COMPLIANCE_TEMPLATES_DIR`. Data root uses `ATA_HOME` (product path; keep as-is).

## API (summary)

| Method | Path | Notes |
|--------|------|-------|
| `*` | `/v1/proxy/{path}` | Multi-vendor proxy + async attestation write |
| GET | `/v1/dashboard/overview` | Today / 7-day trend / vendors |
| GET | `/v1/dashboard/calls/export` | CSV/JSON export |
| GET | `/v1/dashboard/attestation` | Chain integrity + anchor |
| GET/POST | `/v1/public/verify` | Public verify (no login) |
| GET | `/v1/public/badge/{hash}.svg` | Status badge |
| POST | `/v1/public/notarize` | Third-party notarize hints |

Full interactive docs: `/docs` (title: **ai-attestation**).

## Tests

```bash
cd backend
PYTHONPATH=app python -m pytest tests/ -q
```

CI runs backend pytest plus `frontend` / `website` production builds (see `.github/workflows/ci.yml`).

## Privacy

- Does **not** persist request/response bodies — only byte lengths and SHA-256 digests  
- MVP has no PII redaction pipeline

## Contributing / 贡献

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) (中英双语).  
Compliance templates / 合规模板：[`compliance-templates/CONTRIBUTING.md`](./compliance-templates/CONTRIBUTING.md).  
Packaging checks / 打包检查：[`OPENSOURCE_CHECKLIST.md`](./OPENSOURCE_CHECKLIST.md).

Security reports / 安全报告：**[SECURITY.md](./SECURITY.md)**（do not open public Issues for unpatched vulns / 请勿用公开 Issue 报告未修复漏洞）.
