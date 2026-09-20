"""SQLite models for ai-attestation MVP.

Tables: api_calls, attestation_chain, query_history, compliance_checks,
behavior_baselines, drift_marks, api_keys (+ chain_anchors via anchoring.py).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_lock = threading.Lock()


def _default_db_path() -> Path:
    from paths import product_data_root

    return product_data_root() / "attest.db"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(attestation_chain)").fetchall()}
    if "event_type" not in cols:
        conn.execute(
            "ALTER TABLE attestation_chain ADD COLUMN event_type TEXT NOT NULL DEFAULT 'call'"
        )
    if "ref_id" not in cols:
        conn.execute("ALTER TABLE attestation_chain ADD COLUMN ref_id TEXT")
        conn.execute(
            "UPDATE attestation_chain SET ref_id = call_id WHERE ref_id IS NULL"
        )
    call_cols = {r[1] for r in conn.execute("PRAGMA table_info(api_calls)").fetchall()}
    if call_cols and "vendor" not in call_cols:
        conn.execute(
            "ALTER TABLE api_calls ADD COLUMN vendor TEXT NOT NULL DEFAULT 'openai'"
        )
    # Extra indexes for dashboard / pagination (idempotent)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_calls_endpoint ON api_calls(endpoint)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_calls_status ON api_calls(status_code)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_calls_vendor ON api_calls(api_key, vendor)"
    )
    # api_keys enterprise columns
    key_cols = {r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    if key_cols:
        if "name" not in key_cols:
            conn.execute("ALTER TABLE api_keys ADD COLUMN name TEXT")
            conn.execute(
                "UPDATE api_keys SET name = COALESCE(label, 'unnamed') WHERE name IS NULL"
            )
        if "role" not in key_cols:
            conn.execute(
                "ALTER TABLE api_keys ADD COLUMN role TEXT NOT NULL DEFAULT 'read_write'"
            )
        if "status" not in key_cols:
            conn.execute(
                "ALTER TABLE api_keys ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        if "last_used_at" not in key_cols:
            conn.execute("ALTER TABLE api_keys ADD COLUMN last_used_at TEXT")
        # Demo / legacy keys → admin
        conn.execute(
            """
            UPDATE api_keys SET role='admin', status='active',
              name=COALESCE(NULLIF(name,''), NULLIF(label,''), 'demo')
            WHERE api_key LIKE 'ata_demo_%' OR label='demo'
            """
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS report_subscriptions (
          id TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          email TEXT NOT NULL,
          frequency TEXT NOT NULL,
          content_options TEXT NOT NULL DEFAULT '{}',
          last_sent_at TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_report_subs_key
          ON report_subscriptions(api_key);

        CREATE TABLE IF NOT EXISTS report_history (
          id TEXT PRIMARY KEY,
          subscription_id TEXT NOT NULL,
          sent_at TEXT NOT NULL,
          status TEXT NOT NULL,
          error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_report_hist_sub
          ON report_history(subscription_id, sent_at DESC);

        CREATE TABLE IF NOT EXISTS research_artifacts (
          id TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          title TEXT NOT NULL,
          kind TEXT NOT NULL,
          artifact_hash TEXT NOT NULL,
          hash_alg TEXT NOT NULL DEFAULT 'sha256',
          byte_length INTEGER,
          filename_hint TEXT,
          authors_label TEXT,
          description TEXT,
          client_hashed INTEGER NOT NULL DEFAULT 1,
          prev_hash TEXT NOT NULL,
          chain_hash TEXT NOT NULL,
          attest_id TEXT NOT NULL,
          tsa_receipt TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          superseded_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_research_art_key_ts
          ON research_artifacts(api_key, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_research_art_hash
          ON research_artifacts(api_key, artifact_hash);
        CREATE INDEX IF NOT EXISTS idx_research_art_chain
          ON research_artifacts(chain_hash);

        CREATE TABLE IF NOT EXISTS public_shares (
          token TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          revoked INTEGER NOT NULL DEFAULT 0,
          revoked_at TEXT,
          view_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_public_shares_target
          ON public_shares(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_public_shares_api_key
          ON public_shares(api_key);

        CREATE TABLE IF NOT EXISTS research_timeline (
          id TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          event_kind TEXT NOT NULL,
          artifact_id TEXT,
          call_id TEXT,
          vendor TEXT,
          model TEXT,
          label TEXT,
          prev_hash TEXT,
          chain_hash TEXT,
          attest_id TEXT,
          deleted INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_research_timeline_api_key
          ON research_timeline(api_key, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_research_timeline_artifact
          ON research_timeline(artifact_id);
        CREATE INDEX IF NOT EXISTS idx_research_timeline_call
          ON research_timeline(call_id);

        CREATE TABLE IF NOT EXISTS consent_records (
          id TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          vendor TEXT NOT NULL,
          allow_training TEXT NOT NULL,
          source TEXT,
          policy_url TEXT,
          policy_hash TEXT,
          note TEXT,
          prev_hash TEXT,
          chain_hash TEXT,
          attest_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_consent_records_api_key
          ON consent_records(api_key, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_consent_records_vendor
          ON consent_records(api_key, vendor);
        """
    )


