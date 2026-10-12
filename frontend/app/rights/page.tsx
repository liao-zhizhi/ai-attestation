"use client";

import { useEffect } from "react";
import Link from "next/link";
import { GuideShell } from "@/components/GuideShell";

export default function RightsPage() {
  useEffect(() => {
    document.title = "维权指引";
  }, []);

  return (
    <GuideShell
      title="我被 AI 侵权了"
      lede="先把原件和指纹保住。下面不是法律意见，也不能代替律师。"
    >
      <section className="card">
        <h2>现在就做</h2>
        <ol>
          <li>保存原件本身：稿件、图片、工程文件。截图不能代替原件。</li>
          <li>
            打开 <Link href="/witness/file">给文件留指纹</Link>
            ，把原件拖进去，点「开始存证」，再「导出证书」。
          </li>
          <li>把证书和原件放在同一个文件夹。记下页面上的时间戳。</li>
          <li>另外备份一份到你自己的网盘或硬盘。不要只留在这一个网站上。</li>
        </ol>
      </section>

      <section className="card">
        <h2>证书能证明什么</h2>
        <ul>
          <li>在这个时间戳，你提交过这份文件的指纹。</li>
          <li>之后如果文件被改过，指纹对不上。</li>
        </ul>
      </section>

      <section className="card">
        <h2>证书不能证明什么</h2>
        <ul>
          <li>不能证明某家公司训练过、看过或复制了你的作品。</li>
          <li>不能代替法院判决，也不能代替公证处。</li>
          <li>不能证明你一定是最早的作者。它只证明「这个时间，这份指纹已经在这里」。</li>
        </ul>
      </section>

      <section className="card">
        <h2>如果要继续维权</h2>
        <p>
          把原件、证书和时间戳交给律师或你信任的顾问。本站不接受案件委托，也不判断谁侵权。
        </p>
        <p>
          对话记录也可以先存成文本，再走同一条
          <Link href="/witness/file">文件存证</Link>。
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
        ol,
        ul {
          margin: 0;
          padding-left: 1.2em;
        }
        li {
          margin: 6px 0;
        }
        a {
          color: #3dd68c;
        }
      `}</style>
    </GuideShell>
  );
}
