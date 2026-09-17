"use client";

import { useCallback, useEffect, useState } from "react";
import { parseApiError, withApiKey } from "@/lib/api";

type Kind = "call" | "artifact";

type Props = {
  open: boolean;
  kind: Kind;
  targetId: string;
  apiBase: string;
  apiKey: string;
  canWrite: boolean;
  onClose: () => void;
};

/**
 * 生成 / 复制 / 撤销公开验证链接。甲方打开即可看链是否完整，无需登录。
 */
export function ShareLinkDialog({
  open,
  kind,
  targetId,
  apiBase,
  apiKey,
  canWrite,
  onClose,
}: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const displayUrl = (tok: string) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    return `${origin}/verify/${kind}/${tok}`;
  };

  const load = useCallback(async () => {
    if (!open || !apiKey || !targetId) return;
    setErr(null);
    const r = await fetch(
      withApiKey(
        `${apiBase}/v1/public/share/${kind}/${encodeURIComponent(targetId)}`,
        apiKey
      )
    );
    if (!r.ok) {
      setErr(await parseApiError(r, "无法查询公开链接"));
      return;
    }
    const d = await r.json();
    if (d.token) {
      setToken(d.token);
      setUrl(displayUrl(d.token));
    } else {
      setToken(null);
      setUrl(null);
    }
  }, [open, apiBase, apiKey, kind, targetId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  if (!open) return null;

  async function create() {
    if (!canWrite) {
      setErr("当前角色是只读，无法生成公开链接");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(
          `${apiBase}/v1/public/share/${kind}/${encodeURIComponent(targetId)}`,
          apiKey
        ),
        { method: "POST" }
      );
      if (!r.ok) throw new Error(await parseApiError(r, "生成失败"));
      const d = await r.json();
      setToken(d.token);
      setUrl(displayUrl(d.token));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(`${apiBase}/v1/public/share/${encodeURIComponent(token)}`, apiKey),
        { method: "DELETE" }
      );
      if (!r.ok) throw new Error(await parseApiError(r, "撤销失败"));
      setToken(null);
      setUrl(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setErr("复制失败，请手动选中地址");
    }
  }

  return (
    <div
      className="backdrop"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
      role="presentation"
    >
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog">
        <header>
          <h3>公开验证链接</h3>
          <button type="button" className="x" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="lead">
          把链接发给甲方即可。对方不用登录，只能看到时间和哈希，看不到 Key 和原文。
        </p>
        {err && <p className="bad">{err}</p>}
        {url ? (
          <>
            <div className="box mono">{url}</div>
            <div className="row">
              <button type="button" className="accent" onClick={copy} disabled={busy}>
                {copied ? "已复制" : "复制"}
              </button>
              <button type="button" className="warn" onClick={revoke} disabled={busy || !canWrite}>
                {busy ? "处理中…" : "撤销链接"}
              </button>
            </div>
          </>
        ) : (
          <button type="button" className="accent" onClick={create} disabled={busy || !canWrite}>
            {busy ? "生成中…" : "生成公开链接"}
          </button>
        )}
        <style jsx>{`
          .backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.62);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            z-index: 60;
          }
          .modal {
            width: min(560px, 100%);
            background: #111821;
            border: 1px solid #1e2a38;
            border-radius: 8px;
            padding: 18px 20px;
          }
          header {
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          h3 {
            margin: 0;
            font-size: 16px;
          }
          .x {
            background: transparent;
            border: none;
            color: #9eb2c7;
            font-size: 22px;
          }
          .lead {
            color: #9eb2c7;
            font-size: 13px;
            line-height: 1.5;
          }
          .bad {
            color: #ff6b6b;
            font-size: 12px;
          }
          .box {
            background: #0e141c;
            border: 1px solid #1e2a38;
            border-radius: 4px;
            padding: 10px;
            word-break: break-all;
            font-size: 12px;
            color: #3dd68c;
          }
          .mono {
            font-family: var(--mono);
          }
          .row {
            display: flex;
            gap: 10px;
            margin-top: 12px;
            flex-wrap: wrap;
          }
          button {
            background: #152033;
            border: 1px solid #2a3b52;
            color: #d7e0ea;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 13px;
            font-family: var(--mono);
          }
          .accent {
            background: #1a3d2c;
            border-color: #2a5c42;
            color: #3dd68c;
          }
          .warn {
            color: #fb923c;
            border-color: #5c3a22;
          }
          button:disabled {
            opacity: 0.55;
          }
        `}</style>
      </div>
    </div>
  );
}
