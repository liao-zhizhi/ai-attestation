"use client";

export type ComplianceStandard = {
  id: string;
  name: string;
  description: string;
  version: string;
  n_checks: number;
  n_auto: number;
  n_manual: number;
  auto_coverage: number;
  source?: string;
  checks: Array<{
    check_id: string;
    category: string;
    requirement: string;
    auto_check: boolean;
  }>;
};

type Props = {
  standards: ComplianceStandard[];
  selectedId: string;
  selectedIds?: string[];
  onSelect: (id: string) => void;
  onToggle?: (id: string) => void;
  onRun: () => void;
  busy: boolean;
};

export function ComplianceStandards({
  standards,
  selectedId,
  selectedIds,
  onSelect,
  onToggle,
  onRun,
  busy,
}: Props) {
  const multi = !!onToggle && !!selectedIds;
  const selected = standards.find((s) => s.id === selectedId) || standards[0];
  const runLabel = multi && selectedIds && selectedIds.length > 1
    ? `运行 ${selectedIds.length} 个标准（重叠只查一次）`
    : "运行合规检查";

  return (
    <div className="cs">
      <div className="pick">
        {standards.map((s) => (
          <button
            key={s.id}
            type="button"
            className={
              multi
                ? selectedIds!.includes(s.id)
                  ? "active"
                  : ""
                : s.id === selectedId
                  ? "active"
                  : ""
            }
            onClick={() => onSelect(s.id)}
          >
            {multi && (
              <label className="chk" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={selectedIds!.includes(s.id)}
                  onChange={() => onToggle?.(s.id)}
                />
              </label>
            )}
            <strong>{s.name}</strong>
            <span>
              {s.n_auto} 自动 / {s.n_manual} 人工 · 覆盖{" "}
              {(s.auto_coverage * 100).toFixed(0)}%
              {s.source ? ` · ${s.source}` : ""}
            </span>
          </button>
        ))}
      </div>
      {selected && (
        <div className="meta">
          <p>{selected.description}</p>
          <ul>
            {selected.checks.map((c) => (
              <li key={c.check_id}>
                <span className={c.auto_check ? "auto" : "man"}>
                  {c.auto_check ? "AUTO" : "MANUAL"}
                </span>
                <code>{c.check_id}</code>
                <em>{c.category}</em>
              </li>
            ))}
          </ul>
          <button type="button" className="run" onClick={onRun} disabled={busy}>
            {busy ? "检查中…" : runLabel}
          </button>
        </div>
      )}
      <style jsx>{`
        .cs {
          display: grid;
          gap: 12px;
        }
        .pick {
          display: grid;
          gap: 8px;
        }
        .pick button {
          text-align: left;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
          color: #d7e0ea;
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-family: var(--mono);
          font-size: 12px;
          cursor: pointer;
          position: relative;
        }
        .chk {
          position: absolute;
          top: 10px;
          right: 10px;
        }
        .pick button.active {
          border-color: #2a5c42;
          background: #123526;
        }
        .pick span {
          color: #7f8fa3;
          font-size: 11px;
        }
        .meta p {
          margin: 0 0 10px;
          font-size: 13px;
          color: #9eb2c7;
          line-height: 1.5;
        }
        ul {
          list-style: none;
          margin: 0 0 12px;
          padding: 0;
          max-height: 180px;
          overflow-y: auto;
          display: grid;
          gap: 6px;
        }
        li {
          display: flex;
          gap: 8px;
          align-items: center;
          font-size: 11px;
          font-family: var(--mono);
          color: #d7e0ea;
        }
        .auto,
        .man {
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 3px;
        }
        .auto {
          background: #123526;
          color: #3dd68c;
        }
        .man {
          background: #2a2410;
          color: #e6c35c;
        }
        em {
          color: #7f8fa3;
          font-style: normal;
        }
        .run {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 8px 14px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .run:disabled {
          opacity: 0.6;
        }
      `}</style>
    </div>
  );
}
