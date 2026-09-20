"use client";

type HistItem = {
  id?: string;
  timestamp?: string;
  vendor?: string;
  allow_training?: string;
  allow_label?: string;
  chain_hash?: string;
  chain_ok?: boolean;
  policy_hash?: string | null;
};

type Props = {
  items: HistItem[];
};

function tone(allow?: string): string {
  if (allow === "yes") return "ok";
  if (allow === "no") return "bad";
  return "muted";
}

function vendorLabel(v?: string): string {
  if (!v || v === "*") return "全局默认";
  return v;
}

/**
 * 训练同意变更时间线（折叠区内使用）。
 */
export function ConsentHistory({ items }: Props) {
  if (!items.length) {
    return <p className="empty">暂无变更记录</p>;
  }
  return (
    <ul className="hist">
      {items.map((h) => (
        <li key={h.id || `${h.timestamp}-${h.vendor}`}>
          <span className="mono ts">
            {(h.timestamp || "").replace("T", " ").slice(0, 19)}
          </span>
          <span className="vend">{vendorLabel(h.vendor)}</span>
          <span className={tone(h.allow_training)}>
            {h.allow_label || h.allow_training || "未知"}
          </span>
          <span className={h.chain_ok ? "ok" : "bad"}>
            {h.chain_ok ? "链完整" : "链异常"}
          </span>
          {h.chain_hash && (
            <span className="mono hash" title={h.chain_hash}>
              {h.chain_hash.slice(0, 12)}…
            </span>
          )}
        </li>
      ))}
      <style jsx>{`
        .hist {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 6px;
        }
        .hist li {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 12px;
          color: #c5d0dc;
        }
        .empty {
          font-size: 12px;
          color: #7f8fa3;
          margin: 0;
        }
        .ts {
          color: #7f8fa3;
        }
        .vend {
          color: #9eb2c7;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        .muted {
          color: #7f8fa3;
        }
        .hash {
          color: #5b8def;
          font-size: 11px;
        }
        .mono {
          font-family: var(--mono);
        }
      `}</style>
    </ul>
  );
}
