"use client";

type Props = {
  proxyUrl: string;
  githubUrl?: string;
};

/**
 * Beginner-facing step-by-step handbook (Chinese).
 */
export function UserGuide({
  proxyUrl,
  githubUrl = "https://github.com/liao-zhizhi/ai-attestation",
}: Props) {
  const displayProxy = proxyUrl || "http://127.0.0.1:8004/v1/proxy";

  const py = `from openai import OpenAI

# ① 把下面两处换成你自己的 Key
ATA_KEY = "ata_xxxxxx"          # 仪表盘里生成的见证 Key
UPSTREAM_KEY = "sk-xxxxxx"      # 上游厂商 Key（DeepSeek / OpenAI 等）

client = OpenAI(
    # ② 必须指向本项目的代理地址（不要直连厂商）
    base_url="${displayProxy}",
    api_key=UPSTREAM_KEY,
    default_headers={
        "X-Attest-Key": ATA_KEY,  # ③ 见证层用的 Key
    },
)

resp = client.chat.completions.create(
    model="deepseek-chat",  # 按你的上游模型改
    messages=[{"role": "user", "content": "你好，请介绍一下自己"}],
)
print(resp.choices[0].message.content)`;

  return (
    <section className="ug">
      <h2>新手操作手册</h2>
      <p className="lead">
        不用会写代码也能上手。按下面三步走：先拿 Key → 再填进设置 → 最后用代理发一次请求。
      </p>

      <ol className="steps">
        <li>
          <h3>第一步：创建 API Key</h3>
          <p>
            示例：打开左侧菜单 <strong>「设置」</strong> → 点上方的{" "}
            <strong>「API Key 管理」</strong> → 点 <strong>「创建」</strong>，
            输入一个好记的名称（比如 <code>我的测试</code>）。
          </p>
          <p>
            创建成功后会显示一串以 <code>ata_</code> 开头的 Key。请立刻复制保存
            （页面刷新后可能只显示脱敏形式）。
          </p>
          <p className="tip">
            如果看不到「API Key 管理」，说明当前账号不是管理员：可先在「通用」里用
            「签发试用 Key」，或向管理员要一把 Key。
          </p>
        </li>
        <li>
          <h3>第二步：配置 API Key</h3>
          <p>
            回到 <strong>「设置」→「通用」</strong>：
          </p>
          <ul>
            <li>
              在 <strong>「API Key」</strong> 输入框填入第一步的{" "}
              <code>ata_…</code>
              （这就是代理头 <code>X-Attest-Key</code>）
            </li>
            <li>
              点 <strong>「保存」</strong>
            </li>
          </ul>
          <p>
            上游厂商的 Key（如 DeepSeek / OpenAI）<strong>不要</strong>填在这个网页框里。
            它用在你自己的程序里，格式一般是：
          </p>
          <pre className="mono">Authorization: Bearer sk-xxxxxx</pre>
          <p className="tip">
            简单记：网页填 <code>ata_…</code>；你的 Python/SDK 里填厂商{" "}
            <code>sk-…</code>。
          </p>
        </li>
        <li>
          <h3>第三步：调用 API</h3>
          <p>
            把 AI SDK 的请求地址改成代理（不要直连厂商官网）。当前代理地址：
          </p>
          <pre className="mono">{displayProxy}</pre>
          <p>可直接复制下面的 Python 示例（把标注处换成你的 Key）：</p>
          <pre className="code">{py}</pre>
          <p>
            调用成功后，回到左侧 <strong>「仪表盘」</strong> /{" "}
            <strong>「API 调用记录」</strong>，应能看到刚产生的记录。
          </p>
        </li>
      </ol>

      <h3>常见问题 Q&amp;A</h3>
      <dl className="qa">
        <dt>问：提示「后端不可用 / NetworkError」怎么办？</dt>
        <dd>
          答：先在服务器上确认后端已启动，例如执行{" "}
          <code>ps aux | grep uvicorn</code>。
          浏览器访问的应是服务器的 <code>:8004</code>，而不是你电脑上的{" "}
          <code>127.0.0.1</code>。前端页面请用服务器地址打开（如{" "}
          <code>http://服务器IP:3002</code>）。
        </dd>
        <dt>问：Key 填了但好像没用？</dt>
        <dd>
          答：检查是否完整复制了 <code>ata_</code> 开头的字符串（不要多空格）；
          点过「保存」；前后端是否同一台服务器/同一公网地址。厂商{" "}
          <code>sk-</code> Key 要写在你的调用代码里，不是网页设置框。
        </dd>
        <dt>问：CORS / 跨域红字是什么？</dt>
        <dd>
          答：多半是页面在 A 地址，却去请求了错误的后端地址。刷新页面后看设置旁的代理
          URL 是否指向当前服务器的 <code>:8004</code>。
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
          color: #8aa0b5;
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
