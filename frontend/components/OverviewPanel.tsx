"use client";

type Props = {
  todayCalls: number;
  todayCost: number;
  pendingMarks: number;
  complianceLabel: string;
  complianceOk: boolean | null;
  integrityOk: boolean;
  chainLength: number;
  latestHash: string;
  onOpenMarks?: () => void;
  onOpenAttestation?: () => void;
};

export function OverviewPanel({
  todayCalls,
  todayCost,
  pendingMarks,
  complianceLabel,
  complianceOk,
  integrityOk,
  chainLength,
  latestHash,
  onOpenMarks,
  onOpenAttestation,
}: Props) {
  return (
    <div className="ov">
      <article className="card">
        <div className="l">今日调用</div>
        <div className="v mono">{todayCalls}</div>
      </article>
      <article className="card">
        <div className="l">今日费用</div>
        <div className="v mono warn">${todayCost.toFixed(4)}</div>
      </article>
      <article
        className={`card ${pendingMarks > 0 ? "alert" : ""}`}
        role={onOpenMarks ? "button" : undefined}
        onClick={onOpenMarks}
      >
        <div className="l">待审计标记</div>
        <div className={`v mono ${pendingMarks > 0 ? "danger" : ""}`}>
          {pendingMarks}
        </div>
      </article>
      <article className="card">
        <div className="l">合规状态</div>
        <div className="lamp">
          <span
            className={`dot ${
              complianceOk === true ? "ok" : complianceOk === false ? "bad" : "mute"
            }`}
          />
          <span className="mono">{complianceLabel}</span>
        </div>
      </article>
      <article
        className="card wide"
        role={onOpenAttestation ? "button" : undefined}
        onClick={onOpenAttestation}
      >
        <div className="l">完整性验证</div>
        <div className="lamp">
          <span
            className={`dot ${
              chainLength === 0 ? "mute" : integrityOk ? "ok" : "bad"
            }`}
          />
          <span className="mono">
            {chainLength === 0
              ? "待形成"
              : integrityOk
                ? "链完整"
                : "链异常"}{" "}
            · len={chainLength}
          </span>
        </div>
        <div className="hash mono">{latestHash ? `${latestHash.slice(0, 24)}…` : "—"}</div>
      </article>
      <style jsx>{`
        .ov {
          display: grid;
          grid-template-columns: repeat(4, 1fr) 1.4fr;
          gap: 10px;
          margin-bottom: 16px;
        }
        .card {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 12px 14px;
        }
        .card.alert {
          border-color: #6b2a2a;
          background: #1a1010;
          cursor: pointer;
        }
        .card.wide {
          cursor: pointer;
        }
        .l {
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .v {
          margin-top: 8px;
          font-size: 22px;
          font-weight: 600;
        }
        .warn {
          color: #f0b429;
        }
        .danger {
          color: #ff6b6b;
        }
        .lamp {
          margin-top: 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
        }
        .dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #7f8fa3;
        }
        .dot.ok {
          background: #3dd68c;
          box-shadow: 0 0 8px #3dd68c66;
        }
        .dot.bad {
          background: #ff6b6b;
        }
        .dot.mute {
          background: #7f8fa3;
        }
        .hash {
          margin-top: 8px;
          font-size: 11px;
          color: #7f8fa3;
          word-break: break-all;
        }
        .mono {
          font-family: var(--mono);
        }
        @media (max-width: 1100px) {
          .ov {
            grid-template-columns: 1fr 1fr;
          }
          .card.wide {
            grid-column: 1 / -1;
          }
        }
      `}</style>
    </div>
  );
}
