"""Compliance-as-code catalog: open YAML templates + community JSON + custom.

Primary source:
  ``compliance-templates/`` (YAML).

Also loads:
  - ``compliance_community/*.json`` (legacy drops)
  - per-tenant custom templates when ``api_key`` is provided
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from compliance_shared import SHARED_CHECKS
from compliance_templates_loader import (
    is_newer_version,
    load_open_standards,
    load_shared_checks,
    open_template_versions,
)

STANDARD_EU_AI_ACT_TRANSPARENCY = "eu_ai_act_transparency"
STANDARD_US_AI_EO = "us_ai_executive_order"
STANDARD_CN_GENAI = "cn_genai_measures"
STANDARD_ISO_42001 = "iso_iec_42001"
STANDARD_SOC2_AI = "soc2_type_ii_ai"

_COMMUNITY_DIR = Path(__file__).resolve().parent / "compliance_community"


def _shared_map() -> Dict[str, Dict[str, Any]]:
    """Python builtins overlaid by open YAML shared checks (YAML wins)."""
    merged = dict(SHARED_CHECKS)
    merged.update(load_shared_checks())
    return merged


def _compose(prefix: str, group_ids: Sequence[str]) -> List[Dict[str, Any]]:
    shared = _shared_map()
    checks = []
    for gid in group_ids:
        if gid not in shared:
            raise KeyError(f"unknown group_id: {gid}")
        base = shared[gid]
        out = dict(base)
        out["check_id"] = f"{prefix}_{gid}"
        out["group_id"] = gid
        checks.append(out)
    return checks


# Builtin standard definitions (group composition)
_BUILTIN_DEFS: Dict[str, Dict[str, Any]] = {
    STANDARD_EU_AI_ACT_TRANSPARENCY: {
        "id": STANDARD_EU_AI_ACT_TRANSPARENCY,
        "name": "欧盟 AI 法案 · 透明度条款",
        "description": "透明度相关要求可执行检查清单。",
        "version": "0.2.0",
        "source": "builtin",
        "groups": [
            "api_trail_30d",
            "hash_chain",
            "endpoint_recorded",
            "model_recorded",
            "cost_recorded",
            "failures_audited",
            "body_hashes",
            "capability_disclosure",
            "training_data",
            "user_data_training",
            "usage_limits",
        ],
    },
    STANDARD_US_AI_EO: {
        "id": STANDARD_US_AI_EO,
        "name": "美国 AI 行政令 · 安全评估与红队",
        "description": "面向安全评估、红队测试与事件报告的检查项（技术验证工具，非法务意见）。",
        "version": "0.1.0",
        "source": "builtin",
        "groups": [
            "api_trail_30d",
            "hash_chain",
            "failures_audited",
            "body_hashes",
            "safety_assessment",
            "red_team_eval",
            "incident_reporting",
            "capability_disclosure",
            "usage_limits",
        ],
    },
    STANDARD_CN_GENAI: {
        "id": STANDARD_CN_GENAI,
        "name": "中国生成式 AI 服务管理办法",
        "description": "备案、数据安全评估与内容审核相关检查项（技术验证工具，非法务意见）。",
        "version": "0.1.0",
        "source": "builtin",
        "groups": [
            "api_trail_30d",
            "hash_chain",
            "model_recorded",
            "cn_filing",
            "cn_data_security_eval",
            "cn_content_moderation",
            "cn_user_realname",
            "user_data_training",
            "training_data",
            "capability_disclosure",
        ],
    },
    STANDARD_ISO_42001: {
        "id": STANDARD_ISO_42001,
        "name": "ISO/IEC 42001 · AI 管理系统",
        "description": "AI 治理、风险评估与持续改进检查项（映射到可审计证据）。",
        "version": "0.1.0",
        "source": "builtin",
        "groups": [
            "api_trail_30d",
            "hash_chain",
            "iso_governance",
            "iso_risk_assessment",
            "iso_continual_improvement",
            "iso_supplier",
            "safety_assessment",
            "user_data_training",
            "capability_disclosure",
        ],
    },
    STANDARD_SOC2_AI: {
        "id": STANDARD_SOC2_AI,
        "name": "SOC 2 Type II · AI 服务适用部分",
        "description": "安全、可用性、处理完整性、保密性、隐私（AI API 服务子集）。",
        "version": "0.1.0",
        "source": "builtin",
        "groups": [
            "soc2_security",
            "soc2_availability",
            "soc2_processing_integrity",
            "soc2_confidentiality",
            "soc2_privacy",
            "api_trail_30d",
            "hash_chain",
            "cost_recorded",
            "body_hashes",
            "user_data_training",
        ],
    },
}


def _enrich(defn: Dict[str, Any]) -> Dict[str, Any]:
    if "checks" in defn and defn["checks"]:
        checks = list(defn["checks"])
    else:
        prefix = str(defn["id"]).replace("-", "_")[:12]
        checks = _compose(prefix, defn.get("groups") or [])
    n_auto = sum(1 for c in checks if c.get("auto_check"))
    return {
        "id": defn["id"],
        "name": defn["name"],
        "description": defn.get("description") or "",
        "version": defn.get("version") or "0.0.0",
        "source": defn.get("source") or "builtin",
        "groups": list(defn.get("groups") or []),
        "n_checks": len(checks),
        "n_auto": n_auto,
        "n_manual": len(checks) - n_auto,
        "auto_coverage": round(n_auto / max(len(checks), 1), 3),
        "checks": checks,
    }


def _load_community() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    shared = _shared_map()
    if not _COMMUNITY_DIR.is_dir():
        return out
    for path in sorted(_COMMUNITY_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sid = str(raw.get("id") or path.stem)
        raw["id"] = sid
        raw["source"] = "community"
        if raw.get("groups") and not raw.get("checks"):
            raw["checks"] = _compose(f"comm_{sid[:8]}", raw["groups"])
        elif raw.get("checks"):
            for c in raw["checks"]:
                gid = c.get("group_id")
                if gid and gid in shared and "pass_rule" not in c:
                    merged = dict(shared[gid])
                    merged["check_id"] = c.get("check_id") or f"{sid}_{gid}"
                    merged["group_id"] = gid
                    merged.update({k: v for k, v in c.items() if v is not None})
                    c.clear()
                    c.update(merged)
        out[sid] = raw
    return out


def _load_open_yaml_defs() -> Dict[str, Dict[str, Any]]:
    """Open compliance-templates YAML (preferred over hardcoded builtins)."""
    return load_open_standards()


def _all_defs() -> Dict[str, Dict[str, Any]]:
    # Hardcoded fallback → open YAML overrides → community JSON overrides
    merged = dict(_BUILTIN_DEFS)
    merged.update(_load_open_yaml_defs())
    merged.update(_load_community())
    return merged


# Back-compat alias used by older imports
STANDARDS: Dict[str, Dict[str, Any]] = {}


def _refresh_standards_cache() -> None:
    STANDARDS.clear()
    for sid, defn in _all_defs().items():
        STANDARDS[sid] = _enrich(defn)


_refresh_standards_cache()


def list_standards(*, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    _refresh_standards_cache()
    rows = [dict(s) for s in STANDARDS.values()]
    if api_key:
        try:
            from compliance_custom import list_custom_templates, get_custom_template

            for meta in list_custom_templates(api_key):
                full = get_custom_template(api_key, meta["id"])
                if full:
                    rows.append(_enrich(full))
        except Exception:
            pass
    return rows


def get_standard(
    standard_id: str, *, api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    _refresh_standards_cache()
    s = STANDARDS.get(standard_id)
    if s:
        return dict(s)
    if api_key:
        try:
            from compliance_custom import get_custom_template

            custom = get_custom_template(api_key, standard_id)
            if custom:
                return _enrich(custom)
        except Exception:
            return None
    return None


def list_shared_groups() -> List[Dict[str, Any]]:
    return [dict(v) for v in _shared_map().values()]


def template_update_notices(
    *, api_key: Optional[str] = None, pinned: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Compare catalog open versions vs last-used / pinned versions."""
    _refresh_standards_cache()
    available = open_template_versions()
    notices: List[Dict[str, Any]] = []
    pins = dict(pinned or {})
    if api_key:
        try:
            from compliance_custom import list_custom_templates

            for t in list_custom_templates(api_key):
                if t.get("pinned_version"):
                    pins[t["id"]] = t["pinned_version"]
        except Exception:
            pass
    for sid, avail in available.items():
        cur = pins.get(sid) or (STANDARDS.get(sid) or {}).get("version") or avail
        # Notice when open repo version differs from pin, or when we track last_run
        if pins.get(sid) and is_newer_version(avail, pins[sid]):
            notices.append(
                {
                    "template_id": sid,
                    "name": (STANDARDS.get(sid) or {}).get("name") or sid,
                    "current_version": pins[sid],
                    "available_version": avail,
                    "action": "upgrade_available",
                }
            )
        elif not pins.get(sid):
            # Surface open version for UI badge even without pin
            notices.append(
                {
                    "template_id": sid,
                    "name": (STANDARDS.get(sid) or {}).get("name") or sid,
                    "current_version": cur,
                    "available_version": avail,
                    "action": "at_latest"
                    if str(cur) == str(avail)
                    else "upgrade_available",
                }
            )
    return [n for n in notices if n["action"] == "upgrade_available"] or notices


