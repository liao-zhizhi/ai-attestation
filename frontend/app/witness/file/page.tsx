"use client";

import { useEffect, useState } from "react";
import { GuideShell } from "@/components/GuideShell";
import { parseApiError, resolveApiBase, withApiKey } from "@/lib/api";
import { createStoredAccount, readStoredAccount } from "@/lib/account";
import { sha256Hex } from "@/lib/sha256";

type Saved = {
  id: string;
  title: string;
  fingerprint: string;
  timestamp: string;
  notice: string;
};

function formatWhen(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.replace("T", " ").replace("Z", "");
  return d.toLocaleString("zh-CN", { hour12: false });
}

function formatSize(n: number): string {
  if (n < 1024) return `${n} 字节`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function shortPrint(hex: string): string {
  if (hex.length < 20) return hex;
  return `${hex.slice(0, 8)}…${hex.slice(-8)}`;
}

export default function FileWitnessPage() {
  const [apiBase, setApiBase] = useState("");
  const [accountId, setAccountId] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [fingerprint, setFingerprint] = useState("");
  const [hashing, setHashing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [over, setOver] = useState(false);

  useEffect(() => {
    document.title = "给文件留指纹";
    setApiBase(resolveApiBase());
    setAccountId(readStoredAccount());
  }, []);

  async function takeFile(file: File) {
    setErr(null);
    setSaved(null);
    setHashing(true);
    setFileName(file.name);
    setFileSize(file.size);
    try {
      const buf = await file.arrayBuffer();
      const hex = await sha256Hex(buf);
      setFingerprint(hex);
      setTitle((prev) => prev.trim() || file.name.replace(/\.[^.]+$/, "") || file.name);
      setFileSize(buf.byteLength);
    } catch (e) {
      setFingerprint("");
      setErr(e instanceof Error ? e.message : "这台电脑暂时没法计算指纹，请换一个小一点的文件再试。");
    } finally {
      setHashing(false);
    }
  }

  async function accountForWrite(): Promise<string> {
    const existing = readStoredAccount();
    if (existing.length >= 8) {
      setAccountId(existing);
      return existing;
    }
    const created = await createStoredAccount(apiBase, "我的存证账号");
    setAccountId(created);
    return created;
  }

  async function save() {
    if (!fingerprint || !apiBase) return;
    setBusy(true);
    setErr(null);
    try {
      let id = await accountForWrite();
      const body = {
        api_key: id,
        title: title.trim() || fileName || "未命名文件",
        kind: "draft",
        artifact_hash: fingerprint,
        client_hashed: true,
        byte_length: fileSize,
        filename_hint: fileName || null,
      };
      let r = await fetch(`${apiBase}/v1/research/artifacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.status === 401 || r.status === 403) {
        id = await createStoredAccount(apiBase, "我的存证账号");
        setAccountId(id);
        body.api_key = id;
        r = await fetch(`${apiBase}/v1/research/artifacts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      if (!r.ok) throw new Error(await parseApiError(r, "存证没有成功"));
      const d = await r.json();
      const art = d.artifact || {};
      const when = String(art.tsa_receipt?.timestamp || art.timestamp || "");
      setSaved({
        id: String(art.id || ""),
        title: String(art.title || body.title),
        fingerprint,
        timestamp: when,
        notice: typeof d.duplicate_notice === "string" ? d.duplicate_notice : "",
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "存证没有成功";
      setErr(
        /network|fetch|failed to fetch/i.test(msg)
          ? "存证服务暂时连不上。指纹已经在你的电脑上算好，稍后再点「开始存证」。"
          : msg
      );
    } finally {
      setBusy(false);
    }
  }

  async function exportCert() {
    if (!saved?.id || !apiBase) return;
    const id = readStoredAccount();
    if (!id) {
      setErr("这台浏览器里还没有存证账号，请重新点一次「开始存证」。");
      return;
    }
    setExporting(true);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(
          `${apiBase}/v1/research/artifacts/${encodeURIComponent(saved.id)}/certificate`,
          id
        )
      );
      if (!r.ok) throw new Error(await parseApiError(r, "证书导出失败"));
      const blob = await r.blob();
      const cd = r.headers.get("Content-Disposition") || "";
      const m = /filename="?([^"]+)"?/i.exec(cd);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = m?.[1] || "存证证书.zip";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "证书导出失败");
    } finally {
      setExporting(false);
    }
  }

  return (
    <GuideShell
      title="给文件留指纹"
      lede="文件留在你的电脑上。我们只保存指纹和时间戳，不接收文件内容。请自己保管原件。"
    >
      <ol className="steps">
        <li className={fileName ? "done" : "now"}>把文件拖进来</li>
        <li className={fingerprint ? "done" : fileName ? "now" : ""}>填一个标题</li>
        <li className={saved ? "done" : fingerprint ? "now" : ""}>开始存证</li>
        <li className={saved ? "now" : ""}>导出证书</li>
      </ol>

      <div
        className={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) void takeFile(f);
        }}
      >
        <p className="drop-title">{over ? "松开即可" : "把文件拖到这里"}</p>
        <p className="muted">图片、文档、压缩包都可以。内容不会上传。</p>
        <label className="pick">
          或点击选择文件
          <input
            type="file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void takeFile(f);
            }}
          />
        </label>
      </div>

      {fileName && (
        <p className="fileline">
          已选择：{fileName}
          {fileSize != null ? `（${formatSize(fileSize)}）` : ""}
          {hashing ? " · 正在这台电脑上计算指纹…" : ""}
        </p>
      )}

      {fingerprint && !hashing && (
        <div className="print">
          <div className="label">指纹</div>
          <code>{shortPrint(fingerprint)}</code>
          <p className="muted">这不是文件内容。改一个字，指纹就会变。</p>
        </div>
      )}

      <label className="field">
        标题
        <input
          type="text"
          value={title}
          maxLength={200}
          placeholder="例如：第三章草稿"
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      <p className="muted">
        {accountId
          ? "将使用这台浏览器里已有的存证账号。"
          : "还没有存证账号也没关系。点「开始存证」时会自动创建一个，编号保存在这台浏览器里。"}
      </p>

      <div className="row">
        <button
          type="button"
          className="accent"
          disabled={!fingerprint || hashing || busy}
          onClick={() => void save()}
        >
          {busy ? "正在存证…" : "开始存证"}
        </button>
        <button
          type="button"
          disabled={!saved || exporting}
          onClick={() => void exportCert()}
        >
          {exporting ? "正在导出…" : "导出证书"}
        </button>
      </div>

      {saved && (
        <div className="donebox">
          <p className="ok">存证完成。请把证书和原文件放在一起。</p>
          <p>标题：{saved.title}</p>
          <p>时间戳：{formatWhen(saved.timestamp) || "已记录"}</p>
          <p>指纹：{shortPrint(saved.fingerprint)}</p>
          {saved.notice && <p className="warn">{saved.notice}</p>}
          <p className="muted">
            证书只能证明「这个时间你手里有这份指纹」，不能证明某家公司训练或看过原文。这不是法律意见。
          </p>
        </div>
      )}

      {err && <p className="bad">{err}</p>}

      <style jsx>{`
        .steps {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          list-style: none;
          padding: 0;
          margin: 0 0 16px;
        }
        .steps li {
          font-size: 12px;
          color: #7f8fa3;
          border: 1px solid #1e2a38;
          border-radius: 99px;
          padding: 4px 10px;
        }
        .steps li.now {
          color: #3dd68c;
          border-color: #2a5c42;
        }
        .steps li.done {
          color: #d7e0ea;
        }
        .drop {
          border: 1.5px dashed #2a3b52;
          border-radius: 10px;
          padding: 28px 16px;
          text-align: center;
          background: #111821;
        }
        .drop.over {
          border-color: #3dd68c;
          background: #123526;
        }
        .drop-title {
          margin: 0 0 6px;
          font-size: 18px;
          color: #e8eef5;
        }
        .muted {
          color: #9eb2c7;
          font-size: 13px;
          line-height: 1.5;
        }
        .pick {
          display: inline-block;
          margin-top: 12px;
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px 12px;
          cursor: pointer;
          font-size: 13px;
        }
        .pick input {
          display: none;
        }
        .fileline {
          margin: 12px 0 0;
          font-size: 14px;
        }
        .print {
          margin-top: 12px;
          background: #0b0f14;
          border: 1px solid #243044;
          border-radius: 8px;
          padding: 12px;
        }
        .label {
          font-size: 12px;
          color: #7f8fa3;
          margin-bottom: 4px;
        }
        code {
          color: #3dd68c;
          font-family: var(--mono);
          font-size: 14px;
        }
        .field {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-top: 14px;
          font-size: 13px;
          color: #9eb2c7;
        }
        .field input {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 10px 12px;
          font-size: 15px;
        }
        .row {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 12px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 10px 14px;
          font-size: 14px;
        }
        button.accent {
          background: #1a3d2c;
          border-color: #2a5c42;
          color: #3dd68c;
        }
        button:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .donebox {
          margin-top: 16px;
          background: #111821;
          border: 1px solid #2a5c42;
          border-radius: 8px;
          padding: 14px;
        }
        .donebox p {
          margin: 6px 0;
        }
        .ok {
          color: #3dd68c;
        }
        .warn {
          color: #f0b429;
        }
        .bad {
          color: #ff6b6b;
          margin-top: 12px;
        }
      `}</style>
    </GuideShell>
  );
}
