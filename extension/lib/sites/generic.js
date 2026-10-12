/* 新站点共用的读取方式。每个站点只登记自己的域名和选择器，读取逻辑在这里。 */
(function (root) {
  const sites = [];

  function textOf(el) {
    if (!el) return "";
    return String(el.innerText || el.textContent || "").replace(/\r\n/g, "\n").trim();
  }

  function ataRegisterSite(config) {
    if (!config || !config.id || !Array.isArray(config.hosts)) return;
    sites.push(config);
  }

  function ataMatchSite(hostname) {
    const host = String(hostname || "").toLowerCase();
    return sites.find((site) => site.hosts.indexOf(host) !== -1) || null;
  }

  function roleOf(el) {
    const blob = [
      el.getAttribute && el.getAttribute("data-role"),
      el.getAttribute && el.getAttribute("data-message-author-role"),
      el.getAttribute && el.getAttribute("data-testid"),
      el.getAttribute && el.getAttribute("class"),
    ].join(" ");
    const user = /(^|[^a-z])(user|human|question|prompt|self)([^a-z]|$)/i.test(blob) || /用户|提问/.test(blob);
    const bot = /(assistant|answer|markdown|bot|reply|response)/i.test(blob) || /助手|回答/.test(blob);
    if (user && !bot) return "user";
    if (bot && !user) return "assistant";
    return "";
  }

  function collect(doc, selectors) {
    const found = [];
    (selectors || []).forEach((sel) => {
      let nodes = [];
      try {
        nodes = [...doc.querySelectorAll(sel)];
      } catch (_err) {
        nodes = [];
      }
      nodes.forEach((el) => {
        if (found.indexOf(el) === -1) found.push(el);
      });
    });
    const usable = found.filter((el) => {
      if (!el || (el.closest && el.closest("script, style, noscript, textarea, input"))) return false;
      const text = textOf(el);
      return text.length >= 1 && text.length <= 8000;
    });
    return usable.filter((el) => {
      return !usable.some((other) => other !== el && el.contains && el.contains(other) && textOf(other).length > 0);
    });
  }

  function ataReadSiteMessages(doc, site) {
    const nodes = collect(doc, site && site.selectors);
    return nodes
      .map((el) => {
        const role = roleOf(el);
        if (role !== "user" && role !== "assistant") return null;
        return { role, text: textOf(el) };
      })
      .filter(Boolean);
  }

  function ataReadSiteModel(doc, site) {
    const needles = ((site && site.modelNeedles) || []).filter((item) => !/^(模型|model)$/i.test(item));
    const chunks = [];
    if (doc.title) chunks.push(String(doc.title));
    const header = doc.querySelector && doc.querySelector("header");
    if (header) chunks.push(textOf(header).slice(0, 500));
    let labeled = [];
    try {
      labeled = [...doc.querySelectorAll("[class*='model'], [class*='Model']")];
    } catch (_err) {
      labeled = [];
    }
    labeled.slice(0, 20).forEach((el) => chunks.push(textOf(el).slice(0, 80)));
    for (const chunk of chunks) {
      const lines = String(chunk || "").split("\n");
      for (const line of lines) {
        const raw = line.trim();
        if (!raw || raw.length > 40) continue;
        if (needles.some((needle) => raw.indexOf(needle) !== -1)) return raw.slice(0, 80);
      }
    }
    return "unknown";
  }

  function isGenerating(doc) {
    const buttons = doc.querySelectorAll ? doc.querySelectorAll("button") : [];
    for (const button of buttons) {
      const label = String((button.getAttribute && button.getAttribute("aria-label")) || button.innerText || "")
        .trim()
        .toLowerCase();
      if (label === "stop" || label === "stop generating" || label === "停止生成" || label === "停止输出") return true;
    }
    return false;
  }

  function editableOf(target) {
    if (!target || !target.closest) return null;
    const el = target.closest("textarea, input, [contenteditable='true'], [contenteditable='']");
    if (!el) return null;
    if (el.tagName === "INPUT") {
      const type = String(el.getAttribute("type") || "text").toLowerCase();
      if (type && type !== "text" && type !== "search") return null;
    }
    return el;
  }

  function fieldText(el) {
    if (el && "value" in el && el.value != null && el.tagName !== "DIV") return String(el.value);
    return textOf(el);
  }

  function ataWatchSite(site) {
    if (!site || root.__ataGenericWatch) return;
    root.__ataGenericWatch = true;
    const recorded = new Set();
    let pending = null;
    let timer = 0;
    let toldToLogin = false;

    function pairId(pair) {
      return `${pair.prompt}\u0000${pair.response}`;
    }

    function toast(text) {
      const parent = document.documentElement || document.body;
      if (!parent) return;
      let el = document.getElementById("ata-witness-toast");
      if (!el) {
        el = document.createElement("div");
        el.id = "ata-witness-toast";
        el.setAttribute("role", "status");
        el.style.cssText = [
          "position:fixed",
          "right:16px",
          "bottom:16px",
          "z-index:2147483647",
          "background:#123526",
          "color:#3dd68c",
          "border:1px solid #2a5c42",
          "border-radius:8px",
          "padding:10px 14px",
          "font:14px/1.4 sans-serif",
          "box-shadow:0 8px 24px rgba(0,0,0,.35)",
        ].join(";");
        parent.appendChild(el);
      }
      el.textContent = text;
      el.style.display = "block";
      clearTimeout(el._hide);
      el._hide = setTimeout(() => {
        el.style.display = "none";
      }, 1000);
    }

    function markExisting() {
      try {
        const pairs = root.ataPairMessages(ataReadSiteMessages(document, site));
        pairs.forEach((pair) => recorded.add(pairId(pair)));
      } catch (_err) {
        /* 页面还没准备好时忽略 */
      }
    }

    async function sendTurn(canon) {
      if (!canon.prompt) return;
      if (!canon.degraded && !canon.response) return;
      const bytes = new TextEncoder().encode(canon.text);
      const hash = root.ataSha256Hex(bytes);
      const key = canon.degraded ? `degraded\u0000${canon.prompt}` : `${canon.prompt}\u0000${canon.response}`;
      if (recorded.has(key)) return;
      recorded.add(key);
      let res = null;
      try {
        res = await chrome.runtime.sendMessage({
          type: "record",
          hash,
          byteLength: bytes.length,
          title: canon.title,
          filenameHint: canon.filenameHint,
        });
      } catch (_err) {
        recorded.delete(key);
        return;
      }
      if (!res || !res.ok) {
        recorded.delete(key);
        if (res && res.reason === "login" && !toldToLogin) {
          toldToLogin = true;
          toast("请先点击扩展图标登录");
        }
        return;
      }
      if (!res.duplicate) toast("已见证");
    }

    function settle() {
      if (!pending) return;
      let pairs = [];
      let model = "unknown";
      try {
        pairs = root.ataPairMessages(ataReadSiteMessages(document, site));
        model = ataReadSiteModel(document, site);
      } catch (_err) {
        pairs = [];
      }
      const match = pairs.filter((pair) => pair.prompt === pending.prompt && !recorded.has(pairId(pair))).pop();
      if (match && match.response) {
        const canon = root.ataCanonical({
          site: site.id,
          model,
          prompt: match.prompt,
          response: match.response,
        });
        pending = null;
        sendTurn(canon);
        return;
      }
      const age = Date.now() - pending.at;
      if (age < 60000 && (isGenerating(document) || age < 3000)) {
        timer = setTimeout(settle, 1000);
        return;
      }
      const canon = root.ataCanonical({
        site: site.id,
        model: "unknown",
        prompt: pending.prompt,
        response: "",
        degraded: true,
        url: pending.url,
        recordedAt: pending.recordedAt,
      });
      pending = null;
      sendTurn(canon);
    }

    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(settle, 1000);
    }

    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Enter" || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey || event.isComposing) {
          return;
        }
        const field = editableOf(event.target);
        if (!field) return;
        const prompt = fieldText(field).trim();
        if (!prompt) return;
        pending = {
          prompt,
          url: location.href,
          recordedAt: new Date().toISOString(),
          at: Date.now(),
        };
        schedule();
      },
      true
    );

    const observer = new MutationObserver(() => {
      if (pending) schedule();
    });
    const watchRoot = document.documentElement || document.body;
    if (watchRoot) {
      observer.observe(watchRoot, { childList: true, subtree: true, characterData: true });
    }
    markExisting();
  }

  root.ataRegisterSite = ataRegisterSite;
  root.ataMatchSite = ataMatchSite;
  root.ataReadSiteMessages = ataReadSiteMessages;
  root.ataReadSiteModel = ataReadSiteModel;
  root.ataWatchSite = ataWatchSite;
})(globalThis);
