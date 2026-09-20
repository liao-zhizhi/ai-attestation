"use client";

import { useCallback, useEffect, useState } from "react";
import { parseApiError, withApiKey } from "@/lib/api";
import { ConsentHistory } from "./ConsentHistory";

type Allow = "unknown" | "yes" | "no";
type InheritOrAllow = "inherit" | Allow;

type ConsentRow = {
  vendor?: string;
  allow_training?: Allow;
  allow_label?: string;
  timestamp?: string;
  policy_url?: string | null;
  policy_hash?: string | null;
  chain_ok?: boolean;
};

type HistItem = {
  id?: string;
  timestamp?: string;
  vendor?: string;
  allow_training?: string;
  allow_label?: string;
  chain_hash?: string;
  chain_ok?: boolean;
  policy_hash?: string | null;
};

const ALLOW_OPTS: { id: Allow; label: string }[] = [
  { id: "unknown", label: "未知" },
  { id: "yes", label: "允许" },
  { id: "no", label: "不允许" },
];

const VENDORS: { id: string; label: string }[] = [
  { id: "openai", label: "OpenAI" },
  { id: "deepseek", label: "DeepSeek" },
  { id: "anthropic", label: "Anthropic" },
  { id: "zhipu", label: "智谱" },
];

type Props = {
  apiBase: string;
  apiKey: string;
  canWrite: boolean;
  onChainUpdated?: () => void;
};

function tone(allow: string): string {
  if (allow === "yes") return "ok";
  if (allow === "no") return "bad";
  return "muted";
}

/**
 * 训练数据同意：全局默认 + 按厂商覆盖，每次保存写入证据链。
 */
