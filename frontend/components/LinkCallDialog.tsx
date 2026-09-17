"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { parseApiError, withApiKey } from "@/lib/api";
import type { ApiCall } from "./Timeline";

type Props = {
  open: boolean;
  apiBase: string;
  apiKey: string;
  artifactId: string;
  alreadyLinked: Set<string>;
  onClose: () => void;
  onLinked: () => void;
};

/**
 * 从最近调用里选一条，关联到当前科研工件。
 */
export function LinkCallDialog({
  open,
  apiBase,
  apiKey,
  artifactId,
  alreadyLinked,
  onClose,
  onLinked,
}: Props) {
  const [calls, setCalls] = useState<ApiCall[]>([]);
  const [model, setModel] = useState("");
  const [since, setSince] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !apiKey) return;
    fetch(withApiKey(`${apiBase}/v1/dashboard/calls?limit=50`, apiKey))
      .then(async (r) => {
        if (!r.ok) throw new Error(await parseApiError(r, "无法加载调用"));
        return r.json();
      })
      .then((d) => setCalls(d.calls || []))
      .catch((e) => setErr(e instanceof Error ? e.message : "无法加载调用"));
  }, [open, apiBase, apiKey]);

  const filtered = useMemo(() => {
    const q = model.trim().toLowerCase();
    return calls.filter((c) => {
      if (q && !String(c.model || "").toLowerCase().includes(q)) return false;
      if (since && String(c.timestamp || "") < since) return false;
      return true;
    });
  }, [calls, model, since]);

  const link = useCallback(
    async (callId: string) => {
      setBusyId(callId);
      setErr(null);
      try {
        const r = await fetch(`${apiBase}/v1/research/timeline/link-call`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            api_key: apiKey,
            call_id: callId,
            artifact_id: artifactId,
          }),
        });
        if (!r.ok) throw new Error(await parseApiError(r, "关联失败"));
        onLinked();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "关联失败");
      } finally {
        setBusyId(null);
      }
    },
    [apiBase, apiKey, artifactId, onLinked]
  );

  if (!open) return null;

  return (
    <div className="backdrop" onClick={onClose} role="presentation">
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog">
        <header>
          <h3>关联已有调用</h3>
          <button type="button" className="x" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="lead">选择一次 API 调用，记到这条科研存证的时间线上。</p>
        <label>
          按模型筛选
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="例如 gpt-4o"
          />
        </label>
        <label>
          不早于（UTC 时间，可空）
          <input
            value={since}
            onChange={(e) => setSince(e.target.value)}
            placeholder="2026-01-01"
          />
        </label>
        {err && <p className="bad">{err}</p>}
        {filtered.length === 0 ? (
          <p className="empty">没有可关联的调用。可先到「API 调用」点「模拟一条调用」。</p>
        ) : (
          <ul>
            {filtered.map((c) => {
              const linked = alreadyLinked.has(c.id);
              return (
                <li key={c.id}>
                  <div>
                    <div className="mono">{c.timestamp}</div>
                    <div>
                      {c.model || "—"} · {c.endpoint}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={linked || busyId === c.id}
                    onClick={() => link(c.id)}
                  >
                    {linked ? "已关联" : busyId === c.id ? "关联中…" : "关联"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <style jsx>{`
          .backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.62);
            z-index: 60;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
          }
          .modal {
            width: min(640px, 100%);
            max-height: 86vh;
            overflow: auto;
            background: #111821;
            border: 1px solid #1e2a38;
            border-radius: 8px;
            padding: 18px 20px;
          }
          header {
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          h3 {
            margin: 0;
            font-size: 16px;
          }
          .x {
            background: transparent;
            border: none;
            color: #9eb2c7;
            font-size: 22px;
          }
          .lead,
          .empty {
            color: #9eb2c7;
            font-size: 13px;
          }
          label {
            display: grid;
            gap: 6px;
            font-size: 12px;
            color: #7f8fa3;
            margin-bottom: 10px;
          }
          input {
            background: #0e141c;
            border: 1px solid #1e2a38;
            color: #d7e0ea;
            border-radius: 4px;
            padding: 8px 10px;
          }
          ul {
            list-style: none;
            margin: 0;
            padding: 0;
          }
          li {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #152033;
            font-size: 12px;
          }
          .mono {
            font-family: var(--mono);
            font-size: 11px;
            color: #7f8fa3;
          }
          .bad {
            color: #ff6b6b;
            font-size: 12px;
          }
          button {
            background: #1a3d2c;
            border: 1px solid #2a5c42;
            color: #3dd68c;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
            font-family: var(--mono);
            white-space: nowrap;
          }
          button:disabled {
            opacity: 0.5;
          }
        `}</style>
      </div>
    </div>
  );
}
