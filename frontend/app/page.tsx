"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AttestationProof } from "@/components/AttestationProof";
import { BehaviorTab } from "@/components/BehaviorTab";
import { CallDetail } from "@/components/CallDetail";
import { ComplianceTab } from "@/components/ComplianceTab";
import { EmptyState } from "@/components/EmptyState";
import { OverviewPanel } from "@/components/OverviewPanel";
import { QueryHistory, type HistoryItem } from "@/components/QueryHistory";
import { QueryPanel, type QueryFilters } from "@/components/QueryPanel";
import { QueryResults, type QueryResultRow } from "@/components/QueryResults";
import { Sidebar, type NavId } from "@/components/Sidebar";
import { SettingsPanel } from "@/components/SettingsPanel";
import { KeysPanel } from "@/components/KeysPanel";
import { ExportDialog } from "@/components/ExportDialog";
import { Timeline, type ApiCall } from "@/components/Timeline";
import { TrendCharts, type DayPoint, type VendorSlice } from "@/components/TrendCharts";
import { UserGuide } from "@/components/UserGuide";
import { resolveApiBase, parseApiError, formatDetail, withApiKey } from "@/lib/api";

const STORAGE_KEY = "ata_mvp_api_key";
const AUTH_STORAGE_KEY = "ata_mvp_authorization";

function envApiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE ||
    "http://127.0.0.1:8004"
  ).replace(/\/$/, "");
}

const DEFAULT_FILTERS: QueryFilters = {
  time_range: "7d",
  endpoint: "",
  min_cost: "",
  max_cost: "",
  status: "",
  model: "",
  vendor: "",
};

const VENDOR_COLORS = [
  "#3dd68c",
  "#5b8def",
  "#f0b429",
  "#c084fc",
  "#ff6b6b",
  "#2dd4bf",
  "#fb923c",
  "#a3e635",
];

