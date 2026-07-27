"""Offline verification ZIP pack + embeddable badge + chain path for verify page."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Dict, List, Mapping, Optional


# Self-contained offline verifier (no external API). Same logic as server verify_pack.
_OFFLINE_VERIFY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>离线验证 · ai-attestation</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b0f14;color:#d7e0ea;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;color:#3dd68c} .card{background:#121820;border:1px solid #243044;border-radius:8px;padding:16px;margin:12px 0}
.ok{color:#3dd68c}.bad{color:#ff6b6b} button{background:#1a3a2a;color:#3dd68c;border:1px solid #2a5c42;padding:8px 14px;border-radius:4px;cursor:pointer}
pre{white-space:pre-wrap;word-break:break-all;font-size:11px;color:#9eb2c7}
</style>
</head>
<body>
<h1>离线验证包</h1>
<p>本页纯静态运行，不访问任何服务器。将同目录的 <code>report.json</code> / <code>chain.json</code> / <code>pack.json</code> 放在一起即可。</p>
<div class="card">
<button id="run">运行本地验证</button>
<div id="out"></div>
</div>
<script>
async function loadJSON(name){
  const r = await fetch(name);
  if(!r.ok) throw new Error('缺少 '+name+'（请用本地 HTTP 或 file 同目录打开）');
  return r.json();
}
function sha256Hex(str){
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)).then(buf=>{
    return [...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('');
  });
}
/** Match Python json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',', ':')) */
function canonicalJson(v){
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canonicalJson).join(',') + ']';
  const keys = Object.keys(v).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalJson(v[k])).join(',') + '}';
}
async function verify(){
  const out = document.getElementById('out');
  out.innerHTML = '验证中…';
  try {
    const pack = await loadJSON('pack.json');
    const report = pack.report || await loadJSON('report.json');
    const chain = await loadJSON('chain.json').catch(()=>null);
    const results = report.check_results || {};
    const canonical = canonicalJson({standard: report.standard||'', results: results});
    let rhOk = false, rhMsg = '';
    if (window.isSecureContext && crypto.subtle) {
      const hex = await sha256Hex(canonical);
      rhOk = !!(report.report_hash && hex === report.report_hash);
      rhMsg = rhOk ? 'report_hash 与本地重算一致' : 'report_hash 重算不一致（若为旧包可对照 pack.verification）';
    } else {
      rhOk = false;
      rhMsg = '非安全上下文：无法重算 SHA-256（请用本地 http.server 打开）';
    }
    let chainOk = false, chainMsg = '无 chain.json（未验证）';
    if (chain && Array.isArray(chain.links)) {
      let broken = [];
      if (chain.links.length === 0) {
        chainOk = false;
        chainMsg = 'chain.json 为空';
      } else {
        for (let i=1;i<chain.links.length;i++){
          const prev = chain.links[i-1], cur = chain.links[i];
          if (cur.prev_hash && prev.hash && cur.prev_hash !== prev.hash) broken.push(i);
        }
        chainOk = broken.length===0;
        chainMsg = chainOk ? ('相邻链指针完整 · '+chain.links.length+' 节点（完整字段重算请用服务端 verify）') : ('断裂于索引 '+broken.join(','));
      }
    }
    const tsp = pack.timestamp_proof;
    let tspOk = false, tspMsg = '未附带';
    if (tsp) {
      if (window.isSecureContext && crypto.subtle && tsp.payload_hash && tsp.unix != null && tsp.nonce && tsp.token) {
        const expected = await sha256Hex(String(tsp.payload_hash)+'|'+String(tsp.unix)+'|'+String(tsp.nonce));
        const bindOk = String(tsp.payload_hash) === String(report.report_hash || '');
        tspOk = expected === String(tsp.token) && bindOk;
        tspMsg = tspOk ? (tsp.source+' · '+tsp.timestamp+' · token 重算一致') : '时间戳 token 重算失败或未绑定 report_hash';
      } else if (!window.isSecureContext || !crypto.subtle) {
        tspOk = false;
        tspMsg = '非安全上下文：无法重算时间戳 token';
      } else {
        tspOk = false;
        tspMsg = '时间戳字段不完整';
      }
    }
    const anchor = pack.blockchain_anchor;
    const html = [
      '<p class="'+(rhOk?'ok':'bad')+'">报告哈希: '+rhMsg+'</p>',
      '<p class="'+(chainOk?'ok':'bad')+'">哈希链: '+chainMsg+'</p>',
      '<p class="'+(tspOk?'ok':'bad')+'">时间戳: '+tspMsg+'</p>',
      '<p>区块链锚定: '+(anchor? (anchor.network+' · '+anchor.tx_hash) : '未附带')+'</p>',
      '<pre>'+JSON.stringify({report_id: report.id, standard: report.standard_name||report.standard, summary: report.summary}, null, 2)+'</pre>'
    ].join('');
    out.innerHTML = html;
  } catch(e){
    out.innerHTML = '<p class="bad">'+e.message+'</p><p>提示：在包目录执行 <code>python -m http.server 8765</code> 后打开本页。</p>';
  }
}
document.getElementById('run').onclick = verify;
</script>
</body>
</html>
"""


