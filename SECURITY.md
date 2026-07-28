# Security Policy / 安全政策

---

## English

### Reporting a vulnerability

Please report security issues by email:

**security@ai-attestation.com**

(Placeholder address — the maintainer will replace it with a real contact later.)

Include when possible: affected component, reproduction steps, impact, and any suggested fix.

### Do not disclose publicly

- **Do not** report unpatched vulnerabilities in public GitHub Issues or Discussions.
- If Private vulnerability reporting is enabled on this repository, you may use that as well.

### Response commitment

We commit to **respond within 48 hours** of a valid report, and to coordinate disclosure after a fix or mitigation is available.

### MVP deployment notes (brief)

- Bind the API to `127.0.0.1` by default; do not expose an unmodified MVP to the public internet.
- Demo keys are for local use only; issue your own keys in production and keep demo exposure disabled.

---

## 中文

### 如何报告漏洞

请通过邮件报告安全问题：

**security@ai-attestation.com**

（占位邮箱，维护者后续会替换为真实联系方式。）

报告时请尽量包含：影响组件、复现步骤、影响范围、可行的修复建议。

### 请勿公开披露

- **不要**在公开 GitHub Issue / Discussion 中报告未修复的安全漏洞。
- 如仓库已开启 GitHub Private vulnerability reporting，也可一并使用。

### 响应承诺

我们承诺在收到有效报告后 **48 小时内** 予以响应，并在修复或缓解方案就绪后协商披露时机。

### MVP 部署提醒（简要）

- 默认将 API 绑定 `127.0.0.1`，勿把未加固的 MVP 直接暴露公网。
- 演示密钥仅限本地；生产请自行签发密钥并关闭演示暴露开关。
