# Contributing / 贡献指南

Thanks for helping improve **ai-attestation**.  
感谢参与 **ai-attestation**。

---

## English

### Issues

- Search existing issues first.
- Include: **expected behavior / actual behavior / reproduction steps** (commands, environment, versions, relevant logs).
- Security vulnerabilities: follow [`SECURITY.md`](./SECURITY.md). **Do not** open a public issue.

### Pull requests

1. Fork the repo and branch from `main`.
2. Keep changes small and focused; match existing code style (naming, layout, typing habits).
3. Do not commit secrets, `.env`, local `data/*.db`, `.next/`, or `node_modules/`.
4. In the PR body, explain **what changed and why**.

### Compliance templates

1. Add or edit YAML under `compliance-templates/` (`standards/` for standards, `checks/` for shared checks).
2. Follow existing template format; see that folder’s `CONTRIBUTING.md` / `README.md`.
3. Keep wording factual and evidence-oriented; avoid overclaiming “certification” or legal conclusions.

### Tests before submit

```bash
cd backend
PYTHONPATH=app python -m pytest tests/ -q
```

If you touched the frontend:

```bash
cd frontend && npm run build
# optional marketing site:
cd website && npm run build
```

### Local development (optional)

```bash
# Backend
cd backend/app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8004

# Dashboard
cd frontend && npm install && npm run dev
```

---

## 中文

### 提交 Issue

- 先搜索是否已有相同问题。
- 写清：**期望行为 / 实际行为 / 复现步骤**（命令、环境、版本、相关日志）。
- 安全漏洞请走 [`SECURITY.md`](./SECURITY.md)，**不要**开公开 Issue。

### 提交 Pull Request

1. Fork 本仓库，从 `main` 拉新分支。
2. 改动尽量小而聚焦；代码风格对齐现有文件（命名、目录结构、类型习惯）。
3. 不要提交密钥、`.env`、本地 `data/*.db`、`.next/`、`node_modules/`。
4. PR 描述写清**改了什么、为什么改**。

### 合规模板贡献

1. 在 `compliance-templates/` 下新增或修改 YAML（标准见 `standards/`，共享检查见 `checks/`）。
2. 格式参考现有模板；字段含义见该目录的 `CONTRIBUTING.md` / `README.md`。
3. 模板措辞保持可验证、证据导向，避免夸大「认证」「合规结论」。

### 提交前跑测试

```bash
cd backend
PYTHONPATH=app python -m pytest tests/ -q
```

有前端改动时，建议再跑：

```bash
cd frontend && npm run build
# 如改了宣传站：
cd website && npm run build
```

### 本地开发（可选）

```bash
# 后端
cd backend/app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8004

# 仪表盘
cd frontend && npm install && npm run dev
```
