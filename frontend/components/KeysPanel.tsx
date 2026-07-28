"use client";

import { useCallback, useEffect, useState } from "react";

type Props = {
  apiBase: string;
  apiKey: string;
  canAdmin: boolean;
  onCreated?: (key: string) => void;
};

type KeyRow = {
  api_key_masked: string;
  api_key_full: string;
  name: string;
  role: string;
  status: string;
  created_at?: string;
  last_used_at?: string | null;
  is_self?: boolean;
};

/**
 * Standalone Key page: create ata_… keys (matches left-nav「Key」).
 */
export function KeysPanel({ apiBase, apiKey, canAdmin, onCreated }: Props) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [createdOnce, setCreatedOnce] = useState<string | null>(null);
  const [keys, setKeys] = useState<KeyRow[]>([]);

  const loadKeys = useCallback(async () => {
    if (!apiKey || !canAdmin) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/settings/keys?api_key=${encodeURIComponent(apiKey)}`
    );
    if (!r.ok) return;
    const d = await r.json();
    setKeys(d.keys || []);
  }, [apiBase, apiKey, canAdmin]);

  useEffect(() => {
    loadKeys().catch(() => undefined);
  }, [loadKeys]);

  async function createKey() {
    if (!name.trim()) {
      setMsg("请先输入名称");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      // Prefer admin create (named + role) when possible; else public trial issue.
      if (canAdmin && apiKey) {
        const r = await fetch(`${apiBase}/v1/dashboard/settings/keys`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            api_key: apiKey,
            name: name.trim(),
            role: "read_write",
          }),
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) {
          setMsg(
            typeof d.detail === "string"
              ? d.detail
              : `创建失败 (${r.status})`
          );
          return;
        }
        const k = d.key?.api_key as string | undefined;
        if (k) {
          setCreatedOnce(k);
          onCreated?.(k);
        }
        setName("");
        await loadKeys();
        return;
      }

      const r = await fetch(`${apiBase}/v1/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: name.trim() }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || typeof d.api_key !== "string") {
        setMsg(typeof d.detail === "string" ? d.detail : "创建失败");
        return;
      }
      setCreatedOnce(d.api_key);
      onCreated?.(d.api_key);
      setName("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="kp">
      <h2>API Key</h2>
      <p className="lead">
        在这里创建见证层 Key（格式 <code>ata_xxxxxx</code>）。创建成功后请立刻复制保存。
      </p>

      <div className="create">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="输入名称，例如：我的测试"
          spellCheck={false}
        />
        <button type="button" className="accent" onClick={createKey} disabled={busy}>
          {busy ? "创建中…" : "创建"}
        </button>
      </div>

      {createdOnce && (
        <div className="once">
          <div className="label">新 Key（仅完整显示一次，请立刻复制）：</div>
          <code className="mono">{createdOnce}</code>
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(createdOnce);
                setMsg("已复制到剪贴板");
              } catch {
                setMsg("复制失败，请手动选中复制");
              }
            }}
          >
            复制 Key
          </button>
        </div>
      )}

      {msg && <p className="msg">{msg}</p>}

      {canAdmin && keys.length > 0 && (
        <>
          <h3>已有 Key（刷新后仅显示脱敏）</h3>
          <ul className="klist">
            {keys.map((k) => (
              <li key={k.api_key_full}>
                <strong>{k.name}</strong>
                <span className="st">{k.status}</span>
                <div className="mono">{k.api_key_masked}</div>
              </li>
            ))}
          </ul>
        </>
      )}

      <style jsx>{`
        .kp {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 16px 18px;
          max-width: 640px;
        }
        h2 {
          margin: 0 0 8px;
          font-size: 16px;
          color: #e8eef5;
        }
        h3 {
          margin: 18px 0 8px;
          font-size: 13px;
          color: #d7e0ea;
        }
        .lead {
          margin: 0 0 14px;
          font-size: 13px;
          color: #9eb2c7;
        }
        .create {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        input {
          flex: 1;
          min-width: 180px;
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 10px;
          font-family: var(--mono);
          font-size: 12px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 12px;
          font-size: 12px;
          font-family: var(--mono);
        }
        button.accent {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        button:disabled {
          opacity: 0.45;
        }
        .once {
          margin-top: 14px;
          padding: 12px;
          background: #0b0f14;
          border: 1px dashed #2a5c42;
          border-radius: 6px;
          display: grid;
          gap: 8px;
        }
        .label {
          font-size: 12px;
          color: #f0b429;
        }
        .mono,
        code {
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 12px;
          color: #3dd68c;
          word-break: break-all;
        }
        .msg {
          margin-top: 10px;
          font-size: 12px;
          color: #9eb2c7;
        }
        .klist {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 8px;
        }
        .klist li {
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
          display: grid;
          gap: 4px;
        }
        .st {
          font-size: 11px;
          color: #7f8fa3;
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}
