"use client";

import { useState } from "react";

export type DriftMark = {
  id: string;
  call_id: string;
  mark_type: string;
  timestamp: string;
  status: string;
  deviation?: {
    message?: string;
    multiplier?: number;
    metric?: string;
    baseline_value?: unknown;
    current_value?: unknown;
  };
  call_endpoint?: string;
  call_timestamp?: string;
  call_cost_usd?: number;
};

type Props = {
  marks: DriftMark[];
  filter: string;
  onFilter: (v: string) => void;
  onReview: (id: string, status: "reviewed" | "ignored") => void;
  onOpenCall?: (callId: string) => void;
  busy: boolean;
};

function detailNarrative(m: DriftMark): string {
  const x = m.deviation?.multiplier;
  if (typeof x === "number" && Number.isFinite(x)) {
    return `该调用费用超出基线 P95 的 ${x.toFixed(2)} 倍。这是一个值得注意的长程信号——请审查是否合理。`;
  }
  return (
    m.deviation?.message ||
    "检测到偏离基线的信号。这是一个值得注意的长程信号——请审查是否合理。"
  );
}

export function DriftMarksList({
  marks,
  filter,
  onFilter,
  onReview,
  onOpenCall,
  busy,
}: Props) {
  const [detail, setDetail] = useState<DriftMark | null>(null);
  const pendingN = marks.filter((m) => m.status === "pending").length;
  const emptyCopy =
    filter === "pending" || filter === "all"
      ? marks.length === 0
        ? "没有异常信号。你的 AI 行为保持在基线范围内。"
        : null
      : marks.length === 0
        ? "当前筛选下无标记。"
        : null;
  const headerHint =
    filter === "pending" && marks.length > 0
      ? `检测到 ${pendingN || marks.length} 个信号偏离基线。点击逐条审查。`
      : null;

  return (
    <div className="dm">
      <div className="bar">
        <select value={filter} onChange={(e) => onFilter(e.target.value)}>
          <option value="pending">待审计</option>
          <option value="reviewed">已审计</option>
          <option value="ignored">已忽略</option>
          <option value="all">全部</option>
        </select>
        <span className="n">{marks.length} 条</span>
      </div>
      {headerHint && <p className="hint-banner">{headerHint}</p>}
      {!marks.length ? (
        <p className="empty">{emptyCopy}</p>
      ) : (
        <ul>
          {marks.map((m) => (
            <li key={m.id}>
              <div className="top">
                <span className={`t ${m.mark_type}`}>{m.mark_type}</span>
                <code
                  className="link"
                  onClick={() => onOpenCall?.(m.call_id)}
                  onKeyDown={() => undefined}
                  role="button"
                  tabIndex={0}
                >
                  {m.call_id}
                </code>
                <em>{m.call_endpoint || "—"}</em>
              </div>
              <p>{m.deviation?.message || "—"}</p>
              <div className="meta mono">
                {m.call_timestamp || m.timestamp} · status={m.status}
              </div>
              <div className="acts">
                <button type="button" onClick={() => setDetail(m)}>
                  查看长程信号
                </button>
                {m.status === "pending" && (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onReview(m.id, "reviewed")}
                    >
                      已审计
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onReview(m.id, "ignored")}
                    >
                      忽略
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {detail && (
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          onClick={() => setDetail(null)}
          onKeyDown={() => undefined}
        >
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={() => undefined}
          >
            <h4>长程信号</h4>
            <p>{detailNarrative(detail)}</p>
            <div className="meta mono">
              call={detail.call_id}
              <br />
              type={detail.mark_type} · {detail.call_endpoint || "—"}
              <br />
              {detail.call_timestamp || detail.timestamp}
            </div>
            <button type="button" onClick={() => setDetail(null)}>
              关闭
            </button>
            <p className="foot">候选文案，需人肉审核后方可发布</p>
          </div>
        </div>
      )}
      <style jsx>{`
        .bar {
          display: flex;
          gap: 10px;
          align-items: center;
          margin-bottom: 10px;
        }
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 6px 8px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .n {
          font-family: var(--mono);
          font-size: 12px;
          color: #7f8fa3;
        }
        .hint-banner {
          margin: 0 0 12px;
          padding: 8px 10px;
          background: #2a2410;
          border: 1px solid #5a4a1a;
          border-radius: 4px;
          color: #f0b429;
          font-size: 13px;
        }
        .empty {
          color: #9eb2c7;
          font-size: 13px;
          line-height: 1.5;
          margin: 8px 0;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 10px;
        }
        li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
        }
        .top {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
          margin-bottom: 6px;
        }
        .t {
          font-family: var(--mono);
          font-size: 11px;
          padding: 2px 6px;
          border-radius: 3px;
          background: #152033;
          color: #f0b429;
        }
        .link {
          color: #3dd68c;
          cursor: pointer;
          font-size: 12px;
        }
        em {
          font-style: normal;
          color: #7f8fa3;
          font-size: 12px;
        }
        p {
          margin: 0 0 6px;
          font-size: 13px;
          color: #9eb2c7;
        }
        .meta {
          font-size: 11px;
          color: #7f8fa3;
          margin-bottom: 8px;
        }
        .acts {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        button {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 5px 10px;
          font-family: var(--mono);
          font-size: 11px;
          cursor: pointer;
        }
        button:disabled {
          opacity: 0.6;
        }
        .mono {
          font-family: var(--mono);
        }
        .modal {
          position: fixed;
          inset: 0;
          background: rgba(5, 8, 12, 0.72);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 50;
          padding: 16px;
        }
        .card {
          background: #111821;
          border: 1px solid #2a3b52;
          border-radius: 6px;
          padding: 18px 20px;
          max-width: 440px;
          width: 100%;
        }
        .card h4 {
          margin: 0 0 10px;
          font-size: 14px;
          color: #d7e0ea;
        }
        .card p {
          color: #d7e0ea;
          line-height: 1.55;
        }
        .foot {
          margin-top: 12px !important;
          font-size: 10px !important;
          color: #5a6a7a !important;
          font-family: var(--mono);
        }
      `}</style>
    </div>
  );
}
