/* 文心一言。页面结构还没在真实环境里核对，先用回车 + 页面稳定后的可见文本。
   精确选择器留在 PRECISE 里，确认节点后再填，填了会优先于整页文本。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;

  /* 以后按 wenxin.baidu.com 的真实节点补充，例如：
     input: ["textarea.chat-input"]
     answer: [".answer-content"]
     done: [".answer-done"]
     留空时走降级：回车提交，DOM 停 1 秒，对可见文本做指纹。 */
  const PRECISE = {
    input: [],
    answer: [],
    done: [],
  };

  root.ataRegisterSite({
    id: "yiyan",
    label: "文心一言",
    filenameHint: "yiyan-turn",
    hosts: ["wenxin.baidu.com", "www.wenxin.baidu.com", "yiyan.baidu.com"],
    modelNeedles: ["文心", "一言", "ERNIE", "模型", "Model"],
    selectors: [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ],
  });

  function textOf(el) {
    if (!el) return "";
    return String(el.innerText || el.textContent || "").replace(/\r\n/g, "\n").trim();
  }

  function queryAll(doc, selectors) {
    const found = [];
    (selectors || []).forEach((sel) => {
      try {
        doc.querySelectorAll(sel).forEach((el) => {
          if (found.indexOf(el) === -1) found.push(el);
        });
      } catch (_err) {
        /* 选择器尚未填写或写错时忽略 */
      }
    });
    return found;
  }

  function lastText(doc, selectors) {
    const nodes = queryAll(doc, selectors).filter((el) => textOf(el));
    return nodes.length ? textOf(nodes[nodes.length - 1]).slice(0, 20000) : "";
  }

  function visibleText(doc) {
    const body = doc.body;
    if (!body) return "";
    return String(body.innerText || "").replace(/\r\n/g, "\n").trim().slice(0, 20000);
  }

  function fieldText(el) {
    if (!el) return "";
    if ("value" in el && el.tagName !== "DIV") return String(el.value || "");
    return textOf(el);
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

  /* 目前没有可靠的模型节点，主机名已经说明是文心一言。
     PRECISE 补上模型节点后：读到文字就用那段文字，读不到再返回 "unknown"。 */
  function modelName() {
    return "文心一言";
  }

  function watchYiyan(site) {
    if (root.__ataYiyanWatch) return;
    root.__ataYiyanWatch = true;
    const recorded = new Set();
    let pending = null;
    let timer = 0;
    let toldToLogin = false;

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

    function arm(prompt) {
      const text = String(prompt || "").trim();
      if (!text) return;
      pending = {
        prompt: text,
        url: location.href,
        recordedAt: new Date().toISOString(),
        at: Date.now(),
        answerBefore: lastText(document, PRECISE.answer),
        pageBefore: visibleText(document),
      };
      clearTimeout(timer);
      timer = setTimeout(settle, 1000);
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
      const precise = lastText(document, PRECISE.answer);
      const page = visibleText(document);
      const age = Date.now() - pending.at;
      if (precise && precise !== pending.answerBefore) {
        const canon = root.ataCanonical({
          site: site.id,
          model: modelName(),
          prompt: pending.prompt,
          response: precise,
        });
        pending = null;
        sendTurn(canon);
        return;
      }
      if (!PRECISE.answer.length && page && page !== pending.pageBefore && age >= 1000) {
        const canon = root.ataCanonical({
          site: site.id,
          model: modelName(),
          prompt: pending.prompt,
          response: page,
        });
        pending = null;
        sendTurn(canon);
        return;
      }
      if (age < 60000) {
        timer = setTimeout(settle, 1000);
        return;
      }
      const canon = root.ataCanonical({
        site: site.id,
        model: "unknown",
        prompt: pending.prompt,
        response: page,
        degraded: true,
        url: pending.url,
        recordedAt: pending.recordedAt,
      });
      pending = null;
      sendTurn(canon);
    }

    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Enter" || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey || event.isComposing) {
          return;
        }
        const preciseInput = queryAll(document, PRECISE.input).pop();
        const field = preciseInput || editableOf(event.target);
        if (!field) return;
        arm(fieldText(field));
      },
      true
    );

    const observer = new MutationObserver(() => {
      if (pending) {
        clearTimeout(timer);
        timer = setTimeout(settle, 1000);
      }
    });
    const watchRoot = document.documentElement || document.body;
    if (watchRoot) observer.observe(watchRoot, { childList: true, subtree: true, characterData: true });
  }

  const previousWatch = root.ataWatchSite;
  root.ataWatchSite = function (site) {
    if (site && site.id === "yiyan") {
      watchYiyan(site);
      return;
    }
    if (typeof previousWatch === "function") previousWatch(site);
  };
})(globalThis);
