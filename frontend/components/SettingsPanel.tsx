"use client";

import { useCallback, useEffect, useState } from "react";
import { formatDetail, withApiKey } from "@/lib/api";

type SubTab = "general" | "reports";

type Props = {
  apiBase: string;
  apiKey: string;
  setApiKey: (k: string) => void;
  authorization: string;
  setAuthorization: (v: string) => void;
  proxyUrl: string;
  onSaveKey: () => void;
  onCopyProxy: () => void;
  copied: boolean;
  busy: boolean;
  role: string;
};

type HistoryItem = {
  id: string;
  sent_at: string;
  status: string;
  error_message?: string | null;
};

export function SettingsPanel({
  apiBase,
  apiKey,
  setApiKey,
  authorization,
  setAuthorization,
  proxyUrl,
  onSaveKey,
  onCopyProxy,
  copied,
  busy,
  role,
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

  const loadSub = useCallback(async () => {
    if (!apiKey) return;
    const r = await fetch(
      withApiKey(`${apiBase}/v1/dashboard/settings/report-subscription`, apiKey)
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

  useEffect(() => {
    if (tab === "reports") loadSub();
  }, [tab, loadSub]);

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
      setSubMsg(formatDetail(d.detail, "发送失败，请先保存订阅"));
      return;
    }
    setSubMsg(d.message || "已排队");
    setTimeout(loadSub, 800);
  }

  const tabs: { id: SubTab; label: string }[] = [
    { id: "general", label: "通用" },
    { id: "reports", label: "报告订阅" },
  ];

  return (
    <section className="sp">
      <nav className="tabs">
        {tabs.map((t) => (
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
            API Key（X-Attest-Key）
            <input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              spellCheck={false}
              placeholder="ata_xxxxxx"
            />
          </label>
          <label>
            Authorization（上游厂商 Key，仅本机备忘）
            <input
              value={authorization}
              onChange={(e) => setAuthorization(e.target.value)}
              spellCheck={false}
              placeholder="Bearer sk-xxxxxx"
            />
          </label>
          <label>
            base_url
            <input value={proxyUrl} readOnly spellCheck={false} />
          </label>
          <div className="row">
            <button type="button" className="accent" onClick={onSaveKey} disabled={busy}>
              保存
            </button>
            <button type="button" onClick={onCopyProxy}>
              {copied ? "已复制" : "复制代理 URL"}
            </button>
          </div>
          <p className="hint">
            「API Key」填左侧「Key」页生成的 <code>ata_…</code>，保存后用于打开仪表盘。
            「Authorization」只保存在本浏览器，方便你对照写 SDK；真正调用代理时请在代码里传上游{" "}
            <code>sk-…</code>，网页不会替你转发该字段。
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
              <option value="daily">每天</option>
              <option value="weekly">每周</option>
              <option value="monthly">每月</option>
            </select>
          </label>
          <fieldset>
            <legend>内容选项</legend>
            {(
              [
                ["api_overview", "API 概览"],
                ["drift_summary", "漂移摘要"],
                ["compliance_summary", "合规摘要"],
              ] as const
            ).map(([k, label]) => (
              <label key={k} className="chk">
                <input
                  type="checkbox"
                  checked={opts[k]}
                  onChange={(e) => setOpts((o) => ({ ...o, [k]: e.target.checked }))}
                />
                {label}
              </label>
            ))}
          </fieldset>
          <div className="row">
            <button type="button" onClick={saveSub}>
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
        label.chk {
          flex-direction: row;
          align-items: center;
          text-transform: none;
          font-size: 12px;
          color: #c5d0dc;
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
        .hint code {
          color: #3dd68c;
          font-family: var(--mono);
        }
        fieldset {
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
        }
        legend {
          font-size: 11px;
          color: #7f8fa3;
        }
        h3 {
          margin: 4px 0 0;
          font-size: 13px;
          color: #d7e0ea;
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
          flex-wrap: wrap;
          font-size: 12px;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        .err {
          color: #f0b429;
        }
        .msg {
          font-size: 12px;
          color: #9eb2c7;
        }
        .mono {
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}
