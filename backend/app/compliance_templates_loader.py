"""Load open compliance templates from YAML tree (canonical checklist source).

Default root: ``compliance-templates/``
Override: env ``ATA_COMPLIANCE_TEMPLATES_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


def templates_root() -> Path:
    env = os.environ.get("ATA_COMPLIANCE_TEMPLATES_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # backend/app -> backend -> repo -> compliance-templates
    return Path(__file__).resolve().parents[2] / "compliance-templates"


def _read_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML required to load compliance templates")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_shared_checks(root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Return group_id -> check dict from checks/shared.yaml (empty if missing)."""
    root = root or templates_root()
    path = root / "checks" / "shared.yaml"
    if not path.is_file():
        return {}
    doc = _read_yaml(path)
    out: Dict[str, Dict[str, Any]] = {}
    for item in doc.get("checks") or []:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("group_id") or "").strip()
        if not gid:
            continue
        out[gid] = dict(item)
    return out


def load_open_standards(root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load standards/*.yaml as raw defs (id -> defn with groups/checks/version)."""
    root = root or templates_root()
    std_dir = root / "standards"
    if not std_dir.is_dir():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for path in sorted(std_dir.glob("*.yaml")) + sorted(std_dir.glob("*.yml")):
        try:
            doc = _read_yaml(path)
        except (OSError, Exception):
            continue
        if not isinstance(doc, dict):
            continue
        sid = str(doc.get("id") or path.stem).strip()
        if not sid:
            continue
        doc = dict(doc)
        doc["id"] = sid
        doc["source"] = doc.get("source") or "open"
        out[sid] = doc
    return out


def open_template_versions(root: Optional[Path] = None) -> Dict[str, str]:
    return {
        sid: str(defn.get("version") or "0.0.0")
        for sid, defn in load_open_standards(root).items()
    }


def dump_template_yaml(defn: Dict[str, Any]) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    payload: Dict[str, Any] = {
        "schema": "ata-compliance-template-v1",
        "id": defn["id"],
        "name": defn.get("name"),
        "description": defn.get("description") or "",
        "version": defn.get("version") or "0.1.0",
        "source": defn.get("source") or "custom",
    }
    if defn.get("groups"):
        payload["groups"] = list(defn["groups"])
    if defn.get("checks") and (defn.get("export_full_checks") or not defn.get("groups")):
        # Strip runtime enrichment fields for export
        slim = []
        for c in defn["checks"]:
            slim.append(
                {
                    k: c[k]
                    for k in (
                        "check_id",
                        "group_id",
                        "category",
                        "requirement",
                        "check_method",
                        "auto_check",
                        "query_template",
                        "pass_rule",
                        "manual_guidance",
                        "how_to_satisfy",
                    )
                    if k in c and c[k] is not None
                }
            )
        payload["checks"] = slim
    return yaml.safe_dump(
        payload, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def parse_template_yaml(text: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    doc = yaml.safe_load(text) or {}
    if not isinstance(doc, dict) or not doc.get("id"):
        raise ValueError("template YAML must be a mapping with id")
    return doc


def suggest_check_from_goal(goal: str) -> Dict[str, Any]:
    """Check-method helper: map a natural-language goal to a query template draft."""
    g = (goal or "").lower()
    time_range = "30d"
    if "7" in g or "一周" in g or "7天" in g:
        time_range = "7d"
    elif "90" in g or "季度" in g:
        time_range = "90d"
    status = None
    if "失败" in g or "fail" in g or "4xx" in g or "5xx" in g:
        status = "failure"
    auto = True
    pass_rule = "has_calls_with_required_fields"
    category = "透明度"
    if "哈希" in g or "hash" in g or "篡改" in g:
        pass_rule = "chain_integrity"
        category = "安全"
    elif "费用" in g or "cost" in g or "计费" in g:
        pass_rule = "all_have_cost"
        category = "计费"
    elif "模型" in g or "model" in g:
        pass_rule = "model_coverage_ge_90"
    elif "端点" in g or "endpoint" in g:
        pass_rule = "all_have_endpoint"
    elif "正文" in g or "body" in g or "request_hash" in g:
        pass_rule = "all_have_body_hashes"
        category = "安全"
    elif any(k in g for k in ("人工", "政策", "披露", "文档", "备案", "协议")):
        auto = False
        pass_rule = None
    qt: Optional[Dict[str, Any]] = None
    if auto and pass_rule != "chain_integrity":
        qt = {"time_range": time_range, "limit": 500}
        if status:
            qt["status"] = status
    return {
        "goal": goal,
        "draft": {
            "category": category,
            "requirement": goal.strip() or "（请填写要求）",
            "check_method": f"根据目标自动生成：time_range={time_range}"
            + (f", status={status}" if status else ""),
            "auto_check": auto,
            "query_template": qt,
            "pass_rule": pass_rule,
            "manual_guidance": None
            if auto
            else "请人工核验相关文档/声明，并保留版本与日期证据。",
        },
        "note": "助手仅生成草稿查询条件；请人工确认后保存。",
    }


def version_tuple(v: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for p in str(v or "0").split("."):
        try:
            parts.append(int("".join(c for c in p if c.isdigit()) or "0"))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def is_newer_version(available: str, current: str) -> bool:
    return version_tuple(available) > version_tuple(current)
