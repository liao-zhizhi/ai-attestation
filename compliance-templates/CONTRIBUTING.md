# 贡献合规检查模板

我们欢迎社区贡献**可执行检查清单**，而不是空泛的标准宣言。

## 流程（简单，无多级审核）

1. Fork 本仓库（或本目录所在仓库）
2. 在 `standards/` 新增 `your_id.yaml`，或扩展 `checks/shared.yaml` 中的原子检查
3. 本地用产品「自定义模板」导入 YAML 试跑
4. 提交 Pull Request；维护者做一次技术审阅后合并

## 最小标准文件

```yaml
schema: ata-compliance-template-v1
id: my_org_ai_policy
name: 我的组织 AI 政策
description: 内部政策映射到可审计证据
version: 0.1.0
source: community
groups:
  - api_trail_30d
  - hash_chain
  - capability_disclosure
```

## 完整检查项（可选）

```yaml
checks:
  - check_id: my_org_api_trail
    group_id: api_trail_30d   # 可选：复用共享原子
    category: 透明度
    requirement: …
    check_method: …
    auto_check: true
    query_template:
      time_range: 30d
      limit: 500
    pass_rule: has_calls_with_required_fields
```

## 勿做

- 勿提交密钥、生产日志或个人数据
- 勿把模板写成无法验证的「原则宣言」而无 `auto_check` / `manual_guidance`
- 勿宣称本清单具有法律效力

## 审阅标准（技术）

- `id` 唯一、版本符合 semver
- 自动检查须有 `pass_rule` 或可解析的 `query_template`
- 人工项须有 `manual_guidance`
