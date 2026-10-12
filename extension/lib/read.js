/* 从聊天页 DOM 读出角色和可见文字。选择器会随网站改版失效，README 里写了怎么核对。 */
(function (root) {
  function textOf(el) {
    if (!el) return "";
    return String(el.innerText || el.textContent || "").replace(/\r\n/g, "\n").trim();
  }

  function chatgptMessages(doc) {
    const nodes = [...doc.querySelectorAll("[data-message-author-role]")];
    return nodes
      .map((el) => {
        const role = el.getAttribute("data-message-author-role");
        if (role !== "user" && role !== "assistant") return null;
        const content = el.querySelector(".markdown, .prose, .whitespace-pre-wrap, [class*='markdown']");
        return { role, text: textOf(content || el) };
      })
      .filter(Boolean);
  }

  function chatgptModel(doc) {
    const el = doc.querySelector('[data-testid="model-switcher"]');
    const raw = textOf(el).split("\n")[0];
    return raw ? raw.slice(0, 80) : "ChatGPT";
  }

  function outermostAnswer(row) {
    return [...row.querySelectorAll(".ds-markdown")].filter((el) => {
      if (el.closest(".ds-think-content")) return false;
      const parent = el.parentElement;
      if (parent && parent.closest(".ds-markdown")) return false;
      return true;
    });
  }

  function classifyDeepseekRow(row) {
    const answers = outermostAnswer(row);
    const thinking = row.querySelector(".ds-think-content");
    if (answers.length || thinking || row.querySelector(".ds-markdown")) {
      return { role: "assistant", text: answers.map((el) => textOf(el)).filter(Boolean).join("\n\n") };
    }
    const userEl = row.querySelector(".fbb737a4, .ds-collapsible-text");
    const text = textOf(userEl || row);
    if (!text) return null;
    return { role: "user", text };
  }

  function deepseekMessages(doc) {
    const rows = [...doc.querySelectorAll("[data-virtual-list-item-key]")];
    const source = rows.length ? rows : [...doc.querySelectorAll(".ds-message")];
    if (source.length) {
      return source.map(classifyDeepseekRow).filter(Boolean);
    }
    const bits = [];
    doc.querySelectorAll(".fbb737a4, .ds-markdown").forEach((el) => {
      if (el.closest(".ds-think-content")) return;
      if (el.classList.contains("ds-markdown") && el.parentElement && el.parentElement.closest(".ds-markdown")) {
        return;
      }
      const role = el.classList.contains("ds-markdown") ? "assistant" : "user";
      const text = textOf(el);
      if (text) bits.push({ role, text });
    });
    return bits;
  }

  function deepseekModel(doc) {
    const header = doc.querySelector("header") || doc.body || doc;
    const nodes = [...header.querySelectorAll("button, [role='button']")].slice(0, 12);
    for (const node of nodes) {
      const raw = textOf(node).split("\n")[0];
      if (raw && /deepseek|reasoner|\bv3\b|\br1\b/i.test(raw) && raw.length < 40) return raw.slice(0, 80);
    }
    return "DeepSeek";
  }

  function ataIsGenerating(doc) {
    if (doc.querySelector('[data-testid="stop-button"], [data-testid="stop-generating"]')) return true;
    const buttons = doc.querySelectorAll("button");
    for (const button of buttons) {
      const label = String(button.getAttribute("aria-label") || "").trim().toLowerCase();
      if (label === "stop" || label === "stop streaming" || label.includes("停止生成")) return true;
    }
    return false;
  }

  function ataReadMessages(doc, site) {
    return site === "deepseek" ? deepseekMessages(doc) : chatgptMessages(doc);
  }

  function ataReadModel(doc, site) {
    return site === "deepseek" ? deepseekModel(doc) : chatgptModel(doc);
  }

  root.ataIsGenerating = ataIsGenerating;
  root.ataReadMessages = ataReadMessages;
  root.ataReadModel = ataReadModel;
})(globalThis);
