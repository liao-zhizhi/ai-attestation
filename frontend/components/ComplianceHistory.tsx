"use client";

export type ComplianceHistoryItem = {
  id: string;
  timestamp: string;
  standard?: string;
  standard_name?: string;
  summary?: {
    n_pass?: number;
    n_fail?: number;
    n_manual?: number;
  };
  duration_ms?: number;
};

type DiffChange = {
  check_id: string;
  from?: string;
  to?: string;
  improved?: boolean;
  regressed?: boolean;
};

type Props = {
  items: ComplianceHistoryItem[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  compareLeft?: string | null;
  compareRight?: string | null;
  onPickCompare: (id: string, slot: "left" | "right") => void;
  onCompare: () => void;
  diff?: DiffChange[] | null;
};

export function ComplianceHistory({
  items,
  activeId,
  onSelect,
  compareLeft,
  compareRight,
  onPickCompare,
  onCompare,
  diff,
}: Props) {
  if (!items.length) {
    return <div className="empty">暂无合规检查历史。</div>;
  }
  return (
    <div className="ch">
      <div className="cmpbar">
        <span className="mono">
          对比: {compareLeft?.slice(0, 12) || "—"} → {compareRight?.slice(0, 12) || "—"}
        </span>
        <button type="button" onClick={onCompare} disabled={!compareLeft || !compareRight}>
          对比两次检查
        </button>
      </div>
      <ul>
        {items.map((it) => (
          <li key={it.id}>
            <button
              type="button"
              className={activeId === it.id ? "active" : ""}
              onClick={() => onSelect(it.id)}
            >
              <strong>{it.standard_name || it.standard}</strong>
              <span className="mono">
                {it.timestamp} · pass {it.summary?.n_pass ?? 0} / fail{" "}
                {it.summary?.n_fail ?? 0} / manual {it.summary?.n_manual ?? 0}
              </span>
            </button>
            <div className="pick">
              <button type="button" onClick={() => onPickCompare(it.id, "left")}>
                作旧
              </button>
              <button type="button" onClick={() => onPickCompare(it.id, "right")}>
                作新
              </button>
            </div>
          </li>
        ))}
      </ul>
      {diff && (
        <div className="diff">
          <h4>结果变化 ({diff.length})</h4>
          {diff.length === 0 ? (
            <p>无状态变化</p>
          ) : (
            <ul className="dlist">
              {diff.map((d) => (
                <li key={d.check_id} className={d.improved ? "up" : d.regressed ? "down" : ""}>
                  <code>{d.check_id}</code> {d.from} → {d.to}
                  {d.improved ? " ↑" : ""}
                  {d.regressed ? " ↓" : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <style jsx>{`
        .empty {
          color: #7f8fa3;
          font-family: var(--mono);
          font-size: 12px;
        }
        .cmpbar {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          align-items: center;
          margin-bottom: 10px;
          flex-wrap: wrap;
        }
        .cmpbar button,
        .pick button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 4px 8px;
          font-family: var(--mono);
          font-size: 11px;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 8px;
          max-height: 360px;
          overflow-y: auto;
        }
        li {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 6px;
          align-items: stretch;
        }
        li > button.active {
          border-color: #2a5c42;
          background: #123526;
        }
        li > button:first-child {
          text-align: left;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px 10px;
          color: #d7e0ea;
          display: flex;
          flex-direction: column;
          gap: 3px;
          font-size: 12px;
          cursor: pointer;
        }
        .mono {
          font-family: var(--mono);
          color: #7f8fa3;
          font-size: 11px;
        }
        .pick {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .diff {
          margin-top: 12px;
          padding: 10px;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          background: #0e141c;
        }
        h4 {
          margin: 0 0 8px;
          font-size: 12px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        .dlist {
          max-height: 160px;
        }
        .dlist li {
          display: block;
          font-family: var(--mono);
          font-size: 11px;
          color: #d7e0ea;
        }
        .up {
          color: #3dd68c !important;
        }
        .down {
          color: #ff6b6b !important;
        }
      `}</style>
    </div>
  );
}
