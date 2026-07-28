"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { resolveApiBase } from "@/lib/apiBase";


type Verification = {
  ok?: boolean;
  report_hash?: { ok?: boolean; message?: string };
  chain?: { ok?: boolean; message?: string };
  timestamp?: { ok?: boolean; message?: string };
  blockchain_anchor?: { present?: boolean; ok?: boolean; message?: string };
  tee?: { present?: boolean; message?: string };
  disclaimer?: string;
};

type Pack = {
  report?: {
    id?: string;
    standard_name?: string;
    standard?: string;
    timestamp?: string;
    summary?: Record<string, number> & {
      impact_radius_score?: number;
    };
    check_results?: Record<
      string,
      {
        status?: string;
        requirement?: string;
        detail?: string;
        check_id?: string;
        impact_factor?: string;
        impact_factor_zh?: string;
        evidence?: Array<{ call_id?: string; chain_hash?: string; timestamp?: string }>;
      }
    >;
    report_hash?: string;
    chain_hash?: string;
    prev_hash?: string;
  };
  timestamp_proof?: Record<string, unknown>;
  blockchain_anchor?: Record<string, unknown>;
  disclaimer?: string;
};

type PathNode = {
  id?: string;
  label?: string;
  timestamp?: string;
  event_type?: string;
  hash?: string;
  ok?: boolean;
  note?: string;
  highlight?: boolean;
};

