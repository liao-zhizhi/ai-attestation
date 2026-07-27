"use client";

export type BaselineStats = {
  n_calls?: number;
  daily_calls?: { mean?: number; std?: number; min?: number; max?: number };
  endpoints?: { dist?: Record<string, number>; set?: string[] };
  costs?: { daily_mean?: number; p25?: number; p50?: number; p75?: number; p95?: number };
  latency?: { mean?: number; p95?: number };
  models?: { dist?: Record<string, number> };
};

export type Baseline = {
  id: string;
  timestamp: string;
  time_range_start?: string;
  time_range_end?: string;
  time_range_label?: string;
  stats?: BaselineStats;
  baseline_hash?: string;
  chain_hash?: string;
  n_calls?: number;
  deleted?: boolean;
  duration_ms?: number;
};

type Props = {
  baselines: Baseline[];
  selectedId?: string | null;
  timeRange: string;
  onTimeRange: (v: string) => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCheckDrift: () => void;
  busy: boolean;
};

export function BaselinePanel({
  baselines,
  selectedId,
  timeRange,
  onTimeRange,
  onCreate,
  onSelect,
  onDelete,
  onCheckDrift,
  busy,
}: Props) {
  const active = baselines.find((b) => b.id === selectedId) || baselines[0];
  const s = active?.stats;

  return (
    <div className="bp">
      <div className="actions">
        <label>
          基线窗口
          <select value={timeRange} onChange={(e) => onTimeRange(e.target.value)}>
            <option value="7d">过去 7 天</option>
            <option value="30d">过去 30 天</option>
            <option value="1d">今天</option>
          </select>
        </label>
        <button type="button" className="run" onClick={onCreate} disabled={busy}>
          {busy ? "生成中…" : "建立行为基线"}
        </button>
        <button type="button" onClick={onCheckDrift} disabled={busy || !baselines.length}>
          检查漂移
        </button>
      </div>
      <p className="hint">
        行为漂移：只标记、不告警、不阻断。最终判断权留给你。
      </p>
      {active && (
        <div className="stats">
          <h4>当前基线 · {active.id}</h4>
          <dl>
            <div>
              <dt>调用数</dt>
              <dd>{s?.n_calls ?? active.n_calls ?? 0}</dd>
            </div>
            <div>
              <dt>日均调用</dt>
              <dd>
                {s?.daily_calls?.mean?.toFixed?.(1) ?? "—"} ±{" "}
                {s?.daily_calls?.std?.toFixed?.(1) ?? "—"}
              </dd>
            </div>
            <div>
              <dt>费用 P95</dt>
              <dd>${s?.costs?.p95?.toFixed?.(6) ?? "—"}</dd>
            </div>
            <div>
              <dt>耗时 P95</dt>
              <dd>{s?.latency?.p95?.toFixed?.(1) ?? "—"} ms</dd>
            </div>
            <div>
              <dt>端点数</dt>
              <dd>{s?.endpoints?.set?.length ?? 0}</dd>
            </div>
          </dl>
          <div className="mono hash">{active.baseline_hash || "—"}</div>
        </div>
      )}
      <ul>
        {baselines.map((b) => (
          <li key={b.id}>
            <button
              type="button"
              className={b.id === selectedId ? "active" : ""}
              onClick={() => onSelect(b.id)}
            >
              <strong>{b.time_range_label || "7d"}</strong>
              <span className="mono">
                {b.timestamp} · n={b.n_calls ?? b.stats?.n_calls ?? 0}
                {b.deleted ? " · deleted" : ""}
              </span>
            </button>
            {!b.deleted && (
              <button type="button" className="del" onClick={() => onDelete(b.id)}>
                软删
              </button>
            )}
          </li>
        ))}
      </ul>
      <style jsx>{`
        .actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: flex-end;
          margin-bottom: 10px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 7px 9px;
          font-family: var(--mono);
          font-size: 12px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 12px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .run {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .hint {
          margin: 0 0 12px;
          font-size: 12px;
          color: #7f8fa3;
        }
        .stats {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
          margin-bottom: 12px;
        }
        h4 {
          margin: 0 0 8px;
          font-size: 12px;
          color: #9eb2c7;
        }
        dl {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
          gap: 8px;
          margin: 0;
        }
        dt {
          font-size: 10px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        dd {
          margin: 2px 0 0;
          font-family: var(--mono);
          font-size: 13px;
        }
        .hash {
          margin-top: 8px;
          font-size: 10px;
          color: #7f8fa3;
          word-break: break-all;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 6px;
          max-height: 200px;
          overflow-y: auto;
        }
        li {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 6px;
        }
        li > button:first-child {
          text-align: left;
          display: flex;
          flex-direction: column;
          gap: 2px;
          background: #0e141c;
          border: 1px solid #1e2a38;
        }
        li > button.active {
          border-color: #2a5c42;
          background: #123526;
        }
        .del {
          padding: 4px 8px;
          font-size: 11px;
        }
        .mono {
          font-family: var(--mono);
          color: #7f8fa3;
          font-size: 11px;
        }
      `}</style>
    </div>
  );
}
