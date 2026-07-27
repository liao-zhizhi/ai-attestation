# 社区合规检查模板贡献指南

**首选路径**：向开源树提交 YAML ——  
`compliance-templates/`（见该目录 `CONTRIBUTING.md`）。

本目录（`*.json`）仍可作为遗留投递点：服务重启或下次 `list_standards()` 时加载。

## 最小 JSON（遗留）

```json
{
  "id": "my_org_ai_policy",
  "name": "我的组织 AI 政策",
  "description": "内部政策映射",
  "version": "0.1.0",
  "groups": ["api_trail_30d", "hash_chain", "capability_disclosure"]
}
```

产品原则：先交付可执行检查与证据；证据格式保持开放，不私有化。
