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


_CALL_OFFLINE_VERIFY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>调用离线验证 · ai-attestation</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b0f14;color:#d7e0ea;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;color:#3dd68c} .card{background:#121820;border:1px solid #243044;border-radius:8px;padding:16px;margin:12px 0}
.ok{color:#3dd68c}.bad{color:#ff6b6b} button{background:#1a3a2a;color:#3dd68c;border:1px solid #2a5c42;padding:8px 14px;border-radius:4px;cursor:pointer}
pre{white-space:pre-wrap;word-break:break-all;font-size:11px;color:#9eb2c7}
</style>
</head>
<body>
<h1>API 调用 · 离线验证包</h1>
<p>本页纯静态运行，不访问任何服务器。同目录需有 <code>call.json</code>（可选 <code>chain.json</code> / <code>verification.json</code>）。</p>
<p>说明：原始请求/响应正文未入库，本包仅校验哈希链见证字段。</p>
<div class="card">
<button id="run">运行本地验证</button>
<div id="out"></div>
</div>
<script>
async function loadJSON(name){
  const r = await fetch(name);
  if(!r.ok) throw new Error('缺少 '+name+'（请用本地 HTTP 打开：python -m http.server 8765）');
  return r.json();
}
function sha256Hex(str){
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)).then(buf=>{
    return [...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('');
  });
}
/** Match Python: cost_usd formatted as %.8f then joined with | */
function cost8(v){
  const n = Number(v || 0);
  return n.toFixed(8);
}
async function recomputeChainHash(call){
  const GENESIS = '0'.repeat(64);
  const prev = String(call.prev_hash || GENESIS);
  const payload = [
    prev,
    String(call.id || ''),
    String(call.timestamp || ''),
    String(call.endpoint || ''),
    String(call.request_hash || ''),
    String(call.response_hash || ''),
    String(Number(call.status_code || 0)),
    cost8(call.cost_usd),
  ].join('|');
  return sha256Hex(payload);
}
async function verify(){
  const out = document.getElementById('out');
  out.innerHTML = '验证中…';
  try {
    const call = await loadJSON('call.json');
    const chain = await loadJSON('chain.json').catch(()=>null);
    const serverV = await loadJSON('verification.json').catch(()=>null);
    let linkOk = false, linkMsg = '';
    if (window.isSecureContext && crypto.subtle) {
      const expected = await recomputeChainHash(call);
      const actual = String(call.chain_hash || '');
      linkOk = expected === actual;
      linkMsg = linkOk
        ? 'chain_hash 与本地重算一致'
        : ('chain_hash 不一致 expected='+expected+' actual='+actual);
    } else {
      linkMsg = '非安全上下文：无法重算 SHA-256（请用本地 http.server 打开）';
    }
    let adjOk = true, adjMsg = '无 chain.json（跳过邻接检查）';
    if (chain && Array.isArray(chain.links) && chain.links.length >= 2) {
      const trusted = !(chain.meta && chain.meta.adjacency_trusted === false);
      if (!trusted) {
        adjOk = false;
        adjMsg = (chain.meta && chain.meta.message) || '邻接片段不可用（未在全链定位），请以本调用链接校验为准';
      } else {
        const broken = [];
        for (let i=1;i<chain.links.length;i++){
          const prev = chain.links[i-1], cur = chain.links[i];
          if (cur.prev_hash && prev.hash && cur.prev_hash !== prev.hash) broken.push(i);
        }
        adjOk = broken.length === 0;
        adjMsg = adjOk
          ? ('相邻链指针完整 · '+chain.links.length+' 节点')
          : ('断裂于索引 '+broken.join(','));
      }
    }
    const parts = [
      '<p class="'+(linkOk?'ok':'bad')+'">本调用链接: '+linkMsg+'</p>',
      '<p class="'+(adjOk?'ok':'bad')+'">邻接链: '+adjMsg+'</p>',
    ];
    if (serverV) {
      parts.push('<p>服务端当时校验: '+(serverV.ok?'✓ ':'✗ ')+(serverV.message||'')+'</p>');
    }
    parts.push('<pre>'+JSON.stringify({
      id: call.id,
      timestamp: call.timestamp,
      endpoint: call.endpoint,
      model: call.model,
      request_hash: call.request_hash,
      response_hash: call.response_hash,
      prev_hash: call.prev_hash,
      chain_hash: call.chain_hash,
    }, null, 2)+'</pre>');
    out.innerHTML = parts.join('');
  } catch(e){
    out.innerHTML = '<p class="bad">'+e.message+'</p><p>提示：解压后在包目录执行 <code>python -m http.server 8765</code>，再打开本页。</p>';
  }
}
document.getElementById('run').onclick = verify;
</script>
</body>
</html>
"""


def _call_export_record(call: Mapping[str, Any]) -> Dict[str, Any]:
    """Public attestation fields only — never include api_key or raw bodies."""
    keys = (
        "id",
        "timestamp",
        "endpoint",
        "method",
        "model",
        "vendor",
        "status_code",
        "request_size",
        "response_size",
        "duration_ms",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
        "request_hash",
        "response_hash",
        "prev_hash",
        "chain_hash",
    )
    out: Dict[str, Any] = {}
    for k in keys:
        out[k] = call.get(k)
    # Normalize cost so offline verify.html matches Python round(..., 8) + %.8f
    try:
        out["cost_usd"] = round(float(out.get("cost_usd") or 0), 8)
    except (TypeError, ValueError):
        out["cost_usd"] = 0.0
    try:
        out["status_code"] = int(out.get("status_code") or 0)
    except (TypeError, ValueError):
        out["status_code"] = 0
    return out


def build_call_chain_snippet(
    call: Mapping[str, Any],
    *,
    api_key: str,
    db_path: Optional[Any] = None,
    window: int = 6,
) -> Dict[str, Any]:
    """Neighbor links around this call from attestation_chain (for offline context)."""
    from models import list_chain

    target = str(call.get("chain_hash") or "")
    tip = list_chain(api_key, limit=max(window * 4, 24), db_path=db_path)
    idx = next((i for i, r in enumerate(tip) if str(r.get("hash") or "") == target), -1)
    source = "attestation_chain_tip"
    rows = tip
    if idx < 0 and api_key:
        # Old calls may fall outside the tip window — scan full chain.
        rows = list_chain(api_key, limit=None, db_path=db_path)
        idx = next((i for i, r in enumerate(rows) if str(r.get("hash") or "") == target), -1)
        source = "attestation_chain_full"

    if idx < 0:
        links = [
            {
                "id": "prev",
                "event_type": "prev",
                "hash": call.get("prev_hash"),
                "ok": True,
            },
            {
                "id": call.get("id"),
                "timestamp": call.get("timestamp"),
                "event_type": "api_call",
                "hash": call.get("chain_hash"),
                "prev_hash": call.get("prev_hash"),
                "ok": True,
                "highlight": True,
                "label": "本调用",
            },
        ]
        return {
            "links": links,
            "meta": {
                "n_nodes": len(links),
                "source": "call_only",
                "adjacency_trusted": False,
                "message": "未在证据链表中定位本调用，邻接检查仅供参考",
            },
        }

    lo = max(0, idx - window // 2)
    hi = min(len(rows), idx + window // 2 + 1)
    slice_rows = rows[lo:hi]
    links: List[Dict[str, Any]] = []
    for r in slice_rows:
        h = str(r.get("hash") or "")
        links.append(
            {
                "id": r.get("ref_id") or r.get("id"),
                "timestamp": r.get("timestamp"),
                "event_type": r.get("event_type") or "event",
                "hash": h,
                "prev_hash": r.get("prev_hash"),
                "ok": True,
                "highlight": h == target,
                "label": "本调用" if h == target else None,
            }
        )
    return {
        "links": links,
        "meta": {
            "n_nodes": len(links),
            "source": source,
            "adjacency_trusted": True,
        },
    }


def build_call_offline_zip(
    *,
    call: Mapping[str, Any],
    verification: Optional[Mapping[str, Any]] = None,
    chain: Optional[Mapping[str, Any]] = None,
    api_key: Optional[str] = None,
    db_path: Optional[Any] = None,
) -> bytes:
    """ZIP: call.json + chain.json + verification.json + verify.html + README.txt."""
    record = _call_export_record(call)
    if chain is None and api_key:
        chain = build_call_chain_snippet(call, api_key=api_key, db_path=db_path)
    if chain is None:
        chain = build_call_chain_snippet(call, api_key=str(call.get("api_key") or ""), db_path=db_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "call.json",
            json.dumps(record, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "chain.json",
            json.dumps(dict(chain), ensure_ascii=False, indent=2),
        )
        if verification is not None:
            zf.writestr(
                "verification.json",
                json.dumps(dict(verification), ensure_ascii=False, indent=2),
            )
        zf.writestr("verify.html", _CALL_OFFLINE_VERIFY_HTML)
        zf.writestr(
            "README.txt",
            (
                "ai-attestation · API 调用离线验证包\n"
                "================================\n"
                "\n"
                "本 ZIP 含见证字段（哈希），不含请求/响应原文。\n"
                "\n"
                "使用步骤：\n"
                "1. 解压到任意目录\n"
                "2. 在该目录执行：python -m http.server 8765\n"
                "3. 浏览器打开：http://127.0.0.1:8765/verify.html\n"
                "4. 点击「运行本地验证」\n"
                "\n"
                "文件说明：\n"
                "- call.json          本调用见证记录\n"
                "- chain.json         邻接哈希链片段\n"
                "- verification.json  导出时服务端校验结果\n"
                "- verify.html        纯前端离线校验页\n"
                "\n"
                "无需连接 ai-attestation 服务器即可复核本调用的 chain_hash。\n"
            ),
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