def compare_standards(standard_ids: Sequence[str]) -> Dict[str, Any]:
    """Matrix: rows = group_ids, columns = standards, cell = applicable|n/a."""
    _refresh_standards_cache()
    specs = []
    for sid in standard_ids:
        s = STANDARDS.get(sid)
        if not s:
            raise ValueError(f"unknown standard: {sid}")
        specs.append(s)

    # Map standard -> set of group_ids
    std_groups: Dict[str, Set[str]] = {}
    group_meta: Dict[str, Dict[str, Any]] = {}
    for s in specs:
        gset: Set[str] = set()
        for c in s["checks"]:
            gid = str(c.get("group_id") or c.get("check_id"))
            gset.add(gid)
            if gid not in group_meta:
                group_meta[gid] = {
                    "group_id": gid,
                    "category": c.get("category"),
                    "requirement": c.get("requirement"),
                    "auto_check": c.get("auto_check"),
                }
        std_groups[s["id"]] = gset

    all_groups = sorted(group_meta.keys())
    overlap = [
        gid
        for gid in all_groups
        if sum(1 for gset in std_groups.values() if gid in gset) > 1
    ]
    unique: Dict[str, List[str]] = {}
    for s in specs:
        others = [std_groups[o["id"]] for o in specs if o["id"] != s["id"]]
        rest: Set[str] = set().union(*others) if others else set()
        unique[s["id"]] = sorted(std_groups[s["id"]] - rest)

    rows = []
    for gid in all_groups:
        cells = {}
        for s in specs:
            cells[s["id"]] = "适用" if gid in std_groups[s["id"]] else "不适用"
        rows.append({**group_meta[gid], "cells": cells})

    return {
        "standards": [{"id": s["id"], "name": s["name"]} for s in specs],
        "n_groups": len(all_groups),
        "n_overlap": len(overlap),
        "overlap_groups": overlap,
        "unique_groups": unique,
        "matrix": rows,
        "note": "重叠 group 在多标准检查时只执行一次并映射到各标准。",
    }
