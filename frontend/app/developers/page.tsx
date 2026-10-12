"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { GuideShell } from "@/components/GuideShell";
import { readStoredAccount } from "@/lib/account";
import { resolveApiBase } from "@/lib/api";
import { copyText, pythonProxySnippet } from "@/lib/snippet";

export default function DevelopersPage() {
  const [accountId, setAccountId] = useState("");
  const [proxyUrl, setProxyUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyErr, setCopyErr] = useState<string | null>(null);

  useEffect(() => {
    document.title = "开发者接入";
    const base = resolveApiBase();
    setProxyUrl(base ? `${base}/v1/proxy` : "");
    setAccountId(readStoredAccount());
  }, []);

  const snippet = useMemo(
    () => pythonProxySnippet(proxyUrl, accountId),
    [proxyUrl, accountId]
  );

  async function copySnippet() {
    setCopyErr(null);
    const ok = await copyText(snippet);
    if (!ok) {
      setCopyErr("复制失败。请选中下面的代码手动复制。");
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <GuideShell
      title="开发者接入"
      lede="把程序的请求指到存证服务。每次调用都会留下带时间戳的记录，请求正文不会被存下来。"
    >
      <ol className="steps">
        <li>
          <Link href="/?nav=keys">创建一个存证账号</Link>
          。点一下即可，编号会自动生成。
        </li>
        <li>
          安装官方 SDK：<code>pip install openai</code>
        </li>
        <li>
          复制下面的代码。存证账号编号和代理地址已经按这台浏览器填好。把{" "}
          <code>UPSTREAM_KEY</code> 换成厂商给你的密钥（<code>sk-</code> 开头）。
        </li>
        <li>运行一次调用，回到首页的「API 调用记录」就能看到这条记录。</li>
      </ol>

      {!accountId && (
        <p className="warn">
          这台浏览器还没有存证账号，代码里的编号是占位符。先去
          <Link href="/?nav=keys">创建一个存证账号</Link>
          ，再回到这里复制。
        </p>
      )}

      <div className="row">
        <button type="button" className="accent" onClick={() => void copySnippet()}>
          {copied ? "已复制" : "一键复制配置"}
        </button>
        <Link className="textlink" href="/?nav=settings">
          打开设置页
        </Link>
      </div>
      {copyErr && <p className="bad">{copyErr}</p>}
      <pre>{snippet}</pre>
      <p className="muted">
        代码里的 <code>X-Attest-Key</code> 就是存证账号编号，不要和厂商密钥填反。设置页也有同样的「一键复制配置」。
      </p>

      <style jsx>{`
        .steps {
          margin: 0 0 14px;
          padding-left: 1.2em;
          color: #c5d0dc;
          line-height: 1.6;
        }
        .steps li {
          margin: 8px 0;
        }
        code {
          font-family: var(--mono);
          color: #3dd68c;
          font-size: 12px;
        }
        .warn {
          color: #f0b429;
          font-size: 13px;
          line-height: 1.5;
        }
        .row {
          display: flex;
          gap: 12px;
          align-items: center;
          flex-wrap: wrap;
          margin: 8px 0;
        }
        button {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 10px 14px;
          font-size: 14px;
        }
        .textlink {
          color: #9eb2c7;
          font-size: 13px;
        }
        pre {
          background: #0b0f14;
          border: 1px solid #243044;
          border-radius: 8px;
          padding: 12px;
          overflow: auto;
          color: #d7e0ea;
          font-family: var(--mono);
          font-size: 12px;
          line-height: 1.5;
          white-space: pre-wrap;
        }
        .muted {
          color: #9eb2c7;
          font-size: 13px;
          line-height: 1.5;
        }
        .bad {
          color: #ff6b6b;
          font-size: 13px;
        }
      `}</style>
    </GuideShell>
  );
}
