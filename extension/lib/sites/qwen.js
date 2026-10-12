/* 通义千问（qianwen.com）。
   页面是 Tailwind 原子类，class 一改版就失效，所以不靠 class 名。
   输入框是 contenteditable 的 div，没有稳定的发送按钮，用回车当作提交。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;

  /* 实际探查：提问框是 DIV[contenteditable=true]，不是 textarea。 */
  const INPUT_SELECTOR = '[contenteditable="true"]';
  /* 回答停稳再记。生成过程中 DOM 会连续变，静默 1.5 秒视为本轮结束。 */
  const QUIET_MS = 1500;

  root.ataRegisterSite({
    id: "qwen",
    label: "通义千问",
    filenameHint: "qwen-turn",
    hosts: ["qianwen.com", "www.qianwen.com", "tongyi.aliyun.com", "www.tongyi.com", "qianwen.aliyun.com"],
    modelNeedles: ["Qwen", "通义", "千问"],
    selectors: [INPUT_SELECTOR],
  });

  function textOf(el) {
    if (!el) return "";
    return String(el.innerText || el.textContent || "").replace(/\r\n/g, "\n").trim();
  }

  /* 模型名写在回答区顶部，例如 Qwen3.7-千问。匹配不到就用站点名。 */
  function readModel(doc) {
    const text = textOf(doc.body).slice(0, 8000);
    const specific = text.match(/Qwen[\d.]*-千问/);
    if (specific) return specific[0].slice(0, 80);
    const loose = text.match(/Qwen[^\s，。,.]*/);
    if (loose && loose[0].length >= 4 && loose[0].length < 40) return loose[0];
    return "通义千问";
  }

  /* 模型名节点本身很短。整页也包含这几个字，所以只收短文本，避免选中 body。 */
  function modelLabel(doc) {
    const nodes = doc.querySelectorAll("div, span, p, button");
    let best = null;
    let bestLen = 80;
    for (const el of nodes) {
      const raw = textOf(el);
      if (!raw || raw.length >= bestLen) continue;
      if (/Qwen[\d.]*-千问/.test(raw) || /^Qwen\b/.test(raw)) {
        best = el;
        bestLen = raw.length;
      }
    }
    return best;
  }

  /* 从模型名往上找最近的、装得下对话的 div。不使用页面上的 Tailwind class。 */
  function containerFromLabel(label, prompt) {
    let fallback = null;
    let node = label ? label.parentElement : null;
    while (node && node.tagName !== "BODY") {
      if (node.tagName === "DIV" && textOf(node).length > 50) {
        if (!fallback) fallback = node;
        if (prompt && textOf(node).indexOf(prompt) !== -1) return node;
      }
      node = node.parentElement;
    }
    return fallback;
  }

  /* 没有模型名时：在不包含输入框的块里，挑文本够长、又离输入框最近的那个。 */
  function containerNearInput(doc, input) {
    if (!input || !input.getBoundingClientRect) return null;
    const inputRect = input.getBoundingClientRect();
    let best = null;
    let bestDist = Infinity;
    const divs = doc.querySelectorAll("div");
    for (const el of divs) {
      if (el.contains(input) || textOf(el).length < 50) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 40 || rect.height < 16) continue;
      const dist = Math.abs(inputRect.top - rect.bottom);
      if (dist < bestDist) {
        bestDist = dist;
        best = el;
      }
    }
    return best;
  }

  function findContainer(doc, input, prompt) {
    const fromModel = containerFromLabel(modelLabel(doc), prompt);
    if (fromModel) return fromModel;
    return containerNearInput(doc, input);
  }

  /* 容器里模型名和提问之后的最后一段，当作这一轮回答。 */
  function answerIn(container, prompt, input) {
    if (!container) return "";
    let text = textOf(container);
    const typed = input && container.contains(input) ? textOf(input) : "";
    if (typed) text = text.split(typed).join("");
    text = text.replace(/Qwen[\d.]*-千问/g, "");
    if (prompt) {
      const at = text.lastIndexOf(prompt);
      if (at !== -1) text = text.slice(at + prompt.length);
    }
    return text.replace(/\n{3,}/g, "\n\n").trim().slice(0, 20000);
  }

  /* 窄的可编辑节点多半是标题，不是底部提问框。 */
  function composerOf(target) {
    if (!target || !target.closest) return null;
    const el = target.closest(INPUT_SELECTOR);
    if (!el || !el.getBoundingClientRect) return el;
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.width < 80) return null;
    return el;
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

    function arm(input, prompt) {
      const text = String(prompt || "").trim();
      if (!text) return;
      pending = {
        prompt: text,
        input,
        url: location.href,
        recordedAt: new Date().toISOString(),
        at: Date.now(),
        answerBefore: answerIn(findContainer(document, input, text), text, input),
      };
      clearTimeout(timer);
      timer = setTimeout(settle, QUIET_MS);
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
      const answer = answerIn(findContainer(document, pending.input, pending.prompt), pending.prompt, pending.input);
      const fresh = answer && answer !== pending.prompt && answer !== pending.answerBefore;
      if (fresh) {
        const canon = root.ataCanonical({
          site: site.id,
          model: readModel(document),
          prompt: pending.prompt,
          response: answer,
        });
        pending = null;
        sendTurn(canon);
        return;
      }
      /* 回答还没写出来时先等。页面一直没有新正文，60 秒后只记提问。 */
      if (Date.now() - pending.at < 60000) {
        timer = setTimeout(settle, QUIET_MS);
        return;
      }
      /* 回答区对不上时，只记提问、页面地址和时间，模型名用通义千问。 */
      const canon = root.ataCanonical({
        site: site.id,
        model: "通义千问",
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
        /* Shift+Enter 是换行。输入法选字时的 Enter 也不是提交。 */
        if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
        const input = composerOf(event.target);
        if (!input) return;
        arm(input, textOf(input));
      },
      true
    );

    const observer = new MutationObserver((mutations) => {
      if (!pending) return;
      const input = pending.input;
      const outside = mutations.some((mutation) => {
        const node = mutation.target;
        if (!input || !node) return true;
        return node !== input && !(input.contains && input.contains(node));
      });
      if (!outside) return;
      clearTimeout(timer);
      timer = setTimeout(settle, QUIET_MS);
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
