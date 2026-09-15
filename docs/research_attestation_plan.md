# 科研优先权与 AI 隐私见证模块 · 分析与改进方案

**产品：** ai-attestation  
**仓库：** https://github.com/liao-zhizhi/ai-attestation  
**文档性质：** 实施前方案（本文确认前不写业务代码）  
**读者：** 创始人、产品、工程  
**日期：** 2026-09-16  

> **一句话：** 现有系统已经能给「API 调用」装上行车记录仪；科研优先权争议还缺「草稿哈希存证」「训练同意记录」「可交给期刊的优先权证书」。本方案用**新表、新接口、新页面**补上，不改现有 API 行为、不改旧表字段、不破坏现有离线验证包。

---

## 写给非技术读者的摘要

2026 年 9 月的争议（未发表 NS 方程草稿进入 Codex、厂商集中算力、署名与训练数据伦理）暴露的不是「谁更会做数学」，而是：

1. **我什么时候已经有这个想法？** —— 需要不可随意改写的时间与哈希。
2. **我和哪家 AI、说了什么（哈希层面）？** —— 需要独立第三方见证，而不是厂商自己说。
3. **我有没有同意拿去训练？** —— 需要可审计的同意状态，而不是口头回忆。
4. **期刊/机构怎么验？** —— 需要能离线打开的证据包，而不是登录某家控制台。

本产品**已经具备**第 2 点的「API 通道」雏形（多厂商代理 + SHA-256 链 + 离线 ZIP）。  
**尚未具备**第 1、3、4 点面向科研场景的专用能力。

**法律边界（全文适用）：** 本工具提供技术证据与时间线，**不构成法律意见、不构成法院采信保证、不能证明某家模型「一定训练了某份草稿」**。它证明的是：「在本系统记录中，某哈希在某时刻进入了一条可复核的证据链。」

---

## 1. 现有系统能力盘点

### 1.1 产品定位（已实现）

开源 MVP：多厂商 AI API **审计代理**。用户把 SDK 的 `base_url` 指到本服务 `/v1/proxy`，本服务转发上游（OpenAI / Anthropic / DeepSeek 等），**只保存长度与 SHA-256，不保存请求/响应原文**，并写入防篡改哈希链。

本地默认入口：

| 界面 | 地址 |
|------|------|
| 仪表盘 | http://127.0.0.1:3002 |
| 宣传站 | http://127.0.0.1:3003 |
| API | http://127.0.0.1:8004 |

鉴权：仪表盘与代理使用 `ata_…` 见证 Key（`X-Attest-Key` 或 query）；上游厂商 Key 仍走 `Authorization`。角色：`read_only` / `read_write` / `admin`。代理至少需要 `read_write`。

### 1.2 数据流（已实现）

```
用户 SDK / 仪表盘「模拟一条调用」
        │
        ▼
  /v1/proxy  或  /v1/demo/simulate
        │
        ├─ 鉴权 require_key
        ├─ 识别厂商（路径 / Host / 模型名）
        ├─ 转发上游（哈希后丢弃正文）
        ├─ 计量 tokens / 费用
        └─ 计算 prev_hash → chain_hash，异步写入 SQLite
                │
                ▼
     api_calls + attestation_chain
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
   仪表盘    合规检查    离线 ZIP / 公开验证页
```

要点：

- **热路径不存原文**（隐私默认）。
- **统一哈希链**：调用、查询、合规、行为基线、漂移标记都可以挂到同一条 `attestation_chain` 上（用 `event_type` + `ref_id` 区分），不必为科研场景另起一条「无法对照」的链。
- **写入缓冲**：代理路径先算链再批量落库（现有实现）；科研存证建议同步写入，避免「我点了存证但 10 秒后才落盘」的优先权歧义。

### 1.3 前端页面（已实现）

单页仪表盘 `frontend/app/page.tsx`，左侧菜单（`Sidebar.tsx`）：

| 菜单 | 作用 |
|------|------|
| 操作手册 | 小白四步：Key → 设置 → 调用 → 导出验证包 |
| 仪表盘 | 今日调用/费用、趋势、厂商分布、最近调用 |
| API 调用记录 | 列表、查询即审计、导出 CSV/JSON |
| 合规管理 | 多标准检查、历史报告、缺口分析、自定义模板 |
| 行为监控 | 基线、漂移标记 |
| 防篡改证明 | 链完整、链头锚定 |
| 设置 / Key | 订阅报告、角色、签发 Key |
| （独立路由）`/verify/{report_hash}` | 合规报告公开验证，无需登录 |

调用详情弹窗（`CallDetail.tsx`）：展示时间、模型、哈希四元组，按钮「验证完整性」「导出验证包」。

**没有「科研见证」菜单。** 操作手册不覆盖「上传草稿哈希 / 训练同意 / 优先权证书」。

### 1.4 数据库表（已实现，本方案不改字段）

SQLite 文件：`data/attest.db` 或 `ATA_HOME/.ai_attestation/attest.db`。

