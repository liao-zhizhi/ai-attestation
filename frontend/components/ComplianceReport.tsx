"use client";

import { useMemo, useState } from "react";

export type CheckResult = {
  check_id: string;
  category?: string;
  requirement?: string;
  status: string;
  detail?: string;
  manual_guidance?: string;
  review_guidance?: string;
  fail_reason?: string | null;
  evidence_summary?: string;
  query_template?: unknown;
  evidence?: unknown[];
  n_matched?: number;
  auto_check?: boolean;
  how_to_satisfy?: string;
  impact_factor?: string;
  impact_factor_zh?: string;
};

export type ComplianceReportData = {
  id?: string;
  check_id?: string;
  standard?: string;
  standard_name?: string;
  timestamp?: string;
  summary?: {
    n_pass?: number;
    n_fail?: number;
    n_manual?: number;
    n_total?: number;
    template_version?: string;
    template_source?: string;
    impact_radius_score?: number;
    impact_counts?: Record<string, number>;
  };
  check_results?: Record<string, CheckResult>;
  report_hash?: string;
  chain_hash?: string;
  prev_hash?: string;
  duration_ms?: number;
  template_version?: string;
  timestamp_proof?: {
    token?: string;
    timestamp?: string;
    source?: string;
    payload_hash?: string;
    verify_method?: string;
    external?: { status?: string; note?: string };
  };
  timestamp_verify?: { ok?: boolean; message?: string };
};

type Props = {
  report: ComplianceReportData | null;
  proofOk?: boolean | null;
  proofMessage?: string;
  apiBase: string;
  apiKey: string;
  onOpenEvidence?: (callId: string) => void;
  blockchainAnchor?: {
    timestamp?: string;
    tx_hash?: string;
    network?: string;
    status?: string;
    mock?: number | boolean;
  } | null;
  verifyLink?: string | null;
  onMakeVerifyLink?: () => void;
  verifyBusy?: boolean;
};

