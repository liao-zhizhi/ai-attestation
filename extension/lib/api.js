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
    console.log("[AI-Attest] 写入结果:", res && res.status);
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

  function ataCertificateFilename(artifactId, disposition) {
    const header = String(disposition || "");
    const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
    const plain = /filename="?([^";]+)"?/i.exec(header);
    const named = star ? decodeURIComponent(star[1]) : plain ? plain[1].trim() : "";
    if (/^ata_priority_[A-Za-z0-9_-]{1,64}_cert\.zip$/.test(named)) return named;
    const safe = String(artifactId || "").replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 64) || "artifact";
    return `ata_priority_${safe}_cert.zip`;
  }

  async function ataDownloadCertificate(apiBase, apiKey, artifactId) {
    const id = String(artifactId || "");
    const res = await fetch(
      `${ataNormalizeBase(apiBase)}/v1/research/artifacts/${encodeURIComponent(id)}/certificate`,
      { headers: { "X-Attest-Key": apiKey } }
    );
    if (!res.ok) throw new Error(await ataReadError(res));
    const blob = await res.blob();
    const filename = ataCertificateFilename(id, res.headers.get("Content-Disposition"));
    let url = "";
    try {
      url = URL.createObjectURL(blob);
    } catch (_err) {
      url = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("读验证包失败"));
        reader.readAsDataURL(blob);
      });
    }
    try {
      await chrome.downloads.download({ url, filename, saveAs: false });
    } finally {
      if (url.startsWith("blob:")) {
        const blobUrl = url;
        setTimeout(() => URL.revokeObjectURL(blobUrl), 15000);
      }
    }
    return filename;
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
  root.ataCertificateFilename = ataCertificateFilename;
  root.ataDownloadCertificate = ataDownloadCertificate;
  root.ataDetailUrl = ataDetailUrl;
})(globalThis);