| 表 | 用途 |
|----|------|
| `api_calls` | 每次代理/模拟调用：endpoint、vendor、model、status、tokens、cost、request_hash、response_hash、prev_hash、chain_hash |
| `attestation_chain` | 统一链：hash、prev_hash、timestamp、event_type、ref_id |
| `query_history` | 查询即审计 |
| `compliance_checks` | 合规运行结果 |
| `behavior_baselines` / `drift_marks` | 行为基线与漂移 |
| `api_keys` | Key、角色、状态 |
| `report_subscriptions` / `report_history` | 邮件报告 |
| `chain_anchors`（anchoring 模块） | 链头区块链锚定 |

`attestation_chain.event_type` 现有取值包括：`call`、`query`、`compliance`、`baseline`、`drift_mark`、`drift_review`。  
**新增科研事件只需插入新的 event_type 行，不必 ALTER 旧表结构。**

### 1.5 主要 API（已实现，路径与行为冻结）

代理与记录：

- `*` `/v1/proxy/{path}`
- `POST /v1/demo/simulate`
- `GET /v1/dashboard/calls`、`/calls/{id}`、`POST …/verify`
- `GET /v1/reports/{report_id}/export` → 单次调用离线 ZIP

链与时间戳：

- `GET /v1/dashboard/attestation`
- `POST /v1/dashboard/attestation/anchor`
- `POST /v1/dashboard/timestamp`（对任意 payload_hash 盖本地 TSA 收据）
- `POST /v1/public/notarize`（OpenTimestamps / 链上锚定操作说明）

合规与行为：标准列表、检查、缺口、导出 json/pdf/txt/oscal、verify-pack、offline-pack、基线与漂移。

公开验证：`GET/POST /v1/public/verify`（**现有实现面向合规报告包**，不是科研优先权包）。

### 1.6 离线验证包（已实现，格式冻结）

**A. 单次 API 调用包**（`build_call_offline_zip`）

| 文件 | 含义 |
|------|------|
| `call.json` | 见证字段，**不含 api_key、不含原文** |
| `chain.json` | 邻接链片段 + `meta.adjacency_trusted` |
| `verification.json` | 导出时服务端校验 |
| `verify.html` | 浏览器重算 `chain_hash`（与 Python `\|` 拼接规则一致） |
| `README.txt` | `python -m http.server 8765` 后打开 |

**B. 合规报告包**（`build_offline_zip`）

`report.json` + `pack.json` + `chain.json` + `verification.json` + `verify.html` + `README.txt`。

**约束：** 不得改 A/B 的文件名、字段语义与校验算法。科研优先权包必须用**新 ZIP 形态**（见第 7 节），例如 `artifact.json`，避免与 `call.json` 混用导致旧包打不开。

### 1.7 合规模板中与「训练数据」相关的现状

`compliance-templates/checks/shared.yaml` 已有人工项：

- `training_data`：披露训练数据来源
- `user_data_training`：用户数据是否用于训练须有可审计政策

EU AI Act / 中国生成式办法 / ISO 42001 / SOC2 模板引用了这些组。

**缺口：** 这些是「对照隐私政策做人工勾选」，**不是**「每一次科研交互当时的同意开关记录」，也**不能**自动证明 OpenAI/Anthropic 是否拿某次对话去训练。

### 1.8 时间戳与锚定（已实现，效力有限）

- 本地 TSA：`SHA256(payload_hash | unix | nonce)`，平台自签，可离线重算。
- OpenTimestamps：尽力 ping 日历，完整 `.ots` 仍需用户本地客户端。
- 链头锚定：默认 Sepolia **mock**；配置 RPC 后可发真实交易。

对科研优先权：**本地 TSA 足够做 MVP 演示**；对外给期刊时，P1/P2 应引导用户把 **artifact_hash** 提交到 OpenTimestamps 或链上，减少「证据只存在你们服务器」的质疑。

### 1.9 文档与依赖

- `docs/tee_exploratory.md`、`docs/zkp_feasibility.md`：TEE/ZKP **不做产品化**；优先哈希链 + 外部时间戳。
- 后端依赖很少：FastAPI、httpx、PyYAML、python-multipart。科研模块 **不必** 引入重型密码学库即可做 P0。

---

## 2. 与事件的差距分析

### 2.1 事件里真正需要被证明的事实

对照公开争议点（学术优先权、数据伦理、署名、工具商变竞争对手、科研隐私、训练数据）：

