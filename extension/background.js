importScripts("lib/sha256.js", "lib/record.js", "lib/api.js");

const SEEN_LIMIT = 300;

function storageGet(keys) {
  return chrome.storage.local.get(keys);
}

function storageSet(obj) {
  return chrome.storage.local.set(obj);
}

async function sessionState() {
  const data = await storageGet({
    apiKey: "",
    email: "",
    apiBase: ATA_DEFAULT_API_BASE,
    seenHashes: [],
  });
  return {
    apiKey: String(data.apiKey || ""),
    email: String(data.email || ""),
    apiBase: ataNormalizeBase(data.apiBase),
    seenHashes: Array.isArray(data.seenHashes) ? data.seenHashes : [],
  };
}

async function rememberHash(hash) {
  const state = await sessionState();
  const next = state.seenHashes.filter((item) => item !== hash);
  next.push(hash);
  await storageSet({ seenHashes: next.slice(-SEEN_LIMIT) });
}

async function handle(msg) {
  if (!msg || typeof msg.type !== "string") return { ok: false, error: "空请求" };
  if (msg.type === "session") {
    const state = await sessionState();
    return {
      ok: true,
      loggedIn: state.apiKey.length >= 8,
      email: state.email,
      apiBase: state.apiBase,
    };
  }
  if (msg.type === "set-base") {
    await storageSet({ apiBase: ataNormalizeBase(msg.apiBase) });
    return { ok: true, apiBase: ataNormalizeBase(msg.apiBase) };
  }
  if (msg.type === "logout") {
    await storageSet({ apiKey: "", email: "" });
    return { ok: true };
  }
  if (msg.type === "login") {
    const email = String(msg.email || "").trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return { ok: false, error: "邮箱格式不对" };
    }
    const state = await sessionState();
    const apiKey = await ataCreateAccount(state.apiBase, email);
    await storageSet({ apiKey, email });
    return { ok: true, email };
  }
  if (msg.type === "list") {
    const state = await sessionState();
    if (state.apiKey.length < 8) return { ok: false, error: "请先登录" };
    const artifacts = await ataListArtifacts(state.apiBase, state.apiKey);
    return { ok: true, artifacts };
  }
  if (msg.type === "open") {
    const state = await sessionState();
    if (state.apiKey.length < 8) return { ok: false, error: "请先登录" };
    const id = String(msg.id || "");
    if (!id) return { ok: false, error: "缺少记录" };
    const share = await ataShareArtifact(state.apiBase, state.apiKey, id);
    const url = ataDetailUrl(state.apiBase, share);
    await chrome.tabs.create({ url });
    return { ok: true, url };
  }
  if (msg.type === "record") {
    const state = await sessionState();
    if (state.apiKey.length < 8) return { ok: false, reason: "login" };
    const hash = String(msg.hash || "").toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(hash)) return { ok: false, error: "指纹无效" };
    if (state.seenHashes.includes(hash)) return { ok: true, duplicate: true };
    const saved = await ataRegisterArtifact(state.apiBase, state.apiKey, {
      title: String(msg.title || "对话").slice(0, 200),
      hash,
      byteLength: Number(msg.byteLength) >= 0 ? Number(msg.byteLength) : undefined,
      filenameHint: String(msg.filenameHint || "chat-turn").slice(0, 240),
    });
    await rememberHash(hash);
    return {
      ok: true,
      duplicate: Boolean(saved && saved.duplicate_notice),
      id: saved && saved.artifact ? saved.artifact.id : "",
    };
  }
  return { ok: false, error: "未知请求" };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  handle(msg)
    .then(sendResponse)
    .catch((err) => {
      sendResponse({ ok: false, error: err instanceof Error ? err.message : "请求失败" });
    });
  return true;
});
