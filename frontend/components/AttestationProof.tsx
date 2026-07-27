"use client";

type Props = {
  chainLength: number;
  latestHash: string;
  integrityOk: boolean;
  message: string;
  totalCostUsd: number;
  nCalls: number;
  nQueries?: number;
  nCompliance?: number;
  nBaselines?: number;
  nDriftMarks?: number;
  blockchainAnchor?: {
    timestamp?: string;
    tx_hash?: string;
    network?: string;
    status?: string;
    mock?: number | boolean;
  } | null;
  onAnchor?: () => void;
  anchoring?: boolean;
};

function integrityCopy(chainLength: number, integrityOk: boolean): string {
  if (chainLength <= 0) {
    return "证据链尚未形成。等待第一次调用写入记录。";
  }
  if (integrityOk) {
    return "哈希链完整。证据链未受损。";
  }
  return "证据链受损。检测到哈希链断裂。";
}

export function AttestationProof({
  chainLength,
  latestHash,
  integrityOk,
  message,
  totalCostUsd,
  nCalls,
  nQueries = 0,
  nCompliance = 0,
  nBaselines = 0,
  nDriftMarks = 0,
  blockchainAnchor,
  onAnchor,
  anchoring,
}: Props) {
  const narrative = integrityCopy(chainLength, integrityOk);

  return (
    <aside className="panel">
      <h2>证据链。</h2>
      <div className={`badge ${chainLength <= 0 ? "idle" : integrityOk ? "ok" : "bad"}`}>
        {chainLength <= 0 ? "○ 待形成" : integrityOk ? "✓ 链完整" : "✗ 链断裂"}
      </div>
      <p className="narrative">{narrative}</p>
      <dl>
        <div>
          <dt>链长度</dt>
          <dd>{chainLength}</dd>
        </div>
        <div>
          <dt>调用数</dt>
          <dd>{nCalls}</dd>
        </div>
        <div>
          <dt>查询数</dt>
          <dd>{nQueries}</dd>
        </div>
        <div>
          <dt>合规检查</dt>
          <dd>{nCompliance}</dd>
        </div>
        <div>
          <dt>行为基线</dt>
          <dd>{nBaselines}</dd>
        </div>
        <div>
          <dt>漂移标记</dt>
          <dd>{nDriftMarks}</dd>
        </div>
        <div>
          <dt>累计费用</dt>
          <dd>${totalCostUsd.toFixed(6)}</dd>
        </div>
        <div>
          <dt>最新哈希</dt>
          <dd className="mono break">{latestHash || "—"}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{message || "—"}</dd>
        </div>
        <div>
          <dt>区块链锚定</dt>
          <dd className="mono break">
            {blockchainAnchor
              ? `${blockchainAnchor.network} · ${blockchainAnchor.status}${
                  blockchainAnchor.mock ? " · mock" : ""
                }`
              : "尚未锚定"}
            {blockchainAnchor?.tx_hash && (
              <>
                <br />
                {blockchainAnchor.tx_hash}
                <br />
                {blockchainAnchor.timestamp}
              </>
            )}
          </dd>
        </div>
      </dl>
      {onAnchor && (
        <button type="button" className="anc" onClick={onAnchor} disabled={anchoring}>
          {anchoring ? "锚定中…" : "锚定链头（Sepolia mock）"}
        </button>
      )}
      <p className="note">
        调用 / 查询 / 合规 / 基线 / 漂移共享 SHA-256 链。时间戳与链头锚定增强「存在性」证明（非法务效力保证）。
      </p>
      <p className="hint">候选文案，需人肉审核后方可发布</p>
      <style jsx>{`
        .panel {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 16px;
          height: fit-content;
          position: sticky;
          top: 16px;
        }
        h2 {
          margin: 0 0 12px;
          font-size: 14px;
          letter-spacing: 0.04em;
          text-transform: none;
          color: #d7e0ea;
          font-weight: 600;
        }
        .narrative {
          margin: 0 0 14px;
          font-size: 13px;
          line-height: 1.5;
          color: #9eb2c7;
        }
        .badge {
          display: inline-flex;
          align-items: center;
          padding: 6px 10px;
          border-radius: 4px;
          font-family: var(--mono);
          font-size: 13px;
          margin-bottom: 10px;
        }
        .badge.ok {
          background: #123526;
          color: #3dd68c;
          border: 1px solid #1f5a3c;
        }
        .badge.bad {
          background: #3a1515;
          color: #ff6b6b;
          border: 1px solid #6b2a2a;
        }
        .badge.idle {
          background: #152033;
          color: #7f8fa3;
          border: 1px solid #2a3b52;
        }
        dl {
          margin: 0;
          display: grid;
          gap: 12px;
        }
        dt {
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        dd {
          margin: 4px 0 0;
          font-family: var(--mono);
          font-size: 13px;
        }
        .break {
          word-break: break-all;
          line-height: 1.4;
        }
        .note {
          margin: 16px 0 0;
          font-size: 12px;
          color: #7f8fa3;
          line-height: 1.5;
        }
        .hint {
          margin: 8px 0 0;
          font-size: 10px;
          color: #5a6a7a;
          font-family: var(--mono);
        }
        .anc {
          margin-top: 12px;
          width: 100%;
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px;
          font-family: var(--mono);
          font-size: 11px;
          cursor: pointer;
        }
        .anc:disabled {
          opacity: 0.6;
        }
      `}</style>
    </aside>
  );
}