export function ComplianceReport({
  report,
  proofOk,
  proofMessage,
  apiBase,
  apiKey,
  onOpenEvidence,
  blockchainAnchor,
  verifyLink,
  onMakeVerifyLink,
  verifyBusy,
}: Props) {
  const [drillId, setDrillId] = useState<string | null>(null);

  // Hooks must run unconditionally (report may be null on first paint)
  const id = report?.id || report?.check_id || "";
  const summary = report?.summary || {};
  const results = report?.check_results || {};
  const tsp = report?.timestamp_proof;
  const tplVer =
    report?.template_version || summary.template_version || "—";
  const nFail = summary.n_fail ?? 0;
  const nManual = summary.n_manual ?? 0;
  const nTotal = summary.n_total ?? 0;
  const nPass = summary.n_pass ?? 0;
  const statusLine =
    nFail > 0
      ? `${nFail} 项检查未通过，需要复核。`
      : nManual > 0
        ? `自动项已通过；另有 ${nManual} 项需人工确认。`
        : "所有自动检查项已通过。";

  const drilled = useMemo(() => {
    if (!drillId) return null;
    return results[drillId] || null;
  }, [drillId, results]);

  if (!report) {
    return (
      <div className="empty">
        尚未生成合规报告。选择标准后点击「运行合规检查」。
        <div className="hint">候选文案，需人肉审核后方可发布</div>
        <style jsx>{`
          .empty {
            color: #9eb2c7;
            font-size: 13px;
            line-height: 1.5;
          }
          .hint {
            margin-top: 8px;
            font-size: 10px;
            color: #5a6a7a;
            font-family: var(--mono);
          }
        `}</style>
      </div>
    );
  }

  function exportUrl(fmt: string) {
    return `${apiBase}/v1/dashboard/compliance/report/${encodeURIComponent(id)}/export?format=${fmt}`;
  }

  function evidenceExport(checkId: string, fmt: string) {
    return `${apiBase}/v1/dashboard/compliance/report/${encodeURIComponent(id)}/checks/${encodeURIComponent(checkId)}/evidence?format=${fmt}`;
  }

  function offlinePackUrl() {
    return `${apiBase}/v1/dashboard/compliance/report/${encodeURIComponent(id)}/offline-pack`;
  }

  async function downloadAuthed(url: string, fallbackName: string) {
    try {
      const res = await fetch(url, { headers: { "X-Attest-Key": apiKey } });
      if (!res.ok) {
        window.alert(`下载失败 (${res.status})`);
        return;
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const m = /filename="?([^"]+)"?/i.exec(cd);
      const name = m?.[1] || fallbackName;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      window.alert("下载失败");
    }
  }

  return (
    <section className="cr">
      <header>
        <div>
          <h3>{report.standard_name || report.standard}</h3>
          <div className="sub mono">
            {id} · {report.timestamp} · {report.duration_ms?.toFixed?.(1) ?? "—"} ms · 模板 v
            {tplVer}
          </div>
        </div>
        <div className="exports">
          <button type="button" onClick={() => downloadAuthed(exportUrl("json"), `${id}.json`)}>
            JSON
          </button>
          <button type="button" onClick={() => downloadAuthed(exportUrl("txt"), `${id}.txt`)}>
            TXT
          </button>
          <button type="button" onClick={() => downloadAuthed(exportUrl("pdf"), `${id}.pdf`)}>
            PDF
          </button>
          <button type="button" onClick={() => downloadAuthed(exportUrl("oscal"), `${id}.oscal.json`)}>
            OSCAL
          </button>
          <button type="button" onClick={() => downloadAuthed(offlinePackUrl(), `${id}-offline.zip`)}>
            离线验证包
          </button>
          {onMakeVerifyLink && (
            <button type="button" className="share" onClick={onMakeVerifyLink} disabled={verifyBusy}>
              {verifyBusy ? "生成中…" : "生成独立验证链接"}
            </button>
          )}
        </div>
      </header>
      {verifyLink && (
        <div className="sharebox">
          <div className="lbl">独立验证链接（数据编码在 URL，无需登录）</div>
          <a href={verifyLink} target="_blank" rel="noreferrer" className="mono">
            {verifyLink.slice(0, 120)}…
          </a>
          <button
            type="button"
            className="copy"
            onClick={() => navigator.clipboard.writeText(verifyLink)}
          >
            复制
          </button>
        </div>
      )}
      <div
        className={`status-banner ${
          nFail > 0 ? "warn" : nManual > 0 ? "warn" : "ok"
        }`}
      >
        {statusLine}
      </div>
      <div className="stats">
        <span className="pass">通过 {nPass}</span>
        <span className="fail">未通过 {nFail}</span>
        <span className="man">人工 {summary.n_manual ?? 0}</span>
        <span>
          已对齐 {nPass}/{nTotal || "—"} 个维度
        </span>
        {summary.impact_radius_score != null && (
          <span className="radius">影响半径 {summary.impact_radius_score}</span>
        )}
      </div>
      <div className="proof mono">
        report_hash: {report.report_hash || "—"}
        <br />
        chain_hash: {report.chain_hash || "—"}
        <br />
        prev_hash: {report.prev_hash || "—"}
        {proofOk != null && (
          <>
            <br />
            链环验证: {proofOk ? "✓" : "✗"} {proofMessage}
          </>
        )}
      </div>
      {tsp && (
        <div className="tsp">
          <h4>时间戳证明</h4>
          <p className="mono">
            source: {tsp.source} · {tsp.timestamp}
            <br />
            token: {tsp.token}
            <br />
            {tsp.verify_method}
            <br />
            external: {tsp.external?.status} — {tsp.external?.note}
            {report.timestamp_verify && (
              <>
                <br />
                本地校验: {report.timestamp_verify.ok ? "✓" : "✗"}{" "}
                {report.timestamp_verify.message}
              </>
            )}
          </p>
        </div>
      )}
      {blockchainAnchor && (
        <div className="tsp">
          <h4>区块链锚定</h4>
          <p className="mono">
            {blockchainAnchor.network} · {blockchainAnchor.status}
            {blockchainAnchor.mock ? " (mock)" : ""}
            <br />
            {blockchainAnchor.timestamp}
            <br />
            tx: {blockchainAnchor.tx_hash}
          </p>
        </div>
      )}
      <ul>
        {Object.values(results).map((r) => (
          <li key={r.check_id} className={r.status}>
            <div className="row">
              <span className="st">{r.status}</span>
              {r.impact_factor_zh && (
                <span className={`impact ${r.impact_factor || "general"}`}>
                  {r.impact_factor_zh}
                </span>
              )}
              <code>{r.check_id}</code>
              <em>{r.category}</em>
              <button
                type="button"
                className="drill"
                onClick={() => setDrillId(drillId === r.check_id ? null : r.check_id)}
              >
                {drillId === r.check_id ? "收起证据" : "查看证据"}
              </button>
            </div>
            <p>{r.requirement}</p>
            <p className="detail">{r.detail}</p>
            {r.manual_guidance && <p className="guide">指引: {r.manual_guidance}</p>}
            {drillId === r.check_id && drilled && (
              <div className="drillbox">
                <h4>检查项证据</h4>
                {drilled.query_template != null && (
                  <p className="mono">
                    查询条件: {JSON.stringify(drilled.query_template)}
                  </p>
                )}
                <p className="mono">{drilled.evidence_summary || drilled.detail}</p>
                {drilled.status === "fail" && (
                  <p className="failr">
                    未通过原因: {drilled.fail_reason || drilled.detail}
                  </p>
                )}
                {(drilled.status === "manual" || drilled.review_guidance) && (
                  <p className="guide">
                    审查指引:{" "}
                    {drilled.review_guidance ||
                      drilled.manual_guidance ||
                      drilled.how_to_satisfy}
                  </p>
                )}
                <div className="ev">
                  {Array.isArray(drilled.evidence) && drilled.evidence.length > 0 ? (
                    (drilled.evidence as Array<Record<string, unknown>>).map((e, i) => {
                      const cid = e.call_id ? String(e.call_id) : null;
                      return (
                        <button
                          key={i}
                          type="button"
                          className="evb"
                          disabled={!cid || !onOpenEvidence}
                          onClick={() => cid && onOpenEvidence?.(cid)}
                          title={JSON.stringify(e)}
                        >
                          {cid || JSON.stringify(e).slice(0, 60)}
                          {e.endpoint ? ` · ${String(e.endpoint)}` : ""}
                        </button>
                      );
                    })
                  ) : (
                    <span className="none">无关联 API 调用证据</span>
                  )}
                </div>
                <div className="exrow">
                  <button
                    type="button"
                    onClick={() =>
                      downloadAuthed(evidenceExport(r.check_id, "json"), `${r.check_id}-evidence.json`)
                    }
                  >
                    导出证据 JSON
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadAuthed(evidenceExport(r.check_id, "pdf"), `${r.check_id}-evidence.pdf`)
                    }
                  >
                    导出证据 PDF
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      <style jsx>{`
        .empty {
          color: #7f8fa3;
          font-family: var(--mono);
          font-size: 12px;
          padding: 16px 0;
        }
        header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          margin-bottom: 12px;
        }
        h3 {
          margin: 0;
          font-size: 15px;
        }
        .sub {
          margin-top: 4px;
          color: #7f8fa3;
          font-size: 11px;
        }
        .exports {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          align-items: center;
        }
        .exports a,
        .exports button,
        .exports .share {
          color: #3dd68c;
          font-family: var(--mono);
          font-size: 12px;
          text-decoration: none;
          border: 1px solid #2a5c42;
          padding: 4px 8px;
          border-radius: 4px;
          background: transparent;
          cursor: pointer;
        }
        .exports .share:disabled {
          opacity: 0.6;
        }
        .sharebox {
          margin-bottom: 12px;
          padding: 8px 10px;
          background: #0e141c;
          border: 1px solid #2a3b52;
          border-radius: 4px;
        }
        .sharebox .lbl {
          font-size: 11px;
          color: #7f8fa3;
          margin-bottom: 6px;
        }
        .sharebox a {
          color: #9eb2c7;
          font-size: 11px;
          word-break: break-all;
        }
        .sharebox .copy {
          margin-top: 8px;
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 4px 10px;
          font-family: var(--mono);
          font-size: 11px;
          cursor: pointer;
        }
        .stats {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          font-family: var(--mono);
          font-size: 12px;
          margin-bottom: 10px;
        }
        .status-banner {
          margin: 0 0 12px;
          padding: 10px 12px;
          border-radius: 4px;
          font-size: 13px;
          line-height: 1.45;
        }
        .status-banner.ok {
          background: #123526;
          border: 1px solid #1f5a3c;
          color: #3dd68c;
        }
        .status-banner.warn {
          background: #2a2410;
          border: 1px solid #5a4a1a;
          color: #f0b429;
        }
        .pass {
          color: #3dd68c;
        }
        .fail {
          color: #ff6b6b;
        }
        .man {
          color: #e6c35c;
        }
        .proof {
          font-size: 11px;
          color: #9eb2c7;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px 10px;
          margin-bottom: 12px;
          word-break: break-all;
          line-height: 1.5;
        }
        .tsp {
          margin-bottom: 12px;
          padding: 8px 10px;
          background: #0e141c;
          border: 1px solid #2a5c42;
          border-radius: 4px;
        }
        .tsp h4 {
          margin: 0 0 6px;
          font-size: 11px;
          color: #3dd68c;
          text-transform: uppercase;
        }
        .tsp p {
          margin: 0;
          font-size: 11px;
          color: #9eb2c7;
          line-height: 1.5;
          word-break: break-all;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 10px;
          max-height: 520px;
          overflow-y: auto;
        }
        li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px 12px;
        }
        li.fail {
          border-color: #6b2a2a;
        }
        li.pass {
          border-color: #1f5a3c;
        }
        li.manual {
          border-color: #5a4a1f;
        }
        .row {
          display: flex;
          gap: 8px;
          align-items: center;
          font-family: var(--mono);
          font-size: 12px;
          flex-wrap: wrap;
        }
        .st {
          text-transform: uppercase;
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 3px;
          background: #152033;
        }
        .impact {
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 3px;
          border: 1px solid #2a3b52;
          color: #9eb2c7;
        }
        .impact.core {
          border-color: #6b2a2a;
          color: #ff8a8a;
          background: #2a1515;
        }
        .impact.critical {
          border-color: #5a4a1f;
          color: #e6c35c;
          background: #2a2410;
        }
        .impact.general {
          border-color: #2a3b52;
          color: #7f8fa3;
        }
        .radius {
          color: #9eb2c7;
        }
        .drill {
          margin-left: auto;
          background: #152033;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 3px;
          padding: 2px 8px;
          font-size: 11px;
          cursor: pointer;
          font-family: var(--mono);
        }
        em {
          color: #7f8fa3;
          font-style: normal;
          font-size: 11px;
        }
        p {
          margin: 6px 0 0;
          font-size: 12px;
          color: #d7e0ea;
          line-height: 1.45;
        }
        .detail {
          color: #9eb2c7;
          font-family: var(--mono);
          font-size: 11px;
        }
        .guide {
          color: #e6c35c;
          font-size: 11px;
        }
        .failr {
          color: #ff6b6b;
          font-size: 12px;
          font-weight: 600;
        }
        .drillbox {
          margin-top: 10px;
          padding: 10px;
          background: #0a1018;
          border: 1px solid #2a3b52;
          border-radius: 4px;
        }
        .drillbox h4 {
          margin: 0 0 8px;
          font-size: 11px;
          color: #3dd68c;
          text-transform: uppercase;
        }
        .ev {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 8px;
        }
        .evb {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #9eb2c7;
          border-radius: 3px;
          padding: 3px 6px;
          font-family: var(--mono);
          font-size: 10px;
          cursor: pointer;
        }
        .evb:disabled {
          cursor: default;
          opacity: 0.7;
        }
        .none {
          font-size: 11px;
          color: #7f8fa3;
        }
        .exrow {
          display: flex;
          gap: 10px;
          margin-top: 10px;
        }
        .exrow a,
        .exrow button {
          color: #3dd68c;
          font-family: var(--mono);
          font-size: 11px;
          background: transparent;
          border: none;
          padding: 0;
          cursor: pointer;
          text-decoration: underline;
        }
        .mono {
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}
