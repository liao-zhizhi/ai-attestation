/* 智谱 / Kimi / 通义 / 文心。ChatGPT 和 DeepSeek 仍走 content.js，不经过这里。 */
(function () {
  const site = globalThis.ataMatchSite && ataMatchSite(location.hostname);
  if (!site || typeof ataWatchSite !== "function") return;
  ataWatchSite(site);
})();