export default function VerifyClient() {
  const params = useParams();
  const search = useSearchParams();
  const reportHash = String(params?.report_hash || "");
  const token = search.get("p") || "";

  const [apiBase, setApiBase] = useState("http://127.0.0.1:8004");
  const [pack, setPack] = useState<Pack | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedNode, setSelectedNode] = useState<PathNode | null>(null);
  const [notary, setNotary] = useState<Record<string, unknown> | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [impactApiKey, setImpactApiKey] = useState("");
  const [olderCheckId, setOlderCheckId] = useState("");
  const [newerCheckId, setNewerCheckId] = useState("");
  const [impactResult, setImpactResult] = useState<Record<string, unknown> | null>(null);
  const [impactBusy, setImpactBusy] = useState(false);

  useEffect(() => {
    setApiBase(resolveApiBase());
  }, []);

  const load = useCallback(async () => {
    if (!token) {
      setErr("缺少验证包参数 p=…（自包含 token）");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${apiBase}/v1/public/verify?p=${encodeURIComponent(token)}`);
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setPack(d.pack || null);
      const claimed = d.pack?.report?.report_hash;
      if (reportHash && claimed && claimed !== reportHash) {
        setErr("URL 中的 report_hash 与验证包不一致");
        setVerification({
          ...(d.verification || {}),
          ok: false,
          hash_mismatch: true,
        });
      } else {
        setVerification(d.verification || null);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "verify failed");
    } finally {
      setBusy(false);
    }
  }, [token, reportHash, apiBase]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  async function reverify() {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch(`${apiBase}/v1/public/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!r.ok) throw new Error("re-verify failed");
      const d = await r.json();
      setVerification(d.verification || null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "re-verify failed");
    } finally {
      setBusy(false);
    }
  }

  async function requestNotary() {
    const rh = pack?.report?.report_hash || reportHash;
    if (!rh) return;
    const r = await fetch(`${apiBase}/v1/public/notarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_hash: rh, method: "opentimestamps" }),
    });
    if (!r.ok) {
      setErr(await r.text());
      return;
    }
    setNotary(await r.json());
  }

  async function runImpactAnalysis() {
    if (!impactApiKey || impactApiKey.length < 8) {
      setErr("变更影响分析需要有效 api_key");
      return;
    }
    const older = olderCheckId.trim();
    const newer = newerCheckId.trim() || pack?.report?.id || "";
    if (!older || !newer) {
      setErr("请填写 older_check_id 与 newer_check_id（可默认当前报告 id）");
      return;
    }
    setImpactBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/compliance/impact-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: impactApiKey,
          older_check_id: older,
          newer_check_id: newer,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setImpactResult(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "impact analysis failed");
    } finally {
      setImpactBusy(false);
    }
  }

  const report = pack?.report;
  const results = useMemo(
    () => Object.values(report?.check_results || {}),
    [report]
  );

  const pathNodes: PathNode[] = useMemo(() => {
    const nodes: PathNode[] = [];
    if (report?.prev_hash) {
      nodes.push({
        id: "genesis-link",
        label: "链前驱",
        event_type: "prev",
        hash: String(report.prev_hash),
        ok: true,
      });
    }
    const evSeen = new Set<string>();
    for (const r of results) {
      for (const e of r.evidence || []) {
        const cid = e.call_id || "";
        if (!cid || evSeen.has(cid)) continue;
        evSeen.add(cid);
        nodes.push({
          id: cid,
          label: "API 调用",
          timestamp: e.timestamp,
          event_type: "call",
          hash: e.chain_hash,
          ok: true,
        });
      }
    }
    if (report?.chain_hash) {
      const chainOk = verification?.chain?.ok !== false;
      nodes.push({
        id: report.id || "compliance",
        label: "合规报告",
        timestamp: report.timestamp,
        event_type: "compliance",
        hash: report.chain_hash,
        ok: chainOk,
        note: chainOk ? undefined : "完整性验证失败",
        highlight: true,
      });
    }
    return nodes;
  }, [report, results, verification]);

  const badgeStatus = useMemo(() => {
    const s = report?.summary;
    if (!s) return "unknown";
    if ((s.n_fail || 0) > 0) return "fail";
    if ((s.n_manual || 0) > 0 && (s.n_pass || 0) === 0) return "manual";
    if ((s.n_pass || 0) > 0) return "pass";
    return "unknown";
  }, [report]);

  const badgeUrl = `${apiBase}/v1/public/badge/${encodeURIComponent(
    report?.report_hash || reportHash || "unknown"
  )}.svg?status=${encodeURIComponent(badgeStatus)}`;

  function exportPathSvg() {
    const el = svgRef.current;
    if (!el) return;
    const blob = new Blob([el.outerHTML], { type: "image/svg+xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `verify_path_${(report?.report_hash || "pack").slice(0, 12)}.svg`;
    a.click();
  }

  async function exportPathPng() {
    const el = svgRef.current;
    if (!el) return;
    const xml = new XMLSerializer().serializeToString(el);
    const img = new Image();
    const url = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml" }));
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("png export failed"));
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = el.width.baseVal.value || 800;
    canvas.height = el.height.baseVal.value || 120;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#0b0f14";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `verify_path_${(report?.report_hash || "pack").slice(0, 12)}.png`;
    a.click();
  }

  return (
    <main className="shell">
      <header>
        <div className="brand">独立验证</div>
        <div className="sub">ai-attestation · 无需登录 · 自包含验证包</div>
      </header>

      {err && <div className="err">{err}</div>}

      <section className="card">
        <h2>验证状态</h2>
        {busy && !verification ? (
          <p className="mono">加载中…</p>
        ) : !verification ? (
          <p className="mono">{err ? "验证未完成" : "等待验证包…"}</p>
        ) : (
          <>
            <div className={`badge ${verification.ok ? "ok" : "bad"}`}>
              {verification.ok ? "✓ 完整性校验通过" : "✗ 校验未通过或不完整"}
            </div>
            <dl>
              <div>
                <dt>报告哈希</dt>
                <dd>{verification?.report_hash?.message || "—"}</dd>
              </div>
              <div>
                <dt>哈希链</dt>
                <dd>{verification?.chain?.message || "—"}</dd>
              </div>
              <div>
                <dt>时间戳</dt>
                <dd>{verification?.timestamp?.message || "—"}</dd>
              </div>
              <div>
                <dt>区块链锚定</dt>
                <dd>{verification?.blockchain_anchor?.message || "—"}</dd>
              </div>
              <div>
                <dt>TEE</dt>
                <dd>{verification?.tee?.message || "—"}</dd>
              </div>
            </dl>
            <div className="actions">
              <button type="button" onClick={reverify} disabled={busy || !token}>
                {busy ? "验证中…" : "验证完整性"}
              </button>
              {token && (
                <a
                  className="btn"
                  href={`${apiBase}/v1/public/offline-pack?p=${encodeURIComponent(token)}`}
                >
                  下载离线验证包
                </a>
              )}
            </div>
          </>
        )}
      </section>

      {pathNodes.length > 0 && (
        <section className="card">
          <h2>验证路径</h2>
          <p className="hint">时间线节点通过哈希链连接；断裂节点标红。</p>
          <svg
            ref={svgRef}
            width={Math.max(640, pathNodes.length * 140)}
            height={120}
            className="pathsvg"
          >
            {pathNodes.map((n, i) => {
              const x = 40 + i * 140;
              const y = 50;
              if (i > 0) {
                return (
                  <g key={`g-${i}`}>
                    <line
                      x1={x - 140 + 18}
                      y1={y}
                      x2={x - 18}
                      y2={y}
                      stroke={n.ok === false ? "#ff6b6b" : "#2a5c42"}
                      strokeWidth={2}
                    />
                  </g>
                );
              }
              return null;
            })}
            {pathNodes.map((n, i) => {
              const x = 40 + i * 140;
              const y = 50;
              const fill = n.ok === false ? "#ff6b6b" : n.highlight ? "#3dd68c" : "#3d7ea6";
              return (
                <g
                  key={n.id || i}
                  style={{ cursor: "pointer" }}
                  onClick={() => setSelectedNode(n)}
                >
                  <circle cx={x} cy={y} r={16} fill={fill} />
                  <text x={x} y={y + 4} textAnchor="middle" fontSize={9} fill="#0b0f14">
                    {i + 1}
                  </text>
                  <text x={x} y={y + 36} textAnchor="middle" fontSize={10} fill="#9eb2c7">
                    {n.label || n.event_type}
                  </text>
                  {n.note && (
                    <text x={x} y={y + 50} textAnchor="middle" fontSize={9} fill="#ff6b6b">
                      {n.note}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
          <div className="actions">
            <button type="button" onClick={exportPathSvg}>
              导出 SVG
            </button>
            <button type="button" onClick={exportPathPng}>
              导出 PNG
            </button>
          </div>
          {selectedNode && (
            <pre className="mono">{JSON.stringify(selectedNode, null, 2)}</pre>
          )}
        </section>
      )}

      {report && (
        <section className="card">
          <h2>{report.standard_name || report.standard}</h2>
          <p className="mono meta">
            {report.id} · {report.timestamp}
            <br />
            report_hash: {report.report_hash}
            <br />
            chain_hash: {report.chain_hash}
          </p>
          <div className="stats mono">
            pass {report.summary?.n_pass ?? 0} · fail {report.summary?.n_fail ?? 0} ·
            manual {report.summary?.n_manual ?? 0}
            {report.summary?.impact_radius_score != null &&
              ` · 影响半径 ${report.summary.impact_radius_score}`}
          </div>
          <ul>
            {results.map((r, i) => (
              <li key={i} className={r.status || ""}>
                <span className="st">{r.status}</span>
                {r.impact_factor_zh && (
                  <span className={`impact ${r.impact_factor || "general"}`}>
                    {r.impact_factor_zh}
                  </span>
                )}
                <p>{r.requirement}</p>
                <p className="detail">{r.detail}</p>
                {!!r.evidence?.length && (
                  <div className="ev mono">
                    {r.evidence.slice(0, 3).map((e, j) => (
                      <span key={j}>
                        {e.call_id}:{String(e.chain_hash || "").slice(0, 12)}…
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2>变更影响分析</h2>
        <p className="hint">
          对比两次合规运行的检查项状态翻转与影响范围。若验证包已含 impact_factor，上方列表会直接显示；也可输入 api_key 与两次 check_id 调用分析接口。
        </p>
        <div className="impact-form">
          <label>
            api_key
            <input
              value={impactApiKey}
              onChange={(e) => setImpactApiKey(e.target.value)}
              placeholder="ata_…"
              autoComplete="off"
            />
          </label>
          <label>
            older_check_id
            <input
              value={olderCheckId}
              onChange={(e) => setOlderCheckId(e.target.value)}
              placeholder="cmp_…"
            />
          </label>
          <label>
            newer_check_id
            <input
              value={newerCheckId}
              onChange={(e) => setNewerCheckId(e.target.value)}
              placeholder={report?.id || "当前报告 id（可留空）"}
            />
          </label>
          <button type="button" onClick={runImpactAnalysis} disabled={impactBusy}>
            {impactBusy ? "分析中…" : "分析影响"}
          </button>
        </div>
        {impactResult && (
          <div className="impact-out">
            <p className="mono">
              影响半径: {String(impactResult.impact_radius_score ?? "—")} · 受影响{" "}
              {String(impactResult.n_affected ?? 0)} 项
            </p>
            {impactResult.invalidated_reports_hint != null && (
              <p className="hint">{String(impactResult.invalidated_reports_hint)}</p>
            )}
            <pre className="mono">{JSON.stringify(impactResult.affected_checks || [], null, 2)}</pre>
          </div>
        )}
      </section>

      <section className="card">
        <h2>第三方时间戳存证</h2>
        <p className="hint">
          将 report_hash 提交到 OpenTimestamps / 公共链，证明「此报告在某日之前已存在」。
        </p>
        <button type="button" onClick={requestNotary} disabled={!report?.report_hash}>
          生成时间戳请求（OpenTimestamps）
        </button>
        {notary && <pre className="mono">{JSON.stringify(notary, null, 2)}</pre>}
      </section>

      <section className="card">
        <h2>可嵌入徽章</h2>
        <p className="hint">嵌入网站 / README / 邮件签名，点击指向本验证页。</p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={badgeUrl} alt="compliance badge" height={20} />
        <pre className="mono">{`[![ai-attestation](${badgeUrl})](${typeof window !== "undefined" ? `${window.location.origin}/verify/${reportHash || report?.report_hash || ""}` : ""})`}</pre>
      </section>

      {(pack?.timestamp_proof || pack?.blockchain_anchor) && (
        <section className="card">
          <h2>外部证明</h2>
          {pack.timestamp_proof && (
            <pre className="mono">{JSON.stringify(pack.timestamp_proof, null, 2)}</pre>
          )}
          {pack.blockchain_anchor && (
            <pre className="mono">{JSON.stringify(pack.blockchain_anchor, null, 2)}</pre>
          )}
        </section>
      )}

      <p className="disc">
        {verification?.disclaimer ||
          pack?.disclaimer ||
          "技术验证工具，不构成法律意见或合规背书。我们提供检查清单与验证方法，不宣称定义 AI 审计标准。"}
      </p>

      <style jsx>{`
        .shell {
          max-width: 900px;
          margin: 0 auto;
          padding: 24px 20px 48px;
          color: #d7e0ea;
          min-height: 100vh;
        }
        .brand {
          font-size: 22px;
          font-weight: 650;
        }
        .sub {
          color: #7f8fa3;
          font-size: 12px;
          margin-top: 4px;
          font-family: var(--mono), ui-monospace, monospace;
        }
        .card {
          margin-top: 16px;
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 16px;
        }
        h2 {
          margin: 0 0 12px;
          font-size: 14px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .hint {
          margin: 0 0 10px;
          color: #7f8fa3;
          font-size: 12px;
          line-height: 1.45;
        }
        .badge {
          display: inline-block;
          padding: 6px 10px;
          border-radius: 4px;
          font-family: var(--mono), ui-monospace, monospace;
          font-size: 13px;
          margin-bottom: 12px;
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
        dl {
          display: grid;
          gap: 10px;
          margin: 0 0 14px;
        }
        dt {
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        dd {
          margin: 3px 0 0;
          font-family: var(--mono), ui-monospace, monospace;
          font-size: 12px;
        }
        .actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
        }
        button,
        .btn {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 8px 14px;
          font-family: var(--mono), ui-monospace, monospace;
          font-size: 12px;
          cursor: pointer;
          text-decoration: none;
          display: inline-block;
        }
        .pathsvg {
          width: 100%;
          max-width: 100%;
          overflow: auto;
          background: #0e141c;
          border-radius: 4px;
          border: 1px solid #1e2a38;
        }
        .mono {
          font-family: var(--mono), ui-monospace, monospace;
        }
        .meta {
          font-size: 11px;
          color: #9eb2c7;
          line-height: 1.5;
          word-break: break-all;
        }
        .stats {
          margin: 10px 0;
          color: #9eb2c7;
          font-size: 12px;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 8px;
        }
        li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 10px;
        }
        li.fail {
          border-color: #6b2a2a;
        }
        li.pass {
          border-color: #1f5a3c;
        }
        .st {
          font-size: 10px;
          text-transform: uppercase;
          font-family: var(--mono), ui-monospace, monospace;
          color: #e6c35c;
        }
        .impact {
          margin-left: 8px;
          font-size: 10px;
          padding: 1px 6px;
          border-radius: 3px;
          border: 1px solid #2a3b52;
          color: #9eb2c7;
          font-family: var(--mono), ui-monospace, monospace;
        }
        .impact.core {
          border-color: #6b2a2a;
          color: #ff8a8a;
        }
        .impact.critical {
          border-color: #5a4a1f;
          color: #e6c35c;
        }
        .impact-form {
          display: grid;
          gap: 8px;
          margin-bottom: 10px;
        }
        .impact-form label {
          display: grid;
          gap: 4px;
          font-size: 11px;
          color: #7f8fa3;
        }
        .impact-form input {
          background: #0e141c;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 6px 8px;
          font-family: var(--mono), ui-monospace, monospace;
          font-size: 12px;
        }
        .impact-out {
          margin-top: 8px;
        }
        p {
          margin: 6px 0 0;
          font-size: 13px;
          line-height: 1.45;
        }
        .detail {
          color: #9eb2c7;
          font-size: 12px;
          font-family: var(--mono), ui-monospace, monospace;
        }
        .ev {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 8px;
          font-size: 10px;
          color: #7f8fa3;
        }
        pre {
          margin: 10px 0 0;
          font-size: 11px;
          overflow: auto;
          max-height: 220px;
          background: #0e141c;
          padding: 10px;
          border-radius: 4px;
        }
        .err {
          margin-top: 12px;
          color: #ff6b6b;
          font-family: var(--mono), ui-monospace, monospace;
          font-size: 12px;
        }
        .disc {
          margin-top: 20px;
          color: #7f8fa3;
          font-size: 12px;
          line-height: 1.5;
        }
      `}</style>
    </main>
  );
}
