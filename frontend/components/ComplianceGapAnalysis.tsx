"use client";

type GapItem = {
  standard: string;
  standard_name?: string;
  check_id: string;
  group_id?: string;
  category?: string;
  requirement?: string;
  status?: string;
  detail?: string;
  how_to_satisfy?: string;
};

type GapResult = {
  summary: {
    n_satisfied: number;
    n_unsatisfied: number;
    n_partial: number;
    n_total: number;
  };
  by_standard: Record<
    string,
    {
      standard_name: string;
      source: string;
      n_satisfied: number;
      n_unsatisfied: number;
      n_partial: number;
      n_total: number;
    }
  >;
  satisfied: GapItem[];
  unsatisfied: GapItem[];
  partial: GapItem[];
  disclaimer?: string;
};

type Props = {
  standards: Array<{ id: string; name: string }>;
  selected: string[];
  onToggle: (id: string) => void;
  onAnalyze: () => void;
  result: GapResult | null;
  busy: boolean;
};

function Section({
  title,
  items,
  tone,
}: {
  title: string;
  items: GapItem[];
  tone: string;
}) {
  if (!items.length) return null;
  return (
    <div className={`sec ${tone}`}>
      <h4>
        {title} ({items.length})
      </h4>
      <ul>
        {items.map((it) => (
          <li key={`${it.standard}:${it.check_id}`}>
            <div className="top">
              <code>{it.check_id}</code>
              <em>{it.standard_name || it.standard}</em>
            </div>
            <p>{it.requirement}</p>
            {it.how_to_satisfy && (
              <p className="how">如何满足: {it.how_to_satisfy}</p>
            )}
          </li>
        ))}
      </ul>
      <style jsx>{`
        .sec {
          margin-top: 12px;
        }
        h4 {
          margin: 0 0 8px;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .ok h4 {
          color: #3dd68c;
        }
        .bad h4 {
          color: #ff6b6b;
        }
        .man h4 {
          color: #e6c35c;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 8px;
          max-height: 240px;
          overflow-y: auto;
        }
        li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px 10px;
        }
        .top {
          display: flex;
          gap: 8px;
          font-family: var(--mono);
          font-size: 11px;
        }
        em {
          color: #7f8fa3;
          font-style: normal;
        }
        p {
          margin: 4px 0 0;
          font-size: 12px;
          color: #d7e0ea;
        }
        .how {
          color: #9eb2c7;
          font-size: 11px;
        }
      `}</style>
    </div>
  );
}

export function ComplianceGapAnalysis({
  standards,
  selected,
  onToggle,
  onAnalyze,
  result,
  busy,
}: Props) {
  return (
    <div className="cga">
      <p className="hint">
        选择目标标准，基于最近检查结果（无历史则现场评估，不写链）生成差距报告。
      </p>
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
      <button type="button" onClick={onAnalyze} disabled={busy || !selected.length}>
        {busy ? "分析中…" : "生成差距报告"}
      </button>
      {result && (
        <div className="out">
          <p className="mono">
            已满足 {result.summary.n_satisfied} · 未满足 {result.summary.n_unsatisfied} ·
            需人工 {result.summary.n_partial} / 合计 {result.summary.n_total}
          </p>
          {result.disclaimer && <p className="disc">{result.disclaimer}</p>}
          <Section title="已满足" items={result.satisfied} tone="ok" />
          <Section title="未满足" items={result.unsatisfied} tone="bad" />
          <Section title="部分满足 / 需人工" items={result.partial} tone="man" />
        </div>
      )}
      <style jsx>{`
        .hint,
        .disc {
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
        .mono {
          font-family: var(--mono);
          font-size: 12px;
          color: #9eb2c7;
        }
      `}</style>
    </div>
  );
}