| 争议点 | 需要的证据形态 | 今天有没有 |
|--------|----------------|------------|
| 「我在日期 T 已持有草稿/推导 X」 | 内容哈希 + 可信时间 + 独立可验证包 | **部分**：有通用 `timestamp` API，**没有**「研究工件」对象、证书、小白流程 |
| 「我把 X 交给了哪家模型、何时」 | 厂商、模型、时间、prompt/response 哈希 | **部分**：仅当用户走 `/v1/proxy`；**Codex/Chat 网页用不了代理** |
| 「当时是否允许用于训练」 | 用户声明 + 可选服务商政策版本哈希 | **弱**：仅有合规模板人工项，无逐次/逐工件记录 |
| 「给期刊/机构，不依赖 OpenAI 后台」 | 离线 ZIP + 公开验证页 | **部分**：调用包/合规包可用；**没有「优先权证书」叙事与字段** |
| 「厂商是否偷看/训练了私人草稿」 | 厂商侧审计日志、法律程序 | **不能、也不应宣称能证明** |

### 2.2 现有能力能覆盖什么

已经能做、应对本事件「API 通道」的部分：

1. **独立见证 API 交互**：不经过厂商自己的日志系统，由本代理记录哈希链。
2. **多厂商**：检测与转发 OpenAI 兼容及多家国内/国际厂商。
3. **第三方离线复核**：解压 ZIP，本地打开 `verify.html`，不连我们的服务器也能重算哈希。
4. **不存原文**：降低「审计工具反而变成第二份泄密库」的风险。

若 Buckmaster 当时把 Codex **API** 指到本代理，今天至少能证明：「某 ata Key 下，在时间 T，对某 vendor/model 发生了一次请求，request_hash = H」。  
**仍不能证明**请求正文就是那份 NS 草稿（除非他自己保留原文，并能对出同一哈希）。

### 2.3 明确缺什么（本方案要补）

| 缺失 | 事件中的痛点 | 建议归属 |
|------|----------------|----------|
| 研究草稿/推导/提示词的**哈希存证对象** | 上传 Codex 前没有「先盖章」 | P0 |
| **浏览器本地算哈希**（原文可不出网） | 未发表手稿极度敏感 | P0 |
| 带时间戳的**优先权证书 ZIP** | 给期刊/合作者，而不是给内部仪表盘 | P0 最小版 / P2 机构版 |
| 科研时间线（草稿 → 多次 AI 对话 → 同意变更） | 还原「谁先有想法」叙事 | P1 |
| 把代理调用**关联**到某篇草稿 | 「这次 prompt 是在讨论那篇论文」 | P1 |
| 训练数据同意记录（用户侧） | 伦理与 opt-out 争议 | P1 |
| 服务商训练政策版本哈希（快照） | 政策事后被改网页 | P1 |
| 非 API 渠道（ChatGPT/Codex 网页） | 事件主路径很可能是产品 UI | P1 手工粘贴哈希 / P2 浏览器扩展（可选） |
| 机构批量核验接口 | 期刊编辑不想注册产品账号 | P2 |
| 证明「厂商训练了该草稿」 | 舆论焦点 | **永久不做**（能力边界） |

### 2.4 一张对照图

```
事件路径（简化）          今天 ai-attestation           方案目标
─────────────────        ──────────────────           ────────
未发表 PDF/笔记     →    无处可挂                      工件哈希存证（P0）
Codex / Chat 网页   →    代理覆盖不到                  手工登记 + 可选扩展（P1/P2）
Codex / Chat API    →    /v1/proxy 已能见证            关联到工件 + 同意字段（P1）
训练条款口说        →    合规模板人工勾选              同意记录上链（P1）
联合署名谈判        →    无证书                        优先权证书 ZIP（P0/P2）
期刊要验证          →    合规/调用包语义不对           公开 /v1/public/research/verify（P2）
```

---

## 3. 新功能设计（全部新增，保留现有功能）

设计原则：

1. **旧的一个字都不改行为**：现有 `/v1/proxy`、`/v1/reports/{id}/export`、合规包格式保持。
2. **新能力走新前缀**：`/v1/research/*`、菜单「科研见证」、新表。
3. **默认不存原文**：服务端只收哈希；若用户坚持上传原文，P1 用显式开关且默认关。
4. **链仍然只有一条**：科研事件写入现有 `attestation_chain`（新 `event_type`），这样「草稿存证」和「后来的 API 调用」可以在同一条链上排序，优先权叙事才站得住。
5. **小白中文**：按钮、空状态、手册步骤与界面文案一致。

### 3.1 科研优先权见证模式（P0 核心）

**用户故事：**  
「发到 AI 之前，我先让系统记住：这份文件/这段提示词的指纹。出事时我能导出一份证书，别人用同一文件再算一次哈希就能对上。」

流程（给小白）：

1. 打开「科研见证」→「登记想法」。
2. **在自己电脑上选择文件或粘贴文字**（浏览器用 Web Crypto 算 SHA-256，**默认不上传文件内容**）。
3. 填写：标题（可匿名，如「NS 爆破草稿 v3」）、类型（草稿 / 推导 / 提示词 / 其他）、可选作者显示名。
4. 点「写入证据链」。系统记下哈希、时间、链上位置。
5. 点「导出优先权证书」，得到 ZIP。把 ZIP 和**自己保管的原件**一起存档（原件不放我们这里）。

技术要点：

