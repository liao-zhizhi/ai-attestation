"use client";

import { useCallback, useEffect, useState } from "react";
import { BaselineCompare } from "./BaselineCompare";
import { BaselinePanel, type Baseline } from "./BaselinePanel";
import { DriftMarksList, type DriftMark } from "./DriftMarksList";

type Props = {
  apiBase: string;
  apiKey: string;
  onOpenCall?: (callId: string) => void;
  onChainUpdated?: () => void;
};

type Pane = "baseline" | "marks" | "compare";

export function BehaviorTab({ apiBase, apiKey, onOpenCall, onChainUpdated }: Props) {
  const [pane, setPane] = useState<Pane>("baseline");
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("7d");
  const [marks, setMarks] = useState<DriftMark[]>([]);
  const [markFilter, setMarkFilter] = useState("pending");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [olderId, setOlderId] = useState<string | null>(null);
  const [newerId, setNewerId] = useState<string | null>(null);
  const [diff, setDiff] = useState<Record<string, unknown> | null>(null);

  const loadBaselines = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/behavior/baselines?api_key=${encodeURIComponent(apiKey)}&limit=50`
    );
    if (!r.ok) return;
    const d = await r.json();
    const list = d.baselines || [];
    setBaselines(list);
    setSelectedId((prev) => prev || list[0]?.id || null);
  }, [apiBase, apiKey]);

  const loadMarks = useCallback(
    async (statusOverride?: string) => {
      if (!apiKey || apiKey.length < 8) return;
      const status = statusOverride ?? markFilter;
      const r = await fetch(
        `${apiBase}/v1/dashboard/behavior/drift-marks?api_key=${encodeURIComponent(apiKey)}&status=${encodeURIComponent(status)}&limit=200`
      );
      if (!r.ok) return;
      const d = await r.json();
      setMarks(d.marks || []);
    },
    [apiBase, apiKey, markFilter]
  );

  useEffect(() => {
    loadBaselines().catch(() => undefined);
  }, [loadBaselines]);

  useEffect(() => {
    loadMarks().catch(() => undefined);
  }, [loadMarks]);

  async function createBaseline() {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/behavior/baseline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, time_range: timeRange }),
      });
      if (!r.ok) throw new Error("baseline failed");
      const d = await r.json();
      setSelectedId(d.baseline_id);
      await loadBaselines();
      onChainUpdated?.();
      // auto silent drift check after new baseline
      await checkDrift(d.baseline_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  async function checkDrift(baselineId?: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/behavior/check-drift`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          baseline_id: baselineId || selectedId || null,
          window: "today",
        }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || "drift check failed");
      }
      setPane("marks");
      setMarkFilter("pending");
      await loadMarks("pending");
      onChainUpdated?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "drift failed");
    } finally {
      setBusy(false);
    }
  }

  async function review(id: string, status: "reviewed" | "ignored") {
    setBusy(true);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/behavior/drift-marks/${encodeURIComponent(id)}/review`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: apiKey, status, reviewed_by: "dashboard_user" }),
        }
      );
      if (!r.ok) throw new Error("review failed");
      await loadMarks();
      onChainUpdated?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "review failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteBaseline(id: string) {
    setBusy(true);
    try {
      await fetch(
        `${apiBase}/v1/dashboard/behavior/baselines/${encodeURIComponent(id)}?api_key=${encodeURIComponent(apiKey)}`,
        { method: "DELETE" }
      );
      await loadBaselines();
    } finally {
      setBusy(false);
    }
  }

  async function doCompare() {
    if (!olderId || !newerId) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/behavior/baselines/compare?api_key=${encodeURIComponent(apiKey)}&older_id=${encodeURIComponent(olderId)}&newer_id=${encodeURIComponent(newerId)}`
    );
    if (!r.ok) return;
    setDiff(await r.json());
  }

  return (
    <section className="bt">
      <nav>
        {(
          [
            ["baseline", "基线管理"],
            ["marks", "待审计"],
            ["compare", "基线对比"],
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
      {pane === "marks" && markFilter === "pending" && (
        <p className="signal-line">
          {marks.length === 0
            ? "没有异常信号。你的 AI 行为保持在基线范围内。"
            : `检测到 ${marks.length} 个信号偏离基线。点击逐条审查。`}
        </p>
      )}
      {err && <div className="err">{err}</div>}
      {pane === "baseline" && (
        <BaselinePanel
          baselines={baselines}
          selectedId={selectedId}
          timeRange={timeRange}
          onTimeRange={setTimeRange}
          onCreate={createBaseline}
          onSelect={setSelectedId}
          onDelete={deleteBaseline}
          onCheckDrift={() => checkDrift()}
          busy={busy}
        />
      )}
      {pane === "marks" && (
        <DriftMarksList
          marks={marks}
          filter={markFilter}
          onFilter={setMarkFilter}
          onReview={review}
          onOpenCall={onOpenCall}
          busy={busy}
        />
      )}
      {pane === "compare" && (
        <BaselineCompare
          olderId={olderId}
          newerId={newerId}
          baselineOptions={baselines.map((b) => ({
            id: b.id,
            timestamp: b.timestamp,
          }))}
          onPickOlder={setOlderId}
          onPickNewer={setNewerId}
          onCompare={doCompare}
          diff={diff as Parameters<typeof BaselineCompare>[0]["diff"]}
        />
      )}
      <style jsx>{`
        .bt {
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
        .signal-line {
          margin: 0 0 12px;
          font-size: 13px;
          line-height: 1.45;
          color: #9eb2c7;
        }
        .err {
          color: #ff6b6b;
          font-family: var(--mono);
          font-size: 12px;
          margin-bottom: 10px;
        }
      `}</style>
    </section>
  );
}
