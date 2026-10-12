import { formatDetail } from "@/lib/api";

/** 与仪表盘同一份本地存储，换页后仍是同一个存证账号。 */
export const ACCOUNT_STORAGE_KEY = "ata_mvp_api_key";
export const AUTH_STORAGE_KEY = "ata_mvp_authorization";

export function readStoredAccount(): string {
  if (typeof window === "undefined") return "";
  return (localStorage.getItem(ACCOUNT_STORAGE_KEY) || "").trim();
}

export function saveStoredAccount(accountId: string): void {
  localStorage.setItem(ACCOUNT_STORAGE_KEY, accountId.trim());
}

/** 调用现有 POST /v1/keys，并把编号写入本机。不改后端。 */
export async function createStoredAccount(
  apiBase: string,
  label?: string
): Promise<string> {
  const name = (label || "").trim() || "我的存证账号";
  const r = await fetch(`${apiBase.replace(/\/$/, "")}/v1/keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label: name }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || typeof d.api_key !== "string") {
    throw new Error(formatDetail(d.detail, "创建存证账号失败"));
  }
  saveStoredAccount(d.api_key);
  return d.api_key;
}