def init_db(db_path: Optional[Path] = None) -> Path:
    path = Path(db_path) if db_path else _default_db_path()
    with _lock:
        conn = connect(path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS api_calls (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  endpoint TEXT NOT NULL,
                  method TEXT NOT NULL DEFAULT 'POST',
                  model TEXT,
                  vendor TEXT NOT NULL DEFAULT 'openai',
                  status_code INTEGER,
                  request_size INTEGER NOT NULL DEFAULT 0,
                  response_size INTEGER NOT NULL DEFAULT 0,
                  duration_ms REAL NOT NULL DEFAULT 0,
                  prompt_tokens INTEGER NOT NULL DEFAULT 0,
                  completion_tokens INTEGER NOT NULL DEFAULT 0,
                  cost_usd REAL NOT NULL DEFAULT 0,
                  request_hash TEXT NOT NULL,
                  response_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_api_calls_key_ts
                  ON api_calls(api_key, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_api_calls_endpoint
                  ON api_calls(endpoint);
                CREATE INDEX IF NOT EXISTS idx_api_calls_status
                  ON api_calls(status_code);

                CREATE TABLE IF NOT EXISTS attestation_chain (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  call_id TEXT NOT NULL,
                  hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  event_type TEXT NOT NULL DEFAULT 'call',
                  ref_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_attest_key_ts
                  ON attestation_chain(api_key, timestamp DESC);

                CREATE TABLE IF NOT EXISTS query_history (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  query_params TEXT NOT NULL,
                  result_count INTEGER NOT NULL DEFAULT 0,
                  result_ids TEXT NOT NULL DEFAULT '[]',
                  query_hash TEXT NOT NULL,
                  result_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL,
                  duration_ms REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_query_hist_key_ts
                  ON query_history(api_key, timestamp DESC);

                CREATE TABLE IF NOT EXISTS compliance_checks (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  standard TEXT NOT NULL,
                  standard_name TEXT,
                  check_results TEXT NOT NULL,
                  summary TEXT NOT NULL DEFAULT '{}',
                  report_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL,
                  duration_ms REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_compliance_key_ts
                  ON compliance_checks(api_key, timestamp DESC);

                CREATE TABLE IF NOT EXISTS behavior_baselines (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  time_range_start TEXT NOT NULL,
                  time_range_end TEXT NOT NULL,
                  time_range_label TEXT,
                  stats TEXT NOT NULL,
                  baseline_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL,
                  duration_ms REAL NOT NULL DEFAULT 0,
                  deleted INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_baselines_key_ts
                  ON behavior_baselines(api_key, timestamp DESC);

                CREATE TABLE IF NOT EXISTS drift_marks (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  call_id TEXT NOT NULL,
                  mark_type TEXT NOT NULL,
                  baseline_id TEXT NOT NULL,
                  deviation TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  reviewed_by TEXT,
                  reviewed_at TEXT,
                  mark_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL,
                  call_endpoint TEXT,
                  call_timestamp TEXT,
                  call_cost_usd REAL,
                  review_hash TEXT,
                  review_prev_hash TEXT,
                  review_chain_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_drift_marks_key_status
                  ON drift_marks(api_key, status, timestamp DESC);

                CREATE TABLE IF NOT EXISTS api_keys (
                  api_key TEXT PRIMARY KEY,
                  label TEXT,
                  name TEXT,
                  role TEXT NOT NULL DEFAULT 'read_write',
                  status TEXT NOT NULL DEFAULT 'active',
                  created_at TEXT NOT NULL,
                  last_used_at TEXT
                );

                CREATE TABLE IF NOT EXISTS report_subscriptions (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  email TEXT NOT NULL,
                  frequency TEXT NOT NULL,
                  content_options TEXT NOT NULL DEFAULT '{}',
                  last_sent_at TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_report_subs_key
                  ON report_subscriptions(api_key);

                CREATE TABLE IF NOT EXISTS report_history (
                  id TEXT PRIMARY KEY,
                  subscription_id TEXT NOT NULL,
                  sent_at TEXT NOT NULL,
                  status TEXT NOT NULL,
                  error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_report_hist_sub
                  ON report_history(subscription_id, sent_at DESC);

                CREATE TABLE IF NOT EXISTS research_artifacts (
                  id TEXT PRIMARY KEY,
                  api_key TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  title TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  artifact_hash TEXT NOT NULL,
                  hash_alg TEXT NOT NULL DEFAULT 'sha256',
                  byte_length INTEGER,
                  filename_hint TEXT,
                  authors_label TEXT,
                  description TEXT,
                  client_hashed INTEGER NOT NULL DEFAULT 1,
                  prev_hash TEXT NOT NULL,
                  chain_hash TEXT NOT NULL,
                  attest_id TEXT NOT NULL,
                  tsa_receipt TEXT,
                  status TEXT NOT NULL DEFAULT 'active',
                  superseded_by TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_research_art_key_ts
                  ON research_artifacts(api_key, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_research_art_hash
                  ON research_artifacts(api_key, artifact_hash);
                CREATE INDEX IF NOT EXISTS idx_research_art_chain
                  ON research_artifacts(chain_hash);
                """
            )
            _migrate(conn)
            conn.commit()
        finally:
            conn.close()
    return path


def _note_tip(api_key: str, chain_hash: str) -> None:
    """Keep write-buffer tip aligned after sync chain inserts (lazy import)."""
    from write_buffer import note_chain_tip

    note_chain_tip(api_key, chain_hash)


def insert_call(
    row: Dict[str, Any],
    *,
    db_path: Optional[Path] = None,
    update_tip: bool = True,
) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO api_calls (
                  id, api_key, timestamp, endpoint, method, model, vendor, status_code,
                  request_size, response_size, duration_ms,
                  prompt_tokens, completion_tokens, cost_usd,
                  request_hash, response_hash, prev_hash, chain_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["endpoint"],
                    row.get("method", "POST"),
                    row.get("model"),
                    row.get("vendor") or "openai",
                    row.get("status_code"),
                    row["request_size"],
                    row["response_size"],
                    row["duration_ms"],
                    row.get("prompt_tokens", 0),
                    row.get("completion_tokens", 0),
                    row["cost_usd"],
                    row["request_hash"],
                    row["response_hash"],
                    row["prev_hash"],
                    row["chain_hash"],
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'call', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    if update_tip:
        _note_tip(row["api_key"], row["chain_hash"])


def insert_query(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO query_history (
                  id, api_key, timestamp, query_params, result_count, result_ids,
                  query_hash, result_hash, prev_hash, chain_hash, duration_ms
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row.get("query_params_json")
                    or json.dumps(row.get("query_params") or {}, ensure_ascii=False),
                    row["result_count"],
                    row.get("result_ids_json") or "[]",
                    row["query_hash"],
                    row["result_hash"],
                    row["prev_hash"],
                    row["chain_hash"],
                    row.get("duration_ms", 0),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'query', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def insert_compliance(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO compliance_checks (
                  id, api_key, timestamp, standard, standard_name,
                  check_results, summary, report_hash, prev_hash, chain_hash, duration_ms
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["standard"],
                    row.get("standard_name"),
                    row.get("check_results_json")
                    or json.dumps(row.get("check_results") or {}, ensure_ascii=False),
                    row.get("summary_json")
                    or json.dumps(row.get("summary") or {}, ensure_ascii=False),
                    row["report_hash"],
                    row["prev_hash"],
                    row["chain_hash"],
                    row.get("duration_ms", 0),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'compliance', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def _parse_compliance_row(d: Dict[str, Any]) -> Dict[str, Any]:
    try:
        d["check_results"] = json.loads(d.get("check_results") or "{}")
    except json.JSONDecodeError:
        d["check_results"] = {}
    try:
        d["summary"] = json.loads(d.get("summary") or "{}")
    except json.JSONDecodeError:
        d["summary"] = {}
    return d


def list_compliance(
    api_key: str, *, limit: int = 50, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM compliance_checks
                WHERE api_key=? ORDER BY timestamp DESC LIMIT ?
                """,
                (api_key, limit),
            ).fetchall()
            return [_parse_compliance_row(dict(r)) for r in rows]
        finally:
            conn.close()


def get_compliance(
    check_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM compliance_checks WHERE id=?", (check_id,)
            ).fetchone()
            return _parse_compliance_row(dict(row)) if row else None
        finally:
            conn.close()


def insert_baseline(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO behavior_baselines (
                  id, api_key, timestamp, time_range_start, time_range_end,
                  time_range_label, stats, baseline_hash, prev_hash, chain_hash,
                  duration_ms, deleted
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["time_range_start"],
                    row["time_range_end"],
                    row.get("time_range_label"),
                    row.get("stats_json")
                    or json.dumps(row.get("stats") or {}, ensure_ascii=False),
                    row["baseline_hash"],
                    row["prev_hash"],
                    row["chain_hash"],
                    row.get("duration_ms", 0),
                    int(row.get("deleted") or 0),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'baseline', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def _parse_baseline(d: Dict[str, Any]) -> Dict[str, Any]:
    try:
        d["stats"] = json.loads(d.get("stats") or "{}")
    except json.JSONDecodeError:
        d["stats"] = {}
    d["deleted"] = bool(d.get("deleted"))
    return d


def list_baselines(
    api_key: str,
    *,
    limit: int = 50,
    include_deleted: bool = False,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            if include_deleted:
                rows = conn.execute(
                    """
                    SELECT * FROM behavior_baselines
                    WHERE api_key=? ORDER BY timestamp DESC LIMIT ?
                    """,
                    (api_key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM behavior_baselines
                    WHERE api_key=? AND deleted=0 ORDER BY timestamp DESC LIMIT ?
                    """,
                    (api_key, limit),
                ).fetchall()
            return [_parse_baseline(dict(r)) for r in rows]
        finally:
            conn.close()


def get_baseline(
    baseline_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM behavior_baselines WHERE id=?", (baseline_id,)
            ).fetchone()
            return _parse_baseline(dict(row)) if row else None
        finally:
            conn.close()


def soft_delete_baseline(baseline_id: str, *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE behavior_baselines SET deleted=1 WHERE id=?", (baseline_id,)
            )
            conn.commit()
        finally:
            conn.close()


def insert_drift_mark(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO drift_marks (
                  id, api_key, timestamp, call_id, mark_type, baseline_id, deviation,
                  status, reviewed_by, reviewed_at, mark_hash, prev_hash, chain_hash,
                  call_endpoint, call_timestamp, call_cost_usd
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["call_id"],
                    row["mark_type"],
                    row["baseline_id"],
                    row.get("deviation_json")
                    or json.dumps(row.get("deviation") or {}, ensure_ascii=False),
                    row.get("status", "pending"),
                    row.get("reviewed_by"),
                    row.get("reviewed_at"),
                    row["mark_hash"],
                    row["prev_hash"],
                    row["chain_hash"],
                    row.get("call_endpoint"),
                    row.get("call_timestamp"),
                    row.get("call_cost_usd"),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'drift_mark', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def _parse_drift(d: Dict[str, Any]) -> Dict[str, Any]:
    try:
        d["deviation"] = json.loads(d.get("deviation") or "{}")
    except json.JSONDecodeError:
        d["deviation"] = {}
    return d


def list_drift_marks(
    api_key: str,
    *,
    status: Optional[str] = "pending",
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM drift_marks
                    WHERE api_key=? AND status=? ORDER BY timestamp DESC LIMIT ?
                    """,
                    (api_key, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM drift_marks
                    WHERE api_key=? ORDER BY timestamp DESC LIMIT ?
                    """,
                    (api_key, limit),
                ).fetchall()
            return [_parse_drift(dict(r)) for r in rows]
        finally:
            conn.close()


def get_drift_mark(
    mark_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM drift_marks WHERE id=?", (mark_id,)
            ).fetchone()
            return _parse_drift(dict(row)) if row else None
        finally:
            conn.close()


def update_drift_mark_review(
    mark_id: str,
    *,
    status: str,
    reviewed_by: str,
    reviewed_at: str,
    review_attest_id: str,
    review_prev_hash: str,
    review_chain_hash: str,
    review_hash: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    api_key = ""
    out: Dict[str, Any] = {}
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT api_key FROM drift_marks WHERE id=?", (mark_id,)
            ).fetchone()
            if not row:
                return {}
            api_key = row["api_key"] or ""
            cur = conn.execute(
                """
                UPDATE drift_marks SET
                  status=?, reviewed_by=?, reviewed_at=?,
                  review_hash=?, review_prev_hash=?, review_chain_hash=?
                WHERE id=?
                """,
                (
                    status,
                    reviewed_by,
                    reviewed_at,
                    review_hash,
                    review_prev_hash,
                    review_chain_hash,
                    mark_id,
                ),
            )
            if cur.rowcount <= 0:
                return {}
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'drift_review', ?)
                """,
                (
                    review_attest_id,
                    api_key,
                    mark_id,
                    review_chain_hash,
                    review_prev_hash,
                    reviewed_at,
                    mark_id,
                ),
            )
            conn.commit()
            full = conn.execute(
                "SELECT * FROM drift_marks WHERE id=?", (mark_id,)
            ).fetchone()
            out = _parse_drift(dict(full)) if full else {}
        finally:
            conn.close()
    if out:
        _note_tip(api_key, review_chain_hash)
    return out


def latest_chain_hash(api_key: str, *, db_path: Optional[Path] = None) -> str:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT hash FROM attestation_chain
                WHERE api_key=? ORDER BY timestamp DESC, rowid DESC LIMIT 1
                """,
                (api_key,),
            ).fetchone()
            return row["hash"] if row else "0" * 64
        finally:
            conn.close()


def list_calls(
    api_key: str,
    *,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM api_calls
                WHERE api_key=? ORDER BY timestamp DESC LIMIT ? OFFSET ?
                """,
                (api_key, int(limit), int(offset)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def count_calls(api_key: str, *, db_path: Optional[Path] = None) -> int:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM api_calls WHERE api_key=?", (api_key,)
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()


def sum_call_cost(api_key: str, *, db_path: Optional[Path] = None) -> float:
    """Full-table cost total (not capped by list_calls pagination)."""
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS cost FROM api_calls WHERE api_key=?",
                (api_key,),
            ).fetchone()
            return float(row["cost"] if row else 0)
        finally:
            conn.close()


def dashboard_overview(api_key: str, *, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregates for overview cards + 7-day trends + vendor pie (today)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_s = today_start.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    days = []
    for i in range(6, -1, -1):
        d = (today_start - timedelta(days=i)).strftime("%Y-%m-%d")
        days.append(d)
    week_start = (today_start - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    with _lock:
        conn = connect(db_path)
        try:
            today_row = conn.execute(
                """
                SELECT COUNT(*) AS n, COALESCE(SUM(cost_usd), 0) AS cost
                FROM api_calls WHERE api_key=? AND timestamp >= ?
                """,
                (api_key, today_s),
            ).fetchone()
            pending = conn.execute(
                """
                SELECT COUNT(*) AS n FROM drift_marks
                WHERE api_key=? AND status='pending'
                """,
                (api_key,),
            ).fetchone()
            series_rows = conn.execute(
                """
                SELECT substr(timestamp, 1, 10) AS day,
                       COUNT(*) AS calls,
                       COALESCE(SUM(cost_usd), 0) AS cost
                FROM api_calls
                WHERE api_key=? AND timestamp >= ?
                GROUP BY substr(timestamp, 1, 10)
                """,
                (api_key, week_start),
            ).fetchall()
            mark_rows = conn.execute(
                """
                SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS marks
                FROM drift_marks
                WHERE api_key=? AND timestamp >= ?
                GROUP BY substr(timestamp, 1, 10)
                """,
                (api_key, week_start),
            ).fetchall()
            vendor_rows = conn.execute(
                """
                SELECT COALESCE(vendor, 'openai') AS vendor, COUNT(*) AS count
                FROM api_calls
                WHERE api_key=? AND timestamp >= ?
                GROUP BY COALESCE(vendor, 'openai')
                ORDER BY count DESC
                """,
                (api_key, today_s),
            ).fetchall()
            if not vendor_rows:
                vendor_rows = conn.execute(
                    """
                    SELECT COALESCE(vendor, 'openai') AS vendor, COUNT(*) AS count
                    FROM api_calls
                    WHERE api_key=?
                    GROUP BY COALESCE(vendor, 'openai')
                    ORDER BY count DESC
                    LIMIT 12
                    """,
                    (api_key,),
                ).fetchall()
            latest_comp = conn.execute(
                """
                SELECT summary FROM compliance_checks
                WHERE api_key=? ORDER BY timestamp DESC LIMIT 1
                """,
                (api_key,),
            ).fetchone()
        finally:
            conn.close()

    by_calls = {r["day"]: dict(r) for r in series_rows}
    by_marks = {r["day"]: int(r["marks"]) for r in mark_rows}
    series_7d = []
    for d in days:
        row = by_calls.get(d) or {}
        series_7d.append(
            {
                "day": d,
                "calls": int(row.get("calls") or 0),
                "cost": float(row.get("cost") or 0),
                "marks": by_marks.get(d, 0),
            }
        )

    compliance_ok: Optional[bool] = None
    compliance_label = "未检查"
    if latest_comp and latest_comp["summary"]:
        try:
            summary = json.loads(latest_comp["summary"])
        except (TypeError, json.JSONDecodeError):
            summary = {}
        fail = int(summary.get("n_fail") or 0)
        compliance_ok = fail == 0
        compliance_label = "最近检查通过" if fail == 0 else f"有 {fail} 项未通过"

    return {
        "today_calls": int(today_row["n"] if today_row else 0),
        "today_cost": float(today_row["cost"] if today_row else 0),
        "pending_marks": int(pending["n"] if pending else 0),
        "compliance": {"ok": compliance_ok, "label": compliance_label},
        "series_7d": series_7d,
        "vendors_today": [
            {"vendor": r["vendor"], "count": int(r["count"])} for r in vendor_rows
        ],
    }


def query_calls(
    api_key: str,
    *,
    ts_from: Optional[str] = None,
    ts_to: Optional[str] = None,
    endpoint_substr: Optional[str] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    status_code_min: Optional[int] = None,
    status_code_max: Optional[int] = None,
    model_substr: Optional[str] = None,
    vendor: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    clauses = ["api_key=?"]
    args: List[Any] = [api_key]
    if ts_from:
        clauses.append("timestamp >= ?")
        args.append(ts_from)
    if ts_to:
        clauses.append("timestamp <= ?")
        args.append(ts_to)
    if endpoint_substr:
        clauses.append("endpoint LIKE ?")
        args.append(f"%{endpoint_substr}%")
    if min_cost is not None:
        clauses.append("cost_usd >= ?")
        args.append(float(min_cost))
    if max_cost is not None:
        clauses.append("cost_usd <= ?")
        args.append(float(max_cost))
    if status_code_min is not None and status_code_max is not None:
        # timeout heuristic from normalize_params: exactly 408+504
        if int(status_code_min) == 408 and int(status_code_max) == 504:
            clauses.append("status_code IN (408, 504)")
        else:
            clauses.append("status_code >= ? AND status_code <= ?")
            args.extend([int(status_code_min), int(status_code_max)])
    elif status_code_min is not None:
        clauses.append("status_code >= ?")
        args.append(int(status_code_min))
    elif status_code_max is not None:
        clauses.append("status_code <= ?")
        args.append(int(status_code_max))
    if model_substr:
        clauses.append("model LIKE ?")
        args.append(f"%{model_substr}%")
    if vendor:
        clauses.append("COALESCE(vendor, 'openai') = ?")
        args.append(str(vendor).strip().lower())
    args.extend([int(limit), int(offset)])
    sql = (
        f"SELECT * FROM api_calls WHERE {' AND '.join(clauses)} "
        f"ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    )
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(sql, args).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_call(call_id: str, *, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute("SELECT * FROM api_calls WHERE id=?", (call_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_queries(
    api_key: str, *, limit: int = 20, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM query_history
                WHERE api_key=? ORDER BY timestamp DESC LIMIT ?
                """,
                (api_key, limit),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["query_params"] = json.loads(d.get("query_params") or "{}")
                except json.JSONDecodeError:
                    d["query_params"] = {}
                try:
                    d["result_ids"] = json.loads(d.get("result_ids") or "[]")
                except json.JSONDecodeError:
                    d["result_ids"] = []
                out.append(d)
            return out
        finally:
            conn.close()


def get_query(query_id: str, *, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM query_history WHERE id=?", (query_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["query_params"] = json.loads(d.get("query_params") or "{}")
            except json.JSONDecodeError:
                d["query_params"] = {}
            try:
                d["result_ids"] = json.loads(d.get("result_ids") or "[]")
            except json.JSONDecodeError:
                d["result_ids"] = []
            return d
        finally:
            conn.close()


def list_chain(
    api_key: str,
    *,
    limit: Optional[int] = 500,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return chain links in chronological order.

    - ``limit is None``: full chain from genesis (for integrity verification).
    - ``limit`` set: tip-relative newest N (DESC then reverse) for previews/packs.
    """
    with _lock:
        conn = connect(db_path)
        try:
            if limit is None:
                rows = conn.execute(
                    """
                    SELECT * FROM attestation_chain
                    WHERE api_key=? ORDER BY timestamp ASC, rowid ASC
                    """,
                    (api_key,),
                ).fetchall()
                return [dict(r) for r in rows]
            rows = conn.execute(
                """
                SELECT * FROM attestation_chain
                WHERE api_key=? ORDER BY timestamp DESC, rowid DESC LIMIT ?
                """,
                (api_key, int(limit)),
            ).fetchall()
            out = [dict(r) for r in rows]
            out.reverse()
            return out
        finally:
            conn.close()


def count_chain_links(api_key: str, *, db_path: Optional[Path] = None) -> int:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM attestation_chain WHERE api_key=?",
                (api_key,),
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()


def _parse_research_artifact(d: Dict[str, Any]) -> Dict[str, Any]:
    """解析科研工件行：TSA JSON、布尔字段。不含原文。"""
    raw = d.get("tsa_receipt")
    if isinstance(raw, str) and raw.strip():
        try:
            d["tsa_receipt"] = json.loads(raw)
        except json.JSONDecodeError:
            d["tsa_receipt"] = {}
    elif not isinstance(raw, dict):
        d["tsa_receipt"] = None
    d["client_hashed"] = bool(d.get("client_hashed"))
    return d


def insert_research_artifact(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    """写入科研工件并追加 attestation_chain（event_type=research_artifact）。"""
    tsa = row.get("tsa_receipt")
    tsa_json = (
        tsa
        if isinstance(tsa, str)
        else json.dumps(tsa or {}, ensure_ascii=False)
        if tsa
        else None
    )
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO research_artifacts (
                  id, api_key, timestamp, title, kind, artifact_hash, hash_alg,
                  byte_length, filename_hint, authors_label, description,
                  client_hashed, prev_hash, chain_hash, attest_id, tsa_receipt,
                  status, superseded_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["title"],
                    row["kind"],
                    row["artifact_hash"],
                    row.get("hash_alg") or "sha256",
                    row.get("byte_length"),
                    row.get("filename_hint"),
                    row.get("authors_label"),
                    row.get("description"),
                    1 if row.get("client_hashed", True) else 0,
                    row["prev_hash"],
                    row["chain_hash"],
                    row["attest_id"],
                    tsa_json,
                    row.get("status") or "active",
                    row.get("superseded_by"),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'research_artifact', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def count_research_artifacts(api_key: str, *, db_path: Optional[Path] = None) -> int:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM research_artifacts WHERE api_key=?",
                (api_key,),
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()


def list_research_artifacts(
    api_key: str,
    *,
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM research_artifacts
                WHERE api_key=? ORDER BY timestamp DESC LIMIT ? OFFSET ?
                """,
                (api_key, int(limit), int(offset)),
            ).fetchall()
            return [_parse_research_artifact(dict(r)) for r in rows]
        finally:
            conn.close()


def get_research_artifact(
    artifact_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM research_artifacts WHERE id=?", (artifact_id,)
            ).fetchone()
            return _parse_research_artifact(dict(row)) if row else None
        finally:
            conn.close()


def list_prior_artifact_hashes(
    api_key: str,
    artifact_hash: str,
    *,
    exclude_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """同一指纹的历史登记（允许重复；用于「该指纹已于某时登记过」）。"""
    with _lock:
        conn = connect(db_path)
        try:
            if exclude_id:
                rows = conn.execute(
                    """
                    SELECT id, timestamp, title FROM research_artifacts
                    WHERE api_key=? AND artifact_hash=? AND id!=?
                    ORDER BY timestamp ASC
                    """,
                    (api_key, artifact_hash, exclude_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, timestamp, title FROM research_artifacts
                    WHERE api_key=? AND artifact_hash=?
                    ORDER BY timestamp ASC
                    """,
                    (api_key, artifact_hash),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def _parse_timeline(d: Dict[str, Any]) -> Dict[str, Any]:
    d["deleted"] = bool(d.get("deleted"))
    return d


def insert_research_timeline(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    """写入科研时间线并追加 attestation_chain（event_type=research_timeline）。"""
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO research_timeline (
                  id, api_key, timestamp, event_kind, artifact_id, call_id,
                  vendor, model, label, prev_hash, chain_hash, attest_id, deleted
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row.get("event_kind") or "api_call",
                    row.get("artifact_id"),
                    row.get("call_id"),
                    row.get("vendor"),
                    row.get("model"),
                    row.get("label"),
                    row["prev_hash"],
                    row["chain_hash"],
                    row["attest_id"],
                    int(row.get("deleted") or 0),
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'research_timeline', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def insert_consent_record(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    """写入训练同意记录并追加 attestation_chain（event_type=research_consent）。"""
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO consent_records (
                  id, api_key, timestamp, vendor, allow_training, source,
                  policy_url, policy_hash, note, prev_hash, chain_hash, attest_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["timestamp"],
                    row["vendor"],
                    row["allow_training"],
                    row.get("source"),
                    row.get("policy_url"),
                    row.get("policy_hash"),
                    row.get("note"),
                    row["prev_hash"],
                    row["chain_hash"],
                    row["attest_id"],
                ),
            )
            conn.execute(
                """
                INSERT INTO attestation_chain
                  (id, api_key, call_id, hash, prev_hash, timestamp, event_type, ref_id)
                VALUES (?,?,?,?,?,?, 'research_consent', ?)
                """,
                (
                    row["attest_id"],
                    row["api_key"],
                    row["id"],
                    row["chain_hash"],
                    row["prev_hash"],
                    row["timestamp"],
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    _note_tip(row["api_key"], row["chain_hash"])


def get_consent_record(
    consent_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM consent_records WHERE id=?", (consent_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_consent_records(
    api_key: str,
    *,
    limit: int = 200,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """按时间倒序；用于当前有效同意与审计历史。"""
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM consent_records
                WHERE api_key=?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (api_key, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_research_timeline(
    timeline_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """含已软删除行（整链重算需要）。"""
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM research_timeline WHERE id=?", (timeline_id,)
            ).fetchone()
            return _parse_timeline(dict(row)) if row else None
        finally:
            conn.close()


def list_research_timeline(
    api_key: str,
    *,
    artifact_id: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 200,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            clauses = ["api_key=?"]
            args: List[Any] = [api_key]
            if not include_deleted:
                clauses.append("deleted=0")
            if artifact_id:
                clauses.append("artifact_id=?")
                args.append(artifact_id)
            args.append(int(limit))
            rows = conn.execute(
                f"""
                SELECT * FROM research_timeline
                WHERE {' AND '.join(clauses)}
                ORDER BY timestamp DESC LIMIT ?
                """,
                args,
            ).fetchall()
            return [_parse_timeline(dict(r)) for r in rows]
        finally:
            conn.close()


def find_active_timeline_link(
    api_key: str,
    *,
    artifact_id: str,
    call_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT * FROM research_timeline
                WHERE api_key=? AND artifact_id=? AND call_id=? AND deleted=0
                ORDER BY timestamp DESC LIMIT 1
                """,
                (api_key, artifact_id, call_id),
            ).fetchone()
            return _parse_timeline(dict(row)) if row else None
        finally:
            conn.close()


def list_linked_calls(
    api_key: str,
    artifact_id: str,
    *,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """关联到某工件的调用摘要（不含 api_key / 原文）。"""
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT t.id AS timeline_id, t.timestamp AS linked_at, t.label,
                       t.call_id, t.vendor, t.model, t.chain_hash AS timeline_chain_hash,
                       c.timestamp AS call_timestamp, c.endpoint, c.model AS call_model,
                       c.chain_hash AS call_chain_hash, c.prev_hash AS call_prev_hash,
                       c.status_code, c.cost_usd
                FROM research_timeline t
                LEFT JOIN api_calls c ON c.id = t.call_id
                WHERE t.api_key=? AND t.artifact_id=? AND t.deleted=0
                ORDER BY t.timestamp DESC
                """,
                (api_key, artifact_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def soft_delete_research_timeline(
    timeline_id: str, api_key: str, *, db_path: Optional[Path] = None
) -> bool:
    """软删除：链环仍在，列表不再展示。硬删会让整链校验失败。"""
    with _lock:
        conn = connect(db_path)
        try:
            cur = conn.execute(
                """
                UPDATE research_timeline SET deleted=1
                WHERE id=? AND api_key=? AND deleted=0
                """,
                (timeline_id, api_key),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def insert_public_share(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO public_shares (
                  token, api_key, target_type, target_id, created_at,
                  revoked, revoked_at, view_count
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    row["token"],
                    row["api_key"],
                    row["target_type"],
                    row["target_id"],
                    row["created_at"],
                    int(row.get("revoked") or 0),
                    row.get("revoked_at"),
                    int(row.get("view_count") or 0),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_public_share(token: str, *, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM public_shares WHERE token=?", (token,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_active_share(
    api_key: str,
    *,
    target_type: str,
    target_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT * FROM public_shares
                WHERE api_key=? AND target_type=? AND target_id=? AND revoked=0
                ORDER BY created_at DESC LIMIT 1
                """,
                (api_key, target_type, target_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def revoke_public_share(
    token: str, api_key: str, *, revoked_at: str, db_path: Optional[Path] = None
) -> bool:
    with _lock:
        conn = connect(db_path)
        try:
            cur = conn.execute(
                """
                UPDATE public_shares SET revoked=1, revoked_at=?
                WHERE token=? AND api_key=? AND revoked=0
                """,
                (revoked_at, token, api_key),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def bump_share_views(token: str, *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE public_shares SET view_count = view_count + 1 WHERE token=?",
                (token,),
            )
            conn.commit()
        finally:
            conn.close()


def enrich_maps_for_chain(
    api_key: str,
    chain_rows: List[Dict[str, Any]],
    *,
    db_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load event rows referenced by chain links (avoids tip-window enrichment gaps)."""
    calls: Dict[str, Dict[str, Any]] = {}
    queries: Dict[str, Dict[str, Any]] = {}
    comps: Dict[str, Dict[str, Any]] = {}
    bas: Dict[str, Dict[str, Any]] = {}
    marks: Dict[str, Dict[str, Any]] = {}
    arts: Dict[str, Dict[str, Any]] = {}
    timelines: Dict[str, Dict[str, Any]] = {}
    consents: Dict[str, Dict[str, Any]] = {}
    for row in chain_rows:
        et = str(row.get("event_type") or "call")
        ref = str(row.get("ref_id") or row.get("call_id") or "")
        if not ref:
            continue
        if et == "query":
            if ref in queries:
                continue
            q = get_query(ref, db_path=db_path)
            if q and q.get("api_key") == api_key:
                queries[ref] = q
        elif et == "compliance":
            if ref in comps:
                continue
            c = get_compliance(ref, db_path=db_path)
            if c and c.get("api_key") == api_key:
                comps[ref] = c
        elif et == "baseline":
            if ref in bas:
                continue
            b = get_baseline(ref, db_path=db_path)
            if b and b.get("api_key") == api_key:
                bas[ref] = b
        elif et in ("drift_mark", "drift_review"):
            if ref in marks:
                continue
            m = get_drift_mark(ref, db_path=db_path)
            if m and m.get("api_key") == api_key:
                marks[ref] = m
        elif et == "research_artifact":
            if ref in arts:
                continue
            a = get_research_artifact(ref, db_path=db_path)
            if a and a.get("api_key") == api_key:
                arts[ref] = a
        elif et == "research_timeline":
            if ref in timelines:
                continue
            t = get_research_timeline(ref, db_path=db_path)
            if t and t.get("api_key") == api_key:
                timelines[ref] = t
        elif et == "research_consent":
            if ref in consents:
                continue
            cn = get_consent_record(ref, db_path=db_path)
            if cn and cn.get("api_key") == api_key:
                consents[ref] = cn
        else:
            if ref in calls:
                continue
            c = get_call(ref, db_path=db_path)
            if c and c.get("api_key") == api_key:
                calls[ref] = c
    return {
        "calls_by_id": calls,
        "queries_by_id": queries,
        "compliance_by_id": comps,
        "baselines_by_id": bas,
        "drift_marks_by_id": marks,
        "artifacts_by_id": arts,
        "timelines_by_id": timelines,
        "consents_by_id": consents,
    }


def ensure_api_key(
    api_key: str,
    *,
    label: str = "demo",
    name: Optional[str] = None,
    role: str = "read_write",
    db_path: Optional[Path] = None,
) -> None:
    from datetime import datetime, timezone

    with _lock:
        conn = connect(db_path)
        try:
            existing = conn.execute(
                "SELECT api_key, status FROM api_keys WHERE api_key=?", (api_key,)
            ).fetchone()
            if existing:
                # Do not silently revive disabled/deleted keys via ensure
                return
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            display = name or label or "unnamed"
            # New auto-provisioned keys default to least privilege unless caller overrides
            safe_role = role if role in ("read_only", "read_write", "admin") else "read_only"
            conn.execute(
                """
                INSERT INTO api_keys
                  (api_key, label, name, role, status, created_at, last_used_at)
                VALUES (?,?,?,?, 'active', ?, NULL)
                """,
                (api_key, label, display, safe_role, now),
            )
            conn.commit()
        finally:
            conn.close()


def touch_api_key(api_key: str, *, db_path: Optional[Path] = None) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE api_keys SET last_used_at=? WHERE api_key=?", (now, api_key)
            )
            conn.commit()
        finally:
            conn.close()


def get_api_key_row(
    api_key: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE api_key=?", (api_key,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_api_keys(
    *, include_deleted: bool = False, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            if include_deleted:
                rows = conn.execute(
                    "SELECT * FROM api_keys ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM api_keys WHERE status != 'deleted' ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def update_api_key(
    api_key: str,
    *,
    name: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE api_key=?", (api_key,)
            ).fetchone()
            if not row:
                return None
            n = name if name is not None else row["name"] or row["label"]
            r = role if role is not None else row["role"] if "role" in row.keys() else "read_write"
            s = status if status is not None else (
                row["status"] if "status" in row.keys() else "active"
            )
            conn.execute(
                """
                UPDATE api_keys SET name=?, label=?, role=?, status=? WHERE api_key=?
                """,
                (n, n, r, s, api_key),
            )
            conn.commit()
            out = conn.execute(
                "SELECT * FROM api_keys WHERE api_key=?", (api_key,)
            ).fetchone()
            return dict(out) if out else None
        finally:
            conn.close()


def create_api_key_record(
    *,
    name: str,
    role: str = "read_write",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    import secrets
    from datetime import datetime, timezone

    key = "ata_" + secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO api_keys
                  (api_key, label, name, role, status, created_at, last_used_at)
                VALUES (?,?,?,?, 'active', ?, NULL)
                """,
                (key, name, name, role, now),
            )
            conn.commit()
            return {
                "api_key": key,
                "name": name,
                "role": role,
                "status": "active",
                "created_at": now,
                "last_used_at": None,
            }
        finally:
            conn.close()


def upsert_report_subscription(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO report_subscriptions
                  (id, api_key, email, frequency, content_options, last_sent_at, created_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  email=excluded.email,
                  frequency=excluded.frequency,
                  content_options=excluded.content_options
                """,
                (
                    row["id"],
                    row["api_key"],
                    row["email"],
                    row["frequency"],
                    row.get("content_options")
                    if isinstance(row.get("content_options"), str)
                    else json.dumps(row.get("content_options") or {}, ensure_ascii=False),
                    row.get("last_sent_at"),
                    row["created_at"],
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_report_subscription(
    sub_id: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM report_subscriptions WHERE id=?", (sub_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["content_options"] = json.loads(d.get("content_options") or "{}")
            except json.JSONDecodeError:
                d["content_options"] = {}
            return d
        finally:
            conn.close()


def get_report_subscription_for_key(
    api_key: str, *, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT * FROM report_subscriptions
                WHERE api_key=? ORDER BY created_at DESC LIMIT 1
                """,
                (api_key,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["content_options"] = json.loads(d.get("content_options") or "{}")
            except json.JSONDecodeError:
                d["content_options"] = {}
            return d
        finally:
            conn.close()


def list_report_subscriptions(*, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute("SELECT * FROM report_subscriptions").fetchall()
            out = []
            for row in rows:
                d = dict(row)
                try:
                    d["content_options"] = json.loads(d.get("content_options") or "{}")
                except json.JSONDecodeError:
                    d["content_options"] = {}
                out.append(d)
            return out
        finally:
            conn.close()


def mark_subscription_sent(
    sub_id: str, *, sent_at: str, db_path: Optional[Path] = None
) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE report_subscriptions SET last_sent_at=? WHERE id=?",
                (sent_at, sub_id),
            )
            conn.commit()
        finally:
            conn.close()


def insert_report_history(row: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    with _lock:
        conn = connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO report_history
                  (id, subscription_id, sent_at, status, error_message)
                VALUES (?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["subscription_id"],
                    row["sent_at"],
                    row["status"],
                    row.get("error_message"),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def list_report_history(
    subscription_id: str, *, limit: int = 10, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM report_history
                WHERE subscription_id=? ORDER BY sent_at DESC LIMIT ?
                """,
                (subscription_id, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def list_report_history_for_key(
    api_key: str, *, limit: int = 10, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with _lock:
        conn = connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT h.* FROM report_history h
                JOIN report_subscriptions s ON s.id = h.subscription_id
                WHERE s.api_key=?
                ORDER BY h.sent_at DESC LIMIT ?
                """,
                (api_key, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
