"use client";

import { useState } from "react";

type Props = {
  proxyUrl: string;
  onSimulate: () => void;
  busy: boolean;
  canWrite?: boolean;
};

/** 空状态引导：证据链始于一次连接。 */
export function EmptyState({ proxyUrl, onSimulate, busy, canWrite = true }: Props) {
  const [copied, setCopied] = useState(false);
  const displayProxy = proxyUrl || "http://127.0.0.1:8004/v1/proxy";

  const snippet = `from openai import OpenAI

client = OpenAI(
    base_url="${displayProxy}",
    api_key="sk-your-upstream-key",
    default_headers={"X-Attest-Key": "ata_your_key"},
)
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}],
)`;

  async function copyProxy() {
    try {
      await navigator.clipboard.writeText(displayProxy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="guide">
      <h2>证据链，始于一次简单的连接。</h2>
      <ol>
        <li>
          <strong>步骤一</strong>
          <p>
            将你的 AI API 指向审计代理。
            <code className="mono url">{displayProxy}</code>
          </p>
        </li>
        <li>
          <strong>步骤二</strong>
          <p>进行一次正常的 API 调用。每一次请求都会写入可校验的证据链。</p>
        </li>
        <li>
          <strong>步骤三</strong>
          <p>回到这里查看 AI 行为记录，形成可独立验证的证据链。</p>
        </li>
      </ol>
      <div className="acts">
        <button type="button" onClick={copyProxy}>
          {copied ? "已复制" : "复制代理URL"}
        </button>
        <button
          type="button"
          onClick={onSimulate}
          disabled={busy || !canWrite}
          title={!canWrite ? "需要 read_write 或 admin" : undefined}
        >
          {busy ? "写入中…" : "模拟一条调用"}
        </button>
      </div>
      <pre className="mono">{snippet}</pre>
      <p className="hint">候选文案，需人肉审核后方可发布</p>
      <style jsx>{`
        .guide {
          background: #111821;
          border: 1px dashed #2a3b52;
          border-radius: 6px;
          padding: 18px 20px;
          margin-bottom: 16px;
        }
        h2 {
          margin: 0 0 14px;
          font-size: 16px;
          color: #d7e0ea;
        }
        ol {
          margin: 0;
          padding: 0;
          list-style: none;
          display: grid;
          gap: 14px;
        }
        strong {
          color: #3dd68c;
          font-family: var(--mono);
          font-size: 13px;
        }
        p {
          margin: 4px 0 8px;
          color: #9eb2c7;
          font-size: 13px;
          line-height: 1.5;
        }
        .url {
          display: block;
          margin-top: 6px;
          padding: 6px 8px;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          color: #3dd68c;
          font-size: 12px;
          word-break: break-all;
        }
        .acts {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 4px;
        }
        button {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 7px 12px;
          font-family: var(--mono);
          font-size: 12px;
        }
        button:disabled {
          opacity: 0.6;
        }
        pre {
          margin: 16px 0 0;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 12px;
          overflow: auto;
          font-size: 11px;
          line-height: 1.45;
          color: #9eb2c7;
        }
        .mono {
          font-family: var(--mono);
        }
        .hint {
          margin: 12px 0 0;
          font-size: 11px;
          color: #7f8fa3;
          font-family: var(--mono);
        }
      `}</style>
    </section>
  );
}

/** @deprecated 使用 EmptyState；保留别名以免旧引用断裂 */
export function EmptyOnboarding(props: Props) {
  return <EmptyState {...props} />;
}
