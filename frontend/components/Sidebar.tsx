"use client";

export type NavId =
  | "guide"
  | "research"
  | "dashboard"
  | "calls"
  | "compliance"
  | "behavior"
  | "attestation"
  | "settings"
  | "keys";

type Props = {
  active: NavId;
  onNavigate: (id: NavId) => void;
  apiKey: string;
  proxyUrl: string;
  onCopyProxy: () => void;
  copied: boolean;
  showSettings?: boolean;
};

type Item = { id: NavId; label: string; itemKey: string };

const ONBOARD: Item[] = [
  { id: "keys", label: "Key 管理", itemKey: "onboard-keys" },
  { id: "settings", label: "设置", itemKey: "onboard-settings" },
  { id: "calls", label: "API 调用", itemKey: "onboard-calls" },
  { id: "research", label: "见证", itemKey: "onboard-research" },
];

const DAILY: Item[] = [
  { id: "dashboard", label: "仪表盘", itemKey: "daily-dashboard" },
  { id: "calls", label: "API 调用记录", itemKey: "daily-calls" },
  { id: "research", label: "见证", itemKey: "daily-research" },
  { id: "behavior", label: "监控", itemKey: "daily-behavior" },
  { id: "compliance", label: "合规管理", itemKey: "daily-compliance" },
  { id: "attestation", label: "防篡改证明", itemKey: "daily-attestation" },
];

export function Sidebar({
  active,
  onNavigate,
  apiKey,
  proxyUrl,
  onCopyProxy,
  copied,
  showSettings = true,
}: Props) {
  const suffix = apiKey.length >= 6 ? `…${apiKey.slice(-6)}` : "—";
  const onboard = showSettings
    ? ONBOARD
    : ONBOARD.filter((i) => i.id !== "settings" && i.id !== "keys");
  return (
    <aside className="sb">
      <div className="brand">
        <div className="name">ai-attestation</div>
        <div className="tag">开源 AI 审计代理</div>
      </div>
      <nav>
        <div className="grp">新用户上手</div>
        {onboard.map((it) => (
          <button
            key={it.itemKey}
            type="button"
            className={active === it.id ? "on" : ""}
            onClick={() => onNavigate(it.id)}
          >
            {it.label}
          </button>
        ))}
        <div className="split" />
        <div className="grp">日常使用</div>
        {DAILY.map((it) => (
          <button
            key={it.itemKey}
            type="button"
            className={active === it.id ? "on" : ""}
            onClick={() => onNavigate(it.id)}
          >
            {it.label}
          </button>
        ))}
      </nav>
      <div className="foot">
        <div className="k mono">Key {suffix}</div>
        <div className="url mono" title={proxyUrl}>
          {proxyUrl}
        </div>
        <div className="split" />
        <button type="button" className="copy" onClick={onCopyProxy}>
          {copied ? "已复制代理 URL" : "复制代理 URL"}
        </button>
        <button
          type="button"
          className={active === "guide" ? "on" : ""}
          onClick={() => onNavigate("guide")}
        >
          操作手册
        </button>
      </div>
      <style jsx>{`
        .sb {
          width: 220px;
          min-width: 220px;
          background: #0e141c;
          border-right: 1px solid #1e2a38;
          display: flex;
          flex-direction: column;
          min-height: 100vh;
          padding: 18px 12px;
        }
        .brand {
          padding: 4px 8px 18px;
        }
        .name {
          font-weight: 650;
          font-size: 15px;
          letter-spacing: -0.02em;
        }
        .tag {
          color: #7f8fa3;
          font-size: 11px;
          margin-top: 4px;
          font-family: var(--mono);
        }
        nav {
          display: grid;
          gap: 4px;
          flex: 1;
          align-content: start;
        }
        .grp {
          color: #7f8fa3;
          font-size: 10px;
          letter-spacing: 0.08em;
          text-transform: none;
          padding: 10px 10px 4px;
          font-family: var(--mono);
        }
        .split {
          height: 1px;
          background: #1e2a38;
          margin: 10px 6px;
        }
        nav button,
        .foot button {
          text-align: left;
          background: transparent;
          border: 1px solid transparent;
          color: #9eb2c7;
          border-radius: 4px;
          padding: 9px 10px;
          font-family: var(--mono);
          font-size: 12px;
          white-space: nowrap;
        }
        nav button:hover,
        .foot button:hover {
          background: #152033;
          color: #d7e0ea;
        }
        nav button.on,
        .foot button.on {
          background: #123526;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .foot {
          margin-top: 8px;
          padding-top: 4px;
          display: grid;
          gap: 8px;
        }
        .k {
          font-size: 11px;
          color: #7f8fa3;
        }
        .copy {
          background: #152033 !important;
          border: 1px solid #2a3b52 !important;
          color: #d7e0ea !important;
        }
        .url {
          font-size: 10px;
          color: #7f8fa3;
          word-break: break-all;
          padding: 0 10px;
        }
        .mono {
          font-family: var(--mono);
        }
        @media (max-width: 900px) {
          .sb {
            width: 100%;
            min-height: auto;
            border-right: none;
            border-bottom: 1px solid #1e2a38;
          }
          nav {
            grid-template-columns: repeat(3, 1fr);
            flex: none;
          }
          .grp,
          .split {
            grid-column: 1 / -1;
          }
        }
      `}</style>
    </aside>
  );
}
