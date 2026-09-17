"use client";

import { useCallback, useEffect, useState } from "react";
import { parseApiError, withApiKey } from "@/lib/api";
import { LinkCallDialog } from "./LinkCallDialog";

type Linked = {
  timeline_id: string;
  call_id: string;
  timestamp?: string;
  model?: string;
  chain_hash?: string;
  chain_ok?: boolean;
  chain_status_label?: string;
};

type Props = {
  apiBase: string;
  apiKey: string;
  artifactId: string | null;
  canWrite: boolean;
  onChanged?: () => void;
};

/**
 * 当前工件已关联的 API 调用列表。
 */
export function LinkedCallsPanel({
  apiBase,
  apiKey,
  artifactId,
  canWrite,
  onChanged,
}: Props) {
  const [items, setItems] = useState<Linked[]>([]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!apiKey || !artifactId) {
      setItems([]);
      return;
    }
    const r = await fetch(
      withApiKey(
        `${apiBase}/v1/research/artifacts/${encodeURIComponent(artifactId)}/linked-calls`,
        apiKey
      )
    );
    if (!r.ok) {
      setErr(await parseApiError(r, "无法加载关联调用"));
      return;
    }
    const d = await r.json();
    setItems(d.calls || []);
    setErr(null);
  }, [apiBase, apiKey, artifactId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  async function unlink(id: string) {
    setBusyId(id);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(`${apiBase}/v1/research/timeline/${encodeURIComponent(id)}`, apiKey),
        { method: "DELETE" }
      );
      if (!r.ok) throw new Error(await parseApiError(r, "取消关联失败"));
      await load();
      onChanged?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "取消关联失败");
    } finally {
      setBusyId(null);
    }
  }

  if (!artifactId) return null;

  return (
    <section className="panel">
      <div className="head">
        <h3>关联的 API 调用</h3>
        <button type="button" className="accent" onClick={() => setOpen(true)} disabled={!canWrite}>
          关联已有调用
        </button>
      </div>
      <p className="hint">把发给 AI 的那次调用挂在这条存证后面，方便以后对照时间线。</p>
      {err && <p className="bad">{err}</p>}
      {items.length === 0 ? (
        <p className="empty">还没有关联任何调用。</p>
      ) : (
        <ul>
          {items.map((it) => (
            <li key={it.timeline_id}>
              <div>
                <div className="mono">{it.timestamp || "—"}</div>
                <div>
                  {it.model || "—"}{" "}
                  <span className={it.chain_ok ? "ok" : "bad"}>
                    {it.chain_status_label || (it.chain_ok ? "链完整" : "链异常")}
                  </span>
                </div>
              </div>
              <button
                type="button"
                disabled={!canWrite || busyId === it.timeline_id}
                onClick={() => unlink(it.timeline_id)}
              >
                {busyId === it.timeline_id ? "处理中…" : "取消关联"}
              </button>
            </li>
          ))}
        </ul>
      )}
      <LinkCallDialog
        open={open}
        apiBase={apiBase}
        apiKey={apiKey}
        artifactId={artifactId}
        alreadyLinked={new Set(items.map((i) => i.call_id))}
        onClose={() => setOpen(false)}
        onLinked={() => {
          load();
          onChanged?.();
          setOpen(false);
        }}
      />
      <style jsx>{`
        .panel {
          margin-top: 16px;
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          max-width: 720px;
        }
        .head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 10px;
        }
        h3 {
          margin: 0;
          font-size: 14px;
        }
        .hint,
        .empty {
          color: #7f8fa3;
          font-size: 12px;
        }
        .bad {
          color: #ff6b6b;
          font-size: 12px;
        }
        .ok {
          color: #3dd68c;
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
          color: #9eb2c7;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 6px 10px;
          font-size: 12px;
          font-family: var(--mono);
        }
        .accent {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        button:disabled {
          opacity: 0.5;
        }
      `}</style>
    </section>
  );
}
