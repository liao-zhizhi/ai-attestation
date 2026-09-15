"""科研优先权证书 ZIP（P0）。独立模板，不复用调用包 HTML / call.json。"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Dict, Mapping, Optional

from attestation import compute_research_artifact_chain_hash
from research import PACK_TYPE, public_artifact

# ZIP 内约定文件名（测试与导出共用，勿增删以免旧证书说明失效）
CERT_ZIP_NAMES = (
    "artifact.json",
    "chain.json",
    "verification.json",
    "timestamp.json",
    "verify.html",
    "README.txt",
)

# 离线页：校验 pack_type、重算 chain_hash、TSA token、可选原件指纹比对。
_PRIORITY_VERIFY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>优先权证书 · 离线验证 · ai-attestation</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b0f14;color:#d7e0ea;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;color:#3dd68c} .card{background:#121820;border:1px solid #243044;border-radius:8px;padding:16px;margin:12px 0}
.ok{color:#3dd68c}.bad{color:#ff6b6b} .muted{color:#7f8fa3;font-size:12px}
button{background:#1a3a2a;color:#3dd68c;border:1px solid #2a5c42;padding:8px 14px;border-radius:4px;cursor:pointer}
pre{white-space:pre-wrap;word-break:break-all;font-size:11px;color:#9eb2c7}
input[type=file]{color:#9eb2c7;margin-top:8px}
</style>
</head>
<body>
<h1>科研优先权证书 · 离线验证</h1>
<p>本页纯静态运行，不访问任何服务器。同目录需有 <code>artifact.json</code>（可选 <code>chain.json</code> / <code>timestamp.json</code> / <code>verification.json</code>）。</p>
<p class="muted">只验证指纹与链环。不能证明某家 AI 厂商训练或阅读了原文。不构成法律意见。</p>
<div class="card">
<button id="run">运行本地验证</button>
<div id="out"></div>
</div>
<div class="card">
<p>用原件选择文件（可选）：浏览器本地算 SHA-256，与证书中的指纹比对。改一个字即不匹配。</p>
<label>用原件选择文件
<input id="orig" type="file"/>
</label>
<div id="match"></div>
</div>
<script>
async function loadJSON(name){
  const r = await fetch(name);
  if(!r.ok) throw new Error('缺少 '+name+'（请用本地 HTTP 打开：python -m http.server 8765）');
  return r.json();
}
function sha256Hex(buf){
  return crypto.subtle.digest('SHA-256', buf).then(b=>{
    return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
  });
}
async function recomputeChain(art){
  const GENESIS = '0'.repeat(64);
  const prev = String(art.prev_hash || GENESIS);
  const payload = [
    prev,
    'research_artifact',
    String(art.id || ''),
    String(art.timestamp || ''),
    String(art.artifact_hash || ''),
    String(art.kind || ''),
  ].join('|');
  return sha256Hex(new TextEncoder().encode(payload));
}
async function verify(){
  const out = document.getElementById('out');
  out.innerHTML = '验证中…';
  try {
    const art = await loadJSON('artifact.json');
    const chain = await loadJSON('chain.json').catch(()=>null);
    const tsp = await loadJSON('timestamp.json').catch(()=>null);
    const serverV = await loadJSON('verification.json').catch(()=>null);
    const packOk = art.pack_type === 'ata-research-priority-v1';
    let linkOk = false, linkMsg = '';
    if (!packOk) {
      linkMsg = 'pack_type 不是 ata-research-priority-v1（请勿与调用验证包混用）';
    } else if (window.isSecureContext && crypto.subtle) {
      const expected = await recomputeChain(art);
      const actual = String(art.chain_hash || '');
      linkOk = expected === actual;
      linkMsg = linkOk ? 'chain_hash 与本地重算一致' : ('chain_hash 不一致 expected='+expected+' actual='+actual);
    } else {
      linkMsg = '非安全上下文：无法重算 SHA-256（请用本地 http.server 打开）';
    }
    let adjOk = true, adjMsg = '无 chain.json（跳过邻接检查）';
    if (chain && Array.isArray(chain.links) && chain.links.length >= 2) {
      const broken = [];
      for (let i=1;i<chain.links.length;i++){
        const prev = chain.links[i-1], cur = chain.links[i];
        if (cur.prev_hash && prev.hash && cur.prev_hash !== prev.hash) broken.push(i);
      }
      adjOk = broken.length === 0;
      adjMsg = adjOk
        ? ('相邻链指针完整 · '+chain.links.length+' 节点（本证书只含本环与前驱）')
        : ('断裂于索引 '+broken.join(','));
    }
    let tspOk = false, tspMsg = '未附带 timestamp.json';
    const receipt = tsp || art.tsa_receipt;
    if (receipt && receipt.token) {
      if (window.isSecureContext && crypto.subtle && receipt.payload_hash != null && receipt.unix != null && receipt.nonce) {
        const expected = await sha256Hex(new TextEncoder().encode(
          String(receipt.payload_hash)+'|'+String(receipt.unix)+'|'+String(receipt.nonce)
        ));
        const bindOk = String(receipt.payload_hash) === String(art.artifact_hash || '');
        tspOk = expected === String(receipt.token) && bindOk;
        tspMsg = tspOk
          ? ((receipt.source||'local')+' · '+ (receipt.timestamp||'') + ' · token 重算一致（本系统签发，非法院公证）')
          : '时间戳 token 重算失败或未绑定 artifact_hash';
      } else {
        tspMsg = '非安全上下文或时间戳字段不完整';
      }
    }
    const parts = [
      '<p class="'+(packOk?'ok':'bad')+'">证书类型: '+(packOk?'ata-research-priority-v1':'类型不符')+'</p>',
      '<p class="'+(linkOk?'ok':'bad')+'">本环哈希: '+linkMsg+'</p>',
      '<p class="'+(adjOk?'ok':'bad')+'">邻接链: '+adjMsg+'</p>',
      '<p class="'+(tspOk?'ok':'bad')+'">时间戳: '+tspMsg+'</p>',
    ];
    if (serverV) {
      parts.push('<p>导出时服务端校验: '+(serverV.ok?'✓ ':'✗ ')+(serverV.message||'')+'</p>');
    }
    parts.push('<pre>'+JSON.stringify({
      id: art.id,
      title: art.title,
      kind: art.kind,
      timestamp: art.timestamp,
      artifact_hash: art.artifact_hash,
      prev_hash: art.prev_hash,
      chain_hash: art.chain_hash,
    }, null, 2)+'</pre>');
    out.innerHTML = parts.join('');
  } catch(e){
    out.innerHTML = '<p class="bad">'+e.message+'</p><p>提示：解压后在包目录执行 <code>python -m http.server 8765</code>，再打开本页。</p>';
  }
}
document.getElementById('run').onclick = verify;
document.getElementById('orig').addEventListener('change', async (ev) => {
  const box = document.getElementById('match');
  const f = ev.target.files && ev.target.files[0];
  if (!f) { box.innerHTML = ''; return; }
  try {
    const art = await loadJSON('artifact.json');
    const buf = await f.arrayBuffer();
    const hex = await sha256Hex(buf);
    const want = String(art.artifact_hash || '');
    const ok = hex === want;
    box.innerHTML = '<p class="'+(ok?'ok':'bad')+'">'+(ok
      ? '原件与证书指纹一致'
      : ('指纹不匹配。文件='+hex+' 证书='+want))+'</p>';
  } catch (e) {
    box.innerHTML = '<p class="bad">'+e.message+'</p>';
  }
});
</script>
</body>
</html>
"""