def build_chain_path(
    *,
    api_key: str,
    report: Mapping[str, Any],
    db_path=None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a chain visualization path.

    Default ``limit=None`` loads the full chain so integrity is not falsely
    broken at a tip-window edge. Pass a positive limit only for previews.
    """
    from attestation import GENESIS, verify_key_chain
    from models import list_chain

    rows = list_chain(api_key, limit=limit, db_path=db_path)
    links = list(rows)
    nodes = []
    broken_ids: List[str] = []
    for i, r in enumerate(links):
        ok = True
        note = None
        if i == 0:
            # Full-chain mode requires genesis; tip-window previews skip edge check.
            if limit is None and str(r.get("prev_hash") or "") not in ("", GENESIS):
                ok = False
                note = "链未从创世开始"
                broken_ids.append(str(r.get("id") or r.get("call_id") or i))
        else:
            prev = links[i - 1]
            ph = r.get("prev_hash")
            if ph and prev.get("hash") and ph != prev.get("hash"):
                ok = False
                note = "完整性验证失败"
                broken_ids.append(str(r.get("id") or r.get("call_id") or i))
        nodes.append(
            {
                "id": r.get("id") or r.get("call_id"),
                "timestamp": r.get("timestamp"),
                "event_type": r.get("event_type") or "call",
                "hash": r.get("hash") or r.get("chain_hash"),
                "prev_hash": r.get("prev_hash"),
                "ref_id": r.get("ref_id") or r.get("call_id"),
                "ok": ok,
                "note": note,
            }
        )
    # Highlight compliance report node
    rid = report.get("id") or report.get("check_id")
    for n in nodes:
        if n.get("ref_id") == rid or n.get("id") == rid:
            n["highlight"] = True
            n["label"] = "合规报告"
    if limit is None:
        proof = verify_key_chain(api_key, db_path=db_path)
        chain_ok = bool(proof.get("ok")) and len(broken_ids) == 0
        chain_msg = (
            "链完整"
            if chain_ok
            else str(proof.get("message") or f"断裂 {len(broken_ids)} 处")
        )
    else:
        chain_ok = len(broken_ids) == 0
        chain_msg = (
            f"预览窗口完整（最近 {len(nodes)} 环）"
            if chain_ok
            else f"预览窗口断裂 {len(broken_ids)} 处"
        )
    return {
        "report_id": rid,
        "report_hash": report.get("report_hash"),
        "n_nodes": len(nodes),
        "chain_verify": {
            "ok": chain_ok,
            "message": chain_msg,
        },
        "nodes": nodes,
        "broken": broken_ids,
    }


def build_offline_zip(
    *,
    report: Mapping[str, Any],
    pack: Mapping[str, Any],
    chain_path: Optional[Mapping[str, Any]] = None,
    verification: Optional[Mapping[str, Any]] = None,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "report.json",
            json.dumps(dict(report), ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "pack.json",
            json.dumps(dict(pack), ensure_ascii=False, indent=2),
        )
        if chain_path:
            zf.writestr(
                "chain.json",
                json.dumps(
                    {"links": chain_path.get("nodes") or [], "meta": {
                        "n_nodes": chain_path.get("n_nodes"),
                        "broken": chain_path.get("broken"),
                    }},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if verification:
            zf.writestr(
                "verification.json",
                json.dumps(dict(verification), ensure_ascii=False, indent=2),
            )
        zf.writestr("verify.html", _OFFLINE_VERIFY_HTML)
        zf.writestr(
            "README.txt",
            "ai-attestation offline verify pack\n"
            "1. Unzip\n"
            "2. python -m http.server 8765\n"
            "3. Open http://127.0.0.1:8765/verify.html\n"
            "No server from the vendor is required.\n",
        )
    return buf.getvalue()


def compliance_badge_svg(
    *,
    status: str,
    label: str = "AI审计合规",
    report_hash: str = "",
) -> str:
    st = (status or "unknown").lower()
    if st in ("pass", "ok", "passed", "compliant"):
        color = "#3dd68c"
        text = f"{label}：通过 ✓"
    elif st in ("fail", "failed", "noncompliant"):
        color = "#ff6b6b"
        text = f"{label}：未通过 ✗"
    elif st in ("manual", "partial"):
        color = "#e6c35c"
        text = f"{label}：部分/人工"
    else:
        color = "#7f8fa3"
        text = f"{label}：未知"
    # Escape
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    w = max(160, 9 * len(text) + 20)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{text}">
  <title>{text}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect width="{w}" height="20" rx="3" fill="#1e2a38"/>
  <rect x="0" width="78" height="20" rx="3" fill="#152033"/>
  <rect x="70" width="{w - 70}" height="20" rx="3" fill="{color}"/>
  <rect width="{w}" height="20" rx="3" fill="url(#s)"/>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">
    <text x="39" y="14">AI Audit</text>
    <text x="{(70 + w) / 2}" y="14">{text.split('：')[-1] if '：' in text else text}</text>
  </g>
</svg>"""


def build_notarization_request(
    *,
    report_hash: str,
    method: str = "opentimestamps",
) -> Dict[str, Any]:
    """Create a third-party notarization request stub (OTS / public chain).

    Does not call external networks by default — returns instructions + local receipt file path pattern.
    """
    rh = (report_hash or "").strip()
    if len(rh) < 16:
        raise ValueError("report_hash required")
    method = (method or "opentimestamps").lower()
    if method in ("opentimestamps", "ots"):
        return {
            "method": "opentimestamps",
            "payload_hash": rh,
            "status": "pending_user_submit",
            "instructions": [
                "将 report_hash 写入文本文件 hash.txt",
                "使用 ots stamp hash.txt（需安装 OpenTimestamps 客户端）",
                "将生成的 .ots 回传到本产品的时间戳登记接口",
            ],
            "verify_method": "ots verify hash.txt.ots",
            "note": "第三方时间戳可在厂商与本地数据均不可信时仍证明存在性。",
        }
    if method in ("blockchain", "sepolia", "anchor"):
        return {
            "method": "blockchain_anchor",
            "payload_hash": rh,
            "status": "use_existing_anchor_api",
            "instructions": [
                "调用 POST /v1/dashboard/attestation/anchor 锚定链头",
                "独立验证页将显示 tx_hash 与网络",
            ],
            "verify_method": "blockchain explorer + chain_head match",
        }
    raise ValueError(f"unknown notarization method: {method}")
