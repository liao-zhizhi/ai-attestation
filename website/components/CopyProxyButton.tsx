"use client";

import { useState } from "react";

const PROXY_URL =
  process.env.NEXT_PUBLIC_PROXY_URL || "http://127.0.0.1:8004/v1/proxy";
const DASHBOARD_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_URL || "http://127.0.0.1:3002";
const GITHUB_URL =
  process.env.NEXT_PUBLIC_GITHUB_URL ||
  "https://github.com/liao-zhizhi/ai-attestation";

export function CopyProxyButton({ className }: { className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(PROXY_URL);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button type="button" onClick={copy} className={className}>
      {copied ? "已复制代理 URL" : "复制代理 URL"}
    </button>
  );
}

export { PROXY_URL, DASHBOARD_URL, GITHUB_URL };
