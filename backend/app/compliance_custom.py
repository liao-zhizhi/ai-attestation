"""Private custom compliance templates (per API key) + community publish draft.

Storage: ``{ATA_HOME}/.custom_templates/{key_suffix}/``
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from compliance_templates_loader import (
    dump_template_yaml,
    parse_template_yaml,
    suggest_check_from_goal,
)
from paths import product_data_root


def _mvp_root() -> Path:
    return product_data_root()


def _key_dir(api_key: str) -> Path:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    d = _mvp_root() / "custom_templates" / digest
    d.mkdir(parents=True, exist_ok=True)
    return d


_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _validate_id(sid: str) -> str:
    sid = str(sid or "").strip()
    if not _ID_RE.match(sid):
        raise ValueError("id must be snake_case [a-z][a-z0-9_]{2,63}")
    return sid


def list_custom_templates(api_key: str) -> List[Dict[str, Any]]:
    d = _key_dir(api_key)
    out: List[Dict[str, Any]] = []
    for path in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        try:
            doc = parse_template_yaml(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        doc["source"] = "custom"
        doc["path"] = str(path.name)
        out.append(
            {
                "id": doc["id"],
                "name": doc.get("name") or doc["id"],
                "description": doc.get("description") or "",
                "version": doc.get("version") or "0.1.0",
                "source": "custom",
                "n_groups": len(doc.get("groups") or []),
                "n_checks": len(doc.get("checks") or []),
                "pinned_version": _read_pin(api_key, doc["id"]),
            }
        )
    return out


def get_custom_template(api_key: str, template_id: str) -> Optional[Dict[str, Any]]:
    path = _key_dir(api_key) / f"{template_id}.yaml"
    if not path.is_file():
        path = _key_dir(api_key) / f"{template_id}.yml"
    if not path.is_file():
        return None
    doc = parse_template_yaml(path.read_text(encoding="utf-8"))
    doc["source"] = "custom"
    doc["pinned_version"] = _read_pin(api_key, template_id)
    return doc


def save_custom_template(api_key: str, defn: Dict[str, Any]) -> Dict[str, Any]:
    sid = _validate_id(str(defn.get("id") or ""))
    defn = dict(defn)
    defn["id"] = sid
    defn["source"] = "custom"
    defn.setdefault("version", "0.1.0")
    defn.setdefault("name", sid)
    if not defn.get("groups") and not defn.get("checks"):
        raise ValueError("groups or checks required")
    text = dump_template_yaml(defn)
    path = _key_dir(api_key) / f"{sid}.yaml"
    path.write_text(text, encoding="utf-8")
    return get_custom_template(api_key, sid) or defn


def delete_custom_template(api_key: str, template_id: str) -> bool:
    d = _key_dir(api_key)
    removed = False
    for path in (d / f"{template_id}.yaml", d / f"{template_id}.yml"):
        if path.is_file():
            path.unlink()
            removed = True
    pin = d / f".pin_{template_id}.json"
    if pin.is_file():
        pin.unlink()
    return removed


def export_custom_yaml(api_key: str, template_id: str) -> str:
    doc = get_custom_template(api_key, template_id)
    if not doc:
        raise ValueError("template not found")
    return dump_template_yaml(doc)


def import_custom_yaml(api_key: str, text: str) -> Dict[str, Any]:
    doc = parse_template_yaml(text)
    return save_custom_template(api_key, doc)


def publish_draft(api_key: str, template_id: str) -> Dict[str, Any]:
    """Write a community PR draft YAML under compliance-templates/_drafts/ (local)."""
    doc = get_custom_template(api_key, template_id)
    if not doc:
        raise ValueError("template not found")
    from compliance_templates_loader import templates_root

    root = templates_root()
    drafts = root / "_drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    payload = dict(doc)
    payload["source"] = "community"
    text = dump_template_yaml(payload)
    out_path = drafts / f"{template_id}.yaml"
    out_path.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "path": str(out_path.relative_to(root.parent.parent) if False else out_path),
        "relative": f"compliance-templates/_drafts/{template_id}.yaml",
        "next_steps": [
            "Review the draft YAML",
            "Move to standards/ after technical review",
            "Open a Pull Request per CONTRIBUTING.md",
        ],
        "yaml_preview": text[:2000],
    }


def _pin_path(api_key: str, template_id: str) -> Path:
    return _key_dir(api_key) / f".pin_{template_id}.json"


def _read_pin(api_key: str, template_id: str) -> Optional[str]:
    path = _pin_path(api_key, template_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("version")
    except (OSError, json.JSONDecodeError):
        return None


def pin_template_version(api_key: str, template_id: str, version: Optional[str]) -> Dict[str, Any]:
    """Pin to a version string, or clear pin (None) to follow latest open catalog."""
    path = _pin_path(api_key, template_id)
    if version is None or version == "" or version == "latest":
        if path.is_file():
            path.unlink()
        return {"template_id": template_id, "pinned_version": None, "follow": "latest"}
    path.write_text(
        json.dumps({"version": version}, ensure_ascii=False), encoding="utf-8"
    )
    return {"template_id": template_id, "pinned_version": version, "follow": "pinned"}


def check_method_helper(goal: str) -> Dict[str, Any]:
    return suggest_check_from_goal(goal)
