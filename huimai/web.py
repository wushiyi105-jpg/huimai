"""Web 入口:http.server 零依赖,单页两个页签。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .db import Database

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>惠买 · 同款到手哪家便宜</title>
<style>
:root{--bg:#0f1216;--card:#181d24;--line:#27303a;--text:#e7edf3;--dim:#8d99a6;--accent:#e2603a;--ok:#4fc18a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.7 "Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:940px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--dim);font-size:13px;margin-bottom:18px}
.tabs{display:flex;gap:8px;margin-bottom:18px}
.tab{padding:7px 14px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--dim);cursor:pointer}
.tab.on{color:#fff;background:var(--accent);border-color:var(--accent)}
.panel{display:none}.panel.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
label{display:block;font-size:13px;color:var(--dim);margin:10px 0 6px}
select,input,textarea{width:100%;background:#0c1015;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:10px;font:14px/1.6 inherit}
.row{display:flex;gap:10px;align-items:flex-end}.row>*{flex:1}
button.go{margin-top:12px;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 18px;font-weight:600;cursor:pointer}
button.go:disabled{opacity:.55;cursor:wait}
pre{white-space:pre-wrap;word-break:break-word;background:#0c1015;border:1px solid var(--line);border-radius:8px;padding:14px;min-height:90px;font:13px/1.65 "Cascadia Mono",monospace}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500}.hit{color:var(--ok)}
.badge{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--dim);margin-left:8px}
.badge.off{color:var(--accent);border-color:var(--accent)}

:root{--maxw:1000px;--bg:#fcfcf8;--card:#ffffff;--ink:#20243a;--text:#20243a;--dim:#6c7080;--line:#d8dae4;--accent:#3b4a9b;--muted:#6c7080}
.wrap{max-width:1000px}
body{background:#fcfcf8;color:#20243a;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
h1{color:#20243a}
header{max-width:1000px;margin:0 auto}
input,textarea,select{background:#fff;color:#20243a;border-color:#d8dae4;border-radius:2px}
button:not(.ghost):not(.tab){background:#3b4a9b;color:#fff;border-radius:2px}
button.ghost{background:transparent!important;color:#3b4a9b!important;border:1px solid #d8dae4!important}
h2,h3{color:#3b4a9b}
pre{background:#fafaf6;color:#20243a;border-color:#d8dae4}
.item,.card{border-color:#d8dae4;background:#ffffff}
.k,.empty,.hint{color:#6c7080}

h1{font-size:clamp(31px,5vw,39px);line-height:1.26}
.prod{display:block;font-size:11px;line-height:1.4;letter-spacing:.18em;font-weight:650;margin-bottom:8px;opacity:.72}
.lede,.sub{max-width:62ch;line-height:1.75}
.route{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:16px auto 20px;border:1px solid var(--line);background:var(--line);max-width:var(--maxw)}
.route span{padding:11px 13px;background:var(--card);font-size:12px;line-height:1.5}
.route b{display:block;font-size:10px;letter-spacing:.1em;margin-bottom:3px;opacity:.66}
button{min-height:46px}
input,select{min-height:44px}
pre{white-space:pre-wrap}
@media(max-width:680px){
  .wrap{padding:20px 16px 56px}
  .route{grid-template-columns:1fr}
  h1{font-size:30px!important}
  .row>div{min-width:100%!important}
  button{width:100%}
}

:root{--bg:#fcfcf8;--card:#fff;--line:#d8dae4;--text:#20243a;--dim:#6c7080;--accent:#3b4a9b}
body{background:#fcfcf8;color:#20243a}
h1{font-size:38px;line-height:1.25;letter-spacing:-.02em}
.sub{color:#6c7080;font-size:14px}
.tabs{display:flex;gap:0;margin:16px 0;border-bottom:1px solid #d8dae4}
.tab{border:0;border-radius:0;background:transparent;color:#6c7080;padding:10px 18px;border-bottom:3px solid transparent}
.tab.on{background:transparent;color:#20243a;border-bottom-color:#f0d34f}
.card{background:#fff;border:1px solid #d8dae4;border-radius:2px;box-shadow:none}
button,.go{background:#3b4a9b;border-radius:2px;letter-spacing:.03em;color:#fff}
button:hover,.go:hover{background:#303c80}
input,select,textarea{background:#fff;border-color:#d4d7e2;border-radius:2px;color:#20243a;font-variant-numeric:tabular-nums}
input:focus,select:focus,textarea:focus{border-color:#3b4a9b;box-shadow:0 0 0 2px #dfe2f3}
pre{background:#f8f9fd;border-color:#d8dae4;color:#20243a}
.item,.offer{border-left:3px solid #f0d34f;background:#fffdf2}
h3{color:#3b4a9b}


/* mobile-32 */

@media(max-width:760px){
  main{grid-template-columns:1fr!important}
  aside{border-right:0!important;border-bottom:1px solid #d8dae4;width:auto!important}
  section{padding:16px!important}
  .row{flex-wrap:wrap!important}
  .row>div{min-width:100%!important}
  h1{font-size:30px!important}
  .route{grid-template-columns:1fr!important}
  button{min-height:48px}
  pre{overflow-x:auto}
}

/* mobile-height */
@media(max-width:760px){main{min-height:auto!important}aside{min-height:0!important}}
</style></head><body><div class="wrap">
<h1><span class="prod">惠买</span>同款到手，哪家真便宜 <span id="status" class="badge">…</span></h1>
  <p class="sub">给在几个渠道对比同款的人：把 SKU、规格、运费、券条件和售后期限拆开，只用已满足的条件计算到手总价，保留报价时间和原链接。</p>
<div class="sub">内置示例报价,不接电商接口。比的是同一件商品在不同渠道的到手价。</div>
<div class="tabs">
  <button class="tab on" data-tab="cmp">比价</button>
  <button class="tab" data-tab="watch">关注清单</button>
</div>

<div class="panel on" id="cmp">
  
  <div class="route" aria-label="任务步骤"><span><b>01</b>贴各渠道报价</span><span><b>02</b>对齐同款规格</span><span><b>03</b>算到手总价</span></div>
<div class="card">
    <div class="row"><div><label>商品</label><select id="itemSel"></select></div>
    <div><label>目标价(可留空)</label><input id="target" type="number" min="0" step="1" placeholder="例如 600"></div></div>
    <button class="go" id="btnCompare">算到手价与建议</button>
    <button class="go" id="btnWatch" style="background:#2c3540">加进关注清单</button>
    <div id="offers" style="margin-top:14px"></div>
  </div>
  <div class="card"><pre id="outCmp">结果会出现在这里。</pre></div>
</div>

<div class="panel" id="watch">
  <div class="card"><table><thead><tr><th>商品</th><th>现最低</th><th>目标价</th><th>状态</th></tr></thead>
  <tbody id="watchBody"><tr><td colspan="4">读取中…</td></tr></tbody></table></div>
  <div class="sub">到价只是提示,买之前还是要确认店铺、发票与售后。</div>
</div>
</div>
<script>
const $=s=>document.querySelector(s);
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('on',p.id===t.dataset.tab));
});
function loading(btn,on){
  if(on){btn.dataset.label=btn.dataset.label||btn.textContent;btn.disabled=true;btn.textContent='处理中…';}
  else{btn.disabled=false;btn.textContent=btn.dataset.label||btn.textContent;}
}
async function api(path,opt){
  const r=await fetch(path,opt);const j=await r.json();
  if(!r.ok||j.error)throw new Error(j.error||('HTTP '+r.status));
  return j;
}
async function loadItems(){
  const items=await api('/api/items');
  $('#itemSel').innerHTML=items.map(i=>`<option value="${i.id}">${i.name} · ${i.specs}</option>`).join('')||'<option value="">还没有商品</option>';
  await loadOffers();
}
async function loadOffers(){
  const id=$('#itemSel').value;if(!id){$('#offers').innerHTML='';return;}
  const d=await api('/api/item?id='+id);
  const rows=(d.offers||[]).map(o=>`<tr><td>${o.platform}</td><td>¥${o.price}</td><td>¥${o.shipping}</td><td>${o.note||''}</td></tr>`).join('');
  $('#offers').innerHTML=`<table><thead><tr><th>渠道</th><th>售价</th><th>运费</th><th>说明</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function loadWatch(){
  try{
    const rows=await api('/api/watch');
    $('#watchBody').innerHTML=rows.map(w=>`<tr><td>${w.name}</td><td>¥${Math.round(w.best)}</td>
      <td>${w.target?'¥'+Math.round(w.target):'未设'}</td>
      <td class="${w.hit?'hit':''}">${w.hit?'到价':(w.target?'还没到':'观察中')}</td></tr>`).join('')
      ||'<tr><td colspan="4">清单是空的</td></tr>';
  }catch(e){$('#watchBody').innerHTML='<tr><td colspan="4">读取失败</td></tr>';}
}
$('#itemSel').onchange=loadOffers;
$('#btnCompare').onclick=async()=>{
  const btn=$('#btnCompare');loading(btn,true);
  try{
    const r=await api('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({product_id:Number($('#itemSel').value)||0,target:Number($('#target').value)||0})});
    $('#outCmp').textContent=r.text;
  }catch(e){$('#outCmp').textContent='出错:'+e.message;}
  finally{loading(btn,false);}
};
$('#btnWatch').onclick=async()=>{
  const btn=$('#btnWatch');loading(btn,true);
  try{
    await api('/api/watch',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({product_id:Number($('#itemSel').value)||0,target:Number($('#target').value)||0})});
    await loadWatch();
    $('#btnWatch').dataset.label='已加入';
  }catch(e){$('#outCmp').textContent='出错:'+e.message;}
  finally{loading(btn,false);delete btn.dataset.label;}
};
(async()=>{
  try{
    const s=await api('/api/status');
    const b=$('#status');b.textContent=s.offline?'离线模式':'模型 '+s.model;b.classList.toggle('off',s.offline);
    await loadItems();await loadWatch();
  }catch(e){$('#status').textContent='读取失败';}
})();
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    db: Database
    cfg: dict
    force_mock: bool

    def log_message(self, *args):
        pass

    def _json(self, data, code: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        try:
            data = json.loads(text or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        if path == "/":
            self._html(PAGE)
            return
        if path == "/api/status":
            self._json({"mode": "offline" if self.force_mock else "model",
                        "model": self.cfg.get("model", ""), "offline": self.force_mock})
            return
        if path == "/api/items":
            self._json(self.db.list_products())
            return
        if path == "/api/item":
            key = (qs.get("id") or [""])[0]
            p = self.db.get_product(int(key)) if key.isdigit() else None
            if not p:
                self._json({"error": "没这个商品"}, 404)
                return
            p["offers"] = self.db.list_offers(int(p["id"]))
            self._json(p)
            return
        if path == "/api/watch":
            self._json(self.db.list_watch())
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        data = self._read_json()
        try:
            if path == "/api/compare":
                self._compare(data)
            elif path == "/api/watch":
                self._watch(data)
            elif path == "/api/unwatch":
                pid = int(data.get("product_id") or 0)
                self._json({"removed": self.db.remove_watch(pid)})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 502)

    def _compare(self, data: dict):
        from . import agent, tools
        from .cli import render_compare
        pid = int(data.get("product_id") or 0)
        p = self.db.get_product(pid)
        if not p:
            self._json({"error": "先选一个商品"}, 400)
            return
        offers = self.db.list_offers(pid)
        if not offers:
            self._json({"error": "这个商品还没有报价"}, 400)
            return
        target = float(data.get("target") or 0)
        result = agent.compare(p, offers, target, self.cfg, self.force_mock)
        result["text"] = render_compare(result)
        result["unit"] = tools.unit_price(p.get("specs", ""), result["stats"]["best_total"])
        self._json(result)

    def _watch(self, data: dict):
        pid = int(data.get("product_id") or 0)
        p = self.db.get_product(pid)
        if not p:
            self._json({"error": "先选一个商品"}, 400)
            return
        target = float(data.get("target") or 0)
        wid = self.db.add_watch(pid, target)
        self._json({"id": wid, "product_id": pid, "target": target})


def _make_handler(db: Database, cfg: dict, force_mock: bool):
    return type("Handler", (_Handler,), {"db": db, "cfg": cfg, "force_mock": force_mock})


def serve(host: str = "127.0.0.1", port: int = 8772, db_path: str = "data/huimai.db",
          force_mock: bool = False, cfg: dict | None = None):
    from . import llm
    db = Database(db_path)
    cfg = dict(llm.default_config() if cfg is None else cfg)
    if not cfg.get("api_key"):
        force_mock = True
    handler = _make_handler(db, cfg, force_mock)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"🛒 惠买已启动  http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n· 已停止")
    finally:
        httpd.server_close()
        db.close()
