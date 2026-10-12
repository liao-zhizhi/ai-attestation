/* 智谱清言。选择器是通用猜测，待在 chatglm.cn / chat.z.ai 上核对。 */
(function (root) {
  if (typeof root.ataRegisterSite !== "function") return;
  root.ataRegisterSite({
    id: "zhipu",
    label: "智谱清言",
    filenameHint: "zhipu-turn",
    hosts: ["chatglm.cn", "www.chatglm.cn", "chat.z.ai"],
    modelNeedles: ["GLM", "ChatGLM", "智谱", "清言", "模型", "Model"],
    selectors: [
      "[class*='message']",
      "[class*='chat']",
      "[class*='markdown']",
      "[class*='conversation']",
      "[class*='dialog']",
    ],
  });
})(globalThis);