def _chain_snippet(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    """证书只含本环与前驱哈希，不打包整条租户链。"""
    prev = artifact.get("prev_hash")
    return {
        "links": [
            {
                "id": "prev",
                "event_type": "prev",
                "hash": prev,
                "ok": True,
            },
            {
                "id": artifact.get("id"),
                "timestamp": artifact.get("timestamp"),
                "event_type": "research_artifact",
                "hash": artifact.get("chain_hash"),
                "prev_hash": prev,
                "ok": True,
                "highlight": True,
                "label": "科研工件",
            },
        ],
        "meta": {
            "n_nodes": 2,
            "source": "artifact_link",
            "adjacency_trusted": True,
            "pack_type": PACK_TYPE,
            "message": "本证书验证本环；完整账本请用作者环境中的全链校验",
        },
    }


def artifact_certificate_record(row: Mapping[str, Any]) -> Dict[str, Any]:
    """ZIP 内 artifact.json：公开字段 + 免责声明，禁止 api_key。"""
    out = public_artifact(dict(row))
    out["disclaimer"] = (
        "技术存证，不构成法律意见或学术优先权裁定。"
        "原文未包含在本包中。验证者可用原件本地再算 SHA-256 与 artifact_hash 比对。"
    )
    return out


def build_priority_certificate_zip(
    *,
    row: Mapping[str, Any],
    verification: Optional[Mapping[str, Any]] = None,
) -> bytes:
    """生成 ata_priority_{id}_cert.zip。"""
    art = artifact_certificate_record(row)
    chain = _chain_snippet(art)
    tsa = art.get("tsa_receipt") if isinstance(art.get("tsa_receipt"), dict) else {}
    if verification is None:
        prev = str(art.get("prev_hash") or "")
        expected = compute_research_artifact_chain_hash(
            prev_hash=prev,
            artifact_id=str(art.get("id") or ""),
            timestamp=str(art.get("timestamp") or ""),
            artifact_hash=str(art.get("artifact_hash") or ""),
            kind=str(art.get("kind") or ""),
        )
        actual = str(art.get("chain_hash") or "")
        verification = {
            "ok": expected == actual,
            "expected_hash": expected,
            "actual_hash": actual,
            "message": "research_artifact link intact"
            if expected == actual
            else "research_artifact link hash mismatch",
        }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "artifact.json",
            json.dumps(art, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "chain.json",
            json.dumps(chain, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "verification.json",
            json.dumps(dict(verification), ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "timestamp.json",
            json.dumps(tsa or {}, ensure_ascii=False, indent=2),
        )
        zf.writestr("verify.html", _PRIORITY_VERIFY_HTML)
        zf.writestr(
            "README.txt",
            (
                "ai-attestation · 科研优先权证书（离线验证包）\n"
                "==========================================\n"
                "\n"
                "本 ZIP 只含内容指纹（SHA-256），不含草稿/提示词原文。\n"
                "技术存证，不构成法律意见，不能证明某厂商训练了该内容。\n"
                "\n"
                "使用步骤：\n"
                "1. 解压到任意目录\n"
                "2. 在该目录执行：python -m http.server 8765\n"
                "3. 浏览器打开：http://127.0.0.1:8765/verify.html\n"
                "4. 点「运行本地验证」\n"
                "5. 如需核对原件：在页面「用原件选择文件」中选中当时那份文件\n"
                "\n"
                "文件说明：\n"
                "- artifact.json       工件见证（pack_type=ata-research-priority-v1）\n"
                "- chain.json          本环与前驱哈希\n"
                "- verification.json   导出时服务端校验\n"
                "- timestamp.json      本地 TSA 收据\n"
                "- verify.html         纯前端离线校验页（独立模板，勿与调用包混用）\n"
                "\n"
                "无需连接 ai-attestation 服务器即可复核本环 chain_hash。\n"
            ),
        )
    return buf.getvalue()


def certificate_filename(artifact_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in artifact_id)[:64]
    return f"ata_priority_{safe}_cert.zip"
