"use client";

export type NavId =
  | "guide"
  | "dashboard"
  | "calls"
  | "compliance"
  | "behavior"
  | "attestation"
  | "settings";

type Props = {
  active: NavId;
  onNavigate: (id: NavId) => void;
  apiKey: string;
  proxyUrl: string;
  onCopyProxy: () => void;
  copied: boolean;
  showSettings?: boolean;
};

const ITEMS: { id: NavId; label: string }[] = [
  { id: "guide", label: "操作手册" },
  { id: "dashboard", label: "仪表盘" },
  { id: "calls", label: "API 调用记录" },
  { id: "compliance", label: "合规管理" },
  { id: "behavior", label: "行为监控" },
  { id: "attestation", label: "防篡改证明" },
  { id: "settings", label: "设置" },
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
  const items = showSettings ? ITEMS : ITEMS.filter((i) => i.id !== "settings");
  return (
    <aside className="sb">
      <div className="brand">
        <div className="name">ai-attestation</div>
        <div className="tag">开源 AI 审计代理</div>
      </div>
      <nav>
        {items.map((it) => (
          <button
            key={it.id}
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
        <button type="button" className="copy" onClick={onCopyProxy}>
          {copied ? "已复制代理 URL" : "复制代理 URL"}
        </button>
        <div className="url mono" title={proxyUrl}>
          {proxyUrl}
        </div>
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
        }
        nav button {
          text-align: left;
          background: transparent;
          border: 1px solid transparent;
          color: #9eb2c7;
          border-radius: 4px;
          padding: 9px 10px;
          font-family: var(--mono);
          font-size: 12px;
        }
        nav button:hover {
          background: #152033;
          color: #d7e0ea;
        }
        nav button.on {
          background: #123526;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .foot {
          border-top: 1px solid #1e2a38;
          padding-top: 12px;
          display: grid;
          gap: 8px;
        }
        .k {
          font-size: 11px;
          color: #7f8fa3;
        }
        .copy {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 7px 8px;
          font-family: var(--mono);
          font-size: 11px;
        }
        .url {
          font-size: 10px;
          color: #7f8fa3;
          word-break: break-all;
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
        }
      `}</style>
    </aside>
  );
}
