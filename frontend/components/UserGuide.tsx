"use client";

type Props = {
  proxyUrl: string;
  githubUrl?: string;
};

/**
 * Beginner-facing step-by-step handbook (Chinese) — matches live UI.
 */
export function UserGuide({
  proxyUrl,
  githubUrl = "https://github.com/liao-zhizhi/ai-attestation",
}: Props) {
  const displayProxy = proxyUrl || "http://127.0.0.1:8004/v1/proxy";

  const py = `from openai import OpenAI

# ① 两处 Key 都要换成你自己的
ATA_KEY = "ata_xxxxxx"          # 在「Key」页创建的见证 Key
UPSTREAM_KEY = "sk-xxxxxx"      # 上游厂商 Key（DeepSeek / OpenAI 等）

client = OpenAI(
    # ② base_url 用左侧「复制代理 URL」得到的地址
    base_url="${displayProxy}",
    api_key=UPSTREAM_KEY,       # ← 填上游 sk-xxxxxx（不要填 ata_）
    default_headers={
        "X-Attest-Key": ATA_KEY,  # ← 填 ata_xxxxxx
    },
)

resp = client.chat.completions.create(
    model="deepseek-chat",  # 按你的上游模型改
    messages=[{"role": "user", "content": "你好，请介绍一下自己"}],
)
print(resp.choices[0].message.content)`;

  return (
    <section className="ug">
      <h2>新手操作手册（三步上手）</h2>
      <p className="lead">
        看一眼流程图，再按下面三步点：先拿 Key → 再填设置 → 最后写代码调用。
      </p>

      <pre className="flow" aria-label="用户流程图">
{`┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  第一步      │    │  第二步      │    │  第三步      │
│  点击 Key    │ →  │  点击 设置   │ →  │  写代码调用  │
│  创建 ata_xx │    │  填入两个Key │    │  见证生效    │
└─────────────┘    └─────────────┘    └─────────────┘`}
      </pre>

      <ol className="steps">
        <li>
          <h3>第一步：获取 API Key</h3>
          <p>
            操作路径：点击左侧菜单 <strong>「Key」</strong> → 点击{" "}
            <strong>「创建」</strong> → 输入名称（例如{" "}
            <code>我的测试</code>）→ 复制生成的 <code>ata_xxxxxx</code>。
          </p>
          <p className="tip">
            提示：完整 Key <strong>只显示一次</strong>，请立刻复制保存。页面刷新后列表里通常只显示脱敏形式（如{" "}
            <code>ata_xxxx****</code>）。
          </p>
        </li>
        <li>
          <h3>第二步：配置设置</h3>
          <p>
            操作路径：点击左侧菜单 <strong>「设置」</strong>（上方会显示当前角色，例如{" "}
            <code>read_write</code>）：
          </p>
          <ul>
            <li>
              在 <strong>「API Key」</strong> 输入框填入第一步的{" "}
              <code>ata_xxxxxx</code>（即请求头 <code>X-Attest-Key</code>）
            </li>
            <li>
              在 <strong>「Authorization」</strong> 输入框填入{" "}
              <code>Bearer sk-xxxxxx</code>
              （你的上游厂商 Key，如 DeepSeek / OpenAI）
            </li>
            <li>
              确认 <strong>base_url</strong> 显示为代理地址（例如{" "}
              <code>{displayProxy}</code>）
            </li>
            <li>
              点击 <strong>「保存」</strong>
            </li>
          </ul>
        </li>
        <li>
          <h3>第三步：调用 API</h3>
          <p>
            先点左侧菜单底部的 <strong>「复制代理 URL」</strong>
            ，得到代理地址（不要直连厂商官网）。
          </p>
          <pre className="mono">{displayProxy}</pre>
          <p>
            把下面 Python 示例里标注处换成你的 Key 后运行：
            <br />
            · 代码里的 <code>api_key</code> / <code>UPSTREAM_KEY</code> 填上游{" "}
            <code>sk-xxxxxx</code>
            <br />
            · <code>X-Attest-Key</code> / <code>ATA_KEY</code> 填{" "}
            <code>ata_xxxxxx</code>
          </p>
          <pre className="code">{py}</pre>
          <p>
            调用成功后，打开左侧 <strong>「仪表盘」</strong> 或{" "}
            <strong>「API 调用记录」</strong>，应能看到刚产生的记录。
          </p>
        </li>
      </ol>

      <h3>常见问题 Q&amp;A</h3>
      <dl className="qa">
        <dt>问：提示「后端不可用 / NetworkError」怎么办？</dt>
        <dd>
          答：在服务器上确认后端已启动，例如执行{" "}
          <code>ps aux | grep uvicorn</code>。
          用服务器地址打开前端（如 <code>http://服务器IP:3002</code>），
          左侧底部代理 URL 应指向该服务器的 <code>:8004</code>
          ，而不是你自己电脑上的 <code>127.0.0.1</code>（除非你本机同时跑了前后端）。
        </dd>
        <dt>问：Key 填了但好像没用？</dt>
        <dd>
          答：确认已在左侧 <strong>「Key」</strong> 创建并完整复制了{" "}
          <code>ata_</code> 开头字符串；再到 <strong>「设置」</strong> 填入{" "}
          <strong>API Key</strong> 与 <strong>Authorization</strong> 后点了{" "}
          <strong>「保存」</strong>。
          调用代码里：<code>api_key</code> 用上游 <code>sk-</code>，
          <code>X-Attest-Key</code> 用 <code>ata_</code>，不要填反。
        </dd>
        <dt>问：CORS / 跨域红字是什么？</dt>
        <dd>
          答：多半是页面地址与请求的后端地址不一致。看左侧底部「复制代理 URL」旁显示的地址，
          应与当前打开前端的同一台服务器的 <code>:8004</code> 一致，然后强制刷新页面（Ctrl+Shift+R）。
        </dd>
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
        .lead {
          margin: 0 0 12px;
          color: #9eb2c7;
          font-size: 13px;
        }
        .flow {
          background: #0b0f14;
          border: 1px solid #243044;
          border-radius: 6px;
          padding: 12px 14px;
          overflow: auto;
          color: #9ecbff;
          font-size: 11px;
          line-height: 1.35;
          margin: 0 0 16px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .steps {
          margin: 0;
          padding-left: 18px;
        }
        .steps li {
          margin-bottom: 14px;
        }
        .steps p,
        .steps ul {
          margin: 6px 0;
          font-size: 13px;
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
