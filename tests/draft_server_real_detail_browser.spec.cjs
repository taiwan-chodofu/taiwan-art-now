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
 await expect(page.locator('#notice')).toContainText('サーバーに保存');
 const result=await page.evaluate(()=>({state:window.__state,events:window.__renders,local:localStorage.getItem('taiwan_art_favs')}));
 expect(result.state.favs.ex_1.deleted).toBe(false);expect(result.events).toHaveLength(1);expect(result.local).toBeNull();
});
