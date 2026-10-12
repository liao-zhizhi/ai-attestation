/* 把一轮对话收成稳定文本，再交给 SHA-256。原文只留在这个函数的返回值里，调用方哈希后即丢弃。 */
(function (root) {
  function clean(value) {
    return String(value || "").replace(/\r\n/g, "\n").trim();
  }

  function ataCanonical(turn) {
    const site = turn && turn.site === "deepseek" ? "deepseek" : "chatgpt";
    const fallback = site === "deepseek" ? "DeepSeek" : "ChatGPT";
    const model = clean(turn && turn.model).replace(/\s+/g, " ").slice(0, 80) || fallback;
    const prompt = clean(turn && turn.prompt);
    const response = clean(turn && turn.response);
    const text = `site=${site}\nmodel=${model}\n---\nUSER:\n${prompt}\n---\nASSISTANT:\n${response}\n`;
    const label = site === "deepseek" ? "DeepSeek" : "ChatGPT";
    return {
      site,
      model,
      prompt,
      response,
      text,
      title: `${label} · ${model}`.slice(0, 200),
      filenameHint: site === "deepseek" ? "deepseek-turn" : "chatgpt-turn",
    };
  }

  /** items: [{ role: "user"|"assistant", text }]，按页面从上到下。 */
  function ataPairMessages(items) {
    const pairs = [];
    let prompt = null;
    for (const item of items || []) {
      if (!item) continue;
      const text = clean(item.text);
      if (!text) continue;
      if (item.role === "user") prompt = text;
      else if (item.role === "assistant" && prompt) {
        pairs.push({ prompt, response: text });
        prompt = null;
      }
    }
    return pairs;
  }

  root.ataCanonical = ataCanonical;
  root.ataPairMessages = ataPairMessages;
})(globalThis);
