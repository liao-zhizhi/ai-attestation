/* 注入 ChatGPT / DeepSeek。只把指纹发给后台，不把对话原文送出页面。 */
(function () {
  const site = location.hostname.includes("deepseek") ? "deepseek" : "chatgpt";
  const recorded = new Set();
  let baselineReady = false;
  let armedEmpty = false;
  let stableSince = 0;
  let lastKey = "";
  let retryAt = 0;
  let toldToLogin = false;
  let startedAt = Date.now();

  function pairId(pair) {
    return `${pair.prompt}\u0000${pair.response}`;
  }

  function markExisting(pairs, generating) {
    pairs.forEach((pair, index) => {
      const live = generating && index === pairs.length - 1;
      if (!live) recorded.add(pairId(pair));
    });
  }

  function hashTurn(pair, model) {
    const canon = ataCanonical({
      site,
      model,
      prompt: pair.prompt,
      response: pair.response,
    });
    const bytes = new TextEncoder().encode(canon.text);
    return {
      canon,
      hash: ataSha256Hex(bytes),
      byteLength: bytes.length,
    };
  }

  function toast(text) {
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
      (document.documentElement || document.body).appendChild(el);
    }
    el.textContent = text;
    el.style.display = "block";
    clearTimeout(el._hide);
    el._hide = setTimeout(() => {
      el.style.display = "none";
    }, 1000);
  }

  async function tick() {
    if (Date.now() < retryAt) return;
    let messages = [];
    let model = site === "deepseek" ? "DeepSeek" : "ChatGPT";
    let generating = false;
    try {
      messages = ataReadMessages(document, site);
      model = ataReadModel(document, site);
      generating = ataIsGenerating(document);
    } catch (_err) {
      return;
    }
    const pairs = ataPairMessages(messages);
    const last = pairs[pairs.length - 1];
    const key = last ? `${pairs.length}:${last.prompt.length}:${last.response.length}:${last.response.slice(-32)}` : "";
    const now = Date.now();
    if (key !== lastKey) {
      lastKey = key;
      stableSince = now;
    }
    const stable = now - stableSince >= 1000;

    if (!baselineReady) {
      if (!pairs.length) {
        if (now - startedAt >= 2500) {
          baselineReady = true;
          armedEmpty = true;
        }
        return;
      }
      if (generating || !stable) return;
      markExisting(pairs, false);
      baselineReady = true;
      return;
    }

    if (armedEmpty) {
      if (!pairs.length) return;
      if (pairs.length > 1) {
        markExisting(pairs, generating);
        armedEmpty = false;
        return;
      }
      armedEmpty = false;
    }

    if (!last || generating || !stable) return;
    if (recorded.has(pairId(last))) return;
    const packed = hashTurn(last, model);
    if (!packed.canon.prompt || !packed.canon.response) return;
    recorded.add(pairId(last));
    let res = null;
    try {
      res = await chrome.runtime.sendMessage({
        type: "record",
        hash: packed.hash,
        byteLength: packed.byteLength,
        title: packed.canon.title,
        filenameHint: packed.canon.filenameHint,
      });
    } catch (_err) {
      recorded.delete(pairId(last));
      retryAt = Date.now() + 5000;
      return;
    }
    if (!res || !res.ok) {
      recorded.delete(pairId(last));
      retryAt = Date.now() + 5000;
      if (res && res.reason === "login" && !toldToLogin) {
        toldToLogin = true;
        toast("请先点击扩展图标登录");
      }
      return;
    }
    if (!res.duplicate) toast("已见证");
  }

  setInterval(() => {
    tick().catch(() => undefined);
  }, 500);
})();