export default function HomePage() {
  const [nav, setNav] = useState<NavId>("guide");
  // Start from build-time env; resolveApiBase() corrects remote→localhost mistakes after mount.
  const [apiBase, setApiBase] = useState(envApiBase);
  const [apiReady, setApiReady] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [authorization, setAuthorization] = useState("");
  const [calls, setCalls] = useState<ApiCall[]>([]);
  const [pendingMarks, setPendingMarks] = useState(0);
  const [todayCallsN, setTodayCallsN] = useState(0);
  const [todayCostN, setTodayCostN] = useState(0);
  const [complianceLabel, setComplianceLabel] = useState("未检查");
  const [complianceOk, setComplianceOk] = useState<boolean | null>(null);
  const [attest, setAttest] = useState({
    chainLength: 0,
    latestHash: "",
    integrityOk: true,
    message: "",
    totalCostUsd: 0,
    nCalls: 0,
    nQueries: 0,
    nCompliance: 0,
    nBaselines: 0,
    nDriftMarks: 0,
    blockchainAnchor: null as {
      timestamp?: string;
      tx_hash?: string;
      network?: string;
      status?: string;
      mock?: number | boolean;
    } | null,
  });
  const [anchoring, setAnchoring] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiCall | null>(null);
  const [proof, setProof] = useState<{ ok: boolean; message?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [exportingPack, setExportingPack] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [queryOpen, setQueryOpen] = useState(false);
  const [filters, setFilters] = useState<QueryFilters>(DEFAULT_FILTERS);
  const [queryBusy, setQueryBusy] = useState(false);
  const [queryResults, setQueryResults] = useState<QueryResultRow[]>([]);
  const [queryCount, setQueryCount] = useState(0);
  const [queryDuration, setQueryDuration] = useState(0);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [callsOffset, setCallsOffset] = useState(0);
  const [callsHasMore, setCallsHasMore] = useState(false);
  const [series, setSeries] = useState<DayPoint[]>([]);
  const [vendors, setVendors] = useState<VendorSlice[]>([]);
  const [role, setRole] = useState("");
  const [exportOpen, setExportOpen] = useState(false);

  const proxyUrl = useMemo(() => (apiBase ? `${apiBase}/v1/proxy` : ""), [apiBase]);
  const canAdmin = role === "admin";
  const canWrite = role === "admin" || role === "read_write";
  // Hide Settings/Key only after we know the role is read_only (empty = loading/onboarding).
  const showSettings = role !== "read_only";

  useEffect(() => {
    setApiBase(resolveApiBase());
    setApiReady(true);
  }, []);

  useEffect(() => {
    if (!apiReady || !apiBase) return;
    const saved = localStorage.getItem(STORAGE_KEY);
    const savedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
    if (savedAuth) setAuthorization(savedAuth);
    if (saved) setApiKey(saved);
    else {
      fetch(`${apiBase}/health`)
        .then((r) => r.json())
        .then((d) => {
          if (d.demo_api_key) {
            setApiKey(d.demo_api_key);
            localStorage.setItem(STORAGE_KEY, d.demo_api_key);
          }
        })
        .catch(() => undefined);
    }
  }, [apiReady, apiBase]);

  const refresh = useCallback(
    async (key: string, opts?: { append?: boolean; offset?: number }) => {
      if (!apiBase || !key || key.length < 8) return;
      const append = opts?.append ?? false;
      const offset = opts?.offset ?? 0;
      setErr(null);
      try {
        const limit = 100;
        const [cRes, aRes, hRes, oRes, meRes] = await Promise.all([
          fetch(
            withApiKey(
              `${apiBase}/v1/dashboard/calls?limit=${limit}&offset=${offset}`,
              key
            )
          ),
          fetch(withApiKey(`${apiBase}/v1/dashboard/attestation`, key)),
          fetch(
            withApiKey(`${apiBase}/v1/dashboard/query-history?limit=20`, key)
          ),
          append
            ? Promise.resolve(null)
            : fetch(withApiKey(`${apiBase}/v1/dashboard/overview`, key)),
          append
            ? Promise.resolve(null)
            : fetch(withApiKey(`${apiBase}/v1/dashboard/me`, key)),
        ]);
        if (!cRes.ok || !aRes.ok) {
          const failed = !cRes.ok ? cRes : aRes;
          throw new Error(await parseApiError(failed, "仪表盘加载失败"));
        }
        const cJson = await cRes.json();
        const aJson = await aRes.json();
        const batch: ApiCall[] = cJson.calls || [];
        setCalls((prev) => (append ? [...prev, ...batch] : batch));
        setCallsOffset(offset + batch.length);
        setCallsHasMore(Boolean(cJson.has_more ?? batch.length >= limit));
        setAttest({
          chainLength: aJson.chain_length || 0,
          latestHash: aJson.latest_hash || "",
          integrityOk: !!aJson.integrity_ok,
          message: aJson.message || "",
          totalCostUsd: Number(aJson.total_cost_usd || 0),
          nCalls: aJson.n_calls || 0,
          nQueries: aJson.n_queries || 0,
          nCompliance: aJson.n_compliance || 0,
          nBaselines: aJson.n_baselines || 0,
          nDriftMarks: aJson.n_drift_marks || 0,
          blockchainAnchor: aJson.blockchain_anchor || null,
        });
        if (hRes.ok) {
          const hJson = await hRes.json();
          setHistory(hJson.queries || []);
        }
        if (oRes && oRes.ok) {
          const o = await oRes.json();
          setPendingMarks(Number(o.pending_marks || 0));
          if (o.compliance) {
            setComplianceOk(o.compliance.ok);
            setComplianceLabel(o.compliance.label || "未检查");
          }
          const days: DayPoint[] = (o.series_7d || []).map(
            (d: { day: string; calls: number; cost: number; marks: number }) => ({
              day: d.day,
              calls: Number(d.calls || 0),
              cost: Number(d.cost || 0),
              marks: Number(d.marks || 0),
            })
          );
          setSeries(days);
          const vs: VendorSlice[] = (o.vendors_today || []).map(
            (v: { vendor: string; count: number }, i: number) => ({
              vendor: v.vendor,
              count: Number(v.count || 0),
              color: VENDOR_COLORS[i % VENDOR_COLORS.length],
            })
          );
          setVendors(vs);
          setTodayCallsN(Number(o.today_calls || 0));
          setTodayCostN(Number(o.today_cost || 0));
        }
        if (meRes) {
          if (meRes.ok) {
            const me = await meRes.json();
            setRole(me.me?.role || "read_write");
          } else if (meRes.status === 401 || meRes.status === 403) {
            setRole("");
            throw new Error(await parseApiError(meRes, "API Key 无效或权限不足"));
          } else {
            // Avoid leaving role="" forever (canWrite stuck false) after dashboard loaded.
            setRole((prev) => prev || "read_only");
            setErr(await parseApiError(meRes, "无法确认角色，已按只读处理"));
          }
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "load failed");
      }
    },
    [apiBase]
  );

  useEffect(() => {
    if (role === "read_only" && (nav === "settings" || nav === "keys")) {
      setNav("dashboard");
    }
  }, [role, nav]);

  useEffect(() => {
    if (apiReady && apiBase && apiKey) refresh(apiKey);
  }, [apiReady, apiBase, apiKey, refresh]);

  async function onSaveKey() {
    localStorage.setItem(STORAGE_KEY, apiKey.trim());
    localStorage.setItem(AUTH_STORAGE_KEY, authorization.trim());
    await refresh(apiKey.trim());
  }

  async function simulate() {
    if (!apiKey || !canWrite) return;
    setBusy(true);
    try {
      const r = await fetch(`${apiBase}/v1/demo/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (!r.ok) {
        setErr(await parseApiError(r, "模拟调用失败"));
        return;
      }
      await refresh(apiKey);
    } finally {
      setBusy(false);
    }
  }

  function filtersToBody(f: QueryFilters) {
    return {
      api_key: apiKey,
      time_range: f.time_range,
      custom_from: f.custom_from || null,
      custom_to: f.custom_to || null,
      endpoint: f.endpoint.trim() || null,
      min_cost: f.min_cost === "" ? null : Number(f.min_cost),
      max_cost: f.max_cost === "" ? null : Number(f.max_cost),
      status: f.status || null,
      model: f.model.trim() || null,
      vendor: f.vendor?.trim() || null,
    };
  }

  async function runQuery(override?: QueryFilters) {
    if (!apiKey || !canWrite) return;
    const f = override || filters;
    setQueryBusy(true);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filtersToBody(f)),
      });
      if (!r.ok) throw new Error(await parseApiError(r, "查询失败"));
      const d = await r.json();
      setQueryResults(d.results || []);
      setQueryCount(d.count || 0);
      setQueryDuration(Number(d.duration_ms || 0));
      setQueryId(d.query_id || null);
      await refresh(apiKey);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "query failed");
    } finally {
      setQueryBusy(false);
    }
  }

  async function replayHistory(item: HistoryItem) {
    const p = (item.query_params || {}) as Record<string, unknown>;
    const next: QueryFilters = {
      time_range: String(p.time_range || "7d"),
      custom_from: p.custom_from ? String(p.custom_from) : undefined,
      custom_to: p.custom_to ? String(p.custom_to) : undefined,
      endpoint: p.endpoint ? String(p.endpoint) : "",
      min_cost: p.min_cost != null ? String(p.min_cost) : "",
      max_cost: p.max_cost != null ? String(p.max_cost) : "",
      status: p.status ? String(p.status) : "",
      model: p.model ? String(p.model) : "",
      vendor: p.vendor ? String(p.vendor) : "",
    };
    setFilters(next);
    setQueryOpen(true);
    await runQuery(next);
  }

  async function openDetail(id: string) {
    setSelectedId(id);
    setProof(null);
    try {
      const r = await fetch(withApiKey(`${apiBase}/v1/dashboard/calls/${id}`, apiKey));
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.call) {
        setErr(formatDetail(d.detail, "加载调用详情失败"));
        setSelectedId(null);
        setDetail(null);
        return;
      }
      setDetail(d.call);
      setProof(d.proof);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载调用详情失败");
      setSelectedId(null);
      setDetail(null);
    }
  }

  async function verifyDetail() {
    if (!detail) return;
    setVerifying(true);
    try {
      const r = await fetch(
        withApiKey(`${apiBase}/v1/dashboard/calls/${detail.id}/verify`, apiKey),
        { method: "POST" }
      );
      if (!r.ok) {
        setErr(await parseApiError(r, "校验失败"));
        return;
      }
      const d = await r.json();
      setProof({
        ok: !!d.chain_proof?.ok,
        message: d.chain_proof?.message,
      });
    } finally {
      setVerifying(false);
    }
  }

  async function exportVerifyPack() {
    if (!detail || !apiKey) return;
    setExportingPack(true);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(`${apiBase}/v1/reports/${encodeURIComponent(detail.id)}/export`, apiKey)
      );
      if (!r.ok) {
        setErr(await parseApiError(r, "导出验证包失败"));
        return;
      }
      const blob = await r.blob();
      const cd = r.headers.get("Content-Disposition") || "";
      const m = /filename="?([^"]+)"?/i.exec(cd);
      const name = m?.[1] || `ata_call_${detail.id}_verify.zip`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导出验证包失败");
    } finally {
      setExportingPack(false);
    }
  }

  async function copyProxy() {
    try {
      await navigator.clipboard.writeText(proxyUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setErr("无法复制到剪贴板（需 HTTPS 或本机安全上下文）");
    }
  }

  async function anchorChain() {
    if (!apiKey || !canWrite) return;
    setAnchoring(true);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/attestation/anchor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (!r.ok) throw new Error(await parseApiError(r, "锚定失败"));
      await refresh(apiKey);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "anchor failed");
    } finally {
      setAnchoring(false);
    }
  }

  const showEmpty = attest.nCalls === 0 && calls.length === 0 && !err;

  return (
    <div className="layout">
      <Sidebar
        active={nav}
        onNavigate={setNav}
        apiKey={apiKey}
        proxyUrl={proxyUrl}
        onCopyProxy={copyProxy}
        copied={copied}
        showSettings={showSettings}
      />
      <main className="main">
        <header className="top">
          <div>
            <div className="brand">
              {nav === "guide" && "操作手册"}
              {nav === "dashboard" && "仪表盘"}
              {nav === "calls" && "API 调用记录"}
              {nav === "compliance" && "合规管理"}
              {nav === "behavior" && "行为监控"}
              {nav === "attestation" && "防篡改证明"}
              {nav === "settings" && "设置"}
              {nav === "keys" && "Key"}
            </div>
            <div className="sub">独立验证与对账 · MVP</div>
          </div>
          <div className="controls">
            {(nav === "dashboard" || nav === "calls") && (
              <button type="button" onClick={() => setQueryOpen((v) => !v)}>
                {queryOpen ? "收起查询" : "查询即审计"}
              </button>
            )}
            {nav === "calls" && (
              <button type="button" onClick={() => setExportOpen(true)}>
                导出
              </button>
            )}
            <button
              type="button"
              className="accent"
              onClick={simulate}
              disabled={busy || !canWrite || !apiKey}
              title={!canWrite ? "需要 read_write 或 admin" : undefined}
            >
              模拟一条调用
            </button>
          </div>
        </header>

        {err && (
          <div className="err">
            {/network|fetch|failed to fetch|后端/i.test(err)
              ? `后端不可用：${err}（确认 :8004 已启动，且代理 URL 指向正确主机）`
              : err}
          </div>
        )}

        {nav === "guide" && <UserGuide proxyUrl={proxyUrl} />}

        {(nav === "dashboard" || nav === "calls") && queryOpen && (
          <>
            <QueryPanel
              open
              onToggle={() => setQueryOpen(false)}
              filters={filters}
              onChange={setFilters}
              onQuery={() => runQuery()}
              busy={queryBusy}
              canWrite={canWrite}
            />
            <QueryHistory items={history} onReplay={replayHistory} activeId={queryId} />
            <QueryResults
              count={queryCount}
              durationMs={queryDuration}
              results={queryResults}
              queryId={queryId}
              selectedId={selectedId}
              onSelect={openDetail}
            />
          </>
        )}

        {nav === "dashboard" && (
          <>
            <OverviewPanel
              todayCalls={todayCallsN}
              todayCost={todayCostN}
              pendingMarks={pendingMarks}
              complianceLabel={complianceLabel}
              complianceOk={complianceOk}
              integrityOk={attest.integrityOk}
              chainLength={attest.chainLength}
              latestHash={attest.latestHash}
              onOpenMarks={() => setNav("behavior")}
              onOpenAttestation={() => setNav("attestation")}
            />
            {showEmpty ? (
              <EmptyState
                proxyUrl={proxyUrl}
                onSimulate={simulate}
                busy={busy}
                canWrite={canWrite}
              />
            ) : (
              <>
                <TrendCharts series={series} vendors={vendors} />
                <h2 className="sec">最近调用</h2>
                <Timeline calls={calls.slice(0, 20)} selectedId={selectedId} onSelect={openDetail} />
              </>
            )}
          </>
        )}

        {nav === "calls" && (
          <>
            {showEmpty ? (
              <EmptyState
                proxyUrl={proxyUrl}
                onSimulate={simulate}
                busy={busy}
                canWrite={canWrite}
              />
            ) : (
              <>
                <Timeline calls={calls} selectedId={selectedId} onSelect={openDetail} />
                {callsHasMore && (
                  <button
                    type="button"
                    className="more"
                    onClick={() => refresh(apiKey, { append: true, offset: callsOffset })}
                  >
                    加载更多
                  </button>
                )}
              </>
            )}
          </>
        )}

        {nav === "compliance" && (
          <ComplianceTab
            apiBase={apiBase}
            apiKey={apiKey}
            onOpenCall={openDetail}
            onChainUpdated={() => refresh(apiKey)}
          />
        )}

        {nav === "behavior" && (
          <BehaviorTab
            apiBase={apiBase}
            apiKey={apiKey}
            onOpenCall={openDetail}
            onChainUpdated={() => refresh(apiKey)}
          />
        )}

        {nav === "attestation" && (
          <div className="attest-page">
            <AttestationProof
              {...attest}
              onAnchor={anchorChain}
              anchoring={anchoring}
            />
          </div>
        )}

        {nav === "settings" && showSettings && (
          <SettingsPanel
            apiBase={apiBase}
            apiKey={apiKey}
            setApiKey={setApiKey}
            authorization={authorization}
            setAuthorization={setAuthorization}
            proxyUrl={proxyUrl}
            onSaveKey={onSaveKey}
            onCopyProxy={copyProxy}
            copied={copied}
            busy={busy}
            role={role}
          />
        )}

        {nav === "keys" && showSettings && (
          <KeysPanel
            apiBase={apiBase}
            apiKey={apiKey}
            canAdmin={canAdmin}
            onActivateKey={(k) => {
              setApiKey(k);
              localStorage.setItem(STORAGE_KEY, k);
            }}
          />
        )}

        <ExportDialog
          apiBase={apiBase}
          apiKey={apiKey}
          open={exportOpen}
          onClose={() => setExportOpen(false)}
        />

        <CallDetail
          call={detail}
          proof={proof}
          verifying={verifying}
          exporting={exportingPack}
          onVerify={verifyDetail}
          onExport={exportVerifyPack}
          onClose={() => {
            setDetail(null);
            setSelectedId(null);
          }}
        />
      </main>

      <style jsx>{`
        .layout {
          display: flex;
          min-height: 100vh;
        }
        .main {
          flex: 1;
          padding: 18px 22px 40px;
          max-width: 1200px;
        }
        .top {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          align-items: flex-end;
          margin-bottom: 14px;
        }
        .brand {
          font-size: 20px;
          font-weight: 650;
        }
        .sub {
          color: #7f8fa3;
          font-size: 12px;
          margin-top: 4px;
          font-family: var(--mono);
        }
        .controls {
          display: flex;
          gap: 8px;
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
        .err {
          margin-bottom: 12px;
          color: #ff6b6b;
          font-family: var(--mono);
          font-size: 12px;
        }
        .sec {
          margin: 0 0 10px;
          font-size: 12px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .more {
          margin-top: 12px;
          width: 100%;
        }
        .attest-page {
          max-width: 420px;
        }
        .settings {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 16px;
          display: grid;
          gap: 12px;
          max-width: 520px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        input {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 10px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .row {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        .hint {
          font-size: 11px;
          color: #7f8fa3;
          line-height: 1.5;
        }
        .mono {
          font-family: var(--mono);
        }
        @media (max-width: 900px) {
          .layout {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
}
