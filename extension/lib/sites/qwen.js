/* 通义千问（qianwen.com）。先用精确节点；页面上没有这些节点时，退回回车后抓取可见文本。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;

  /* 输入框。回车或点发送时从这里读提问；读完页面通常会清空。 */
  const INPUT_SELECTOR = "textarea.message-input-textarea";
  /* 发送按钮。点它等同于回车。只认这个类，避免误点别的按钮。 */
  const SEND_SELECTOR = ".message-input-right-button-send";
  /* 回答结束。这个按钮出现，表示本轮回答已经写完，可以记指纹。 */
  const DONE_SELECTOR = ".copy-response-button";
  /* 回答正文。要同时有 phase-answer，生成过程中的别的阶段不算。 */
  const ANSWER_SELECTOR = ".response-message-content.phase-answer";
  /* 用户提问。输入框被清空后，用最后一条提问补上原文。 */
  const QUESTION_SELECTOR = "[data-chat-list-key$='-question']";

  root.ataRegisterSite({
    id: "qwen",
    label: "通义千问",
    filenameHint: "qwen-turn",
    hosts: ["qianwen.com", "www.qianwen.com", "tongyi.aliyun.com", "www.tongyi.com", "qianwen.aliyun.com"],
    modelNeedles: ["Qwen", "通义", "千问", "模型", "Model"],
    selectors: [
      INPUT_SELECTOR,
      SEND_SELECTOR,
      DONE_SELECTOR,
      ANSWER_SELECTOR,
      QUESTION_SELECTOR,
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

  function queryAll(doc, selector) {
    try {
      return [...doc.querySelectorAll(selector)];
    } catch (_err) {
      return [];
    }
  }

  function fieldText(el) {
    if (!el) return "";
    if ("value" in el && el.tagName !== "DIV") return String(el.value || "");
    return textOf(el);
  }

  function inputEl(doc) {
    return doc.querySelector(INPUT_SELECTOR);
  }

  function lastQuestion(doc) {
    const nodes = queryAll(doc, QUESTION_SELECTOR);
    return nodes.length ? textOf(nodes[nodes.length - 1]).slice(0, 20000) : "";
  }

  function latestAnswer(doc) {
    const nodes = queryAll(doc, ANSWER_SELECTOR).filter((el) => textOf(el));
    return nodes.length ? nodes[nodes.length - 1] : null;
  }

  function visibleText(doc) {
    const body = doc.body;
    if (!body) return "";
    return String(body.innerText || "").replace(/\r\n/g, "\n").trim().slice(0, 20000);
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

  function hasPreciseDom(doc) {
    return Boolean(doc.querySelector(INPUT_SELECTOR + "," + QUESTION_SELECTOR + "," + ANSWER_SELECTOR));
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
      const text = String(prompt || "").trim() || lastQuestion(document);
      if (!text) return;
      pending = {
        prompt: text,
        url: location.href,
        recordedAt: new Date().toISOString(),
        at: Date.now(),
        answerBefore: textOf(latestAnswer(document)),
        pageBefore: visibleText(document),
        copies: new Set(queryAll(document, DONE_SELECTOR)),
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

    function modelName() {
      try {
        const found = root.ataReadSiteModel(document, site);
        if (found && found !== "unknown") return found;
      } catch (_err) {
        /* 用站点名 */
      }
      return "通义千问";
    }

    function recordAnswer(prompt, response) {
      const canon = root.ataCanonical({
        site: site.id,
        model: modelName(),
        prompt,
        response,
      });
      pending = null;
      sendTurn(canon);
    }

    function settle() {
      if (!pending) return;
      const answerEl = latestAnswer(document);
      const answer = textOf(answerEl).slice(0, 20000);
      const freshCopy = queryAll(document, DONE_SELECTOR).some((el) => !pending.copies.has(el));
      const age = Date.now() - pending.at;
      /* 精确路径：新的复制按钮出现，并且最后一条 phase-answer 是新正文。 */
      if (freshCopy && answer && answer !== pending.answerBefore) {
        recordAnswer(pending.prompt || lastQuestion(document), answer);
        return;
      }
      /* 降级：页面上没有输入框、提问或回答节点时，DOM 停稳后记可见文本。 */
      if (!hasPreciseDom(document)) {
        const page = visibleText(document);
        if (page && page !== pending.pageBefore && age >= 1000) {
          recordAnswer(pending.prompt, page);
          return;
        }
      }
      if (age < 60000) {
        timer = setTimeout(settle, 1000);
        return;
      }
      const page = visibleText(document);
      if (page && page !== pending.pageBefore) {
        recordAnswer(pending.prompt, page);
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
        const named = inputEl(document);
        if (named) {
          if (event.target !== named && !(named.contains && named.contains(event.target))) return;
          arm(fieldText(named));
          return;
        }
        /* 没有精确输入框时，任意输入区的回车都算提交。 */
        const focused = editableOf(event.target);
        if (!focused) return;
        arm(fieldText(focused));
      },
      true
    );

    document.addEventListener(
      "click",
      (event) => {
        if (!event.target || !event.target.closest || !event.target.closest(SEND_SELECTOR)) return;
        const named = inputEl(document);
        arm(fieldText(named) || lastQuestion(document));
      },
      true
    );

    const observer = new MutationObserver(() => {
      if (!pending) return;
      clearTimeout(timer);
      timer = setTimeout(settle, 1000);
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
