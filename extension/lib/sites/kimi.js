/* Kimi。选择器是通用猜测，待在 kimi.moonshot.cn / kimi.com 上核对。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;
  root.ataRegisterSite({
    id: "kimi",
    label: "Kimi",
    filenameHint: "kimi-turn",
    hosts: ["kimi.moonshot.cn", "kimi.com", "www.kimi.com"],
    modelNeedles: ["Kimi", "Moonshot", "模型", "Model"],
    selectors: [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ],
  });
})(globalThis);
