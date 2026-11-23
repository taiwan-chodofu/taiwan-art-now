// Isolated staging harness: real detail button markup, server-first bridge.
// Production template and legacy handlers are not modified or mounted.
const {test,expect}=require('@playwright/test');
const fs=require('node:fs'),path=require('node:path');
const raw=fs.readFileSync(path.resolve(__dirname,'../templates/exhibition_detail_page.html'),'utf8');
function html(){
 const buttons=['visited','fav'].map(kind=>{
  const m=raw.match(new RegExp('<button class="action-btn" id="'+kind+'Btn"[\\s\\S]*?<\\/button>'));
  if(!m)throw Error('real button missing: '+kind);
  return m[0].replace(/\s+onclick="[^"]*"/g,'').replace(/{%[\s\S]*?%}/g,'').replace(/{{[\s\S]*?}}/g,'');
 });
 return '<!doctype html><meta charset="utf-8">'+buttons.join('')+'<p id="notice" hidden></p>';
}
test('real detail markup: isolated server-first save does not invoke legacy handlers',async({page})=>{
 await page.route('**/detail-server-staging',r=>r.fulfill({status:200,contentType:'text/html',body:html()}));
 await page.goto('http://127.0.0.1:8765/detail-server-staging');
 await page.evaluate(()=>{localStorage.removeItem('taiwan_art_favs');localStorage.removeItem('taiwan_art_visited');window.__state={revision:0,favs:{},visited:{}};window.__renders=[];});
 await page.route('**/api/private-subscribers/v2/**',async route=>{
  const request=route.request();const state=await page.evaluate(()=>window.__state);
  if(request.method()==='GET')return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
  const body=request.postDataJSON();if(body.base_revision!==state.revision)return route.fulfill({status:409,body:'{}'});
  const next={...state,revision:state.revision+1,favs:{...state.favs},visited:{...state.visited}};
  for(const kind of ['favs','visited'])for(const [key,op]of Object.entries(body.changes[kind]))next[kind][key]={revision:next.revision,deleted:!!op.delete,value:op.delete?null:op.set};
  await page.evaluate(x=>{window.__state=x},next);
  return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(next)});
 });
 for(const name of ['draft_versioned_sync.js','draft_authenticated_state.js','draft_authenticated_writer.js','draft_server_page_action.js','draft_server_button_bridge.js'])await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 await page.evaluate(()=>{
  window.__bridge=TanDraftServerButtonBridge.mount({win:window,fetchImpl:fetch.bind(window),lang:'ja',notice:document.getElementById('notice'),buttons:[
   {element:document.getElementById('favBtn'),kind:'favs',key:'ex_1',action:'set',value:{title:'Exhibition'},expectedRevision:0},
   {element:document.getElementById('visitedBtn'),kind:'visited',key:'ex_1',action:'set',value:'2026-11-23',expectedRevision:0}
  ],onRender:x=>window.__renders.push(x)});
 });
 await page.locator('#favBtn').click();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 await expect(page.locator('#notice')).toContainText('サーバーに保存');
 const result=await page.evaluate(()=>({state:window.__state,events:window.__renders,local:localStorage.getItem('taiwan_art_favs')}));
 expect(result.state.favs.ex_1.deleted).toBe(false);expect(result.events).toHaveLength(1);expect(result.local).toBeNull();
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
});

