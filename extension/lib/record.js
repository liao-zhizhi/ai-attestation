/* 把一轮对话收成稳定文本，再交给 SHA-256。原文只留在这个函数的返回值里，调用方哈希后即丢弃。 */
(function (root) {
  const SITES = {
    chatgpt: { label: "ChatGPT", hint: "chatgpt-turn" },
    deepseek: { label: "DeepSeek", hint: "deepseek-turn" },
    zhipu: { label: "智谱清言", hint: "zhipu-turn" },
    kimi: { label: "Kimi", hint: "kimi-turn" },
    qwen: { label: "通义千问", hint: "qwen-turn" },
    yiyan: { label: "文心一言", hint: "yiyan-turn" },
  };

  function clean(value) {
    return String(value || "").replace(/\r\n/g, "\n").trim();
  }

  function ataCanonical(turn) {
    const site = SITES[turn && turn.site] ? turn.site : "chatgpt";
    const meta = SITES[site];
    const fallback = site === "chatgpt" || site === "deepseek" ? meta.label : "unknown";
    const model = clean(turn && turn.model).replace(/\s+/g, " ").slice(0, 80) || fallback;
    const prompt = clean(turn && turn.prompt);
    const response = clean(turn && turn.response);
    const degraded = Boolean(turn && turn.degraded);
    const url = clean(turn && turn.url).slice(0, 500);
    const recordedAt = clean(turn && turn.recordedAt).slice(0, 40);
    const text = degraded
      ? `site=${site}\nmodel=${model}\nurl=${url}\ntime=${recordedAt}\n---\nUSER:\n${prompt}\n---\nASSISTANT:\n${response}\n`
      : `site=${site}\nmodel=${model}\n---\nUSER:\n${prompt}\n---\nASSISTANT:\n${response}\n`;
    return {
      site,
      model,
      prompt,
      response,
      text,
      title: `${meta.label} · ${model}`.slice(0, 200),
      filenameHint: meta.hint,
      degraded,
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
