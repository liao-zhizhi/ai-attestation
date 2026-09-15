"use client";

import { useEffect, useMemo, useState } from "react";
import { parseApiError } from "@/lib/api";

/** 浏览器本地 SHA-256（UTF-8 文本或文件字节），不把原文发给服务器。 */
export async function sha256Hex(data: BufferSource): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const KINDS: { id: string; label: string }[] = [
  { id: "draft", label: "草稿" },
  { id: "derivation", label: "推导" },
  { id: "prompt", label: "提示词" },
  { id: "note", label: "笔记" },
  { id: "other", label: "其他" },
];

type Source = "file" | "paste" | "hash";

type Props = {
  apiBase: string;
  apiKey: string;
  canWrite: boolean;
  onRegistered: () => void;
};

/**
 * 登记入口：本地文件 / 粘贴文字 / 我已有哈希 → 显示 64 位哈希 → 「写入证据链」。
 */
export function ArtifactRegister({ apiBase, apiKey, canWrite, onRegistered }: Props) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState<Source>("file");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("draft");
  const [authors, setAuthors] = useState("");
  const [description, setDescription] = useState("");
  const [paste, setPaste] = useState("");
  const [hashInput, setHashInput] = useState("");
  const [digest, setDigest] = useState("");
  const [byteLength, setByteLength] = useState<number | null>(null);
  const [filenameHint, setFilenameHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [hashing, setHashing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const hashOk = useMemo(() => /^[0-9a-f]{64}$/i.test(digest.trim()), [digest]);

  useEffect(() => {
    if (source !== "paste") return;
    const text = paste;
    if (!text) {
      setDigest("");
      setByteLength(null);
      return;
    }
    let cancelled = false;
    setHashing(true);
    (async () => {
      try {
        const bytes = new TextEncoder().encode(text);
        const hex = await sha256Hex(bytes);
        if (!cancelled) {
          setDigest(hex);
          setByteLength(bytes.byteLength);
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "本地哈希失败");
          setDigest("");
        }
      } finally {
        if (!cancelled) setHashing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source, paste]);

  async function onPickFile(file: File | null) {
    setErr(null);
    setMsg(null);
    if (!file) {
      setDigest("");
      setByteLength(null);
      setFilenameHint("");
      return;
    }
    setHashing(true);
    try {
      const buf = await file.arrayBuffer();
      const hex = await sha256Hex(buf);
      setDigest(hex);
      setByteLength(buf.byteLength);
      setFilenameHint(file.name);
      if (!title.trim()) setTitle(file.name.replace(/\.[^.]+$/, "") || file.name);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "本地哈希失败（需 HTTPS 或本机安全上下文）");
      setDigest("");
    } finally {
      setHashing(false);
    }
  }

  function onHashTyped(v: string) {
    const h = v.trim().toLowerCase();
    setHashInput(v);
    setDigest(/^[0-9a-f]{64}$/.test(h) ? h : "");
    setByteLength(null);
    setFilenameHint("");
  }

  async function submit() {
    if (!canWrite) {
      setErr("需要 read_write 或 admin 才能写入证据链");
      return;
    }
    const h = digest.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(h)) {
      setErr("请先得到 64 位哈希，再点「写入证据链」");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {
        api_key: apiKey,
        title: title.trim() || "未命名工件",
        kind,
        artifact_hash: h,
        client_hashed: true,
      };
      if (byteLength != null) body.byte_length = byteLength;
      if (filenameHint.trim()) body.filename_hint = filenameHint.trim();
      if (authors.trim()) body.authors_label = authors.trim();
      if (description.trim()) body.description = description.trim();
      const r = await fetch(`${apiBase}/v1/research/artifacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await parseApiError(r, "登记失败"));
      const d = await r.json();
      const notice = d.duplicate_notice ? ` ${d.duplicate_notice}` : "";
      setMsg(`已写入证据链。指纹 ${h.slice(0, 12)}…${notice}`);
      setPaste("");
      setHashInput("");
      onRegistered();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "登记失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="reg">
      <button
        type="button"
        className="accent"
        onClick={() => setOpen(true)}
        disabled={!apiKey}
      >
        登记一份草稿或提示词
      </button>
      {open && (
        <div className="form">
          <p className="hint">原文只在本浏览器里算指纹，不会上传。标题可用代号。</p>
          <div className="modes">
            <button
              type="button"
              className={source === "file" ? "on" : ""}
              onClick={() => {
                setSource("file");
                setDigest("");
                setByteLength(null);
              }}
            >
              本地文件
            </button>
            <button
              type="button"
              className={source === "paste" ? "on" : ""}
              onClick={() => {
                setSource("paste");
                setDigest("");
                setByteLength(null);
              }}
            >
              粘贴文字
            </button>
            <button
              type="button"
              className={source === "hash" ? "on" : ""}
              onClick={() => {
                setSource("hash");
                onHashTyped(hashInput);
              }}
            >
              我已有哈希
            </button>
          </div>

          {source === "file" && (
            <label>
              选择本地文件
              <input
                type="file"
                onChange={(e) => onPickFile(e.target.files?.[0] || null)}
              />
            </label>
          )}
          {source === "paste" && (
            <label>
              粘贴文字（仅本机哈希，原文不会上传）
              <textarea
                rows={6}
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                placeholder="把草稿或提示词粘贴在这里"
              />
            </label>
          )}
          {source === "hash" && (
            <label>
              我已有哈希（64 位 SHA-256 十六进制）
              <input
                value={hashInput}
                onChange={(e) => onHashTyped(e.target.value)}
                placeholder="64 位十六进制"
                spellCheck={false}
              />
            </label>
          )}

          <label>
            标题
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="可用代号，例如：草稿-A"
              maxLength={200}
            />
          </label>
          <label>
            类型
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            作者显示名（选填）
            <input
              value={authors}
              onChange={(e) => setAuthors(e.target.value)}
              placeholder="不填则仅 Key 租户可见时间线"
              maxLength={120}
            />
          </label>
          <label>
            备注（选填，不要贴原文）
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
            />
          </label>

          <div className="hashbox">
            <div className="hl">64 位哈希（将写入证据链，不是原文）</div>
            <code className="mono">
              {hashing ? "正在本机计算…" : digest || "选择文件、粘贴文字或填入哈希后显示"}
            </code>
          </div>

          <button
            type="button"
            className="accent"
            onClick={submit}
            disabled={busy || hashing || !hashOk || !canWrite}
            title={!canWrite ? "需要 read_write 或 admin" : undefined}
          >
            {busy ? "写入中…" : "写入证据链"}
          </button>
          {msg && <p className="ok">{msg}</p>}
          {err && <p className="bad">{err}</p>}
        </div>
      )}
      <style jsx>{`
        .reg {
          margin-bottom: 16px;
        }
        .form {
          margin-top: 12px;
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 14px;
          display: grid;
          gap: 10px;
          max-width: 640px;
        }
        .modes {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
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
        button.on,
        button.accent {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 11px;
          color: #7f8fa3;
        }
        input,
        textarea,
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 10px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .hint {
          margin: 0;
          color: #9eb2c7;
          font-size: 12px;
        }
        .hashbox {
          background: #0b0f14;
          border: 1px solid #243044;
          border-radius: 4px;
          padding: 8px 10px;
        }
        .hl {
          font-size: 11px;
          color: #7f8fa3;
          margin-bottom: 4px;
        }
        .mono {
          word-break: break-all;
          color: #3dd68c;
          font-size: 12px;
        }
        .ok {
          color: #3dd68c;
          font-size: 12px;
          margin: 0;
        }
        .bad {
          color: #ff6b6b;
          font-size: 12px;
          margin: 0;
        }
      `}</style>
    </section>
  );
}
