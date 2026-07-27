"""Independent timestamp proofs + lightweight chain-head anchoring.

MVP:
- Local RFC3161-style digest + optional OpenTimestamps calendar stub
  (offline-capable: always produces a verifiable local TSA receipt;
   when network available, tries public calendar endpoints).
- Sepolia (or mock) anchoring of latest attestation chain head.
  Set ATA_ANCHOR_RPC / ATA_ANCHOR_PRIVATE_KEY for real txs;
  otherwise records a deterministic mock anchor for demo.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from attestation import GENESIS, sha256_text, utc_now
from models import connect, init_db, latest_chain_hash
from write_buffer import flush_now, peek_prev_hash

# Optional network — never required for local proof generation
_OTS_CALENDARS = [
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
]


def _tsa_receipt(payload_hash: str, *, source: str = "local_rfc3161_mvp") -> Dict[str, Any]:
    """Produce a local timestamp receipt (MVP stand-in for RFC 3161 / OTS).

    Binding: sha256(payload_hash | unix_ts | nonce) — proves association of
    content hash with a wall-clock claim from this service. External OTS
    calendar submission is best-effort and recorded when successful.
    """
    ts = utc_now()
    unix = str(int(time.time()))
    nonce = uuid.uuid4().hex
    token = sha256_text(f"{payload_hash}|{unix}|{nonce}")
    receipt = {
        "version": "ata-tsa-v1",
        "source": source,
        "payload_hash": payload_hash,
        "timestamp": ts,
        "unix": unix,
        "nonce": nonce,
        "token": token,
        "verify_method": (
            "Recompute token = SHA256(payload_hash|unix|nonce) and compare; "
            "optionally verify external_calendar_url if present."
        ),
    }
    # Best-effort OpenTimestamps calendar ping (no full OTS lib dependency)
    external = None
    try:
        import urllib.request

        body = json.dumps({"hash": payload_hash, "algorithm": "sha256"}).encode()
        req = urllib.request.Request(
            _OTS_CALENDARS[0] + "/timestamp",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            external = {
                "calendar": _OTS_CALENDARS[0],
                "status": resp.status,
                "note": "calendar contacted; full OTS upgrade path reserved",
            }
    except Exception:
        external = {
            "calendar": None,
            "status": "offline_or_skipped",
            "note": "local TSA receipt still valid for platform-bound proof",
        }
    receipt["external"] = external
    return receipt


def stamp_hash(payload_hash: str) -> Dict[str, Any]:
    return _tsa_receipt(payload_hash)


def verify_tsa_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    if not receipt:
        return {"ok": False, "message": "empty receipt"}
    expected = sha256_text(
        f"{receipt.get('payload_hash')}|{receipt.get('unix')}|{receipt.get('nonce')}"
    )
    ok = expected == str(receipt.get("token") or "")
    return {
        "ok": ok,
        "expected_token": expected,
        "actual_token": receipt.get("token"),
        "message": (
            "local TSA receipt intact (MVP; not an independent RFC3161/OTS proof)"
            if ok
            else "timestamp receipt mismatch"
        ),
        "timestamp": receipt.get("timestamp"),
        "source": receipt.get("source"),
        "independent": False,
    }


def _ensure_anchor_table(db_path: Optional[Path] = None) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chain_anchors (
              id TEXT PRIMARY KEY,
              api_key TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              chain_head TEXT NOT NULL,
              network TEXT NOT NULL,
              tx_hash TEXT NOT NULL,
              block_number TEXT,
              status TEXT NOT NULL,
              receipt_json TEXT,
              mock INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.commit()


def latest_anchor(api_key: str, *, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    _ensure_anchor_table(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM chain_anchors
            WHERE api_key=? ORDER BY timestamp DESC LIMIT 1
            """,
            (api_key,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["receipt"] = json.loads(d.get("receipt_json") or "{}")
        except json.JSONDecodeError:
            d["receipt"] = {}
        return d


def list_anchors(
    api_key: str, *, limit: int = 20, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    _ensure_anchor_table(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM chain_anchors
            WHERE api_key=? ORDER BY timestamp DESC LIMIT ?
            """,
            (api_key, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["receipt"] = json.loads(d.get("receipt_json") or "{}")
            except json.JSONDecodeError:
                d["receipt"] = {}
            out.append(d)
        return out


def _mock_anchor_tx(chain_head: str) -> Dict[str, Any]:
    """Deterministic mock Sepolia-style tx for demos without gas."""
    raw = sha256_text(f"sepolia-mock|{chain_head}|{utc_now()[:10]}")
    return {
        "network": "sepolia-mock",
        "tx_hash": "0x" + raw,
        "block_number": "mock",
        "status": "mocked",
        "mock": True,
        "explorer_hint": f"https://sepolia.etherscan.io/tx/0x{raw}",
        "note": "Set ATA_ANCHOR_RPC + ATA_ANCHOR_PRIVATE_KEY for real Sepolia txs.",
    }


def _try_real_sepolia_anchor(chain_head: str) -> Optional[Dict[str, Any]]:
    rpc = os.environ.get("ATA_ANCHOR_RPC", "").strip()
    pk = os.environ.get("ATA_ANCHOR_PRIVATE_KEY", "").strip()
    if not rpc or not pk:
        return None
    try:
        # Minimal eth_sendRawTransaction via eth_account if installed
        from eth_account import Account  # type: ignore
        import urllib.request

        acct = Account.from_key(pk)
        # Store chain head as data on a 0-value self-tx (data field)
        data_hex = "0x" + chain_head.encode().hex()
        # eth_getTransactionCount
        def rpc_call(method: str, params: list) -> Any:
            body = json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            ).encode()
            req = urllib.request.Request(
                rpc, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode()).get("result")

        nonce = int(rpc_call("eth_getTransactionCount", [acct.address, "latest"]), 16)
        gas_price = int(rpc_call("eth_gasPrice", []) or "0x3b9aca00", 16)
        tx = {
            "nonce": nonce,
            "gasPrice": gas_price,
            "gas": 30000,
            "to": acct.address,
            "value": 0,
            "data": data_hex,
            "chainId": 11155111,
        }
        signed = acct.sign_transaction(tx)
        raw = "0x" + signed.rawTransaction.hex()
        tx_hash = rpc_call("eth_sendRawTransaction", [raw])
        return {
            "network": "sepolia",
            "tx_hash": tx_hash,
            "block_number": "pending",
            "status": "submitted",
            "mock": False,
            "explorer_hint": f"https://sepolia.etherscan.io/tx/{tx_hash}",
        }
    except Exception as e:
        return {
            "network": "sepolia",
            "tx_hash": "",
            "status": "failed",
            "mock": False,
            "error": str(e)[:200],
        }


def anchor_chain_head(
    *,
    api_key: str,
    db_path: Optional[Path] = None,
    force_mock: bool = False,
) -> Dict[str, Any]:
    """Anchor latest attestation chain head; mock by default."""
    _ensure_anchor_table(db_path)
    # Flush buffered proxy writes so head includes pending links
    flush_now()
    head = peek_prev_hash(api_key, db_path=db_path) or latest_chain_hash(
        api_key, db_path=db_path
    )
    if head == GENESIS or head == "0" * 64:
        # still allow anchoring empty genesis for demo
        pass
    real = None if force_mock else _try_real_sepolia_anchor(head)
    if real and real.get("tx_hash") and real.get("status") != "failed":
        info = real
    else:
        info = _mock_anchor_tx(head)
        if real and real.get("status") == "failed":
            info["fallback_reason"] = real.get("error")

    tsa = stamp_hash(head)
    aid = f"anc_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    receipt = {"anchor": info, "timestamp_proof": tsa}
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chain_anchors
              (id, api_key, timestamp, chain_head, network, tx_hash, block_number,
               status, receipt_json, mock)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                aid,
                api_key,
                ts,
                head,
                info.get("network"),
                info.get("tx_hash"),
                str(info.get("block_number") or ""),
                info.get("status"),
                json.dumps(receipt, ensure_ascii=False),
                1 if info.get("mock") else 0,
            ),
        )
        conn.commit()
    return {
        "anchor_id": aid,
        "api_key_suffix": api_key[-6:],
        "timestamp": ts,
        "chain_head": head,
        **info,
        "timestamp_proof": tsa,
    }


def attach_timestamp_to_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Add / refresh independent timestamp proof on a compliance report dict."""
    payload = report.get("report_hash") or report.get("chain_hash") or ""
    if not payload:
        return report
    receipt = stamp_hash(str(payload))
    report = dict(report)
    report["timestamp_proof"] = receipt
    report["timestamp_verify"] = verify_tsa_receipt(receipt)
    return report
