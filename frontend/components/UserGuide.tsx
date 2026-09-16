"use client";

type Props = {
  proxyUrl: string;
  githubUrl?: string;
};

/**
 * 操作手册 — 文案必须与侧边栏 / 页面按钮完全一致。
 */
export function UserGuide({
  proxyUrl,
  githubUrl = "https://github.com/liao-zhizhi/ai-attestation",
}: Props) {
  const displayProxy = proxyUrl || "http://127.0.0.1:8004/v1/proxy";

  const py = `from openai import OpenAI

# ① 两处都要换成你自己的（不要填反）
ATA_KEY = "ata_xxxxxx"       # 「Key 管理」里生成的见证 Key
UPSTREAM_KEY = "sk-xxxxxx"   # 上游厂商 Key（DeepSeek / OpenAI 等，不要带 Bearer 前缀）

client = OpenAI(
    # ② 左侧底部「复制代理 URL」得到的地址（与「设置」里 base_url 相同）
    base_url="${displayProxy}",
    api_key=UPSTREAM_KEY,              # ← 上游 sk-xxxxxx
    default_headers={
        "X-Attest-Key": ATA_KEY,       # ← ata_xxxxxx
    },
)

resp = client.chat.completions.create(
    model="deepseek-chat",  # 按上游模型改名
    messages=[{"role": "user", "content": "你好，请介绍一下自己"}],
)
print(resp.choices[0].message.content)`;

  return (
    <section className="ug">
      <h2>操作手册</h2>
      <ul className="lead3">
        <li>我们只保存指纹，不上传原文</li>
        <li>请自己保存原件</li>
        <li>离线验证，不依赖任何服务器</li>
      </ul>
      <p className="lead">
        左侧菜单分两块：上面「新用户上手」（Key 管理、设置、API 调用、见证），下面「日常使用」（仪表盘、API
        调用记录、见证、监控、合规管理、防篡改证明）。最底部固定「复制代理 URL」和「操作手册」。两处「见证」是同一页。
      </p>

      <h3>第一部分：新用户四步上手</h3>
      <ol className="steps">
        <li>
          <h3>1. Key 管理</h3>
          <p>点左侧「新用户上手」里的 <strong>「Key 管理」</strong>，创建 <code>ata_xxx</code> 凭证并立刻复制保存。</p>
          <ol className="sub">
            <li>
              在输入框填写名称（占位提示：<code>输入名称，例如：我的测试</code>）
            </li>
            <li>
              点绿色按钮 <strong>「创建」</strong>
            </li>
            <li>
              出现黄色提示框 <strong>「新 Key（仅完整显示一次，请立刻复制）：」</strong>
              ，下面是一串 <code>ata_</code> 开头的完整 Key
            </li>
            <li>
              点 <strong>「复制 Key」</strong> 保存到别处
            </li>
            <li>
              若需要切换，再点 <strong>「设为当前 Key」</strong>
              （第一次创建且你还没有 Key 时，系统会自动设为当前）
            </li>
          </ol>
          <p className="tip">
            完整 Key 只完整显示一次。管理员在「已有 Key」列表里通常只看到脱敏形式（如{" "}
            <code>ata_xxxx****</code>）。点「设为当前 Key」后，再到「设置」确认并保存。
          </p>
        </li>
        <li>
          <h3>2. 设置</h3>
          <p>
            点左侧 <strong>「设置」</strong>。默认停在上方标签 <strong>「通用」</strong>
            （旁边还有「报告订阅」，新手可先不管）。
          </p>
          <ul>
            <li>
              在标签为 <strong>「API Key（X-Attest-Key）」</strong> 的输入框填入{" "}
              <code>ata_xxxxxx</code>
            </li>
            <li>
              在标签为 <strong>「Authorization（上游厂商 Key，仅本机备忘）」</strong>{" "}
              的输入框可填 <code>Bearer sk-xxxxxx</code>
              ——只保存在本浏览器，网页<strong>不会</strong>用它去调上游
            </li>
            <li>
              只读框 <strong>「base_url」</strong> 应显示代理地址，例如{" "}
              <code>{displayProxy}</code>
            </li>
            <li>
              点绿色按钮 <strong>「保存」</strong>
            </li>
          </ul>
        </li>
        <li>
          <h3>3. API 调用</h3>
          <p>
            点左侧 <strong>「API 调用」</strong>（与「日常使用」里的「API 调用记录」是同一页）。
            右上角已有 <strong>「模拟一条调用」</strong>，没有上游 Key 时可先点它写入一条演示数据。
          </p>
          <p>
            要用自己的代码：点底部 <strong>「复制代理 URL」</strong>，把 SDK 的{" "}
            <code>base_url</code> 指到该地址，不要直连厂商官网。
          </p>
          <pre className="mono">{displayProxy}</pre>
          <p>复制下面 Python 示例，只改标注处：</p>
          <ul>
            <li>
              <code>UPSTREAM_KEY</code> / <code>api_key=</code> → 上游{" "}
              <code>sk-xxxxxx</code>（不要填 <code>ata_</code>）
            </li>
            <li>
              <code>ATA_KEY</code> / <code>X-Attest-Key</code> →{" "}
              <code>ata_xxxxxx</code>
            </li>
            <li>
              <code>base_url=</code> → 与底部复制到的代理 URL 一致
            </li>
          </ul>
          <pre className="code">{py}</pre>
        </li>
        <li>
          <h3>4. 见证</h3>
          <p>
            点左侧任意一处 <strong>「见证」</strong>（上手区和日常区是同一页）。
            这里做科研优先权存证：发 AI 之前先留下指纹。
          </p>
          <p>
            某次 API 调用的证据要带离线给别人看：到 <strong>「API 调用」</strong> /{" "}
            <strong>「API 调用记录」</strong> 点开一条，弹出 <strong>「调用详情」</strong>
            ，在 <strong>「验证完整性」</strong> 旁边点 <strong>「导出验证包」</strong>
            （文件名类似 <code>ata_call_…_verify.zip</code>）。
          </p>
        </li>
      </ol>

      <h3>第二部分：日常使用六步</h3>
      <ol className="steps">
        <li>
          <strong>「仪表盘」</strong>：今日调用量、费用、链完整性。
        </li>
        <li>
          <strong>「API 调用记录」</strong>：每次调用的哈希链详情。点开一条可「验证完整性」或「导出验证包」。
        </li>
        <li>
          <strong>「见证」</strong>：科研优先权存证（发 AI 前先留指纹），详见下面第三部分。
        </li>
        <li>
          <strong>「监控」</strong>：行为漂移标记（对应原来的行为基线 / 漂移审查）。
        </li>
        <li>
          <strong>「合规管理」</strong>：EU AI Act 等检查清单，点「运行合规检查」。
        </li>
        <li>
          <strong>「防篡改证明」</strong>：给甲方 / 监管看的整链证明（可锚定链头）。
        </li>
      </ol>

      <h3>第三部分：科研优先权存证</h3>
      <p>
        <strong>什么时候用：</strong>把未发表草稿发给任何 AI 之前。
      </p>
      <p>
        <strong>怎么用：</strong>
      </p>
      <ol className="sub">
        <li>
          点左侧 <strong>「见证」</strong>
        </li>
        <li>
          点 <strong>「登记一份草稿或提示词」</strong>
        </li>
        <li>
          选择 <strong>「本地文件」</strong> 或 <strong>「粘贴文字」</strong> 或{" "}
          <strong>「我已有哈希」</strong>
        </li>
        <li>
          等页面显示 64 位哈希后，点 <strong>「写入证据链」</strong>
        </li>
        <li>
          点 <strong>「导出优先权证书」</strong>，下载 ZIP（文件名类似{" "}
          <code>ata_priority_…_cert.zip</code>），与原件放在一起保管
        </li>
      </ol>
      <p>
        <strong>离线验证：</strong>解压 ZIP，在该目录执行{" "}
        <code>python -m http.server 8765</code>，打开{" "}
        <code>http://127.0.0.1:8765/verify.html</code>，点 <strong>「运行本地验证」</strong>
        ，再用 <strong>「用原件选择文件」</strong> 上传原件比对指纹。
      </p>
      <p className="tip">
        关键说明：不能证明某家 AI 厂商训练或阅读了你的草稿，只能证明你什么时候有过这份东西。这不是法律意见。
      </p>

      <h3>第四部分：HTTPS 说明</h3>
      <ul>
        <li>
          网站已启用 HTTPS（地址栏盾牌图标）：<code>https://ai-attestation.com</code>
        </li>
        <li>HTTP 会自动跳转到 HTTPS</li>
        <li>证书有效期到 2026-12-15，自动续期</li>
        <li>不需要你做任何操作</li>
      </ul>

      <h3>第五部分：常见问题 Q&amp;A</h3>
      <dl className="qa">
        <dt>问：提示「后端不可用 / NetworkError」怎么办？</dt>
        <dd>
          答：在服务器执行 <code>ps aux | grep uvicorn</code> 确认后端在跑。
          用服务器地址打开前端。看左侧底部「复制代理 URL」旁的地址，应是该服务器的{" "}
          <code>:8004</code>
          ，而不是你电脑上的 <code>127.0.0.1</code>（除非本机同时跑了前后端）。然后强制刷新（Ctrl+Shift+R）。
        </dd>
        <dt>问：Key 创建了 / 填了但好像没用？</dt>
        <dd>
          答：在「Key 管理」确认已 <strong>「复制 Key」</strong>；若未自动切换，点{" "}
          <strong>「设为当前 Key」</strong>。再到「设置」→「通用」，确认{" "}
          <strong>「API Key（X-Attest-Key）」</strong> 里是完整 <code>ata_…</code>，并点了{" "}
          <strong>「保存」</strong>。
          「Authorization」只是备忘。写代码时：<code>api_key</code> 用上游 <code>sk-</code>，
          <code>X-Attest-Key</code> 用 <code>ata_</code>，不要填反。
        </dd>
        <dt>问：找不到「导出验证包」按钮？</dt>
        <dd>
          答：该按钮在<strong>调用详情弹窗底部</strong>，紧挨「验证完整性」。
          请先到「仪表盘」或「API 调用记录」点开某一条调用；没产生调用时可先点右上角「模拟一条调用」。
        </dd>
        <dt>问：导出的 ZIP 里为什么没有请求原文？</dt>
        <dd>
          答：系统设计为请求/响应正文只算哈希、不落库。验证包用{" "}
          <code>request_hash</code> / <code>response_hash</code> /{" "}
          <code>chain_hash</code> 做见证，可离线复核链接是否被篡改。
        </dd>
        <dt>问：右上角「模拟一条调用」点不了？ / 为什么按钮是灰色的？</dt>
        <dd>
          答：可能没保存 Key，或角色是只读 <code>read_only</code>
          。需要先在「设置」保存有效的 <code>ata_</code> Key，且角色为{" "}
          <code>read_write</code> 或 <code>admin</code>。把鼠标悬停在按钮上也可能看到提示。
        </dd>
        <dt>问：CORS / 跨域红字是什么？</dt>
        <dd>
          答：通常是前端页面主机与请求的后端主机不一致。以左侧底部显示的代理 URL 为准，强制刷新后再试。
        </dd>
        <dt>问：会不会把论文传给你们？</dt>
        <dd>
          答：默认不会；「见证」只把浏览器算好的指纹发给服务器，不上传文件内容。请自行保管原件。
        </dd>
        <dt>问：能不能证明 OpenAI 训练了？</dt>
        <dd>
          答：不能。只能证明你何时有过这份指纹。这不是法律意见，也不能证明某家厂商阅读或训练了原文。
        </dd>
        <dt>问：和「导出验证包」有什么区别？</dt>
        <dd>
          答：「导出验证包」在调用详情底部，证明某次 API 调用链接；「导出优先权证书」在「见证」，证明某份内容指纹进入证据链的时间。两套 ZIP 不要混用。
        </dd>
        <dt>问：crypto.subtle is undefined？</dt>
        <dd>
          答：已修复。登记页现在用纯 JS SHA-256，不依赖浏览器的 <code>crypto.subtle</code>
          ，在 HTTP 下也能算指纹。
        </dd>
        <dt>问：服务器拉不动代码？</dt>
        <dd>答：已配置 SSH 连接，正常。</dd>
      </dl>

      <h3>联系支持</h3>
      <p>
        若仍无法解决，请到 GitHub 仓库提交 Issue（写清复现步骤与报错原文）：
        <br />
        <a href={githubUrl} target="_blank" rel="noreferrer">
          {githubUrl}
        </a>
      </p>

      <style jsx>{`
        .ug {
          background: #111821;
          border: 1px solid #2a3b52;
          border-radius: 8px;
          padding: 18px 20px 20px;
          margin-bottom: 16px;
          color: #c5d0dc;
          line-height: 1.55;
        }
        h2 {
          margin: 0 0 8px;
          font-size: 18px;
          color: #e8eef5;
        }
        h3 {
          margin: 16px 0 8px;
          font-size: 15px;
          color: #d7e0ea;
        }
        .lead3 {
          margin: 0 0 12px;
          padding-left: 18px;
          color: #d7e0ea;
          font-size: 14px;
        }
        .lead {
          margin: 0 0 12px;
          color: #9eb2c7;
          font-size: 13px;
        }
        .steps {
          margin: 0;
          padding-left: 18px;
        }
        .steps > li {
          margin-bottom: 14px;
        }
        .steps p,
        .steps ul,
        .steps .sub {
          margin: 6px 0;
          font-size: 13px;
        }
        .sub {
          padding-left: 18px;
        }
        .sub li {
          margin-bottom: 4px;
        }
        .tip {
          color: #f0b429;
          font-size: 12px !important;
        }
        code,
        .mono {
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 12px;
          color: #3dd68c;
        }
        pre.mono,
        pre.code {
          background: #0b0f14;
          border: 1px solid #243044;
          border-radius: 6px;
          padding: 10px 12px;
          overflow: auto;
          color: #b8c7d6;
          font-size: 12px;
          line-height: 1.45;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .qa dt {
          margin-top: 10px;
          font-weight: 600;
          color: #d7e0ea;
          font-size: 13px;
        }
        .qa dd {
          margin: 4px 0 0;
          font-size: 13px;
          color: #9eb2c7;
        }
        a {
          color: #5b8def;
        }
      `}</style>
    </section>
  );
}
