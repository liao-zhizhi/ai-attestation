"use client";

import { useParams } from "next/navigation";
import { PublicVerifyView } from "@/components/PublicVerifyView";

export default function PublicCallVerifyPage() {
  const params = useParams();
  const token = String(params?.token || "");
  return <PublicVerifyView kind="call" token={token} />;
}
