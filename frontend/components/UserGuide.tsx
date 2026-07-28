"use client";

type Props = {
  proxyUrl: string;
  githubUrl?: string;
};

/**
 * Beginner handbook — wording must match Sidebar / KeysPanel / SettingsPanel exactly.
 */
export function UserGuide({
  proxyUrl,
  githubUrl = "https://github.com/liao-zhizhi/ai-attestation",
}: Props) {
  const displayProxy = proxyUrl || "http://127.0.0.1:8004/v1/proxy";

  const py = `from openai import OpenAI

# ① 两处都要换成你自己的（不要填反）
ATA_KEY = "ata_xxxxxx"       # 「Key」页生成的见证 Key
UPSTREAM_KEY = "sk-xxxxxx"   # 上游厂商 Key（DeepSeek / OpenAI 等，不要带 Bearer 前缀）

client = OpenAI(
    # ② 左侧底部「复制代理 URL」得到的地址（与设置页 base_url 相同）
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
      <h2>新手操作手册（上手指南）</h2>
      <p className="lead">
        左侧菜单从上到下是：操作手册 → 仪表盘 → API 调用记录 → 合规管理 → 行为监控 →
        防篡改证明 → 设置 → Key；最底下有「复制代理 URL」。按下面步骤走即可。
      </p>

      <pre className="flow" aria-label="用户流程图">
{`┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐
│ ① Key    │ → │ ② 设置   │ → │ ③ 调用   │ → │ ④ 导出验证包 │
│ 创建 ata_ │   │ 填入保存  │   │ 写代码   │   │ 调用详情底部 │
└──────────┘   └──────────┘   └──────────┘   └──────────────┘`}
      </pre>

      <ol className="steps">
        <li>
          <h3>第一步：获取 API Key</h3>
          <p>操作路径（与页面按钮文字一致）：</p>
          <ol className="sub">
            <li>
              点左侧菜单 <strong>「Key」</strong>（页面标题也是 Key；内容区标题为{" "}
              <strong>API Key</strong>）
            </li>
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
              若页面提示需要切换，再点 <strong>「设为当前 Key」</strong>
              （第一次创建且你还没有 Key 时，系统会自动设为当前）
            </li>
          </ol>
          <p className="tip">
            注意：完整 Key 只完整显示一次。管理员账号在下方「已有 Key」列表刷新后通常只看到脱敏形式（如{" "}
            <code>ata_xxxx****</code>）。点「设为当前 Key」后，界面会提示再到「设置」确认并保存。
          </p>
        </li>
        <li>
          <h3>第二步：配置设置</h3>
          <p>
            点左侧菜单 <strong>「设置」</strong>。默认停在上方标签{" "}
            <strong>「通用」</strong>（旁边还有「报告订阅」，新手可先不管）。
            你会看到一行 <code>当前角色：…</code>（例如 <code>read_write</code> 或{" "}
            <code>admin</code>）。
          </p>
          <ul>
            <li>
              在标签为 <strong>「API Key（X-Attest-Key）」</strong> 的输入框填入第一步的{" "}
              <code>ata_xxxxxx</code>（占位符也是 <code>ata_xxxxxx</code>）
            </li>
            <li>
              在标签为 <strong>「Authorization（上游厂商 Key，仅本机备忘）」</strong>{" "}
              的输入框可填 <code>Bearer sk-xxxxxx</code>
              ——这只保存在本浏览器，方便你对照；网页<strong>不会</strong>用它去调上游
            </li>
            <li>
              只读框 <strong>「base_url」</strong> 应显示代理地址，例如{" "}
              <code>{displayProxy}</code>
            </li>
            <li>
              点绿色按钮 <strong>「保存」</strong>（同排还有「复制代理 URL」）
            </li>
          </ul>
          <p className="tip">
            仪表盘能否打开，只取决于「API Key（X-Attest-Key）」是否正确并已点「保存」。
            上游 <code>sk-…</code> 必须写在第三步的代码里。
          </p>
        </li>
        <li>
          <h3>第三步：调用 API</h3>
          <p>
            点左侧菜单<strong>最底部</strong>的 <strong>「复制代理 URL」</strong>
            （设置页「通用」里也有同名按钮），得到代理地址。不要直连厂商官网。
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
              <code>base_url=</code> → 与左侧复制到的代理 URL 一致
            </li>
          </ul>
          <pre className="code">{py}</pre>
          <p>
            调用成功后，打开左侧 <strong>「仪表盘」</strong> 或{" "}
            <strong>「API 调用记录」</strong> 查看记录。
            若暂时没有上游 Key，也可在右上角点 <strong>「模拟一条调用」</strong>
            （需要当前角色为 <code>read_write</code> 或 <code>admin</code>）先写入一条演示数据。
          </p>
        </li>
        <li>
          <h3>第四步：导出验证包（可选）</h3>
          <p>
            需要把某次调用的证据带离线、给别人复核时，用这个功能（不依赖服务器也能打开校验页）。
          </p>
          <ol className="sub">
            <li>
              打开左侧 <strong>「仪表盘」</strong> 或 <strong>「API 调用记录」</strong>
            </li>
            <li>
              在列表里<strong>点开一条调用</strong>，弹出标题为 <strong>「调用详情」</strong> 的窗口
            </li>
            <li>
              在窗口底部，<strong>「验证完整性」</strong> 按钮旁边，点{" "}
              <strong>「导出验证包」</strong>
            </li>
            <li>
              浏览器会下载一个 ZIP（文件名类似{" "}
              <code>ata_call_…_verify.zip</code>）
            </li>
          </ol>
          <p>解压后目录里有：</p>
          <ul>
            <li>
              <code>call.json</code> — 该次调用的见证字段（时间、端点、哈希等；
              <strong>不含</strong>请求/响应原文）
            </li>
            <li>
              <code>chain.json</code> — 邻接哈希链片段
            </li>
            <li>
              <code>verification.json</code> — 导出时服务端的校验结果
            </li>
            <li>
              <code>verify.html</code> — 纯前端离线校验页
            </li>
            <li>
              <code>README.txt</code> — 使用说明
            </li>
          </ul>
          <p>离线验证步骤：</p>
          <ol className="sub">
            <li>解压 ZIP 到任意文件夹</li>
            <li>
              在该文件夹打开终端，执行：<code>python -m http.server 8765</code>
            </li>
            <li>
              浏览器打开 <code>http://127.0.0.1:8765/verify.html</code>
            </li>
            <li>
              点页面上的 <strong>「运行本地验证」</strong>
            </li>
          </ol>
          <p className="tip">
            同窗口里的「验证完整性」是连服务器当场校验整条链；「导出验证包」是下载 ZIP，方便离线或交给第三方复核。
          </p>
        </li>
      </ol>

      <h3>常见问题 Q&amp;A</h3>
      <dl className="qa">
        <dt>问：提示「后端不可用 / NetworkError」怎么办？</dt>
        <dd>
          答：在服务器执行 <code>ps aux | grep uvicorn</code> 确认后端在跑。
          用服务器地址打开前端（如 <code>http://服务器IP:3002</code>）。
          看左侧底部「复制代理 URL」旁的地址，应是该服务器的 <code>:8004</code>
          ，而不是你电脑上的 <code>127.0.0.1</code>（除非本机同时跑了前后端）。然后强制刷新（Ctrl+Shift+R）。
        </dd>
        <dt>问：Key 创建了 / 填了但好像没用？</dt>
        <dd>
          答：在「Key」页确认已 <strong>「复制 Key」</strong>；若未自动切换，点{" "}
          <strong>「设为当前 Key」</strong>。再到「设置」→「通用」，确认{" "}
          <strong>「API Key（X-Attest-Key）」</strong> 里是完整 <code>ata_…</code>，并点了{" "}
          <strong>「保存」</strong>。
          「Authorization」只是备忘，填了也不会单独让仪表盘生效。
          写代码时：<code>api_key</code> 用上游 <code>sk-</code>，
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
        <dt>问：右上角「模拟一条调用」点不了？</dt>
        <dd>
          答：需要先在「设置」保存有效的 <code>ata_</code> Key，且角色为{" "}
          <code>read_write</code> 或 <code>admin</code>（只读 <code>read_only</code>{" "}
          不能写）。把鼠标悬停在按钮上也可能看到提示。
        </dd>
        <dt>问：CORS / 跨域红字是什么？</dt>
        <dd>
          答：通常是前端页面主机与请求的后端主机不一致。以左侧底部显示的代理 URL 为准，强制刷新后再试。
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
