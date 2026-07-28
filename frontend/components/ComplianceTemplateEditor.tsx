"use client";

import { useCallback, useEffect, useState } from "react";

type TemplateMeta = {
  id: string;
  name: string;
  description?: string;
  version?: string;
  source?: string;
  n_groups?: number;
  n_checks?: number;
  pinned_version?: string | null;
};

type Props = {
  apiBase: string;
  apiKey: string;
  onChanged?: () => void;
};

const EMPTY = `schema: ata-compliance-template-v1
id: my_private_policy
name: 我的私有合规检查模板
description: 仅对本 API Key 可见
version: 0.1.0
source: custom
groups:
  - api_trail_30d
  - hash_chain
  - cost_recorded
# 可编程护栏示例（type: rule）—
# checks:
#   - check_id: high_spend_audit
#     type: rule
#     auto_check: true
#     category: 计费
#     requirement: 日调用量与费用超阈则待审计
#     rule:
#       all:
#         - field: call_count
#           op: gt
#           value: 100
#           window: 1d
#         - field: total_cost_usd
#           op: gt
#           value: 50
#           window: 1d
#     on_match: fail
#     detail_template: "调用量与费用超阈，标记待审计"
`;

export function ComplianceTemplateEditor({ apiBase, apiKey, onChanged }: Props) {
  const [list, setList] = useState<TemplateMeta[]>([]);
  const [yamlText, setYamlText] = useState(EMPTY);
  const [selected, setSelected] = useState<string | null>(null);
  const [goal, setGoal] = useState("验证过去30天所有API调用记录的完整性");
  const [helperOut, setHelperOut] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [updates, setUpdates] = useState<
    Array<{ template_id: string; available_version: string; current_version: string; action: string }>
  >([]);

  const reload = useCallback(async () => {
    if (!apiKey || apiKey.length < 8) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/compliance/templates/custom?api_key=${encodeURIComponent(apiKey)}`
    );
    if (!r.ok) throw new Error("load custom templates failed");
    const d = await r.json();
    setList(d.templates || []);
    const u = await fetch(
      `${apiBase}/v1/dashboard/compliance/templates/updates?api_key=${encodeURIComponent(apiKey)}`
    );
    if (u.ok) {
      const ud = await u.json();
      setUpdates(ud.updates || []);
    }
  }, [apiBase, apiKey]);

  useEffect(() => {
    reload().catch((e) => setErr(e instanceof Error ? e.message : "load failed"));
  }, [reload]);

  async function loadOne(id: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/compliance/templates/custom/${encodeURIComponent(id)}?api_key=${encodeURIComponent(apiKey)}`
      );
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setYamlText(d.yaml || "");
      setSelected(id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "load failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveImport() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await fetch(`${apiBase}/v1/dashboard/compliance/templates/custom/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, yaml_text: yamlText }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setMsg(`已保存 ${d.template?.id} v${d.template?.version}`);
      setSelected(d.template?.id || null);
      await reload();
      onChanged?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm(`删除私有模板 ${id}？`)) return;
    const r = await fetch(
      `${apiBase}/v1/dashboard/compliance/templates/custom/${encodeURIComponent(id)}?api_key=${encodeURIComponent(apiKey)}`,
      { method: "DELETE" }
    );
    if (!r.ok) {
      setErr(await r.text());
      return;
    }
    setMsg(`已删除 ${id}`);
    if (selected === id) {
      setSelected(null);
      setYamlText(EMPTY);
    }
    await reload();
    onChanged?.();
  }

  async function publish(id: string) {
    setBusy(true);
    try {
      const r = await fetch(
        `${apiBase}/v1/dashboard/compliance/templates/custom/${encodeURIComponent(id)}/publish?api_key=${encodeURIComponent(apiKey)}`,
        { method: "POST" }
      );
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setMsg(`已生成社区草稿：${d.relative}（按 CONTRIBUTING 提 PR）`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "publish failed");
    } finally {
      setBusy(false);
    }
  }

  async function runHelper() {
    const r = await fetch(`${apiBase}/v1/dashboard/compliance/templates/helper`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
    });
    if (!r.ok) {
      setErr(await r.text());
      return;
    }
    const d = await r.json();
    setHelperOut(JSON.stringify(d.draft, null, 2));
  }

  async function pin(id: string, version: string | null) {
    const r = await fetch(`${apiBase}/v1/dashboard/compliance/templates/pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, template_id: id, version }),
    });
    if (!r.ok) {
      setErr(await r.text());
      return;
    }
    setMsg(version ? `已固定 ${id}@${version}` : `已跟随最新 ${id}`);
    await reload();
  }

  return (
    <section className="ed">
      <header>
        <h3>自定义合规检查模板</h3>
        <p className="hint">
          私有模板仅本 Key 可见。核心检查清单开源于{" "}
          <code>compliance-templates/</code>；商业能力在产品侧，证据格式不私有化。
        </p>
      </header>

      {updates.filter((u) => u.action === "upgrade_available").length > 0 && (
        <div className="upd">
          <strong>模板有新版本</strong>
          <ul>
            {updates
              .filter((u) => u.action === "upgrade_available")
              .map((u) => (
                <li key={u.template_id}>
                  {u.template_id}: {u.current_version} → {u.available_version}{" "}
                  <button type="button" onClick={() => pin(u.template_id, null)}>
                    跟随最新
                  </button>
                  <button type="button" onClick={() => pin(u.template_id, u.current_version)}>
                    保持旧版
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}

      {err && <div className="err">{err}</div>}
      {msg && <div className="ok">{msg}</div>}

      <div className="grid">
        <aside>
          <button type="button" className="new" onClick={() => { setYamlText(EMPTY); setSelected(null); }}>
            + 新建
          </button>
          <ul>
            {list.map((t) => (
              <li key={t.id} className={selected === t.id ? "on" : ""}>
                <button type="button" className="pick" onClick={() => loadOne(t.id)}>
                  {t.name}
                  <span className="mono">
                    {t.id} · v{t.version}
                  </span>
                </button>
                <div className="acts">
                  <button type="button" onClick={() => publish(t.id)}>
                    发布到社区
                  </button>
                  <button type="button" className="danger" onClick={() => remove(t.id)}>
                    删除
                  </button>
                </div>
              </li>
            ))}
            {list.length === 0 && <li className="empty">暂无私有模板</li>}
          </ul>
        </aside>
        <div className="main">
          <label>
            YAML（导入/导出格式与开源仓库一致；可用 type: rule 定义可编程护栏，见默认注释示例）
          </label>
          <textarea value={yamlText} onChange={(e) => setYamlText(e.target.value)} rows={18} spellCheck={false} />
          <div className="bar">
            <button type="button" onClick={saveImport} disabled={busy}>
              {busy ? "保存中…" : "保存 / 导入 YAML"}
            </button>
            <a
              className="dl"
              href={`data:text/yaml;charset=utf-8,${encodeURIComponent(yamlText)}`}
              download={`${selected || "template"}.yaml`}
            >
              导出 YAML
            </a>
          </div>

          <div className="helper">
            <h4>检查方法助手</h4>
            <input value={goal} onChange={(e) => setGoal(e.target.value)} />
            <button type="button" onClick={runHelper}>
              生成查询条件草稿
            </button>
            {helperOut && <pre>{helperOut}</pre>}
          </div>
        </div>
      </div>

      <style jsx>{`
        .ed {
          display: grid;
          gap: 12px;
        }
        header h3 {
          margin: 0 0 4px;
          font-size: 15px;
        }
        .hint {
          margin: 0;
          color: #7f8fa3;
          font-size: 12px;
          line-height: 1.45;
        }
        .hint code {
          color: #9eb2c7;
        }
        .upd {
          background: #1a2a14;
          border: 1px solid #2a5c42;
          border-radius: 6px;
          padding: 10px 12px;
          font-size: 12px;
        }
        .upd ul {
          margin: 6px 0 0;
          padding-left: 18px;
        }
        .upd button {
          margin-left: 6px;
          font-size: 11px;
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 3px;
          padding: 2px 6px;
          cursor: pointer;
        }
        .err {
          color: #ff6b6b;
          font-size: 12px;
        }
        .ok {
          color: #3dd68c;
          font-size: 12px;
        }
        .grid {
          display: grid;
          grid-template-columns: 240px 1fr;
          gap: 12px;
        }
        @media (max-width: 800px) {
          .grid {
            grid-template-columns: 1fr;
          }
        }
        aside ul {
          list-style: none;
          margin: 8px 0 0;
          padding: 0;
          display: grid;
          gap: 8px;
        }
        aside li {
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px;
        }
        aside li.on {
          border-color: #2a5c42;
        }
        .pick {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 2px;
          width: 100%;
          background: transparent;
          border: 0;
          color: #d7e0ea;
          cursor: pointer;
          text-align: left;
          font-size: 13px;
        }
        .mono {
          font-family: var(--mono);
          font-size: 10px;
          color: #7f8fa3;
        }
        .acts {
          display: flex;
          gap: 6px;
          margin-top: 6px;
        }
        .acts button {
          font-size: 10px;
          background: #152033;
          border: 1px solid #2a3b52;
          color: #9eb2c7;
          border-radius: 3px;
          padding: 2px 6px;
          cursor: pointer;
        }
        .acts .danger {
          color: #ff6b6b;
          border-color: #6b2a2a;
        }
        .new {
          width: 100%;
          background: #1a3a2a;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 6px;
          cursor: pointer;
          font-family: var(--mono);
          font-size: 12px;
        }
        .empty {
          color: #7f8fa3;
          font-size: 12px;
          padding: 8px;
        }
        .main label {
          display: block;
          font-size: 11px;
          color: #7f8fa3;
          margin-bottom: 4px;
        }
        textarea {
          width: 100%;
          box-sizing: border-box;
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 10px;
          font-family: var(--mono);
          font-size: 11px;
          line-height: 1.4;
        }
        .bar {
          display: flex;
          gap: 10px;
          align-items: center;
          margin-top: 8px;
        }
        .bar button {
          background: #1a3a2a;
          border: 1px solid #2a5c42;
          color: #3dd68c;
          border-radius: 4px;
          padding: 6px 12px;
          cursor: pointer;
          font-family: var(--mono);
          font-size: 12px;
        }
        .dl {
          color: #9eb2c7;
          font-size: 12px;
          font-family: var(--mono);
        }
        .helper {
          margin-top: 16px;
          padding-top: 12px;
          border-top: 1px solid #1e2a38;
        }
        .helper h4 {
          margin: 0 0 8px;
          font-size: 12px;
          color: #3dd68c;
        }
        .helper input {
          width: 100%;
          box-sizing: border-box;
          background: #0e141c;
          border: 1px solid #1e2a38;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 8px;
          margin-bottom: 8px;
          font-size: 12px;
        }
        .helper button {
          background: #152033;
          border: 1px solid #2a3b52;
          color: #d7e0ea;
          border-radius: 4px;
          padding: 6px 10px;
          cursor: pointer;
          font-size: 12px;
        }
        .helper pre {
          margin-top: 8px;
          background: #0e141c;
          border: 1px solid #1e2a38;
          border-radius: 4px;
          padding: 8px;
          font-size: 11px;
          color: #9eb2c7;
          overflow: auto;
        }
      `}</style>
    </section>
  );
}
