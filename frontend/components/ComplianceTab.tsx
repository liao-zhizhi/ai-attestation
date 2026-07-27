"use client";

import { useCallback, useEffect, useState } from "react";
import { ComplianceGapAnalysis } from "./ComplianceGapAnalysis";
import {
  ComplianceHistory,
  type ComplianceHistoryItem,
} from "./ComplianceHistory";
import {
  ComplianceReport,
  type ComplianceReportData,
} from "./ComplianceReport";
import { ComplianceStandardCompare } from "./ComplianceStandardCompare";
import {
  ComplianceStandards,
  type ComplianceStandard,
} from "./ComplianceStandards";
import { ComplianceTemplateEditor } from "./ComplianceTemplateEditor";

type Props = {
  apiBase: string;
  apiKey: string;
  onOpenCall?: (callId: string) => void;
  onChainUpdated?: () => void;
};

type Pane = "standards" | "report" | "history" | "compare" | "gap" | "templates";

export function ComplianceTab({ apiBase, apiKey, onOpenCall, onChainUpdated }: Props) {
  const [pane, setPane] = useState<Pane>("standards");
  const [standards, setStandards] = useState<ComplianceStandard[]>([]);
  const [selected, setSelected] = useState("eu_ai_act_transparency");
  const [selectedIds, setSelectedIds] = useState<string[]>(["eu_ai_act_transparency"]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<ComplianceReportData | null>(null);
  const [proofOk, setProofOk] = useState<boolean | null>(null);
  const [proofMsg, setProofMsg] = useState("");
  const [history, setHistory] = useState<ComplianceHistoryItem[]>([]);
  const [compareLeft, setCompareLeft] = useState<string | null>(null);
  const [compareRight, setCompareRight] = useState<string | null>(null);
  const [diff, setDiff] = useState<
    Array<{
      check_id: string;
      from?: string;
      to?: string;
      improved?: boolean;
      regressed?: boolean;
    }> | null
  >(null);
  const [matrixIds, setMatrixIds] = useState<string[]>([
    "eu_ai_act_transparency",
    "iso_iec_42001",
  ]);
  const [matrix, setMatrix] = useState<Parameters<
    typeof ComplianceStandardCompare
  >[0]["result"]>(null);
  const [gapIds, setGapIds] = useState<string[]>(["eu_ai_act_transparency"]);
  const [gap, setGap] = useState<Parameters<typeof ComplianceGapAnalysis>[0]["result"]>(
    null
  );
  const [blockchainAnchor, setBlockchainAnchor] = useState<{
    timestamp?: string;
    tx_hash?: string;
    network?: string;
    status?: string;
    mock?: number | boolean;
  } | null>(null);
  const [verifyLink, setVerifyLink] = useState<string | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);

  const loadStandards = useCallback(async () => {
    const q =
      apiKey && apiKey.length >= 8
        ? `?api_key=${encodeURIComponent(apiKey)}`
        : "";
    const r = await fetch(`${apiBase}/v1/dashboard/compliance/standards${q}`);
    if (!r.ok) throw new Error("standards fetch failed");
    const d = await r.json();
    const list = d.standards || [];
    setStandards(list);
    setSelected((prev) => {
      if (prev && list.some((s: { id?: string }) => s.id === prev)) return prev;
      return list[0]?.id || prev;
    });
  }, [apiBase, apiKey]);

  const loadHistory = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/compliance/history?api_key=${encodeURIComponent(apiKey)}&limit=50`
    );
    if (!r.ok) return;
    const d = await r.json();
    setHistory(d.checks || []);
  }, [apiBase, apiKey]);

  useEffect(() => {
    loadStandards().catch((e) => setErr(e instanceof Error ? e.message : "load failed"));
  }, [loadStandards]);

  useEffect(() => {
    loadHistory().catch(() => undefined);
  }, [loadHistory]);

  function applyReport(d: Record<string, unknown>) {
    setReport({
      id: d.check_id as string,
      check_id: d.check_id as string,
      standard: d.standard as string,
      standard_name: d.standard_name as string,
      timestamp: d.timestamp as string,
      summary: d.summary as ComplianceReportData["summary"],
      check_results: d.check_results as ComplianceReportData["check_results"],
      report_hash: d.report_hash as string,
      chain_hash: d.chain_hash as string,
      prev_hash: d.prev_hash as string,
      duration_ms: d.duration_ms as number,
      timestamp_proof: d.timestamp_proof as ComplianceReportData["timestamp_proof"],
      timestamp_verify: d.timestamp_verify as ComplianceReportData["timestamp_verify"],
    });
    // Fresh run has a new report — clear prior anchor / proof until re-verified
    setBlockchainAnchor(null);
    setProofOk(null);
    setProofMsg("已写入哈希链（打开报告可复核链环）");
    setVerifyLink(null);
    setPane("report");
  }

  async function runCheck() {
    if (!apiKey) return;
    setBusy(true);
    setErr(null);
    try {
      const ids = selectedIds.length ? selectedIds : [selected];
      const r = await fetch(`${apiBase}/v1/dashboard/compliance/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          standard: ids[0],
          standards: ids.length > 1 ? ids : undefined,
        }),
      });
      if (!r.ok) throw new Error("compliance check failed");
      const d = await r.json();
      if (d.bundle && Array.isArray(d.reports) && d.reports[0]) {
        applyReport(d.reports[0]);
        if (d.reports.length > 1) {
          setErr(
            `已运行 ${d.reports.length} 个标准；当前展示第一个，其余见「历史」`
          );
        }
      } else {
        applyReport(d);
      }
      await loadHistory();
      onChainUpdated?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "check failed");
    } finally {
      setBusy(false);
    }
  }

  async function openReport(id: string) {
    setBusy(true);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/compliance/report/${encodeURIComponent(id)}?api_key=${encodeURIComponent(apiKey)}`
      );
      if (!r.ok) throw new Error("report fetch failed");
      const d = await r.json();
      setReport(d.report);
      setProofOk(!!d.proof?.ok);
      setProofMsg(d.proof?.message || "");
      setBlockchainAnchor(d.blockchain_anchor || null);
      setVerifyLink(null);
      setPane("report");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "report failed");
    } finally {
      setBusy(false);
    }
  }

  async function makeVerifyLink() {
    const id = report?.id || report?.check_id;
    if (!id || !apiKey) return;
    setVerifyBusy(true);
    setErr(null);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/compliance/report/${encodeURIComponent(id)}/verify-pack?api_key=${encodeURIComponent(apiKey)}`
      );
      if (!r.ok) throw new Error("verify-pack failed");
      const d = await r.json();
      const path = d.verify_path as string;
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      setVerifyLink(`${origin}${path}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "verify link failed");
    } finally {
      setVerifyBusy(false);
    }
  }

  async function doCompare() {
    if (!compareLeft || !compareRight) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/compliance/compare?api_key=${encodeURIComponent(apiKey)}&older_id=${encodeURIComponent(compareLeft)}&newer_id=${encodeURIComponent(compareRight)}`
    );
    if (!r.ok) return;
    const d = await r.json();
    setDiff(d.changes || []);
  }

  function toggleId(list: string[], id: string, set: (v: string[]) => void) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  async function runMatrix() {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/compliance/standards/compare?ids=${encodeURIComponent(matrixIds.join(","))}`
      );
      if (!r.ok) throw new Error("compare failed");
      setMatrix(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "compare failed");
    } finally {
      setBusy(false);
    }
  }

  async function runGap() {
    if (!apiKey) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/compliance/gap-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, standards: gapIds }),
      });
      if (!r.ok) throw new Error("gap analysis failed");
      setGap(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "gap failed");
    } finally {
      setBusy(false);
    }
  }

  const leanStandards = standards.map((s) => ({ id: s.id, name: s.name }));

  return (
    <section className="ct">
      <nav>
        {(
          [
            ["standards", "合规检查模板"],
            ["templates", "自定义模板"],
            ["compare", "标准对比"],
            ["gap", "差距分析"],
            ["report", "合规报告"],
            ["history", "合规历史"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={pane === k ? "on" : ""}
            onClick={() => setPane(k)}
          >
            {label}
          </button>
        ))}
      </nav>
      {err && <div className="err">{err}</div>}
      {busy && (
        <div className="progress" role="status">
          <div className="bar" />
          <span>
            正在运行合规检查… 已加载 —/{standards.length || "—"} 个标准
          </span>
        </div>
      )}
      {pane === "standards" && (
        <ComplianceStandards
          standards={standards}
          selectedId={selected}
          selectedIds={selectedIds}
          onSelect={(id) => {
            setSelected(id);
            setSelectedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
          }}
          onToggle={(id) => {
            setSelectedIds((prev) => {
              if (prev.includes(id)) {
                const next = prev.filter((x) => x !== id);
                return next.length ? next : [id];
              }
              return [...prev, id];
            });
          }}
          onRun={runCheck}
          busy={busy}
        />
      )}
      {pane === "templates" && (
        <ComplianceTemplateEditor
          apiBase={apiBase}
          apiKey={apiKey}
          onChanged={() => loadStandards().catch(() => undefined)}
        />
      )}
      {pane === "compare" && (
        <ComplianceStandardCompare
          standards={leanStandards}
          selected={matrixIds}
          onToggle={(id) => toggleId(matrixIds, id, setMatrixIds)}
          onCompare={runMatrix}
          result={matrix}
          busy={busy}
        />
      )}
      {pane === "gap" && (
        <ComplianceGapAnalysis
          standards={leanStandards}
          selected={gapIds}
          onToggle={(id) => toggleId(gapIds, id, setGapIds)}
          onAnalyze={runGap}
          result={gap}
          busy={busy}
        />
      )}
      {pane === "report" && (
        <ComplianceReport
          report={report}
          proofOk={proofOk}
          proofMessage={proofMsg}
          apiBase={apiBase}
          apiKey={apiKey}
          onOpenEvidence={onOpenCall}
          blockchainAnchor={blockchainAnchor}
          verifyLink={verifyLink}
          onMakeVerifyLink={makeVerifyLink}
          verifyBusy={verifyBusy}
        />
      )}
      {pane === "history" && (
        <ComplianceHistory
          items={history}
          activeId={report?.id || report?.check_id}
          onSelect={openReport}
          compareLeft={compareLeft}
          compareRight={compareRight}
          onPickCompare={(id, slot) => {
            if (slot === "left") setCompareLeft(id);
            else setCompareRight(id);
          }}
          onCompare={doCompare}
          diff={diff}
        />
      )}
      <style jsx>{`
        .ct {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          margin-bottom: 16px;
        }
        nav {
          display: flex;
          gap: 6px;
          margin-bottom: 14px;
          flex-wrap: wrap;
        }
        nav button {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #9eb2c7;
          border-radius: 4px;
          padding: 6px 12px;
          font-family: var(--mono);
          font-size: 12px;
          cursor: pointer;
        }
        nav button.on {
          background: #123526;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .err {
          color: #ff6b6b;
          font-family: var(--mono);
          font-size: 12px;
          margin-bottom: 10px;
        }
        .progress {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 12px;
          font-family: var(--mono);
          font-size: 12px;
          color: #7f8fa3;
        }
        .bar {
          width: 120px;
          height: 4px;
          border-radius: 2px;
          background: linear-gradient(90deg, #1a3d2c, #3dd68c, #1a3d2c);
          background-size: 200% 100%;
          animation: slide 1.2s linear infinite;
        }
        @keyframes slide {
          0% {
            background-position: 100% 0;
          }
          100% {
            background-position: -100% 0;
          }
        }
      `}</style>
    </section>
  );
}
