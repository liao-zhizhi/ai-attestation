# AI 对话见证（Chrome 扩展，本地测试版）

在 ChatGPT 和 DeepSeek 的聊天页里，等一轮回答结束后，在你自己的浏览器里计算对话指纹，再写入已有的见证接口。对话原文不会上传。

这是开发者模式加载的测试版，不是 Chrome 网上应用店里的扩展。下面没有上架步骤。

## 现在能做的

- 点扩展图标，用邮箱和固定验证码登录，拿到一个 `ata_` 编号并保存在本机
- 在 `https://chatgpt.com`、`https://chat.openai.com`、`https://chat.deepseek.com` 上，新的一轮问答结束后右下角出现「已见证」
- 弹窗里看最近 10 条：时间、模型（写在标题里）、指纹前 12 位、是否已写入
- 点一条，打开网站上的详情页

## 还没做

- 真的发邮件验证码（现在固定是 `123456`，不会发信）
- 从扩展里导出离线验证包
- 智谱、文心一言
- 隐私政策页

固定验证码只为了在你自己的电脑上把流程跑通。知道这个码的人都可以领到一个新编号。不要把这个扩展发给普通用户，等真实验证码接上再说。

## 安装

1. 打开 Chrome，地址栏输入 `chrome://extensions` 并回车。
2. 打开右上角「开发者模式」。
3. 点「加载已解压的扩展程序」。
4. 选中本仓库的 `extension` 文件夹（里面要能直接看到 `manifest.json`）。
5. 工具栏出现「AI 对话见证」。如果没看到，点拼图图标把它固定出来。

改完代码后，回到 `chrome://extensions`，在这张卡片上点刷新。

## 登录

1. 点扩展图标。
2. 默认接口地址是网站正在用的 `http://47.119.118.245:8004`。本机另起了后端时，打开底部「服务器地址」，改成 `http://127.0.0.1:8004`，点「保存地址」。
3. 填写邮箱，点「发送验证码」。不会有邮件。
4. 验证码填 `123456`，点「登录」。
5. 登录成功后弹窗显示「已登录」。编号只存在这台浏览器的扩展存储里。

每次点登录都会向 `POST /v1/keys` 再要一个新编号。退出登录只是从这台浏览器删掉它，服务器上的编号还在。

## 在聊天页测试

先登录，再打开聊天页。扩展不会把你打开页面时已经存在的旧对话全部记进去，只记登录之后新完成的一轮。

1. 打开 [ChatGPT](https://chatgpt.com) 或 [DeepSeek](https://chat.deepseek.com)，并处于已登录、能正常发消息的状态。
2. 新开一轮，发送一句话，等回答完全停住。
3. 大约 1 秒后，页面右下角应出现绿色「已见证」，再过 1 秒消失。
4. 再点扩展图标。列表里应有一条新记录：时间、类似 `ChatGPT · …` 或 `DeepSeek · …` 的标题、12 位指纹、状态「已写入」。
5. 点这条记录。线上接口会打开 `https://ai-attestation.com/verify/artifact/…`。本机接口会打开 `http://127.0.0.1:3002/verify/artifact/…`（需要本机前端也在跑）。

没登录就聊天时，页面只提示一次「请先点击扩展图标登录」，这一轮不会补记。

## 它实际发送了什么

本地用纯 JS SHA-256 计算指纹，算法结果与 Python `hashlib.sha256` 一致。发给 `POST /v1/research/artifacts` 的只有：

- 标题，例如 `ChatGPT · GPT-4o`（用来在列表里显示模型）
- 64 位指纹
- 参与计算的字节数
- 文件名提示 `chatgpt-turn` 或 `deepseek-turn`

不发送提问和回答的正文。列表来自已有的 `GET /v1/research/artifacts`。点开详情时调用已有的公开链接接口，拿到网页地址。

指纹对应的文本格式是：

```text
site=chatgpt
model=模型名
---
USER:
提问
---
ASSISTANT:
回答
```

## 没出现「已见证」时

1. 确认扩展已启用，并且是在 `chatgpt.com` 或 `chat.deepseek.com`，不是别的镜像站。
2. 确认已经登录，服务器地址能打开。浏览器直接访问 `http://127.0.0.1:8004/health` 或线上的 `/health`，应看到 `"ok": true`。
3. 在聊天页按 F12，看 Console 里有没有扩展报错。
4. 网站改版后，消息节点可能对不上。在开发者工具里检查：
   - ChatGPT 的一条消息上还应有 `data-message-author-role="user"` 或 `"assistant"`。
   - DeepSeek 的回答区域还应有 `ds-markdown`，思考过程在 `ds-think-content` 里（这段不计入正文）。
5. 对上之后改 `extension/lib/read.js`，回到扩展页点刷新，再试一次。

## 文件

```text
extension/
├── manifest.json
├── popup.html
├── popup.js
├── content.js
├── background.js
├── lib/
│   ├── sha256.js
│   ├── record.js
│   ├── read.js
│   └── api.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md
```
