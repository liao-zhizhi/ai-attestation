"use client";

import { useEffect, useState } from "react";
import { resolveApiBase } from "@/lib/api";

type Kind = "call" | "artifact";

type CallData = {
  timestamp?: string;
  model?: string;
  endpoint?: string;
  cost_usd?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  request_hash?: string;
  response_hash?: string;
  prev_hash?: string;
  chain_hash?: string;
  chain_ok?: boolean;
  chain_status_label?: string;
  disclaimer?: string;
};

type ArtifactData = {
  timestamp?: string;
  title?: string;
  kind?: string;
  artifact_hash?: string;
  byte_length?: number;
  authors_label?: string;
  prev_hash?: string;
  chain_hash?: string;
  chain_ok?: boolean;
  chain_status_label?: string;
  disclaimer?: string;
};

type Props = { kind: Kind; token: string };

/**
 * 公开验证页：无需登录。只展示指纹与链状态。
 */
export function PublicVerifyView({ kind, token }: Props) {
  const [data, setData] = useState<CallData & ArtifactData>();
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = resolveApiBase();
    setLoading(true);
    fetch(`${base}/v1/public/verify/${kind}/${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (r.status === 404) {
          throw new Error("这条公开链接不存在或已被撤销");
        }
        if (!r.ok) throw new Error(`无法加载验证页（${r.status}）`);
        return r.json();
      })
      .then((d) => {
        setData(d);
        setErr(null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [kind, token]);

  const ok = data?.chain_ok !== false && !err && !loading && !!data;

  return (
    <main className="pv">
      <p className="brand">本页由 ai-attestation.com 提供见证</p>
      {loading && <p className="muted">正在核对哈希链…</p>}
      {err && (
        <>
          <div className="badge bad">✗ 无法验证</div>
          <p className="err">{err}</p>
        </>
      )}
      {data && !err && (
        <>
          <div className={ok ? "badge ok" : "badge bad"}>
            {ok ? "✓ 链完整" : "✗ 链异常"}
          </div>
          {kind === "call" ? (
            <table>
              <tbody>
                <Row k="时间" v={data.timestamp} />
                <Row k="模型" v={data.model} />
                <Row k="端点" v={data.endpoint} />
                <Row k="费用" v={data.cost_usd != null ? `$${data.cost_usd}` : "—"} />
                <Row
                  k="token 数"
                  v={`${data.prompt_tokens ?? 0} in / ${data.completion_tokens ?? 0} out`}
                />
              </tbody>
            </table>
          ) : (
            <table>
              <tbody>
                <Row k="时间" v={data.timestamp} />
                <Row k="标题" v={data.title} />
                <Row k="类型" v={data.kind} />
                <Row k="作者标注" v={data.authors_label} />
                <Row k="字节数" v={data.byte_length != null ? String(data.byte_length) : "—"} />
              </tbody>
            </table>
          )}
          <h2>哈希链</h2>
          <table>
            <tbody>
              {kind === "call" ? (
                <>
                  <Row k="request_hash" v={data.request_hash} mono />
                  <Row k="response_hash" v={data.response_hash} mono />
                </>
              ) : (
                <Row k="artifact_hash" v={data.artifact_hash} mono />
              )}
              <Row k="prev_hash" v={data.prev_hash} mono />
              <Row k="chain_hash" v={data.chain_hash} mono />
            </tbody>
          </table>
          <p className="foot">
            {data.disclaimer || "此页面数据由 ai-attestation.com 独立见证，可离线复核"}
          </p>
        </>
      )}
      <style jsx>{`
        .pv {
          max-width: 720px;
          margin: 0 auto;
          padding: 32px 20px 48px;
        }
        .brand {
          color: #7f8fa3;
          font-size: 13px;
          letter-spacing: 0.04em;
        }
        .badge {
          font-size: 28px;
          font-weight: 650;
          margin: 12px 0 20px;
        }
        .ok {
          color: #3dd68c;
        }
        .bad {
          color: #ff6b6b;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 18px;
        }
        h2 {
          font-size: 14px;
          color: #9eb2c7;
          margin: 8px 0;
        }
        .foot {
          color: #7f8fa3;
          font-size: 12px;
          line-height: 1.5;
          margin-top: 24px;
        }
        .muted,
        .err {
          color: #9eb2c7;
        }
        .err {
          color: #ff6b6b;
        }
      `}</style>
    </main>
  );
}

function Row({ k, v, mono }: { k: string; v?: string | number | null; mono?: boolean }) {
  return (
    <tr>
      <th>{k}</th>
      <td className={mono ? "mono" : undefined}>{v == null || v === "" ? "—" : String(v)}</td>
      <style jsx>{`
        th {
          text-align: left;
          color: #7f8fa3;
          font-weight: 500;
          width: 140px;
          padding: 8px 10px 8px 0;
          vertical-align: top;
          font-size: 12px;
        }
        td {
          padding: 8px 0;
          font-size: 13px;
          word-break: break-all;
        }
        .mono {
          font-family: var(--mono);
          font-size: 11px;
          color: #3dd68c;
        }
      `}</style>
    </tr>
  );
}
