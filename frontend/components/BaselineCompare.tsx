"use client";

type Diff = {
  summary?: string;
  daily_call_growth_pct?: number | null;
  endpoints_added?: string[];
  endpoints_removed?: string[];
  daily_call_mean_older?: number;
  daily_call_mean_newer?: number;
  cost_p95_older?: number;
  cost_p95_newer?: number;
};

type Props = {
  olderId: string | null;
  newerId: string | null;
  baselineOptions: Array<{ id: string; timestamp: string }>;
  onPickOlder: (id: string) => void;
  onPickNewer: (id: string) => void;
  onCompare: () => void;
  diff: Diff | null;
};

export function BaselineCompare({
  olderId,
  newerId,
  baselineOptions,
  onPickOlder,
  onPickNewer,
  onCompare,
  diff,
}: Props) {
  return (
    <div className="bc">
      <div className="row">
        <label>
          旧基线
          <select
            value={olderId || ""}
            onChange={(e) => onPickOlder(e.target.value)}
          >
            <option value="">—</option>
            {baselineOptions.map((b) => (
              <option key={b.id} value={b.id}>
                {b.id.slice(0, 12)}… {b.timestamp}
              </option>
            ))}
          </select>
        </label>
        <label>
          新基线
          <select
            value={newerId || ""}
            onChange={(e) => onPickNewer(e.target.value)}
          >
            <option value="">—</option>
            {baselineOptions.map((b) => (
              <option key={b.id} value={b.id}>
                {b.id.slice(0, 12)}… {b.timestamp}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={onCompare} disabled={!olderId || !newerId}>
          对比
        </button>
      </div>
      {diff && (
        <div className="out">
          <p>{diff.summary}</p>
          <ul>
            <li>
              日均调用: {diff.daily_call_mean_older?.toFixed?.(1)} →{" "}
              {diff.daily_call_mean_newer?.toFixed?.(1)}
              {diff.daily_call_growth_pct != null
                ? ` (${diff.daily_call_growth_pct > 0 ? "+" : ""}${diff.daily_call_growth_pct}%)`
                : ""}
            </li>
            <li>费用 P95: {String(diff.cost_p95_older)} → {String(diff.cost_p95_newer)}</li>
            <li>新增端点: {(diff.endpoints_added || []).join(", ") || "无"}</li>
            <li>消失端点: {(diff.endpoints_removed || []).join(", ") || "无"}</li>
          </ul>
        </div>
      )}
      <style jsx>{`
        .row {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          align-items: flex-end;
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
          font-size: 11px;
          min-width: 180px;
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
        .out {
          margin-top: 12px;
          padding: 10px;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
        }
        p {
          margin: 0 0 8px;
          color: #3dd68c;
          font-family: var(--mono);
          font-size: 12px;
        }
        ul {
          margin: 0;
          padding-left: 16px;
          color: #9eb2c7;
          font-size: 12px;
          font-family: var(--mono);
        }
      `}</style>
    </div>
  );
}
