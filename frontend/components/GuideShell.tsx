"use client";

import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  title: string;
  lede: string;
  children: ReactNode;
};

/** 小白向导页的统一外壳：返回首页 + 标题。 */
export function GuideShell({ title, lede, children }: Props) {
  return (
    <main className="guide-page">
      <p className="back">
        <Link href="/">← 返回首页</Link>
      </p>
      <h1>{title}</h1>
      <p className="lede">{lede}</p>
      {children}
    </main>
  );
}
