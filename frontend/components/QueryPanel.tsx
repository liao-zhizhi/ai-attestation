"use client";

export type QueryFilters = {
  time_range: string;
  custom_from?: string;
  custom_to?: string;
  endpoint: string;
  min_cost: string;
  max_cost: string;
  status: string;
  model: string;
  vendor?: string;
};

type Props = {
  open: boolean;
  onToggle: () => void;
  filters: QueryFilters;
  onChange: (next: QueryFilters) => void;
  onQuery: () => void;
  busy: boolean;
  canWrite?: boolean;
};

export function QueryPanel({
  open,
  onToggle,
  filters,
  onChange,
  onQuery,
  busy,
  canWrite = true,
}: Props) {
  function set<K extends keyof QueryFilters>(key: K, value: QueryFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="qp">
      <button type="button" className="toggle" onClick={onToggle}>
        <span>{open ? "▾" : "▸"}</span> 查询即审计
        <em>查询即审计 · MVP</em>
      </button>
      {open && (
        <div className="body">
          <div className="row">
            <label>
              时间范围
              <select
                value={filters.time_range}
                onChange={(e) => set("time_range", e.target.value)}
              >
                <option value="today">今天</option>
                <option value="7d">最近 7 天</option>
                <option value="30d">最近 30 天</option>
                <option value="all">全部</option>
                <option value="custom">自定义</option>
              </select>
            </label>
            {filters.time_range === "custom" && (
              <>
                <label>
                  从
                  <input
                    type="datetime-local"
                    value={filters.custom_from || ""}
                    onChange={(e) => set("custom_from", e.target.value)}
                  />
                </label>
                <label>
                  至
                  <input
                    type="datetime-local"
                    value={filters.custom_to || ""}
                    onChange={(e) => set("custom_to", e.target.value)}
                  />
                </label>
              </>
            )}
            <label>
              API 端点
              <input
                value={filters.endpoint}
                onChange={(e) => set("endpoint", e.target.value)}
                placeholder="chat/completions"
                spellCheck={false}
              />
            </label>
            <label>
              模型
              <input
                value={filters.model}
                onChange={(e) => set("model", e.target.value)}
                placeholder="gpt-4"
                spellCheck={false}
              />
            </label>
            <label>
              厂商
              <select
                value={filters.vendor || ""}
                onChange={(e) => set("vendor", e.target.value)}
              >
                <option value="">全部</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="azure">Azure</option>
                <option value="cohere">Cohere</option>
                <option value="baidu">百度文心</option>
                <option value="alibaba">阿里通义</option>
                <option value="tencent">腾讯混元</option>
                <option value="bytedance">字节豆包</option>
                <option value="deepseek">DeepSeek</option>
                <option value="zhipu">智谱</option>
                <option value="moonshot">月之暗面</option>
              </select>
            </label>
          </div>
          <div className="row">
            <label>
              最低费用
              <input
                type="number"
                step="0.0001"
                value={filters.min_cost}
                onChange={(e) => set("min_cost", e.target.value)}
                placeholder="0"
              />
            </label>
            <label>
              最高费用
              <input
                type="number"
                step="0.0001"
                value={filters.max_cost}
                onChange={(e) => set("max_cost", e.target.value)}
                placeholder="100"
              />
            </label>
            <label>
              调用状态
              <select
                value={filters.status}
                onChange={(e) => set("status", e.target.value)}
              >
                <option value="">全部</option>
                <option value="success">成功</option>
                <option value="failure">失败</option>
                <option value="timeout">超时</option>
              </select>
            </label>
            <button
              type="button"
              className="run"
              onClick={onQuery}
              disabled={busy || !canWrite}
              title={!canWrite ? "需要 read_write 或 admin" : undefined}
            >
              {busy ? "查询中…" : "查询"}
            </button>
          </div>
        </div>
      )}
      <style jsx>{`
        .qp {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          margin-bottom: 16px;
        }
        .toggle {
          width: 100%;
          display: flex;
          align-items: center;
          gap: 8px;
          background: transparent;
          border: none;
          color: #d7e0ea;
          padding: 12px 14px;
          font-family: var(--mono);
          font-size: 13px;
          text-align: left;
          cursor: pointer;
        }
        .toggle em {
          margin-left: auto;
          font-style: normal;
          color: #7f8fa3;
          font-size: 11px;
        }
        .body {
          padding: 0 14px 14px;
          border-top: 1px solid #1e2a38;
        }
        .row {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          align-items: flex-end;
          margin-top: 12px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 11px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        input,
        select {
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 7px 9px;
          font-family: var(--mono);
          font-size: 12px;
          min-width: 140px;
        }
        .run {
          background: #1a3d2c;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 8px 16px;
          font-family: var(--mono);
          font-size: 12px;
          height: 34px;
        }
        .run:disabled {
          opacity: 0.6;
        }
      `}</style>
    </section>
  );
}