test('real Discover markup: server-first want action never writes local exhibition map',async({page})=>{
 const discover=fs.readFileSync(path.resolve(__dirname,'../templates/discover.html'),'utf8');
 const extract=(id)=>{const marker='id="'+id+'"';const at=discover.indexOf(marker);if(at<0)return null;const start=discover.lastIndexOf('<button',at);const end=discover.indexOf('</button>',at);return start>=0&&end>at?[discover.slice(start,end+9)]:null;};
 const like=extract('likeBtn');
 const seen=extract('visitedBtn');
 if(!like||!seen)throw Error('actual Discover action markup changed');
 const markup=(like[0]+seen[0]).replaceAll('{{ labels.like }}','Save').replaceAll('{{ labels.seen }}','Seen');
 await page.route('**/discover-server-staging',r=>r.fulfill({status:200,contentType:'text/html',body:'<!doctype html><meta charset="utf-8">'+markup+'<p id="notice"></p>'}));
 await page.goto('http://127.0.0.1:8765/discover-server-staging');
 await page.evaluate(()=>{localStorage.removeItem('taiwan_art_favs');localStorage.removeItem('taiwan_art_visited');});
 let state={revision:0,favs:{},visited:{}};
 await page.route('**/api/private-subscribers/v2/**',route=>{
  const req=route.request();
  if(req.method()==='GET')return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
  const data=req.postDataJSON();
  if(data.base_revision!==state.revision)return route.fulfill({status:409,body:'{}'});
  state={revision:1,favs:{a:{revision:1,deleted:false,value:{title:'A'}}},visited:{}};
  return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
 });
 for(const name of ['draft_versioned_sync.js','draft_authenticated_state.js','draft_authenticated_writer.js','draft_server_page_action.js','draft_server_button_bridge.js'])await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 await page.evaluate(()=>{
  window.__renders=[];
  window.__bridge=TanDraftServerButtonBridge.mount({win:window,fetchImpl:fetch.bind(window),lang:'ja',notice:document.getElementById('notice'),buttons:[
   {element:document.getElementById('likeBtn'),kind:'favs',key:'a',action:'set',value:{title:'A'},expectedRevision:0}
  ],onRender:x=>__renders.push(x)});
 });
 await page.locator('#likeBtn').click();
 await expect(page.locator('#notice')).toContainText('サーバーに保存');
 expect(state.favs.a.deleted).toBe(false);
 expect(await page.evaluate(()=>({favs:localStorage.getItem('taiwan_art_favs'),visited:localStorage.getItem('taiwan_art_visited'),renders:__renders.length}))).toEqual({favs:null,visited:null,renders:1});
});

test('detail refresh supplies authoritative state but never re-enables stale descriptors',async({page})=>{
 await page.route('**/detail-refresh-staging',r=>r.fulfill({status:200,contentType:'text/html',body:html()}));
 await page.goto('http://127.0.0.1:8765/detail-refresh-staging');
 let state={revision:0,favs:{},visited:{}};
 await page.route('**/api/private-subscribers/v2/**',route=>{
  const req=route.request();
  if(req.method()==='GET')return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
  const data=req.postDataJSON();
  if(data.base_revision!==state.revision)return route.fulfill({status:409,body:'{}'});
  state={revision:1,favs:{ex_1:{revision:1,deleted:false,value:{title:'Exhibition'}}},visited:{}};
  return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
 });
 for(const name of ['draft_versioned_sync.js','draft_authenticated_state.js','draft_authenticated_writer.js','draft_server_page_action.js','draft_server_button_bridge.js'])await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 await page.evaluate(()=>{
  window.__refreshes=[];
  window.__bridge=TanDraftServerButtonBridge.mount({win:window,fetchImpl:fetch.bind(window),lang:'ja',notice:document.getElementById('notice'),buttons:[
   {element:document.getElementById('favBtn'),kind:'favs',key:'ex_1',action:'set',value:{title:'Exhibition'},expectedRevision:0},
   {element:document.getElementById('visitedBtn'),kind:'visited',key:'ex_1',action:'set',value:'2026-11-23',expectedRevision:0}
  ],onRefresh:state=>window.__refreshes.push(state)});
 });
 await page.locator('#favBtn').click();
 await expect.poll(()=>page.evaluate(()=>window.__refreshes.length)).toBe(1);
 expect(await page.evaluate(()=>window.__refreshes[0].revision)).toBe(1);
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
});