- 客户端：`crypto.subtle.digest('SHA-256')`，与后端 `hashlib.sha256` 十六进制小写一致。
- 服务端：只接收 `artifact_hash`（64 hex）、元数据、字节长度（可选）。拒绝正文。
- 可选：用户已在别处算好哈希，可直接粘贴。
- 写入后立即 `flush` + 本地 TSA（复用 `stamp_hash`），P0 即可导出。

### 3.2 AI 交互隐私见证（P1）

两条来源，互不破坏：

| 来源 | 做法 |
|------|------|
| 已走 `/v1/proxy` 的调用 | **不改代理响应**。P1 增加可选请求头 `X-Attest-Research-Id`（工件 id）。代理**忽略未知头已经是现状**；新增头仅在写入 `api_calls` 之后，向 **新表** `research_timeline` 插一条关联（失败不影响代理成功）。若担心「一点都不碰代理代码」，也可 P1 用仪表盘「把已有 call_id 关联到工件」的纯新 API，代理完全不动。 |
| 网页版 Chat/Codex | 用户从产品 UI 复制 prompt，在「科研见证」里「登记一次交互」：厂商、模型、时间（可手填）、prompt 哈希（本地算）、可选 response 哈希、关联工件。 |

**推荐决策（待确认）：** P0 完全不碰 `/v1/proxy`；P1 优先「事后关联 call_id」，需要自动关联时再加可选请求头（默认不加就不写关联，旧客户端无感）。

### 3.3 训练数据使用声明与审计（P1）

记录的是 **用户侧声明 + 政策快照**，不是厂商履约证明。

- 全局默认同意：`allow_training: unknown | yes | no`（默认 `unknown`，避免替用户做主）。
- 可按厂商覆盖：例如「DeepSeek 允许 / OpenAI 不允许」。
- 每次变更生成一条 `consent_records`，上链（`event_type=consent`）。
- 登记交互或关联调用时，**把当时有效的同意状态抄一份到时间线**（快照），以后改开关不影响历史。
- 合规检查：新增**自动规则**（新模板组，不改旧 YAML 语义）：若近 30 天有科研交互且同意状态为 `unknown`，记为 fail/manual。旧标准文件可在 P1 **追加**一个 group 引用；若担心动开源模板，则只做产品内「科研」检查页。

导出「训练同意合规摘要」PDF/JSON：列出时间线、每条快照、免责声明。

### 3.4 独立第三方见证（贯穿）

对外话术（操作手册必须写清）：

- 验证者不需要 OpenAI / Anthropic 账号。
- 验证者不需要相信仪表盘截图。
- 验证者需要：证书 ZIP +（可选）作者出示的原件文件。
- 验证者打开 `verify.html` 重算链与时间戳 token；若作者提供原件，在同一页「选择文件」再算哈希，与 `artifact.json` 中的哈希比对。

机构接口（P2）：`POST /v1/public/research/verify` 只接收证书 JSON/token，**不读租户数据库中的其他调用**。

### 3.5 前端「科研见证」+ 手册

新菜单插在「操作手册」和「仪表盘」之间，或「防篡改证明」之前，避免打乱老用户对「调用记录 / 合规」的记忆。建议顺序：

操作手册 → **科研见证** → 仪表盘 → …

手册新增「第五步：科研优先权（可选）」：配流程图、截图级按钮名、Q&A（见第 6 节）。

---

## 4. 数据模型设计

### 4.1 兼容策略

- **禁止** DROP/重命名 `api_calls` 等旧表字段。
- **禁止** 修改现有离线包文件名。
- **允许** `CREATE TABLE IF NOT EXISTS` 新表。
- **允许** 向 `attestation_chain` **插入**新 `event_type`（不是改列）。
- **不** 给 `api_calls` 加 `research_id` 列（那会改旧表）。关联放在新表 `research_timeline.call_id`（可空）。

### 4.2 新表：`research_artifacts`（研究工件）

一条 = 一次「想法/文件/提示词」的指纹登记。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | `art_` + hex |
| `api_key` | TEXT | 租户 |
| `timestamp` | TEXT | UTC，与现有 `utc_now()` 同格式 |
| `title` | TEXT | 用户标题，不含机密细节亦可 |
| `kind` | TEXT | `draft` / `derivation` / `prompt` / `note` / `other` |
| `artifact_hash` | TEXT | SHA-256 hex，必填 |
| `hash_alg` | TEXT | 默认 `sha256` |
| `byte_length` | INTEGER | 可选，原文字节数 |
| `filename_hint` | TEXT | 可选，仅文件名不含路径 |
| `authors_label` | TEXT | 可选显示名，非身份证明 |
| `description` | TEXT | 可选短描述 |
| `client_hashed` | INTEGER | 1=浏览器本地哈希 |
| `prev_hash` / `chain_hash` | TEXT | 与统一链一致 |
| `attest_id` | TEXT | 对应 chain 行 id |
| `tsa_receipt` | TEXT | JSON，本地 TSA |
| `status` | TEXT | `active` / `superseded` / `withdrawn` |
| `superseded_by` | TEXT | 可选，新版本工件 id |

