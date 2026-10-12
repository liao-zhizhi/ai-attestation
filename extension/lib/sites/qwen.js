/* 通义千问。优先用页面上的输入框、发送按钮和回答容器；对不上时退回回车 + 可见文本。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;

  const INPUT_SELECTORS = ["textarea.message-input-textarea", "[class*='message-input']"];
  const ANSWER_SELECTORS = [".response-message-content", "[class*='response-message']"];
  const DONE_SELECTORS = [".copy-response-button", "[class*='copy']"];

  root.ataRegisterSite({
    id: "qwen",
    label: "通义千问",
    filenameHint: "qwen-turn",
    hosts: ["qianwen.com", "www.qianwen.com", "tongyi.aliyun.com", "www.tongyi.com", "qianwen.aliyun.com"],
    modelNeedles: ["Qwen", "通义", "千问", "模型", "Model"],
    selectors: INPUT_SELECTORS.concat(ANSWER_SELECTORS, [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ]),
  });

  function textOf(el) {
    if (!el) return "";
    return String(el.innerText || el.textContent || "").replace(/\r\n/g, "\n").trim();
  }

  function queryAll(doc, selectors) {
    const found = [];
    selectors.forEach((sel) => {
      try {
        doc.querySelectorAll(sel).forEach((el) => {
          if (found.indexOf(el) === -1) found.push(el);
        });
      } catch (_err) {
        /* 选择器写错时跳过，继续用剩下的 */
      }
    });
    return found;
  }

  function lastText(doc, selectors) {
    const nodes = queryAll(doc, selectors).filter((el) => textOf(el) && !(el.closest && el.closest("textarea, input")));
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

  function inputEl(doc) {
    const nodes = queryAll(doc, INPUT_SELECTORS).filter((el) => {
      const tag = el.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT") return true;
      const editable = el.getAttribute && el.getAttribute("contenteditable");
      return editable === "" || editable === "true";
    });
    return nodes.length ? nodes[nodes.length - 1] : null;
  }

  function sendButton(target) {
    if (!target || !target.closest) return null;
    const specific = target.closest(".message-input-right-button-send");
    if (specific) return specific;
    const broad = target.closest("[class*='send']");
    if (!broad) return null;
    if (broad.tagName === "BUTTON" || broad.getAttribute("role") === "button") return broad;
    return null;
  }

  function editableOf(target) {
    if (!target || !target.closest) return null;
    return target.closest("textarea, input, [contenteditable='true'], [contenteditable='']");
  }

  function watchQwen(site) {
    if (root.__ataQwenWatch) return;
    root.__ataQwenWatch = true;
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
        answerBefore: lastText(document, ANSWER_SELECTORS),
        pageBefore: visibleText(document),
        doneBefore: queryAll(document, DONE_SELECTORS).length,
      };
      clearTimeout(timer);
      timer = setTimeout(settle, 1000);
    }

    async function sendTurn(canon) {
      if (!canon.prompt) return;
      if (!canon.degraded && !canon.response) return;
      const bytes = new TextEncoder().encode(canon.text);
      const hash = root.ataSha256Hex(bytes);
      const key = `${canon.prompt}\u0000${canon.response}`;
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

    function modelName() {
      try {
        const found = root.ataReadSiteModel(document, site);
        if (found && found !== "unknown") return found;
      } catch (_err) {
        /* 用站点名 */
      }
      return "通义千问";
    }

    function settle() {
      if (!pending) return;
      const answer = lastText(document, ANSWER_SELECTORS);
      const page = visibleText(document);
      const done = queryAll(document, DONE_SELECTORS).length;
      const age = Date.now() - pending.at;
      const copied = done > pending.doneBefore;
      if (answer && answer !== pending.answerBefore && (copied || age >= 1000)) {
        const canon = root.ataCanonical({
          site: site.id,
          model: modelName(),
          prompt: pending.prompt,
          response: answer,
        });
        pending = null;
        sendTurn(canon);
        return;
      }
      const hasAnswerNode = queryAll(document, ANSWER_SELECTORS).length > 0;
      if (!hasAnswerNode && page && page !== pending.pageBefore && age >= 3000) {
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
        response: "",
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
        const focused = editableOf(event.target);
        if (!focused) return;
        const named = inputEl(document);
        if (named && focused !== named && !(named.contains && named.contains(focused))) return;
        arm(fieldText(focused));
      },
      true
    );

    document.addEventListener(
      "click",
      (event) => {
        if (!sendButton(event.target)) return;
        const named = inputEl(document);
        const focused = editableOf(document.activeElement);
        const field = focused && (!named || focused === named || (named.contains && named.contains(focused))) ? focused : named;
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
    if (site && site.id === "qwen") {
      watchQwen(site);
      return;
    }
    if (typeof previousWatch === "function") previousWatch(site);
  };
})(globalThis);
