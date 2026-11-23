const {test,expect}=require('@playwright/test');
const path=require('node:path');
async function boot(page,{failPost=false}={}){
 await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
 await page.setContent('<button id="want">観たい</button><button id="seen">観た</button><p id="notice" hidden></p>');
 await page.evaluate(()=>{localStorage.removeItem('taiwan_art_favs');localStorage.removeItem('taiwan_art_visited');});
 await page.route('**/api/private-subscribers/v2/**',async route=>{
  const req=route.request(),url=req.url();
  if(req.method()==='POST'&&failPost)return route.abort('failed');
  const state=await page.evaluate(()=>window.__syntheticServer);
  if(req.method()==='GET')return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)});
  const {base_revision,changes}=req.postDataJSON();
  if(base_revision!==state.revision)return route.fulfill({status:409,contentType:'application/json',body:'{}'});
  const next={...state,revision:state.revision+1,favs:{...state.favs},visited:{...state.visited}};
  for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(changes[kind]))next[kind][key]={revision:next.revision,deleted:!!op.delete,value:op.delete?null:op.set};
  await page.evaluate(s=>{window.__syntheticServer=s},next);
  return route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(next)});
 });
 await page.evaluate(()=>{window.__syntheticServer={revision:0,favs:{},visited:{}};window.__renderEvents=[];});
 for(const name of ['draft_versioned_sync.js','draft_authenticated_state.js','draft_authenticated_writer.js','draft_server_page_action.js','draft_server_button_bridge.js'])
  await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 await page.evaluate(()=>{
  window.__bridge=TanDraftServerButtonBridge.mount({win:window,fetchImpl:window.fetch.bind(window),lang:'ja',
   notice:document.getElementById('notice'),
   buttons:[{element:document.getElementById('want'),kind:'favs',key:'art',action:'set',value:{title:'Art'},expectedRevision:0},
    {element:document.getElementById('seen'),kind:'visited',key:'art',action:'set',value:'2026-11-23',expectedRevision:0}],
   onRender:x=>window.__renderEvents.push(x)});
 });
}
test('Chromium draft: server-confirmed button updates UI, not legacy storage',async({page})=>{
 await boot(page);await page.locator('#want').click();
 await expect(page.locator('#notice')).toContainText('サーバーに保存');
 await expect(page.locator('#want')).toBeDisabled();
 const data=await page.evaluate(()=>({server:window.__syntheticServer,events:window.__renderEvents,local:localStorage.getItem('taiwan_art_favs')}));
 expect(data.server.favs.art.deleted).toBe(false);expect(data.events).toHaveLength(1);expect(data.local).toBeNull();
});
test('Chromium draft: second button with stale revision asks for reload, does not claim success',async({page})=>{
 await boot(page);await page.locator('#want').click();await page.locator('#seen').click();
 await expect(page.locator('#notice')).toContainText('ページを再読み込み');
 const data=await page.evaluate(()=>({server:window.__syntheticServer,events:window.__renderEvents}));
 expect(data.server.visited.art).toBeUndefined();expect(data.events).toHaveLength(1);
});
test('Chromium draft: failed POST never announces success or auto-retries',async({page})=>{
 await boot(page,{failPost:true});await page.locator('#want').click();
 await expect(page.locator('#notice')).toContainText('保存できたか確認できません');
 expect(await page.evaluate(()=>window.__renderEvents.length)).toBe(0);
});
test('Chromium draft: legacy inline onclick blocks staging mount',async({page})=>{
 await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
 for(const name of ['draft_versioned_sync.js','draft_authenticated_state.js','draft_authenticated_writer.js','draft_server_page_action.js','draft_server_button_bridge.js'])
  await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 const message=await page.evaluate(()=>{const b=document.createElement('button'),n=document.createElement('p');b.onclick=()=>{};try{TanDraftServerButtonBridge.mount({win:window,fetchImpl:fetch,buttons:[{element:b,kind:'favs',key:'a',action:'set',value:true,expectedRevision:0}],notice:n});return 'unexpected success';}catch(e){return e.message;}});
 expect(message).toContain('invalid staging mount');
});

test('Chromium draft: cached legacy tab can overwrite local map but not server-confirmed want',async({browser})=>{
 const context=await browser.newContext();
 try{
  const modern=await context.newPage(),legacy=await context.newPage();
  await boot(modern);
  await legacy.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
  const stale=await legacy.evaluate(()=>localStorage.getItem('taiwan_art_favs')||'{}');
  await modern.locator('#want').click();
  await expect(modern.locator('#notice')).toContainText('サーバーに保存');
  await legacy.evaluate(raw=>{
   const map=JSON.parse(raw);map.older={title:'Cached tab'};
   localStorage.setItem('taiwan_art_favs',JSON.stringify(map));
  },stale);
  const local=await modern.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')));
  expect(Object.keys(local)).toEqual(['older']);
  const server=await modern.evaluate(()=>window.__syntheticServer);
  expect(server.favs.art.deleted).toBe(false);
  expect(server.favs.art.value.title).toBe('Art');
  // This is isolation, not automatic recovery of the legacy local map.
 }finally{await context.close();}
});
