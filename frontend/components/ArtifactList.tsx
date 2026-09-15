"use client";

const KIND_LABEL: Record<string, string> = {
  draft: "草稿",
  derivation: "推导",
  prompt: "提示词",
  note: "笔记",
  other: "其他",
};

export type ArtifactRow = {
  id: string;
  timestamp: string;
  title?: string;
  kind?: string;
  artifact_hash?: string;
  hash_prefix?: string;
  chain_ok?: boolean;
  duplicate_notice?: string | null;
  first_seen_at?: string | null;
};

type Props = {
  items: ArtifactRow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onExport: (id: string) => void;
  exportingId: string | null;
};

/** 工件列表：时间、标题、类型、哈希前 12 位、链状态。 */
export function ArtifactList({
  items,
  selectedId,
  onSelect,
  onExport,
  exportingId,
}: Props) {
  if (!items.length) {
    return (
      <p className="empty">
        还没有科研存证。在把未发表内容发给任何 AI 之前，先在这里留下指纹。全程可以不上传原文。
        <style jsx>{`
          .empty {
            color: #9eb2c7;
            font-size: 13px;
            line-height: 1.55;
            background: #111821;
            border: 1px dashed #2a3b52;
            border-radius: 6px;
            padding: 16px;
          }
        `}</style>
      </p>
    );
  }
  return (
    <div className="list">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>标题</th>
            <th>类型</th>
            <th>哈希前 12 位</th>
            <th>链状态</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((it) => {
            const prefix = it.hash_prefix || String(it.artifact_hash || "").slice(0, 12);
            return (
              <tr
                key={it.id}
                className={selectedId === it.id ? "on" : ""}
                onClick={() => onSelect(it.id)}
              >
                <td className="mono">{it.timestamp || "—"}</td>
                <td>
                  {it.title || "未命名工件"}
                  {it.duplicate_notice ? (
                    <div className="dup">{it.duplicate_notice}</div>
                  ) : null}
                </td>
                <td>{KIND_LABEL[it.kind || ""] || it.kind || "—"}</td>
                <td className="mono">{prefix || "—"}</td>
                <td className={it.chain_ok ? "ok" : "bad"}>
                  {it.chain_ok ? "链完整" : "链异常"}
                </td>
                <td>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onExport(it.id);
                    }}
                    disabled={exportingId === it.id}
                  >
                    {exportingId === it.id ? "导出中…" : "导出优先权证书"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <style jsx>{`
        .list {
          overflow-x: auto;
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
        }
        th {
          text-align: left;
          color: #7f8fa3;
          font-weight: 500;
          padding: 8px 10px;
          border-bottom: 1px solid #1e2a38;
        }
        td {
          padding: 8px 10px;
          border-bottom: 1px solid #152033;
          vertical-align: top;
        }
        tr {
          cursor: pointer;
        }
        tr.on {
          background: #123526;
        }
        .mono {
          font-family: var(--mono);
          font-size: 11px;
          color: #9eb2c7;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        .dup {
          color: #f0b429;
          font-size: 11px;
          margin-top: 4px;
        }
        button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 6px 8px;
          font-size: 11px;
          font-family: var(--mono);
        }
      `}</style>
    </div>
  );
}
