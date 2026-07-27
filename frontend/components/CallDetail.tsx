"use client";

import type { ApiCall } from "./Timeline";

type Proof = { ok: boolean; message?: string; expected_hash?: string; actual_hash?: string };

type Props = {
  call: ApiCall | null;
  proof: Proof | null;
  verifying: boolean;
  onVerify: () => void;
  onClose: () => void;
};

export function CallDetail({ call, proof, verifying, onVerify, onClose }: Props) {
  if (!call) return null;
  return (
    <div className="backdrop" onClick={onClose} role="presentation">
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog">
        <header>
          <h3>调用详情</h3>
          <button type="button" className="x" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="grid">
          <Field label="时间" value={call.timestamp} />
          <Field label="方法" value={call.method || "POST"} />
          <Field label="端点" value={call.endpoint} />
          <Field label="模型" value={call.model || "—"} />
          <Field label="状态" value={String(call.status_code ?? "—")} />
          <Field label="耗时" value={`${call.duration_ms} ms`} />
          <Field label="请求大小" value={`${call.request_size} B`} />
          <Field label="响应大小" value={`${call.response_size} B`} />
          <Field
            label="Tokens"
            value={`${call.prompt_tokens ?? 0} in / ${call.completion_tokens ?? 0} out`}
          />
          <Field label="费用" value={`$${Number(call.cost_usd).toFixed(8)}`} />
        </div>
        <div className="chain">
          <h4>哈希链</h4>
          <Field label="request_hash" value={call.request_hash} mono />
          <Field label="response_hash" value={call.response_hash} mono />
          <Field label="prev_hash" value={call.prev_hash} mono />
          <Field label="chain_hash" value={call.chain_hash} mono />
        </div>
        <footer>
          <button type="button" className="primary" onClick={onVerify} disabled={verifying}>
            {verifying ? "验证中…" : "验证完整性"}
          </button>
          {proof && (
            <span className={proof.ok ? "ok" : "bad"}>
              {proof.ok ? "✓ " : "✗ "}
              {proof.message}
            </span>
          )}
        </footer>
        <style jsx>{`
          .backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.62);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            z-index: 50;
          }
          .modal {
            width: min(720px, 100%);
            max-height: 90vh;
            overflow: auto;
            background: #111821;
            border: 1px solid #1e2a38;
            border-radius: 8px;
            padding: 18px 20px 20px;
          }
          header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
          }
          h3 {
            margin: 0;
            font-size: 16px;
          }
          h4 {
            margin: 16px 0 8px;
            font-size: 12px;
            color: #7f8fa3;
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }
          .x {
            background: transparent;
            border: none;
            color: #7f8fa3;
            font-size: 22px;
            line-height: 1;
          }
          .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
          }
          .chain {
            margin-top: 8px;
          }
          footer {
            margin-top: 18px;
            display: flex;
            align-items: center;
            gap: 14px;
          }
          .primary {
            background: #1a3d2c;
            color: #3dd68c;
            border: 1px solid #2a5c42;
            border-radius: 4px;
            padding: 8px 14px;
            font-family: var(--mono);
            font-size: 13px;
          }
          .primary:disabled {
            opacity: 0.6;
          }
          .ok {
            color: #3dd68c;
            font-family: var(--mono);
            font-size: 13px;
          }
          .bad {
            color: #ff6b6b;
            font-family: var(--mono);
            font-size: 13px;
          }
        `}</style>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="f">
      <div className="l">{label}</div>
      <div className={mono ? "v mono" : "v"}>{value}</div>
      <style jsx>{`
        .l {
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .v {
          margin-top: 3px;
          font-size: 13px;
          word-break: break-all;
        }
        .mono {
          font-family: var(--mono);
          font-size: 12px;
        }
      `}</style>
    </div>
  );
}
