"use client";

import { useCallback, useEffect, useState } from "react";
import { parseApiError, withApiKey } from "@/lib/api";
import { ArtifactList, type ArtifactRow } from "./ArtifactList";
import { ArtifactRegister } from "./ArtifactRegister";
import { PriorityCertificate } from "./PriorityCertificate";

type Props = {
  apiBase: string;
  apiKey: string;
  canWrite: boolean;
  onChainUpdated?: () => void;
};

type Detail = {
  artifact: {
    id?: string;
    timestamp?: string;
    title?: string;
    kind?: string;
    artifact_hash?: string;
    prev_hash?: string;
    chain_hash?: string;
    tsa_receipt?: { timestamp?: string; source?: string } | null;
  };
  proof?: { ok?: boolean };
  duplicate_notice?: string | null;
};

/**
 * 「科研见证」容器：登记、列表、优先权证书。
 * 不改代理调用页；只提交客户端算好的 SHA-256。
 */
export function ResearchTab({ apiBase, apiKey, canWrite, onChainUpdated }: Props) {
  const [items, setItems] = useState<ArtifactRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(
      withApiKey(`${apiBase}/v1/research/artifacts?limit=50`, apiKey)
    );
    if (!r.ok) {
      setErr(await parseApiError(r, "无法加载科研工件"));
      return;
    }
    const d = await r.json();
    setItems(d.artifacts || []);
    setErr(null);
  }, [apiBase, apiKey]);

  const loadDetail = useCallback(
    async (id: string) => {
      if (!apiKey) return;
      const r = await fetch(
        withApiKey(`${apiBase}/v1/research/artifacts/${encodeURIComponent(id)}`, apiKey)
      );
      if (!r.ok) {
        setDetail(null);
        return;
      }
      setDetail(await r.json());
    },
    [apiBase, apiKey]
  );

  useEffect(() => {
    loadList().catch(() => undefined);
  }, [loadList]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId).catch(() => undefined);
    else setDetail(null);
  }, [selectedId, loadDetail]);

  async function exportCert(id: string) {
    setExportingId(id);
    setErr(null);
    try {
      const r = await fetch(
        withApiKey(
          `${apiBase}/v1/research/artifacts/${encodeURIComponent(id)}/certificate`,
          apiKey
        )
      );
      if (!r.ok) throw new Error(await parseApiError(r, "导出失败"));
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ata_priority_${id}_cert.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExportingId(null);
    }
  }

  return (
    <div className="rs">
      <p className="lead">
        我们只保存指纹；请自己保存原件；这不是法院判决。
      </p>
      <p className="sub">
        技术存证不能证明某家 AI 厂商训练或阅读了你的草稿。登记前请确认当前 Key
        已在「设置」里点过「保存」。
      </p>
      {err && <p className="bad">{err}</p>}
      <ArtifactRegister
        apiBase={apiBase}
        apiKey={apiKey}
        canWrite={canWrite}
        onRegistered={() => {
          loadList();
          onChainUpdated?.();
        }}
      />
      <h3>已登记工件</h3>
      <ArtifactList
        items={items}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onExport={exportCert}
        exportingId={exportingId}
      />
      <PriorityCertificate
        artifact={detail?.artifact || null}
        proofOk={detail?.proof?.ok ?? null}
        duplicateNotice={detail?.duplicate_notice || null}
        onExport={() => selectedId && exportCert(selectedId)}
        exporting={!!selectedId && exportingId === selectedId}
      />
      <style jsx>{`
        .lead {
          margin: 0 0 6px;
          font-size: 14px;
          color: #d7e0ea;
        }
        .sub {
          margin: 0 0 14px;
          font-size: 12px;
          color: #7f8fa3;
          line-height: 1.5;
        }
        .bad {
          color: #ff6b6b;
          font-size: 12px;
        }
        h3 {
          margin: 8px 0;
          font-size: 13px;
          color: #9eb2c7;
        }
      `}</style>
    </div>
  );
}
