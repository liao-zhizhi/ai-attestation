"use client";

type MatrixRow = {
  group_id: string;
  category?: string;
  requirement?: string;
  auto_check?: boolean;
  cells: Record<string, string>;
};

type CompareResult = {
  standards: Array<{ id: string; name: string }>;
  n_groups: number;
  n_overlap: number;
  overlap_groups: string[];
  unique_groups: Record<string, string[]>;
  matrix: MatrixRow[];
  note?: string;
};

type Props = {
  standards: Array<{ id: string; name: string }>;
  selected: string[];
  onToggle: (id: string) => void;
  onCompare: () => void;
  result: CompareResult | null;
  busy: boolean;
};

export function ComplianceStandardCompare({
  standards,
  selected,
  onToggle,
  onCompare,
  result,
  busy,
}: Props) {
  return (
    <div className="csc">
      <p className="hint">选择至少两个标准，查看检查项重叠矩阵（适用 / 不适用）。</p>
      <div className="picks">
        {standards.map((s) => (
          <label key={s.id}>
            <input
              type="checkbox"
              checked={selected.includes(s.id)}
              onChange={() => onToggle(s.id)}
            />
            {s.name}
          </label>
        ))}
      </div>
      <button type="button" onClick={onCompare} disabled={busy || selected.length < 2}>
        {busy ? "对比中…" : "生成对比矩阵"}
      </button>
      {result && (
        <div className="out">
          <p className="mono">
            共 {result.n_groups} 个原子项 · 重叠 {result.n_overlap} · {result.note}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>检查组</th>
                  <th>类别</th>
                  {result.standards.map((s) => (
                    <th key={s.id}>{s.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.matrix.map((row) => (
                  <tr key={row.group_id}>
                    <td className="mono">{row.group_id}</td>
                    <td>{row.category}</td>
                    {result.standards.map((s) => (
                      <td
                        key={s.id}
                        className={row.cells[s.id] === "适用" ? "yes" : "no"}
                      >
                        {row.cells[s.id]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <style jsx>{`
        .hint {
          color: #7f8fa3;
          font-size: 12px;
          margin: 0 0 10px;
        }
        .picks {
          display: grid;
          gap: 6px;
          margin-bottom: 12px;
        }
        label {
          display: flex;
          gap: 8px;
          align-items: center;
          font-size: 12px;
          color: #d7e0ea;
          font-family: var(--mono);
        }
        button {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 8px 14px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .out {
          margin-top: 14px;
        }
        .mono {
          font-family: var(--mono);
          font-size: 11px;
          color: #9eb2c7;
        }
        .table-wrap {
          overflow: auto;
          max-height: 420px;
          border: 1px solid #1e2a38;
          border-radius: 4px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 11px;
        }
        th,
        td {
          padding: 6px 8px;
          border-bottom: 1px solid #1a2330;
          text-align: left;
          color: #d7e0ea;
        }
        th {
          position: sticky;
          top: 0;
          background: #111821;
          color: #7f8fa3;
          text-transform: uppercase;
          font-size: 10px;
        }
        .yes {
          color: #3dd68c;
        }
        .no {
          color: #7f8fa3;
        }
      `}</style>
    </div>
  );
}
