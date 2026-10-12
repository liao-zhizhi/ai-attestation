const guest = document.getElementById("guest");
const home = document.getElementById("home");
const emailInput = document.getElementById("email");
const codeInput = document.getElementById("code");
const codeHint = document.getElementById("code-hint");
const guestErr = document.getElementById("guest-err");
const homeErr = document.getElementById("home-err");
const list = document.getElementById("list");
const empty = document.getElementById("empty");
const who = document.getElementById("who");
const syncNote = document.getElementById("sync-note");
const guestNote = document.getElementById("guest-note");
const baseInput = document.getElementById("base");
const logoutBtn = document.getElementById("logout");

const TEST_CODE = "123456";
let pendingEmail = "";

function send(msg) {
  return chrome.runtime.sendMessage(msg);
}

function showGuest() {
  guest.hidden = false;
  home.hidden = true;
  logoutBtn.hidden = true;
}

function showHome(email) {
  guest.hidden = true;
  home.hidden = false;
  logoutBtn.hidden = false;
  who.textContent = email ? `已登录 ${email}` : "已登录";
}

function formatWhen(iso) {
  if (!iso) return "时间未知";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso).replace("T", " ").slice(0, 19);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function renderList(artifacts) {
  list.innerHTML = "";
  const rows = Array.isArray(artifacts) ? artifacts.slice(0, 10) : [];
  empty.hidden = rows.length > 0;
  rows.forEach((row) => {
    const li = document.createElement("li");
    const wrap = document.createElement("div");
    wrap.className = "item-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "item";
    const hash = String(row.hash_prefix || String(row.artifact_hash || "").slice(0, 12));
    const chain = row.chain_ok ? "已写入" : "异常";
    button.innerHTML = "";
    const top = document.createElement("div");
    top.className = "top";
    const when = document.createElement("span");
    when.textContent = formatWhen(row.timestamp);
    const state = document.createElement("span");
    state.textContent = chain;
    if (!row.chain_ok) state.className = "chain-bad";
    top.append(when, state);
    const model = document.createElement("div");
    model.textContent = row.title || "对话";
    const digest = document.createElement("div");
    digest.className = "hash";
    digest.textContent = hash;
    button.append(top, model, digest);
    button.addEventListener("click", async () => {
      homeErr.className = "err";
      homeErr.textContent = "正在打开详情…";
      const res = await send({ type: "open", id: row.id });
      homeErr.textContent = res && res.ok ? "" : (res && res.error) || "打不开详情页";
    });
    const exp = document.createElement("button");
    exp.type = "button";
    exp.className = "export";
    exp.textContent = "导出";
    exp.addEventListener("click", async () => {
      exp.disabled = true;
      exp.textContent = "导出中";
      homeErr.className = "err";
      homeErr.textContent = "";
      const res = await send({ type: "export", id: row.id });
      exp.disabled = false;
      exp.textContent = "导出";
      if (res && res.ok) {
        homeErr.className = "ok";
        homeErr.textContent = "已开始下载";
      } else {
        homeErr.className = "err";
        homeErr.textContent = (res && res.error) || "导出失败";
      }
    });
    wrap.append(button, exp);
    li.append(wrap);
    list.append(li);
  });
}

async function refresh() {
  homeErr.className = "err";
  homeErr.textContent = "";
  const res = await send({ type: "list" });
  if (!res || !res.ok) {
    homeErr.textContent = (res && res.error) || "列表加载失败";
    renderList([]);
    return;
  }
  renderList(res.artifacts);
}

async function boot() {
  const session = await send({ type: "session" });
  baseInput.value = (session && session.apiBase) || "";
  if (session && session.loggedIn) {
    showHome(session.email);
    await refresh();
    return;
  }
  showGuest();
  const pending = await chrome.storage.session.get({ pendingEmail: "" });
  if (pending.pendingEmail) {
    pendingEmail = pending.pendingEmail;
    emailInput.value = pendingEmail;
    codeInput.disabled = false;
    document.getElementById("login").disabled = false;
    codeHint.hidden = false;
  }
}

document.getElementById("send").addEventListener("click", async () => {
  guestErr.textContent = "";
  guestNote.textContent = "";
  const email = emailInput.value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    guestErr.textContent = "请填写有效邮箱";
    return;
  }
  pendingEmail = email;
  await chrome.storage.session.set({ pendingEmail: email });
  codeInput.disabled = false;
  document.getElementById("login").disabled = false;
  codeHint.hidden = false;
  codeInput.focus();
});

document.getElementById("login").addEventListener("click", async () => {
  guestErr.textContent = "";
  if (!pendingEmail) {
    guestErr.textContent = "请先发送验证码";
    return;
  }
  if (emailInput.value.trim() !== pendingEmail) {
    guestErr.textContent = "邮箱已改，请重新发送验证码";
    return;
  }
  if (codeInput.value.trim() !== TEST_CODE) {
    guestErr.textContent = "验证码不对";
    return;
  }
  const res = await send({ type: "login", email: pendingEmail });
  if (!res || !res.ok) {
    guestErr.textContent = (res && res.error) || "登录失败";
    return;
  }
  await chrome.storage.session.remove("pendingEmail");
  showHome(res.email || pendingEmail);
  syncNote.textContent = res.synced
    ? "编号已写入网站。打开 ai-attestation.com 会使用同一个存证账号。"
    : `登录成功，但没能写入网站：${res.syncError || "请再登录一次"}`;
  await refresh();
});

document.getElementById("save-base").addEventListener("click", async () => {
  const res = await send({ type: "set-base", apiBase: baseInput.value });
  baseInput.value = (res && res.apiBase) || baseInput.value;
  const target = home.hidden ? guestErr : homeErr;
  target.textContent = res && res.ok ? "地址已保存" : "地址没保存";
});

logoutBtn.addEventListener("click", async () => {
  logoutBtn.disabled = true;
  const res = await send({ type: "logout" });
  logoutBtn.disabled = false;
  if (!res || !res.ok) {
    homeErr.className = "err";
    homeErr.textContent = (res && res.error) || "退出失败";
    return;
  }
  pendingEmail = "";
  codeInput.value = "";
  codeInput.disabled = true;
  document.getElementById("login").disabled = true;
  codeHint.hidden = true;
  syncNote.textContent = "";
  showGuest();
  guestNote.textContent = res.siteCleared === false
    ? `已退出。网站上的编号没能清掉：${res.syncError || "请再打开一次网站"}`
    : "已退出";
});

boot().catch((err) => {
  guestErr.textContent = err instanceof Error ? err.message : "扩展没有就绪";
  showGuest();
});
