# AI 对话见证（Chrome 扩展，本地测试版）

在聊天页里，等一轮回答结束后，在你自己的浏览器里计算对话指纹，再写入已有的见证接口。对话原文不会上传。

这是开发者模式加载的测试版，不是 Chrome 网上应用店里的扩展。下面没有上架步骤。

## 现在能做的

- 点扩展图标，用邮箱和固定验证码登录，拿到一个 `ata_` 编号并保存在本机
- 在下面表格里的站点上，新的一轮问答结束后右下角出现「已见证」
- 弹窗右上角可以退出登录。这会清掉扩展里的编号，并清掉 `ai-attestation.com` 上的 `ata_mvp_api_key`
- 弹窗里看最近 10 条：时间、模型（写在标题里）、指纹前 12 位、是否已写入
- 点一条，打开网站上的详情页。点「导出」，下载 `ata_priority_art_…_cert.zip`
- 退出登录后弹窗回到未登录状态，并提示「已退出」

## 站点状态

| 站点 | 状态 |
| --- | --- |
| DeepSeek（`chat.deepseek.com`） | 实测通过 |
| ChatGPT（`chatgpt.com`、`chat.openai.com`） | 代码完成，选择器按页面结构写过，待你本机再确认 |
| 智谱清言（`chatglm.cn`、`chat.z.ai`） | 代码完成，待用户测试 |
| Kimi（`kimi.moonshot.cn`、`kimi.com`） | 代码完成，待用户测试 |
| 通义千问（`qianwen.com`，以及 `tongyi.aliyun.com`） | 代码完成，待用户测试。优先认回答容器，对不上就记可见文本 |
| 文心一言（`wenxin.baidu.com`，以及 `yiyan.baidu.com`） | 代码完成，待用户测试。回车后等页面稳定，再对可见文本做指纹 |

ChatGPT 和 DeepSeek 用各自的页面选择器。后四个站点各自一个文件（`extension/lib/sites/`），共用同一套做法：常见消息容器、回车提交、页面变化停 1 秒后再记。读不到完整问答时，只记提问的指纹、页面地址和时间，模型名写成 `unknown`。

## 还没做

- 真的发邮件验证码（现在固定是 `123456`，不会发信）
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
5. 登录成功后弹窗显示「已登录」，并把同一个编号写入 `ai-attestation.com` 的本地存储（键名 `ata_mvp_api_key`，与网站「当前账号」相同）。若当时已经打开网站，那个页面会刷新一次。之后打开网站，左侧「存证账号」应是这一编号。

每次点登录都会向 `POST /v1/keys` 再要一个新编号。点右上角「退出登录」会从扩展存储里删掉编号，并在 `ai-attestation.com` 的页面里删掉 `ata_mvp_api_key`。当时已经打开网站时，那个页面会刷新一次。服务器上的编号还在。

## 在聊天页测试

先登录，再打开聊天页。扩展不会把你打开页面时已经存在的旧对话全部记进去，只记登录之后新完成的一轮。

1. 打开 [DeepSeek](https://chat.deepseek.com)（已实测）或 [ChatGPT](https://chatgpt.com)，并处于已登录、能正常发消息的状态。智谱、Kimi、通义、文心也可以按同样步骤试，这四个还没在真实页面上对过选择器。
2. 新开一轮，发送一句话，等回答完全停住。
3. 大约 1 秒后，页面右下角应出现绿色「已见证」，再过 1 秒消失。
4. 再点扩展图标。列表里应有一条新记录：时间、类似 `DeepSeek · …` 的标题、12 位指纹、状态「已写入」。
5. 点这条记录。线上接口会打开 `https://ai-attestation.com/verify/artifact/…`。本机接口会打开 `http://127.0.0.1:3002/verify/artifact/…`（需要本机前端也在跑）。
6. 点这条记录旁边的「导出」。浏览器应下载 `ata_priority_art_…_cert.zip`。
7. 点右上角「退出登录」。弹窗回到邮箱登录，并显示「已退出」。再打开网站，左侧不应再是刚才那个编号。

没登录就聊天时，页面只提示一次「请先点击扩展图标登录」，这一轮不会补记。

## 它实际发送了什么

本地用纯 JS SHA-256 计算指纹，算法结果与 Python `hashlib.sha256` 一致。发给 `POST /v1/research/artifacts` 的只有：

- 标题，例如 `ChatGPT · GPT-4o`（用来在列表里显示模型）
- 64 位指纹
- 参与计算的字节数
- 文件名提示，例如 `deepseek-turn`、`chatgpt-turn`、`kimi-turn`

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
5. 对上之后改对应文件，回到扩展页点刷新，再试一次。ChatGPT / DeepSeek 改 `extension/lib/read.js`。智谱、Kimi、通义、文心分别改 `extension/lib/sites/zhipu.js`、`kimi.js`、`qwen.js`、`yiyan.js` 里的 `selectors`。

## 文件

```text
extension/
├── manifest.json
├── popup.html
├── popup.js
├── content.js
├── content-generic.js
├── background.js
├── lib/
│   ├── sha256.js
│   ├── record.js
│   ├── read.js
│   ├── api.js
│   └── sites/
│       ├── generic.js
│       ├── zhipu.js
│       ├── kimi.js
│       ├── qwen.js
│       └── yiyan.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md
```
