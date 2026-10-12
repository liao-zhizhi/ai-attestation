/** 在点击回调里复制。同步选择优先，失败再试异步剪贴板。 */
export async function copyText(text: string): Promise<boolean> {
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.focus();
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    if (ok) return true;
  } catch {
    /* 再试异步剪贴板 */
  }
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function jsString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/** 设置页「一键复制配置」：填入当前存证账号编号和代理地址。 */
export function pythonProxySnippet(proxyUrl: string, accountId: string): string {
  const id = accountId.trim() || "ata_请先创建存证账号";
  const base = (proxyUrl || "http://127.0.0.1:8004/v1/proxy").replace(/\/$/, "");
  return `from openai import OpenAI

# 存证账号编号（已按当前浏览器填入）
ATA_KEY = "${jsString(id)}"
# 换成你的上游厂商密钥（DeepSeek / OpenAI 等，不要加 Bearer）
UPSTREAM_KEY = "sk-xxxxxx"

client = OpenAI(
    base_url="${jsString(base)}",
    api_key=UPSTREAM_KEY,
    default_headers={
        "X-Attest-Key": ATA_KEY,
    },
)

resp = client.chat.completions.create(
    model="deepseek-chat",  # 按上游模型改名
    messages=[{"role": "user", "content": "你好，请介绍一下自己"}],
)
print(resp.choices[0].message.content)
`;
}
