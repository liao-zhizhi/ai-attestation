"use client";

export type ApiCall = {
  id: string;
  timestamp: string;
  endpoint: string;
  method?: string;
  model?: string | null;
  vendor?: string | null;
  status_code?: number;
  request_size: number;
  response_size: number;
  duration_ms: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd: number;
  request_hash: string;
  response_hash: string;
  prev_hash: string;
  chain_hash: string;
};

type Props = {
  calls: ApiCall[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

const VENDOR_SHORT: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Claude",
  google: "Gemini",
  azure: "Azure",
  cohere: "Cohere",
  baidu: "文心",
  alibaba: "通义",
  tencent: "混元",
  bytedance: "豆包",
  deepseek: "DeepSeek",
  zhipu: "智谱",
  moonshot: "Kimi",
};

export function Timeline({ calls, selectedId, onSelect }: Props) {
  if (!calls.length) {
    return (
      <div className="empty">
        暂无调用。使用「模拟一条调用」或把 SDK base_url 指到代理后产生证据。
      </div>
    );
  }
  return (
    <ul className="tl">
      {calls.map((c) => {
        const ok = (c.status_code || 0) < 400;
        const vendor = c.vendor || "openai";
        const label = VENDOR_SHORT[vendor] || vendor;
        return (
          <li key={c.id}>
            <button
              type="button"
              className={`row ${selectedId === c.id ? "active" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="ts">{c.timestamp.replace("T", " ").replace("Z", "")}</span>
              <span className="vendor" title={vendor}>
                {label}
              </span>
              <span className="ep">{c.endpoint}</span>
              <span className={`st ${ok ? "ok" : "bad"}`}>{c.status_code ?? "—"}</span>
              <span className="cost">${Number(c.cost_usd).toFixed(6)}</span>
              <span className="hash">{c.chain_hash ? `${c.chain_hash.slice(0, 10)}…` : "—"}</span>
            </button>
          </li>
        );
      })}
      <style jsx>{`
        .tl {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 6px;
          max-height: calc(100vh - 210px);
          overflow: auto;
        }
        .row {
          width: 100%;
          display: grid;
          grid-template-columns: 150px 64px 1fr 52px 92px 88px;
          gap: 10px;
          align-items: center;
          text-align: left;
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          padding: 10px 12px;
          border-radius: 4px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .row:hover {
          border-color: #2f4560;
        }
        .row.active {
          border-color: #3dd68c;
          background: #122018;
        }
        .ts {
          color: #7f8fa3;
        }
        .vendor {
          color: #5b8def;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .ep {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .st.ok {
          color: #3dd68c;
        }
        .st.bad {
          color: #ff6b6b;
        }
        .cost {
          color: #f0b429;
        }
        .hash {
          color: #7f8fa3;
        }
        .empty {
          color: #7f8fa3;
          font-family: var(--mono);
          font-size: 13px;
          padding: 24px 8px;
        }
        @media (max-width: 960px) {
          .row {
            grid-template-columns: 1fr 1fr;
          }
        }
      `}</style>
    </ul>
  );
}
