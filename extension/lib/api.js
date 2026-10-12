/* 只调用已经存在的接口。不上传对话原文。 */
(function (root) {
  const ATA_DEFAULT_API_BASE = "http://47.119.118.245:8004";

  function ataNormalizeBase(url) {
    const raw = String(url || "").trim();
    return (raw || ATA_DEFAULT_API_BASE).replace(/\/$/, "");
  }

  async function ataReadError(res) {
    try {
      const data = await res.json();
      const detail = data && data.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      if (detail != null) return JSON.stringify(detail);
    } catch (_err) {
      /* 用状态码 */
    }
    return `请求失败 (${res.status})`;
  }

  async function ataCreateAccount(apiBase, email) {
    const label = String(email || "").trim().slice(0, 80) || "extension";
    const res = await fetch(`${ataNormalizeBase(apiBase)}/v1/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || typeof data.api_key !== "string") {
      throw new Error(typeof data.detail === "string" ? data.detail : "创建存证账号失败");
    }
    return data.api_key;
  }

  async function ataRegisterArtifact(apiBase, apiKey, payload) {
    const res = await fetch(`${ataNormalizeBase(apiBase)}/v1/research/artifacts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        title: payload.title,
        kind: "prompt",
        artifact_hash: payload.hash,
        byte_length: payload.byteLength,
        filename_hint: payload.filenameHint,
        client_hashed: true,
      }),
    });
    if (!res.ok) throw new Error(await ataReadError(res));
    return res.json();
  }

  async function ataListArtifacts(apiBase, apiKey) {
    const url = `${ataNormalizeBase(apiBase)}/v1/research/artifacts?limit=10&api_key=${encodeURIComponent(apiKey)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(await ataReadError(res));
    const data = await res.json();
    return data.artifacts || [];
  }

  /** 已有公开链接接口。返回 { token, url }，用来打开网站上的详情页。 */
  async function ataShareArtifact(apiBase, apiKey, artifactId) {
    const res = await fetch(
      `${ataNormalizeBase(apiBase)}/v1/public/share/artifact/${encodeURIComponent(artifactId)}`,
      {
        method: "POST",
        headers: { "X-Attest-Key": apiKey },
      }
    );
    if (!res.ok) throw new Error(await ataReadError(res));
    return res.json();
  }

  function ataDetailUrl(apiBase, share) {
    const token = share && share.token ? String(share.token) : "";
    const base = ataNormalizeBase(apiBase);
    if (/127\.0\.0\.1|localhost/.test(base)) {
      return `http://127.0.0.1:3002/verify/artifact/${encodeURIComponent(token)}`;
    }
    if (share && typeof share.url === "string" && share.url) return share.url;
    return `https://ai-attestation.com/verify/artifact/${encodeURIComponent(token)}`;
  }

  root.ATA_DEFAULT_API_BASE = ATA_DEFAULT_API_BASE;
  root.ataNormalizeBase = ataNormalizeBase;
  root.ataCreateAccount = ataCreateAccount;
  root.ataRegisterArtifact = ataRegisterArtifact;
  root.ataListArtifacts = ataListArtifacts;
  root.ataShareArtifact = ataShareArtifact;
  root.ataDetailUrl = ataDetailUrl;
})(globalThis);
