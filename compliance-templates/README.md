# ai-attestation — Compliance Templates（开源合规检查模板）

> **定位**：可执行的检查清单与查询模板，不是空泛白皮书。  
> **原则**：先落地可验证证据与工具，再扩展互操作格式；核心清单开源，商业版提供高级能力。

本目录是产品内置合规检查模板的**权威源**（YAML）。社区可 Fork → 新增模板 → PR。产品通过同步加载本目录（同仓路径；亦可作 Git submodule）。

## 布局

```
checks/shared.yaml          # 原子检查（group_id）
standards/*.yaml            # 标准 = groups 组合 + 语义化 version
CONTRIBUTING.md             # 贡献流程
```

## 模板字段（标准文件）

| 字段 | 说明 |
|------|------|
| `id` | 稳定标识（snake_case） |
| `name` / `description` | 展示名与说明 |
| `version` | 语义化版本（如 `0.2.0`） |
| `groups` | 引用 `checks/shared.yaml` 中的 `group_id` |

也可在标准中提供完整 `checks` 数组（含 `check_id`、`category`、`requirement`、`check_method`、`auto_check`、`query_template` 等）。

## 产品如何同步

- 默认路径：`compliance-templates/`
- 环境变量覆盖：`ATA_COMPLIANCE_TEMPLATES_DIR`
- 私有自定义模板存于租户本地目录，不进入本开源树；可选「发布到社区」生成 PR 草稿 YAML

## 声明

本仓库提供**技术验证工具与检查清单**，不宣称定义「AI 审计标准」，不提供法律意见。
