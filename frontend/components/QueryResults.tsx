"use client";

export type QueryResultRow = {
  id: string;
  timestamp: string;
  endpoint: string;
  model?: string | null;
  status_code?: number | null;
  cost_usd?: number | null;
  duration_ms?: number | null;
};

type Props = {
  count: number;
  durationMs: number;
  results: QueryResultRow[];
  queryId?: string | null;
  onSelect: (id: string) => void;
  selectedId?: string | null;
};

function toCsv(rows: QueryResultRow[]): string {
  const header = ["timestamp", "endpoint", "model", "status_code", "cost_usd", "id"];
  const lines = [header.join(",")];
  for (const r of rows) {
    lines.push(
      [
        r.timestamp,
        JSON.stringify(r.endpoint || ""),
        JSON.stringify(r.model || ""),
        String(r.status_code ?? ""),
        String(r.cost_usd ?? ""),
        r.id,
      ].join(",")
    );
  }
  return lines.join("\n");
}

export function QueryResults({
  count,
  durationMs,
  results,
  queryId,
  onSelect,
  selectedId,
}: Props) {
  if (!queryId && results.length === 0 && count === 0) return null;

  async function copyJson() {
    await navigator.clipboard.writeText(JSON.stringify(results, null, 2));
  }

  function exportCsv() {
    const blob = new Blob([toCsv(results)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `query-${queryId || "results"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="qr">
      <div className="head">
        <div>
          共找到 <strong>{count}</strong> 条记录，查询耗时{" "}
          <strong>{durationMs.toFixed(1)}</strong> ms
          {queryId && <span className="qid"> · {queryId}</span>}
        </div>
        <div className="actions">
          <button type="button" onClick={copyJson}>
            复制 JSON
          </button>
          <button type="button" onClick={exportCsv}>
            导出 CSV
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>端点</th>
              <th>模型</th>
              <th>状态</th>
              <th>费用</th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty">
                  无匹配记录
                </td>
              </tr>
            ) : (
              results.map((r) => (
                <tr
                  key={r.id}
                  className={selectedId === r.id ? "sel" : ""}
                  onClick={() => onSelect(r.id)}
                >
                  <td className="mono">{r.timestamp}</td>
                  <td>{r.endpoint}</td>
                  <td className="mono">{r.model || "—"}</td>
                  <td className="mono">{r.status_code ?? "—"}</td>
                  <td className="mono">${Number(r.cost_usd || 0).toFixed(6)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <style jsx>{`
        .qr {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          margin-bottom: 16px;
          overflow: hidden;
        }
        .head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          align-items: center;
          padding: 10px 14px;
          border-bottom: 1px solid #1e2a38;
          font-size: 12px;
          color: #9eb2c7;
          font-family: var(--mono);
        }
        .qid {
          color: #7f8fa3;
        }
        .actions {
          display: flex;
          gap: 8px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 5px 10px;
          font-size: 11px;
          font-family: var(--mono);
        }
        .table-wrap {
          overflow-x: auto;
          max-height: 280px;
          overflow-y: auto;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
        }
        th {
          text-align: left;
          padding: 8px 12px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          font-size: 10px;
          font-weight: 600;
          position: sticky;
          top: 0;
          background: #111821;
        }
        td {
          padding: 8px 12px;
          border-top: 1px solid #1a2330;
          color: #d7e0ea;
        }
        tr {
          cursor: pointer;
        }
        tr:hover td {
          background: #152033;
        }
        tr.sel td {
          background: #1a3d2c;
        }
        .mono {
          font-family: var(--mono);
        }
        .empty {
          text-align: center;
          color: #7f8fa3;
          padding: 24px;
        }
      `}</style>
    </section>
  );
}
