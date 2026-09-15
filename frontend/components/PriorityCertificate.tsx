"use client";

type Artifact = {
  id?: string;
  timestamp?: string;
  title?: string;
  kind?: string;
  artifact_hash?: string;
  prev_hash?: string;
  chain_hash?: string;
  tsa_receipt?: { timestamp?: string; source?: string } | null;
};

type Props = {
  artifact: Artifact | null;
  proofOk?: boolean | null;
  duplicateNotice?: string | null;
  onExport: () => void;
  exporting: boolean;
};

/** 详情区：完整哈希、TSA 时间、导出优先权证书。 */
export function PriorityCertificate({
  artifact,
  proofOk,
  duplicateNotice,
  onExport,
  exporting,
}: Props) {
  if (!artifact) {
    return (
      <p className="hint">
        在列表中点开一条记录，可查看完整指纹并点「导出优先权证书」。
        <style jsx>{`
          .hint {
            color: #7f8fa3;
            font-size: 12px;
            margin-top: 12px;
          }
        `}</style>
      </p>
    );
  }
  const tsa = artifact.tsa_receipt?.timestamp || "—";
  return (
    <section className="cert">
      <h3>优先权证书</h3>
      <dl>
        <dt>标题</dt>
        <dd>{artifact.title || "—"}</dd>
        <dt>完整哈希</dt>
        <dd className="mono">{artifact.artifact_hash || "—"}</dd>
        <dt>链环 chain_hash</dt>
        <dd className="mono">{artifact.chain_hash || "—"}</dd>
        <dt>链状态</dt>
        <dd className={proofOk ? "ok" : "bad"}>{proofOk ? "链完整" : "链异常"}</dd>
        <dt>TSA 时间（本系统签发）</dt>
        <dd className="mono">{tsa}</dd>
        <dt>登记时间</dt>
        <dd className="mono">{artifact.timestamp || "—"}</dd>
      </dl>
      {duplicateNotice ? <p className="dup">{duplicateNotice}</p> : null}
      <p className="disc">
        技术存证，不构成法律意见或学术优先权裁定。ZIP 不含原文；请与原件放在一起保管。
      </p>
      <button type="button" className="accent" onClick={onExport} disabled={exporting}>
        {exporting ? "导出中…" : "导出优先权证书"}
      </button>
      <style jsx>{`
        .cert {
          margin-top: 16px;
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          max-width: 720px;
        }
        h3 {
          margin: 0 0 10px;
          font-size: 14px;
        }
        dl {
          display: grid;
          grid-template-columns: 140px 1fr;
          gap: 6px 10px;
          margin: 0 0 12px;
          font-size: 12px;
        }
        dt {
          color: #7f8fa3;
        }
        dd {
          margin: 0;
          word-break: break-all;
        }
        .mono {
          font-family: var(--mono);
          font-size: 11px;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        .dup {
          color: #f0b429;
          font-size: 12px;
        }
        .disc {
          color: #7f8fa3;
          font-size: 12px;
          line-height: 1.5;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 12px;
          font-size: 12px;
          font-family: var(--mono);
        }
        button.accent {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
      `}</style>
    </section>
  );
}
