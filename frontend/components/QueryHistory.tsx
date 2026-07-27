"use client";

export type HistoryItem = {
  id: string;
  timestamp: string;
  query_params?: Record<string, unknown> | null;
  result_count?: number;
  duration_ms?: number;
};

type Props = {
  items: HistoryItem[];
  onReplay: (item: HistoryItem) => void;
  activeId?: string | null;
};

function summarize(params: Record<string, unknown> | null | undefined): string {
  if (!params) return "—";
  const parts: string[] = [];
  if (params.time_range) parts.push(String(params.time_range));
  if (params.endpoint) parts.push(`ep:${params.endpoint}`);
  if (params.model) parts.push(`model:${params.model}`);
  if (params.status) parts.push(`status:${params.status}`);
  if (params.min_cost != null) parts.push(`≥$${params.min_cost}`);
  if (params.max_cost != null) parts.push(`≤$${params.max_cost}`);
  return parts.length ? parts.join(" · ") : "全部条件";
}

export function QueryHistory({ items, onReplay, activeId }: Props) {
  if (!items.length) return null;
  return (
    <section className="qh">
      <h3>查询历史</h3>
      <ul>
        {items.map((it) => (
          <li key={it.id}>
            <button
              type="button"
              className={activeId === it.id ? "active" : ""}
              onClick={() => onReplay(it)}
            >
              <span className="sum">{summarize(it.query_params)}</span>
              <span className="meta">
                {it.timestamp} · {it.result_count ?? 0} 条
              </span>
            </button>
          </li>
        ))}
      </ul>
      <style jsx>{`
        .qh {
          margin-bottom: 16px;
        }
        h3 {
          margin: 0 0 8px;
          font-size: 12px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 6px;
          max-height: 160px;
          overflow-y: auto;
        }
        button {
          width: 100%;
          text-align: left;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px 10px;
          color: #d7e0ea;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }
        button:hover,
        button.active {
          border-color: #2a5c42;
          background: #123526;
        }
        .sum {
          font-family: var(--mono);
          font-size: 12px;
        }
        .meta {
          font-size: 11px;
          color: #7f8fa3;
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}