索引：`(api_key, timestamp DESC)`、`(api_key, artifact_hash)`、`chain_hash`。

同一哈希允许重复登记（证明「再次确认」）；列表上提示「该指纹已于某时登记过」。

### 4.3 新表：`consent_records`（同意变更）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | `cns_` + hex |
| `api_key` | TEXT | |
| `timestamp` | TEXT | |
| `vendor` | TEXT | `*` 表示全局默认，或 `openai` 等 |
| `allow_training` | TEXT | `unknown` / `yes` / `no` |
| `source` | TEXT | `user_dashboard` / `imported_policy` |
| `policy_url` | TEXT | 可选，服务商政策链接 |
| `policy_hash` | TEXT | 可选，政策页面/PDF 哈希 |
| `note` | TEXT | |
| `prev_hash` / `chain_hash` / `attest_id` | TEXT | 上链 |

索引：`(api_key, timestamp DESC)`、`(api_key, vendor)`。

**当前有效同意** = 按 vendor 取最新一条，缺则回退 `vendor='*'`，再缺则为 `unknown`。

### 4.4 新表：`research_timeline`（科研时间线事件）

把「工件、同意、API 调用、手工登记的网页交互」串成叙事，同时各自仍在统一哈希链上。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | `rtl_` + hex |
| `api_key` | TEXT | |
| `timestamp` | TEXT | |
| `event_kind` | TEXT | `artifact` / `consent` / `api_call` / `manual_chat` |
| `artifact_id` | TEXT | 可空，关联工件 |
| `consent_id` | TEXT | 可空 |
| `call_id` | TEXT | 可空，对应 `api_calls.id`，无外键强制（旧库兼容） |
| `vendor` / `model` | TEXT | 交互类填写 |
| `prompt_hash` / `response_hash` | TEXT | 手工登记时用；api_call 可从调用行复制哈希 |
| `allow_training_snapshot` | TEXT | 事件发生时的同意抄本 |
| `label` | TEXT | 用户备注 |
| `prev_hash` / `chain_hash` / `attest_id` | TEXT | 上链 |

索引：`(api_key, timestamp DESC)`、`(artifact_id)`、`(call_id)`。

说明：`event_kind=artifact` 的时间线行可以与 `research_artifacts` **同一 chain_hash**（一次写入产两条业务行、一个 chain 事件），或工件表自带链字段、时间线只做索引。推荐：**工件/同意自己上链；时间线行可选再链一次会让链过吵。P0 只把工件上链；P1 时间线表作查询索引，仅 `manual_chat` 需要单独上链。**

### 4.5 与 `api_calls` 的关联

```
research_artifacts 1 ──< research_timeline >── 0..1 api_calls
                         research_timeline >── 0..1 consent_records
```

- 不改 `api_calls`。
- 删除调用记录（若未来有）不得级联删除工件；时间线 `call_id` 变为悬空时展示「调用已不在库中，哈希见时间线副本」。
- 验证包导出工件时，可附带关联 `call_id` 列表，但不把 `api_key` 写进 ZIP。

### 4.6 统一链 event_type 新取值（不改表结构）

| event_type | ref_id 指向 |
|------------|-------------|
| `research_artifact` | `research_artifacts.id` |
| `research_consent` | `consent_records.id` |
| `research_manual` | `research_timeline.id`（网页交互） |

`verify_chain` 对未知 `event_type` 今日会走「当作 call」分支并失败。**实施时必须在 `attestation.py` 增加这三种类型的重算规则**（这是逻辑扩展，不是删旧算法）。旧事件验证行为保持不变。

哈希载荷建议（与现有风格一致，`|` 拼接）：

```
research_artifact: prev|research_artifact|id|timestamp|artifact_hash|kind
research_consent:  prev|research_consent|id|timestamp|vendor|allow_training|policy_hash
research_manual:   prev|research_manual|id|timestamp|vendor|model|prompt_hash|response_hash
```

---

## 5. API 设计

统一鉴权：`require_key` / `resolve_api_key`，与现网一致。  
写操作：`read_write` 或 `admin`。  
读操作：`read_only` 即可。  
公开核验：**无 Key**，且不得根据 token 枚举其他租户数据。

### 5.1 P0 端点

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/v1/research/artifacts` | 登记工件（body：title、kind、artifact_hash、…） |
| `GET` | `/v1/research/artifacts` | 列表（分页） |
| `GET` | `/v1/research/artifacts/{id}` | 详情 + 单条链证明 |
| `GET` | `/v1/research/artifacts/{id}/certificate` | 下载优先权证书 ZIP |
| `POST` | `/v1/research/hash` | 可选：服务端对上传的**临时**字节算哈希后立即丢弃（默认不开放；见待确认） |

`POST /v1/research/artifacts` 校验：`artifact_hash` 匹配 `^[0-9a-f]{64}$`。

### 5.2 P1 端点

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/v1/research/consent` | 当前有效同意（全局 + 分厂商） |
| `PUT` | `/v1/research/consent` | 新增一条同意变更（上链） |
| `GET` | `/v1/research/timeline` | 时间线（可按 artifact_id 过滤） |
| `POST` | `/v1/research/timeline/manual` | 登记网页交互 |
| `POST` | `/v1/research/timeline/link-call` | body：`call_id` + `artifact_id`，校验 call 属于该 api_key |
| `GET` | `/v1/research/consent/report` | 同意审计摘要 JSON |
| `GET` | `/v1/research/consent/report/export` | txt/pdf，风格对齐现有合规导出 |

