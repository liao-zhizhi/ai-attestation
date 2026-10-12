console.log("[AI-Attest] content script 已加载，当前 URL:", location.href);
/* 智谱 / Kimi / 通义 / 文心。ChatGPT 和 DeepSeek 仍走 content.js，不经过这里。 */
(function () {
  const site = globalThis.ataMatchSite && ataMatchSite(location.hostname);
  console.log("[AI-Attest] 匹配站点:", site && site.id);
  if (!site || typeof ataWatchSite !== "function") return;
  ataWatchSite(site);
})();
