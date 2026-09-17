"use client";

import { useParams } from "next/navigation";
import { PublicVerifyView } from "@/components/PublicVerifyView";

export default function PublicArtifactVerifyPage() {
  const params = useParams();
  const token = String(params?.token || "");
  return <PublicVerifyView kind="artifact" token={token} />;
}
