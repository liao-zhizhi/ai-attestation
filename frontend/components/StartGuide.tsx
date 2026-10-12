"use client";

import Link from "next/link";

const CARDS = [
  {
    href: "/witness/file",
    title: "我要给文件留指纹",
    text: "把文件拖进来。指纹在你自己的电脑上算好，再留下时间戳并导出证书。",
  },
  {
    href: "/witness/chat",
    title: "我要见证 AI 对话",
    text: "网页里的对话不会自动记录。这里说明扩展的现状，以及今天就能用的办法。",
  },
  {
    href: "/developers",
    title: "我是开发者，要审计 API 调用",
    text: "把程序接到存证服务。每次调用都会留下带时间戳的记录。",
  },
  {
    href: "/rights",
    title: "我被 AI 侵权了",
    text: "先保住原件和指纹。看清证书能证明什么、不能证明什么。",
  },
];

/** 仪表盘上方的四选一。不要求先有存证账号。 */
export function StartGuide() {
  return (
    <section className="start" aria-label="你想做什么">
      <div className="head">
        <h2>你想做什么？</h2>
        <p>先选一件事。不用懂技术名词，也不必先创建账号。</p>
      </div>
      <div className="grid">
        {CARDS.map((card) => (
          <Link key={card.href} href={card.href} className="card">
            <span className="t">{card.title}</span>
            <span className="d">{card.text}</span>
          </Link>
        ))}
      </div>
      <style jsx>{`
        .start {
          background: #111821;
          border: 1px solid #2a5c42;
          border-radius: 8px;
          padding: 16px 16px 14px;
          margin-bottom: 16px;
        }
        .head h2 {
          margin: 0;
          font-size: 18px;
          color: #e8eef5;
          letter-spacing: 0;
          text-transform: none;
        }
        .head p {
          margin: 6px 0 12px;
          color: #9eb2c7;
          font-size: 13px;
        }
        .grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }
        .card {
          display: flex;
          flex-direction: column;
          gap: 6px;
          text-decoration: none;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 8px;
          padding: 14px 14px 16px;
          min-height: 108px;
        }
        .card:hover {
          border-color: #2a5c42;
          background: #123526;
        }
        .t {
          color: #e8eef5;
          font-size: 15px;
          font-weight: 650;
        }
        .d {
          color: #9eb2c7;
          font-size: 13px;
          line-height: 1.45;
        }
        @media (max-width: 700px) {
          .grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
