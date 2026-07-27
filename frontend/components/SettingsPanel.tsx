"use client";

import { useCallback, useEffect, useState } from "react";

type SubTab = "general" | "reports" | "keys";

type Props = {
  apiBase: string;
  apiKey: string;
  setApiKey: (k: string) => void;
  proxyUrl: string;
  onSaveKey: () => void;
  onIssueKey: () => void;
  onCopyProxy: () => void;
  copied: boolean;
  busy: boolean;
  role: string;
  canAdmin: boolean;
};

type HistoryItem = {
  id: string;
  sent_at: string;
  status: string;
  error_message?: string | null;
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

export function SettingsPanel({
  apiBase,
  apiKey,
  setApiKey,
  proxyUrl,
  onSaveKey,
  onIssueKey,
  onCopyProxy,
  copied,
  busy,
  role,
  canAdmin,
}: Props) {
  const [tab, setTab] = useState<SubTab>("general");
  const [email, setEmail] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [opts, setOpts] = useState({
    api_overview: true,
    drift_summary: true,
    compliance_summary: true,
  });
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [subMsg, setSubMsg] = useState<string | null>(null);
  const [keys, setKeys] = useState<KeyRow[]>([]);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("read_write");
  const [reveal, setReveal] = useState<Record<string, boolean>>({});
  const [createdOnce, setCreatedOnce] = useState<string | null>(null);

  const loadSub = useCallback(async () => {
    if (!apiKey) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/settings/report-subscription?api_key=${encodeURIComponent(apiKey)}`
    );
    if (!r.ok) return;
    const d = await r.json();
    if (d.subscription) {
      setEmail(d.subscription.email || "");
      setFrequency(d.subscription.frequency || "weekly");
      setOpts({
        api_overview: d.subscription.content_options?.api_overview !== false,
        drift_summary: d.subscription.content_options?.drift_summary !== false,
        compliance_summary:
          d.subscription.content_options?.compliance_summary !== false,
      });
    }
    setHistory(d.history || []);
  }, [apiBase, apiKey]);

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
    if (tab === "reports") loadSub();
    if (tab === "keys") loadKeys();
  }, [tab, loadSub, loadKeys]);

  async function saveSub() {
    setSubMsg(null);
    const r = await fetch(`${apiBase}/v1/dashboard/settings/report-subscription`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        email,
        frequency,
        content_options: opts,
      }),
    });
    if (!r.ok) {
      setSubMsg("保存失败（需要 read_write 及以上权限）");
      return;
    }
    setSubMsg("订阅已保存");
    await loadSub();
  }

  async function testSub() {
    setSubMsg(null);
    const r = await fetch(
      `${apiBase}/v1/dashboard/settings/report-subscription/test`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
      }
    );
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = d.detail;
      setSubMsg(
        typeof detail === "string"
          ? detail
          : detail != null
            ? JSON.stringify(detail)
            : "发送失败，请先保存订阅"
      );
      return;
    }
    setSubMsg(d.message || "已排队");
    setTimeout(loadSub, 800);
  }

  async function createKey() {
    if (!newName.trim()) return;
    const r = await fetch(`${apiBase}/v1/dashboard/settings/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        name: newName.trim(),
        role: newRole,
      }),
    });
    const d = await r.json().catch(() => ({}));
    if (r.ok) {
      setCreatedOnce(d.key?.api_key || null);
      setNewName("");
      setSubMsg("");
      await loadKeys();
    } else {
      const detail = d.detail;
      setSubMsg(
        typeof detail === "string"
          ? detail
          : detail
            ? JSON.stringify(detail)
            : `创建密钥失败 (${r.status})`
      );
    }
  }

  async function patchKey(target: string, patch: Record<string, string>) {
    await fetch(`${apiBase}/v1/dashboard/settings/keys`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, target_key: target, ...patch }),
    });
    await loadKeys();
  }

  const tabs: { id: SubTab; label: string; adminOnly?: boolean; hideForReadonly?: boolean }[] = [
    { id: "general", label: "通用" },
    { id: "reports", label: "报告订阅" },
    { id: "keys", label: "API Key 管理", adminOnly: true },
  ];

  return (
    <section className="sp">
      <nav className="tabs">
        {tabs
          .filter((t) => !t.adminOnly || canAdmin)
          .map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "on" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
      </nav>
      <div className="role mono">当前角色：{role || "—"}</div>

      {tab === "general" && (
        <div className="pane">
          <label>
            API Key
            <input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              spellCheck={false}
              placeholder="ata_…"
            />
          </label>
          <div className="row">
            <button type="button" onClick={onSaveKey}>
              保存并加载
            </button>
            <button type="button" onClick={onIssueKey} disabled={busy}>
              签发新 Key
            </button>
            <button type="button" onClick={onCopyProxy}>
              {copied ? "已复制" : "复制代理 URL"}
            </button>
          </div>
          <p className="hint mono">
            base_url={proxyUrl}
            <br />
            Header X-Attest-Key · Authorization=Bearer &lt;upstream&gt;
          </p>
        </div>
      )}

      {tab === "reports" && (
        <div className="pane">
          <label>
            接收邮箱（多个用逗号分隔）
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="audit@company.com, ciso@company.com"
            />
          </label>
          <label>
            频率
            <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
              <option value="daily">每日（昨日摘要）</option>
              <option value="weekly">每周一（上周报告）</option>
              <option value="monthly">每月 1 日（上月报告）</option>
            </select>
          </label>
          <fieldset>
            <legend>报告内容</legend>
            {(
              [
                ["api_overview", "API 调用概览"],
                ["drift_summary", "待审计标记摘要"],
                ["compliance_summary", "合规状态摘要"],
              ] as const
            ).map(([k, label]) => (
              <label key={k} className="chk">
                <input
                  type="checkbox"
                  checked={opts[k]}
                  onChange={(e) => setOpts({ ...opts, [k]: e.target.checked })}
                />
                {label}
              </label>
            ))}
          </fieldset>
          <div className="row">
            <button type="button" className="accent" onClick={saveSub}>
              保存订阅
            </button>
            <button type="button" onClick={testSub}>
              立即发送测试报告
            </button>
          </div>
          {subMsg && <p className="msg">{subMsg}</p>}
          <h3>最近发送历史</h3>
          {history.length === 0 ? (
            <p className="hint">暂无发送记录</p>
          ) : (
            <ul className="hist">
              {history.map((h) => (
                <li key={h.id}>
                  <span className="mono">{h.sent_at?.replace("T", " ").slice(0, 19)}</span>
                  <span className={h.status === "success" ? "ok" : "bad"}>
                    {h.status}
                  </span>
                  {h.error_message && (
                    <span className="err mono" title={h.error_message}>
                      {h.error_message.slice(0, 48)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === "keys" && canAdmin && (
        <div className="pane">
          <div className="create">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="新 Key 名称"
            />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
              <option value="read_only">read_only</option>
              <option value="read_write">read_write</option>
              <option value="admin">admin</option>
            </select>
            <button type="button" className="accent" onClick={createKey}>
              创建
            </button>
          </div>
          {createdOnce && (
            <p className="msg mono">
              新 Key（仅显示一次）：{createdOnce}
            </p>
          )}
          <ul className="klist">
            {keys.map((k) => (
              <li key={k.api_key_full}>
                <div className="khead">
                  <strong>{k.name}</strong>
                  <span className={`st ${k.status}`}>{k.status}</span>
                  <span className="role-b">{k.role}</span>
                </div>
                <div className="mono keyline">
                  {reveal[k.api_key_full] ? k.api_key_full : k.api_key_masked}
                  <button
                    type="button"
                    onClick={() =>
                      setReveal((r) => ({
                        ...r,
                        [k.api_key_full]: !r[k.api_key_full],
                      }))
                    }
                  >
                    {reveal[k.api_key_full] ? "隐藏" : "显示"}
                  </button>
                </div>
                <div className="meta mono">
                  创建 {k.created_at?.slice(0, 10) || "—"} · 最后使用{" "}
                  {k.last_used_at?.slice(0, 16).replace("T", " ") || "—"}
                </div>
                <div className="row">
                  {k.status === "active" ? (
                    <button
                      type="button"
                      disabled={!!k.is_self}
                      onClick={() => patchKey(k.api_key_full, { status: "disabled" })}
                    >
                      禁用
                    </button>
                  ) : k.status === "disabled" ? (
                    <button
                      type="button"
                      onClick={() => patchKey(k.api_key_full, { status: "active" })}
                    >
                      重新启用
                    </button>
                  ) : null}
                  {k.status !== "deleted" && (
                    <button
                      type="button"
                      disabled={!!k.is_self}
                      onClick={() => patchKey(k.api_key_full, { status: "deleted" })}
                    >
                      删除
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <style jsx>{`
        .sp {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          max-width: 640px;
        }
        .tabs {
          display: flex;
          gap: 6px;
          margin-bottom: 12px;
          flex-wrap: wrap;
        }
        .tabs button {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #9eb2c7;
          border-radius: 4px;
          padding: 6px 12px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .tabs button.on {
          background: #123526;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .role {
          font-size: 11px;
          color: #7f8fa3;
          margin-bottom: 12px;
        }
        .pane {
          display: grid;
          gap: 12px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        input,
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 10px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .row {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
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
        .hint {
          font-size: 11px;
          color: #7f8fa3;
          line-height: 1.5;
        }
        fieldset {
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
        }
        legend {
          font-size: 11px;
          color: #7f8fa3;
          padding: 0 6px;
        }
        .chk {
          flex-direction: row;
          align-items: center;
          text-transform: none;
          font-size: 13px;
          color: #d7e0ea;
          margin-top: 6px;
        }
        .msg {
          color: #3dd68c;
          font-size: 12px;
        }
        h3 {
          margin: 8px 0 0;
          font-size: 12px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        .hist {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 6px;
        }
        .hist li {
          display: flex;
          gap: 10px;
          font-size: 12px;
          align-items: center;
          flex-wrap: wrap;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        .err {
          color: #7f8fa3;
          font-size: 11px;
        }
        .create {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        .klist {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 10px;
        }
        .klist li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
        }
        .khead {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .st.active {
          color: #3dd68c;
          font-size: 11px;
        }
        .st.disabled {
          color: #f0b429;
          font-size: 11px;
        }
        .role-b {
          font-size: 11px;
          color: #5b8def;
          font-family: var(--mono);
        }
        .keyline {
          margin-top: 6px;
          font-size: 12px;
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .keyline button {
          padding: 4px 8px;
          font-size: 11px;
        }
        .meta {
          margin: 6px 0;
          font-size: 11px;
          color: #7f8fa3;
        }
        .mono {
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}