export function ConsentPanel({ apiBase, apiKey, canWrite, onChainUpdated }: Props) {
  const [globalAllow, setGlobalAllow] = useState<Allow>("unknown");
  const [overrides, setOverrides] = useState<Record<string, InheritOrAllow>>({});
  const [loadedGlobal, setLoadedGlobal] = useState<Allow>("unknown");
  const [loadedOverrides, setLoadedOverrides] = useState<Record<string, InheritOrAllow>>({});
  const [history, setHistory] = useState<HistItem[]>([]);
  const [vendorsOpen, setVendorsOpen] = useState(false);
  const [histOpen, setHistOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(withApiKey(`${apiBase}/v1/research/consent`, apiKey));
    if (!r.ok) {
      setErr(await parseApiError(r, "无法加载训练同意"));
      return;
    }
    const d = await r.json();
    const g = (d.global as ConsentRow | null)?.allow_training || "unknown";
    setGlobalAllow(g === "yes" || g === "no" ? g : "unknown");
    const next: Record<string, InheritOrAllow> = {};
    const by = (d.by_vendor || {}) as Record<string, ConsentRow>;
    for (const v of VENDORS) {
      const row = by[v.id];
      next[v.id] =
        row?.allow_training === "yes" ||
        row?.allow_training === "no" ||
        row?.allow_training === "unknown"
          ? row.allow_training
          : "inherit";
    }
    setOverrides(next);
    setLoadedGlobal(g === "yes" || g === "no" ? g : "unknown");
    setLoadedOverrides(next);
    setErr(null);
  }, [apiBase, apiKey]);

  const loadHist = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(
      withApiKey(`${apiBase}/v1/research/consent/report`, apiKey)
    );
    if (!r.ok) return;
    const d = await r.json();
    setHistory(d.history || []);
  }, [apiBase, apiKey]);

  useEffect(() => {
    load().catch(() => undefined);
    loadHist().catch(() => undefined);
  }, [load, loadHist]);

  async function putOne(vendor: string, allow_training: Allow) {
    const r = await fetch(`${apiBase}/v1/research/consent`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        vendor,
        allow_training,
        source: "user_dashboard",
      }),
    });
    if (!r.ok) {
      if (r.status === 403) throw new Error("需要 read_write 或 admin 才能保存");
      if (r.status === 422) throw new Error("请求格式错误");
      throw new Error(await parseApiError(r, "保存失败"));
    }
  }

  async function save() {
    if (!canWrite) {
      setErr("需要 read_write 或 admin 才能保存");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      let wrote = 0;
      if (globalAllow !== loadedGlobal) {
        await putOne("*", globalAllow);
        wrote += 1;
      }
      for (const v of VENDORS) {
        const val = overrides[v.id] || "inherit";
        const prev = loadedOverrides[v.id] || "inherit";
        if (val === "inherit" || val === prev) continue;
        await putOne(v.id, val);
        wrote += 1;
      }
      setMsg(wrote ? "同意设置已写入证据链" : "没有需要保存的变更");
      await load();
      await loadHist();
      onChainUpdated?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function exportReport(format: "txt" | "json") {
    setExporting(true);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(
          `${apiBase}/v1/research/consent/report/export?format=${format}`,
          apiKey
        )
      );
      if (!r.ok) throw new Error(await parseApiError(r, "导出失败"));
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ata_consent_report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="cns">
      <h3>训练数据同意</h3>
      <p className="lead">
        记录你是否允许某厂商用你的数据训练。每次变更都会写入证据链。
      </p>
      <label>
        全局默认
        <select
          value={globalAllow}
          onChange={(e) => setGlobalAllow(e.target.value as Allow)}
          disabled={!canWrite}
          className={tone(globalAllow)}
        >
          {ALLOW_OPTS.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <p className={`status ${tone(globalAllow)}`}>
        当前全局：{ALLOW_OPTS.find((o) => o.id === globalAllow)?.label}
      </p>
      <button type="button" className="link" onClick={() => setVendorsOpen((v) => !v)}>
        {vendorsOpen ? "收起按厂商覆盖" : "按厂商覆盖（可选）"}
      </button>
      {vendorsOpen && (
        <div className="vendors">
          {VENDORS.map((v) => {
            const val = overrides[v.id] || "inherit";
            const shown = val === "inherit" ? globalAllow : val;
            return (
              <label key={v.id}>
                {v.label}
                <select
                  value={val}
                  disabled={!canWrite}
                  className={tone(shown)}
                  onChange={(e) =>
                    setOverrides((o) => ({
                      ...o,
                      [v.id]: e.target.value as InheritOrAllow,
                    }))
                  }
                >
                  <option value="inherit">跟随全局</option>
                  {ALLOW_OPTS.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      )}
      <div className="row">
        <button type="button" onClick={save} disabled={!canWrite || busy}>
          {busy ? "保存中…" : "保存"}
        </button>
        <button
          type="button"
          onClick={() => exportReport("txt")}
          disabled={exporting}
        >
          导出审计摘要
        </button>
        <button
          type="button"
          onClick={() => exportReport("json")}
          disabled={exporting}
        >
          导出 JSON
        </button>
      </div>
      {msg && <p className="ok">{msg}</p>}
      {err && <p className="err">{err}</p>}
      <button type="button" className="link" onClick={() => setHistOpen((v) => !v)}>
        {histOpen ? "收起变更历史" : "变更历史"}
      </button>
      {histOpen && <ConsentHistory items={history} />}
      <style jsx>{`
        .cns {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          margin: 0 0 16px;
          display: grid;
          gap: 10px;
        }
        h3 {
          margin: 0;
          font-size: 13px;
          color: #d7e0ea;
        }
        .lead {
          margin: 0;
          font-size: 12px;
          color: #7f8fa3;
          line-height: 1.5;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 11px;
          color: #7f8fa3;
        }
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 10px;
          font-family: var(--mono);
          font-size: 12px;
          max-width: 280px;
        }
        select.ok {
          border-color: #2a5c42;
          color: #3dd68c;
        }
        select.bad {
          border-color: #5c2a2a;
          color: #ff6b6b;
        }
        select.muted {
          color: #9eb2c7;
        }
        .status {
          font-size: 12px;
          margin: 0;
        }
        .status.ok {
          color: #3dd68c;
        }
        .status.bad {
          color: #ff6b6b;
        }
        .status.muted {
          color: #7f8fa3;
        }
        .vendors {
          display: grid;
          gap: 8px;
        }
        .row {
          display: flex;
          flex-wrap: wrap;
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
        button:disabled {
          opacity: 0.45;
        }
        button.link {
          background: transparent;
          border: none;
          color: #5b8def;
          padding: 0;
          text-align: left;
        }
        .ok {
          color: #3dd68c;
          font-size: 12px;
          margin: 0;
        }
        .err {
          color: #ff6b6b;
          font-size: 12px;
          margin: 0;
        }
      `}</style>
    </section>
  );
}
