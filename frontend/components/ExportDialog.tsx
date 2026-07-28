"use client";

import { useState } from "react";
import { parseApiError } from "@/lib/api";

type Props = {
  apiBase: string;
  apiKey: string;
  open: boolean;
  onClose: () => void;
};

export function ExportDialog({ apiBase, apiKey, open, onClose }: Props) {
  const [format, setFormat] = useState<"csv" | "json">("csv");
  const [timeRange, setTimeRange] = useState("7d");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [vendor, setVendor] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!open) return null;

  async function download() {
    setBusy(true);
    setErr(null);
    try {
      const q = new URLSearchParams({
        api_key: apiKey,
        format,
        time_range: timeRange,
      });
      if (vendor) q.set("vendor", vendor);
      if (status) q.set("status", status);
      if (timeRange === "custom") {
        if (customFrom) q.set("custom_from", customFrom);
        if (customTo) q.set("custom_to", customTo);
      }
      const r = await fetch(`${apiBase}/v1/dashboard/calls/export?${q.toString()}`);
      if (!r.ok) throw new Error(await parseApiError(r, "导出失败"));
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "csv" ? "ata_calls_export.csv" : "ata_calls_export.json";
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mask" role="dialog">
      <div className="box">
        <header>
          <h2>导出调用记录</h2>
          <button type="button" onClick={onClose}>
            ×
          </button>
        </header>
        <label>
          格式
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as "csv" | "json")}
          >
            <option value="csv">CSV（Excel 友好）</option>
            <option value="json">JSON</option>
          </select>
        </label>
        <label>
          时间范围
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
            <option value="today">今天</option>
            <option value="7d">最近 7 天</option>
            <option value="30d">最近 30 天</option>
            <option value="all">全部</option>
            <option value="custom">自定义</option>
          </select>
        </label>
        {timeRange === "custom" && (
          <div className="row">
            <label>
              从
              <input
                type="datetime-local"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
              />
            </label>
            <label>
              至
              <input
                type="datetime-local"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
              />
            </label>
          </div>
        )}
        <label>
          厂商
          <select value={vendor} onChange={(e) => setVendor(e.target.value)}>
            <option value="">全部</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="azure">Azure</option>
            <option value="deepseek">DeepSeek</option>
            <option value="alibaba">阿里通义</option>
            <option value="baidu">百度文心</option>
            <option value="tencent">腾讯混元</option>
            <option value="bytedance">字节豆包</option>
            <option value="zhipu">智谱</option>
            <option value="moonshot">月之暗面</option>
            <option value="cohere">Cohere</option>
          </select>
        </label>
        <label>
          状态
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">全部</option>
            <option value="success">成功</option>
            <option value="failure">失败</option>
          </select>
        </label>
        {err && <p className="err">{err}</p>}
        {busy && <p className="load">正在准备导出…</p>}
        <div className="actions">
          <button type="button" onClick={onClose}>
            取消
          </button>
          <button type="button" className="go" onClick={download} disabled={busy}>
            下载
          </button>
        </div>
      </div>
      <style jsx>{`
        .mask {
          position: fixed;
          inset: 0;
          background: #0b0f14cc;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 40;
        }
        .box {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 8px;
          padding: 16px 18px;
          width: min(420px, 92vw);
          display: grid;
          gap: 12px;
        }
        header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        h2 {
          margin: 0;
          font-size: 15px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
        }
        select,
        input {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 7px 9px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
        }
        .actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 12px;
          font-family: var(--mono);
          font-size: 12px;
        }
        button.go {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        .err {
          color: #ff6b6b;
          font-size: 12px;
        }
        .load {
          color: #f0b429;
          font-family: var(--mono);
          font-size: 12px;
        }
      `}</style>
    </div>
  );
}
