"use client";

import { Suspense } from "react";
import VerifyClient from "./VerifyClient";

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: 24, color: "#9eb2c7", fontFamily: "monospace" }}>
          加载验证页…
        </main>
      }
    >
      <VerifyClient />
    </Suspense>
  );
}
