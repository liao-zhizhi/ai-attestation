"""Self-contained compliance verify packs for shareable /verify pages.

Pack is zlib+base64url encoded JSON. Recipients can verify report_hash,
TSA receipt, chain link, and blockchain anchor without DB access.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Any, Dict, Mapping, Optional

from anchoring import verify_tsa_receipt
from attestation import compute_compliance_chain_hash, sha256_text
from compliance import results_report_hash


PACK_VERSION = "ata-verify-pack-v1"


def build_verify_pack(
    report: Mapping[str, Any],
    *,
    timestamp_proof: Optional[Mapping[str, Any]] = None,
    blockchain_anchor: Optional[Mapping[str, Any]] = None,
    tee_attestation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a portable pack from a compliance row (+ optional proofs)."""
    standard = str(report.get("standard") or "")
    results = report.get("check_results") or {}
    tsp = dict(timestamp_proof or report.get("timestamp_proof") or {})
    anchor = None
    if blockchain_anchor:
        anchor = {
            "network": blockchain_anchor.get("network"),
            "tx_hash": blockchain_anchor.get("tx_hash"),
            "timestamp": blockchain_anchor.get("timestamp"),
            "chain_head": blockchain_anchor.get("chain_head"),
            "status": blockchain_anchor.get("status"),
            "mock": blockchain_anchor.get("mock"),
        }
    pack = {
        "version": PACK_VERSION,
        "disclaimer": "Technical verification only — not legal advice.",
        "report": {
            "id": report.get("id") or report.get("check_id"),
            "standard": standard,
            "standard_name": report.get("standard_name"),
            "timestamp": report.get("timestamp"),
            "summary": report.get("summary"),
            "check_results": results,
            "report_hash": report.get("report_hash"),
            "prev_hash": report.get("prev_hash"),
            "chain_hash": report.get("chain_hash"),
        },
        "timestamp_proof": tsp or None,
        "blockchain_anchor": anchor,
        "tee_attestation": tee_attestation,
    }
    return pack


def encode_pack(pack: Mapping[str, Any]) -> str:
    raw = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def decode_pack(token: str) -> Dict[str, Any]:
    pad = "=" * (-len(token) % 4)
    raw = zlib.decompress(base64.urlsafe_b64decode(token + pad))
    return json.loads(raw.decode("utf-8"))


def verify_pack(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Offline verification of a share pack."""
    report = pack.get("report") or {}
    standard = str(report.get("standard") or "")
    results = report.get("check_results") or {}
    expected_rh = results_report_hash(standard, results)
    claimed_rh = str(report.get("report_hash") or "")
    report_ok = expected_rh == claimed_rh and bool(claimed_rh)

    chain_ok = False
    chain_msg = "missing chain fields"
    prev = str(report.get("prev_hash") or "")
    claimed_ch = str(report.get("chain_hash") or "")
    rid = str(report.get("id") or "")
    ts = str(report.get("timestamp") or "")
    if rid and ts and claimed_rh and prev and claimed_ch:
        recomputed = compute_compliance_chain_hash(
            check_id=rid,
            timestamp=ts,
            standard=standard,
            report_hash=claimed_rh,
            prev_hash=prev,
        )
        chain_ok = recomputed == claimed_ch
        chain_msg = "chain link intact" if chain_ok else "chain link mismatch"

    tsp = pack.get("timestamp_proof") or {}
    if tsp:
        tsa = verify_tsa_receipt(dict(tsp))
        # Also require payload binds to report_hash
        bind_ok = str(tsp.get("payload_hash") or "") == claimed_rh
        tsa["bind_ok"] = bind_ok
        tsa["ok"] = bool(tsa.get("ok")) and bind_ok
        if not bind_ok:
            tsa["message"] = "timestamp payload_hash does not match report_hash"
    else:
        tsa = {"ok": False, "message": "no timestamp proof in pack"}

    anchor = pack.get("blockchain_anchor")
    anchor_status = {
        "present": bool(anchor),
        "ok": bool(anchor and anchor.get("tx_hash")),
        "message": (
            "anchor present (verify tx on explorer independently)"
            if anchor and anchor.get("tx_hash")
            else "no blockchain anchor"
        ),
        "anchor": anchor,
    }

    tee = pack.get("tee_attestation")
    # Exploratory stubs are informational only — never count as verified TEE
    tee_status = {
        "present": bool(tee),
        "ok": False,
        "message": (tee or {}).get("note")
        or (
            "exploratory TEE stub (not manufacturer-verifiable)"
            if tee
            else "no TEE attestation"
        ),
        "tee": tee,
    }

    overall = report_ok and chain_ok and bool(tsa.get("ok"))
    return {
        "ok": overall,
        "report_hash": {
            "ok": report_ok,
            "expected": expected_rh,
            "claimed": claimed_rh,
            "message": "report_hash matches results" if report_ok else "report_hash mismatch",
        },
        "chain": {"ok": chain_ok, "message": chain_msg, "claimed": claimed_ch},
        "timestamp": tsa,
        "blockchain_anchor": anchor_status,
        "tee": tee_status,
        "pack_version": pack.get("version"),
        "disclaimer": pack.get("disclaimer"),
    }


def report_to_oscal(report: Mapping[str, Any], *, pack: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Minimal OSCAL-inspired assessment-results document (machine-readable)."""
    results = report.get("check_results") or {}
    findings = []
    for cid, r in results.items():
        status = str(r.get("status") or "")
        findings.append(
            {
                "uuid": cid,
                "title": r.get("requirement") or cid,
                "description": r.get("detail") or "",
                "target": {"type": "component", "title": report.get("standard_name")},
                "related-observations": [
                    {
                        "uuid": f"obs-{cid}",
                        "description": r.get("manual_guidance") or r.get("detail") or "",
                        "methods": ["TEST" if r.get("auto_check") else "EXAMINE"],
                    }
                ],
                "related-risks": [],
                "status": {
                    "state": {
                        "pass": "satisfied",
                        "fail": "not-satisfied",
                        "manual": "other",
                        "partial": "other",
                    }.get(status, "other")
                },
            }
        )
    doc = {
        "oscal-version": "1.1.2",
        "metadata": {
            "title": f"ATA Compliance — {report.get('standard_name') or report.get('standard')}",
            "last-modified": report.get("timestamp"),
            "version": "1.0",
            "oscal-version": "1.1.2",
            "remarks": "Generated by ai-attestation. Not a legal compliance attestation.",
        },
        "assessment-results": {
            "uuid": str(report.get("id") or report.get("check_id") or ""),
            "metadata": {
                "title": "Compliance check results",
                "last-modified": report.get("timestamp"),
                "version": "1.0",
                "oscal-version": "1.1.2",
            },
            "results": [
                {
                    "uuid": str(report.get("id") or ""),
                    "title": report.get("standard_name") or report.get("standard"),
                    "description": json.dumps(report.get("summary") or {}, ensure_ascii=False),
                    "start": report.get("timestamp"),
                    "end": report.get("timestamp"),
                    "findings": findings,
                    "local-definitions": {
                        "ata-verification": {
                            "report_hash": report.get("report_hash"),
                            "chain_hash": report.get("chain_hash"),
                            "prev_hash": report.get("prev_hash"),
                            "timestamp_proof": (pack or {}).get("timestamp_proof")
                            or report.get("timestamp_proof"),
                            "blockchain_anchor": (pack or {}).get("blockchain_anchor"),
                        }
                    },
                }
            ],
        },
    }
    return doc


def pack_integrity_token(pack: Mapping[str, Any]) -> str:
    """Optional outer hash of the pack body for quick link integrity checks."""
    blob = json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)
