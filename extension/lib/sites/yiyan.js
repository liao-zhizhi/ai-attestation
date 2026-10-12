/* 文心一言。选择器是通用猜测，待在 yiyan.baidu.com 上核对。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;
  root.ataRegisterSite({
    id: "yiyan",
    label: "文心一言",
    filenameHint: "yiyan-turn",
    hosts: ["yiyan.baidu.com"],
    modelNeedles: ["文心", "一言", "ERNIE", "模型", "Model"],
    selectors: [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ],
  });
})(globalThis);