代理可选头（若确认要做自动关联）：

```
X-Attest-Research-Id: art_xxxx
X-Attest-Allow-Training: no
```

**默认实现：不解析这些头，直到产品确认。** 解析时必须失败安全：坏 id 只记日志，**不得**让上游调用失败。

### 5.3 P2 端点

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/v1/public/research/verify` | body：证书 token 或 pack JSON |
| `GET` | `/v1/public/research/verify` | 短 token（注意 URL 长度，优先 POST） |
| `GET` | `/v1/public/research/badge/{artifact_hash}.svg` | 与现有合规 badge 并列，新路径 |
| `POST` | `/v1/research/artifacts/{id}/notarize` | 封装现有 notarize，payload=artifact_hash |

**禁止**把科研包塞进现有 `/v1/public/verify` 的合规 pack 逻辑，以免旧验证页解析失败。新页面：`/verify/research/{artifact_hash}`。

### 5.4 错误与配额（P0 建议）

- 哈希格式错误：400
- 不属于自己的 id：404（避免探测）
- 只读 Key 写：403
- 单 Key 工件上限：例如 10_000（防刷链）

---

## 6. 前端设计

### 6.1 菜单与路由

- `NavId` 增加 `research`。
- 新组件：`ResearchTab.tsx`（容器）、`ArtifactRegister.tsx`、`ArtifactList.tsx`、`PriorityCertificate.tsx`、P1 再加 `ConsentPanel.tsx`、`ResearchTimeline.tsx`。
- 仍为单页内导航，降低路由改造风险；证书核验可用独立路由（对标现有 `/verify/...`）。

### 6.2 「科研见证」页面信息架构（小白）

1. **顶部三句话：** 我们只保存指纹；请自己保存原件；这不是法院判决。
2. **主按钮：** 「登记一份草稿或提示词」。
3. **列表：** 时间、标题、类型、哈希前 12 位、链状态。
4. **详情：** 完整哈希、TSA 时间、导出证书、（P1）关联的调用。
5. **（P1）同意条：** 「是否允许厂商用我的输入训练」—— 未知 / 允许 / 不允许，分厂商可展开。
6. **（P1）时间线：** 竖向：登记 → 若干次 AI → 同意变更。

空状态文案示例：

> 还没有科研存证。在把未发表内容发给任何 AI 之前，先在这里留下指纹。全程可以不上传原文。

### 6.3 操作手册更新（必须与按钮同名）

在现有四步之后增加：

**第五步：科研优先权存证（推荐在调用 AI 之前做）**

1. 左侧点「科研见证」。
2. 点「登记一份草稿或提示词」。
3. 选择「本地文件」或「粘贴文字」或「我已有哈希」。
4. 等页面显示 64 位哈希后再点「写入证据链」。
5. 点「导出优先权证书」，下载 ZIP，与原件放在同一加密盘。

Q&A 增补：

- 问：会不会把论文传给你们？答：默认不会；只传指纹。
- 问：能不能证明 OpenAI 训练了？答：不能。只能证明你何时有过这份指纹、以及（若走代理）何时与哪家模型发生过哈希意义上的交互。
- 问：和「导出验证包」有什么区别？答：调用验证包证明某次 API 调用链接；优先权证书证明某份内容指纹进入证据链的时间。

### 6.4 不要动的界面

调用详情、合规、行为、现有验证包按钮文案与位置保持。科研入口只新增，不替换「导出验证包」。

---

## 7. 离线验证包扩展（优先权证书）

### 7.1 新 ZIP 文件清单（与调用包并列，不复用 call.json）

建议文件名：`ata_priority_{artifact_id_safe}_cert.zip`

| 文件 | 是否必须 | 说明 |
|------|----------|------|
| `artifact.json` | 是 | 工件见证字段 + 免责声明 |
| `chain.json` | 是 | 至少含本环及 prev；P0 可只含本环+创世/前驱哈希 |
| `verification.json` | 是 | 导出时服务端 `ok` / 重算结果 |
| `verify.html` | 是 | **新模板**（科研），不要覆盖调用包 HTML |
| `README.txt` | 是 | 中文步骤 |
| `timestamp.json` | 建议 | TSA 收据（也可内嵌 artifact） |
| `consent_snapshot.json` | P1 | 导出时的同意状态 |
| `timeline.json` | P1 | 关联事件摘要（无原文） |

`artifact.json` 建议字段：

```json
{
  "pack_type": "ata-research-priority-v1",
  "disclaimer": "技术存证，不构成法律意见或学术优先权裁定。",
  "id": "art_…",
  "timestamp": "…Z",
  "title": "…",
  "kind": "draft",
  "artifact_hash": "64hex",
  "hash_alg": "sha256",
  "byte_length": 12345,
  "client_hashed": true,
  "prev_hash": "…",
  "chain_hash": "…",
  "authors_label": "…"
}
```

`pack_type` 用于让 `verify.html` 拒绝误打开放进文件夹的 `call.json`。

### 7.2 `verify.html` 离线如何验证（P0）

纯静态，流程与现有调用包相同：解压 → `python -m http.server 8765` → 打开页面（需安全上下文才能用 `crypto.subtle`）。

校验步骤：

1. 读 `artifact.json`，确认 `pack_type`。
2. 按与后端相同的拼接规则重算 `chain_hash`，与文件内字段比较。
3. 若有 `timestamp.json`：重算 `SHA256(payload_hash|unix|nonce)`，且 `payload_hash === artifact_hash`。
4. **原件复核（可选）：** `<input type="file">`，浏览器算 SHA-256，与 `artifact_hash` 比较。通过则显示「原件与证书指纹一致」。
5. 明确写出：**时间戳在 P0 是本系统签发**；若存在 OTS/链上字段再显示「请到日历/浏览器独立核验」。

P0 邻接链：若 ZIP 只有一环，页面显示「已验证本环；完整账本请用作者提供的更长 chain.json 或在线核验」。不要假装整条租户链都在包里。

### 7.3 与旧包共存

| 包 | 入口 API | 主 JSON |
|----|----------|---------|
| 调用见证 | `GET /v1/reports/{id}/export` | `call.json` |
| 合规报告 | `…/offline-pack` | `report.json` / `pack.json` |
| 优先权证书 | `GET /v1/research/artifacts/{id}/certificate` | `artifact.json` |

校验 HTML 三套分开，避免脚本假设字段名。

---

## 8. 分阶段实施计划

### P0 最小可行（建议 1 个短迭代）

**目标：** 科研人员能在发 AI 之前留下指纹，并导出可离线打开的证书。

包含：

- 新表 `research_artifacts`（及 chain 新 event_type 校验）
- `POST/GET` artifacts + certificate ZIP
- 前端「科研见证」登记/列表/导出
- 浏览器本地哈希
- 本地 TSA 写入证书
- 操作手册第五步
- pytest：登记、重算链、ZIP 内文件、verify 规则与 Python 一致
- **不改** `/v1/proxy`、旧表字段、旧 ZIP

不包含：同意、时间线、网页 Chat、机构核验页、真实 OTS 集成增强。

### P1 多厂商交互 + 训练同意

- 表 `consent_records`、`research_timeline`
- 同意面板 + 审计摘要导出
- 手工登记 Chat 交互
- 关联已有 `call_id`
- 时间线 UI
- 合规：科研检查页或新 YAML group（不修改旧检查算法，只追加）
- 文档：讲清「同意记录 ≠ 厂商未训练」

可选（需确认）：代理读取 `X-Attest-Research-Id`。

### P2 优先权证书增强 + 机构验证

- `/verify/research/...` 公开页
- `/v1/public/research/verify`
- 证书内引导 OpenTimestamps（复用 `build_notarization_request`）
- 徽章 SVG
- 机构批量：一次提交多个 artifact_hash（防滥用限流）
- 可选研究：浏览器扩展监听 Chat 网页（法律与 ToS 风险高，默认不做）

ZKP/TEE：继续按现有 docs，**不纳入本模块承诺。**

---

## 9. 测试计划

### 9.1 后端 pytest（CI 已有 `PYTHONPATH=app pytest tests/`）

新增 `backend/tests/test_research_attestation.py`，建议用例：

- 登记合法哈希 → 链 `verify_key_chain` 仍 ok，且 `n` 含新类型计数
- 篡改 `artifact_hash` 后单条校验失败
- 只读 Key 不能 POST
- 证书 ZIP 含且仅含约定文件名；`artifact.json` 无 `api_key`、无原文
- 证书 chain_hash 与库中一致
- 旧测试全绿：调用 ZIP、合规、代理、计量（回归）
- P1：同意快照不随后续 PUT 改写历史时间线
- P1：link-call 不能关联别人的 `call_id`
- P2：public verify 不返回其他租户工件

### 9.2 前端

- `frontend` `npm run build`（CI 已有）
- 手册文案与按钮字符串一致（可用简单 grep 测试或人工清单）
- 本地哈希：同一文件两次登记哈希相同

### 9.3 端到端演示脚本（给创始人拍视频）

1. 启动后端+仪表盘（现有 README）。
2. 创建 Key，打开「科研见证」。
3. 用一个小文本文件 `idea.txt`（内容：「多尺度放大构造爆破解 草稿」）本地哈希并上链。
4. 导出证书，换一台浏览器/无痕窗口，只打开 ZIP 里的 `verify.html` + 再选 `idea.txt`，显示双绿。
5. （P1）模拟一条代理调用，关联到该工件，时间线出现两点。
6. 强调免责声明出现在证书 README。

不要在演示里声称「这能告赢 OpenAI」。

---

## 10. 风险与合规

### 10.1 隐私

- **默认哈希存证**是正确方向，与现网「不存 body」一致。
- 标题、文件名、作者显示名仍可能泄露研究主题 → UI 提示可用代号。
- 服务端哈希接口（若开放）会短暂接触原文 → P0 **不开放**，避免成为攻击面。
- 时间线关联 call_id 可能让看到证书的人推断「还存在哪些 API 调用」→ 证书默认不放 call 列表，或仅放哈希。

### 10.2 法律效力边界（必须印在产品上）

本系统可以支持的陈述：

> 「在 ai-attestation 租户链上，哈希 H 于时间 T（本机/本服务时钟 + 可选外部日历）被记录，且该链环可被独立重算。」

本系统**不可以**支持的陈述：

- 哈希对应的内容一定是完整论文 / 一定先于他人完成证明；
- 某公司复制、训练或阅读了该内容；
- 学术期刊必须承认优先权；
- 替代律师函、公证处或 RFC3161 合格 TSA。

P0 时钟是**服务器本地时间**。对抗「事后改系统时间」的能力有限；P2 外部时间戳用于补强。

### 10.3 数据迁移与性能

- 新表空库即可用；旧用户升级只多几张表，旧功能不变。
- 工件上链与高频代理争用同一 SQLite 锁：P0 科研写入量小；保持科研路径同步、代理仍走缓冲。
- 证书不要打包整条超长链（调用包已用窗口）；优先权包以本环 + TSA 为主。

### 10.4 产品与舆论风险

- 用该事件做营销需谨慎：当事人未授权时，文档用「同类场景」而非指控口吻。
- 「独立见证」不得暗示已通过司法鉴定资质。

### 10.5 安全

- 公开核验接口防 ZIP 炸弹、超大 JSON。
- 科研页面 XSS：标题做转义（现有前端风格）。
- 继续默认绑定 `127.0.0.1`（SECURITY.md）。

---

## 11. 待确认问题

请在实施前确认下列决策（工程按你的选择落地）：

1. **P0 是否完全不改 `/v1/proxy`？** 推荐：是。P1 用「关联已有调用」；自动请求头作为后续开关。
2. **证书默认语言与署名？** 仅 Key 租户匿名，还是必填作者姓名/ORCID？（推荐 P0 选填显示名，不做身份认证。）
3. **是否允许服务端上传原文算哈希？** 推荐 P0 禁止；只接受客户端哈希。
4. **同一内容多次登记：** 允许（推荐）还是拒绝重复哈希？
5. **菜单名称：** 「科研见证」vs「优先权存证」vs「草稿指纹」？
6. **同意默认值：** `unknown`（推荐）还是跟进各厂商公开默认（易过时且像法律建议）？
7. **P1 是否改开源 `compliance-templates/`** 追加自动检查，还是只做产品内科研页，以免模板版本噪音？
8. **公开验证页是否进 P0？** 推荐 P0 只给 ZIP；公开页放 P2，减少未审接口面。
9. **是否把本事件写入官网文案？** 推荐方案文档内部举例，官网用中性「未发表研究 + 多厂商 AI」描述。

---

## 附录 A · 实施时建议的文件清单（确认后再建）

仅作规划，**本次不创建业务代码**：

- `backend/app/research.py` — 工件/同意/时间线领域逻辑  
- `backend/app/research_cert.py` — 证书 ZIP 与科研版 verify.html  
- `backend/tests/test_research_attestation.py`  
- `frontend/components/ResearchTab.tsx` 等  
- `frontend/app/verify/research/[artifact_hash]/`（P2）  
- `UserGuide.tsx` 增加第五步  
- `compliance-templates` 仅在确认问题 7 为「是」时追加 YAML  

旧文件保持入口，仅 `main.py` **追加**路由、`models.py` **追加** `CREATE TABLE`、`attestation.py` **追加** event 分支。

## 附录 B · 成功标准（P0）

创始人可用这条清单验收：

- [ ] 旧：模拟调用、导出调用验证包、合规检查，行为与现在一致  
- [ ] 新：不上传文件内容，能对一个 txt 留下 64 位哈希并出现在列表  
- [ ] 新：ZIP 在断网后用 `python -m http.server` 打开能显示链校验通过  
- [ ] 新：用原件选择文件能显示指纹匹配；改一个字的文件显示不匹配  
- [ ] 新：手册能让未读过代码的人独立走完登记与导出  

---

*本文只规划、不实施。确认第 11 节问题后，再按 P0 → P1 → P2 开做。*
