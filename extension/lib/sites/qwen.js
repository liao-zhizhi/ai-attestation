/* 通义千问。选择器是通用猜测，待在 tongyi.aliyun.com 上核对。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;
  root.ataRegisterSite({
    id: "qwen",
    label: "通义千问",
    filenameHint: "qwen-turn",
    hosts: ["tongyi.aliyun.com", "www.tongyi.com", "qianwen.aliyun.com"],
    modelNeedles: ["Qwen", "通义", "千问", "模型", "Model"],
    selectors: [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ],
  });
})(globalThis);
