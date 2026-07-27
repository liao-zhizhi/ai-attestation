import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ai-attestation",
  description:
    "Open-source AI API audit proxy with tamper-proof evidence chain. 每一次 AI 调用，都应留下可独立验证的证据。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
