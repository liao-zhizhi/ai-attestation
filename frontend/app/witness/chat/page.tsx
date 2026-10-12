"use client";

import { useEffect } from "react";
import Link from "next/link";
import { GuideShell } from "@/components/GuideShell";

export default function ChatWitnessPage() {
  useEffect(() => {
    document.title = "见证 AI 对话";
  }, []);

  return (
    <GuideShell
      title="见证 AI 对话"
      lede="ChatGPT、Claude、文心一言这类网页对话，不会自动经过本站。要留下时间戳，按下面做。"
    >
      <section className="card">
        <h2>浏览器扩展</h2>
        <p>
          能自动盯着网页对话的扩展还没有发布，所以这里没有商店安装按钮。请不要安装来路不明的同名扩展。
        </p>
        <p className="muted">发布之后，安装引导会直接出现在这一页。</p>
      </section>

      <section className="card">
        <h2>今天就能做</h2>
        <ol>
          <li>在对话窗口里选中要留证的内容，粘贴到记事本，保存成文本文件。</li>
          <li>
            打开 <Link href="/witness/file">给文件留指纹</Link>
            ，把这个文件拖进去。
          </li>
          <li>填一个你自己认得的标题，点「开始存证」。</li>
          <li>点「导出证书」，和原文件放在一起。</li>
        </ol>
        <p className="muted">对话内容只在你的电脑上计算指纹，不会上传。</p>
      </section>

      <section className="card">
        <h2>如果你是用程序调用 AI</h2>
        <p>
          那就不用复制网页。到 <Link href="/developers">开发者接入</Link>
          ，按说明把程序指过来，每次调用都会留下记录。
        </p>
      </section>

      <style jsx>{`
        .card {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 8px;
          padding: 14px 16px;
          margin-bottom: 12px;
        }
        h2 {
          margin: 0 0 8px;
          font-size: 16px;
          color: #e8eef5;
        }
        p,
        li {
          color: #c5d0dc;
          line-height: 1.6;
          font-size: 14px;
        }
        ol {
          margin: 0;
          padding-left: 1.2em;
        }
        li {
          margin: 6px 0;
        }
        .muted {
          color: #9eb2c7;
          font-size: 13px;
        }
        a {
          color: #3dd68c;
        }
      `}</style>
    </GuideShell>
  );
}
