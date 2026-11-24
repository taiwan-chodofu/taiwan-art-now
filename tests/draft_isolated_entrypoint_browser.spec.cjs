const {test,expect}=require('@playwright/test');
const path=require('node:path');
const url='http://127.0.0.1:8765/tests/fixtures/isolated_staging_exhibition.html?key=art';
function response(state){return {status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify(state)};}
test('isolated HTML entrypoint: save want, save seen, remove want, keep seen',async({page})=>{
 let state={revision:0,favs:{},visited:{}},writes=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{
  const req=route.request();
  if(req.method()==='GET')return route.fulfill(response(state));
  writes++;
  const {base_revision,changes}=req.postDataJSON();
  if(base_revision!==state.revision)return route.fulfill({status:409,body:'{}'});
  const next={revision:state.revision+1,favs:{...state.favs},visited:{...state.visited}};
  for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(changes[kind]))
   next[kind][key]={revision:next.revision,deleted:!!op.delete,value:op.delete?null:op.set};
  state=next;
  return route.fulfill(response(state));
 });
 await page.goto(url);
 await expect(page.locator('#favBtn')).toBeEnabled();
 await page.locator('#favBtn').click();
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
 await page.locator('#visitedBtn').click();
 await expect(page.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
 await page.locator('#favBtn').click();
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','false');
 await expect(page.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
 expect(writes).toBe(3);
 expect(state.favs.art.deleted).toBe(true);
 expect(state.visited.art.deleted).toBe(false);
 expect(await page.evaluate(()=>[localStorage.getItem('taiwan_art_favs'),localStorage.getItem('taiwan_art_visited')])).toEqual([null,null]);
});
test('isolated HTML entrypoint: missing key stays disabled without API requests',async({page})=>{
 let calls=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{calls++;return route.abort();});
 await page.goto(url.replace('?key=art',''));
 await expect(page.locator('#notice')).toContainText('展示IDを確認できません');
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 expect(calls).toBe(0);
});
test('isolated HTML entrypoint: uncertain POST stays locked without automatic retry',async({page})=>{
 let writes=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST'){writes++;return route.abort('failed');}
  return route.fulfill(response({revision:0,favs:{},visited:{}}));
 });
 await page.goto(url);
 await expect(page.locator('#favBtn')).toBeEnabled();
 await page.locator('#favBtn').click();
 await expect(page.locator('#notice')).toContainText('保存できたか確認できません');
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 expect(writes).toBe(1);
});

test('isolated HTML entrypoint: unauthenticated response cannot enable saves',async({page})=>{
 let writes=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill({status:403,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:'{"error":"forbidden"}'});
 });
 await page.goto(url);
 await expect(page.locator('#notice')).toContainText('ページを再読み込み');
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 expect(writes).toBe(0);
});
test('isolated HTML entrypoint: HTML login redirect is not trusted as saved state',async({page})=>{
 let writes=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill({status:200,contentType:'text/html',body:'<html><body>Login</body></html>'});
 });
 await page.goto(url);
 await expect(page.locator('#notice')).toContainText('ページを再読み込み');
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 expect(writes).toBe(0);
});

test('opt-in review only asks about previously removed exhibition and does not write',async({page})=>{
 let writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill(response({revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}}));
 });
 await page.goto(url+'&review=1');
 const review=page.locator('#migrationReview');
 await expect(review).toContainText('「観たい」に戻しますか？');
 await expect(review.getByRole('button',{name:'戻さない'})).toBeVisible();
 await review.getByRole('button',{name:'「観たい」に戻す'}).click();
 await expect(review.getByRole('button',{name:'「観たい」に戻す'})).toBeDisabled();
 await expect(page.locator('#notice')).toContainText('まだ登録は変更していません');
 expect(writes).toBe(0);
 expect(await page.evaluate(()=>window.__draftReviewIntent)).toEqual({
  kind:'favs',key:'art',choice:'request_restore',requiresFreshRead:true
 });
});
test('opt-in review stays invisible when registration was not explicitly deleted',async({page})=>{
 let writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill(response({revision:0,favs:{},visited:{}}));
 });
 await page.goto(url+'&review=1');
 await expect(page.locator('#favBtn')).toBeEnabled();
 await expect(page.locator('#migrationReview')).toBeEmpty();
 expect(writes).toBe(0);
});

test('opt-in review: keeping a deletion dismisses question without writing',async({page})=>{
 let writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill(response({revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}}));
 });
 await page.goto(url+'&review=1');
 await expect(page.locator('#migrationReview').getByRole('button',{name:'戻さない'})).toBeVisible();
 await page.locator('#migrationReview').getByRole('button',{name:'戻さない'}).click();
 await expect(page.locator('#migrationReview')).toBeEmpty();
 expect(writes).toBe(0);
});

test('explicit second confirmation restores only reviewed tombstone and preserves seen',async({page})=>{
 let writes=0;
 let server={revision:2,favs:{art:{revision:1,deleted:true,value:null}},visited:{art:{revision:2,deleted:false,value:true}}};
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().url().endsWith('/issue'))return route.fulfill(response({token:'synthetic'}));
  if(route.request().method()==='POST')expect(route.request().url()).toMatch(/review\/keep\/consume$/);
  const request=route.request();
  if(request.method()==='GET')return route.fulfill(response(server));
  writes++;
  const body=request.postDataJSON();
  expect(body.token).toBe('synthetic');
  server={...server,revision:3,favs:{art:{revision:3,deleted:false,value:body.local_value}}};
  return route.fulfill(response(server));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 expect(writes).toBe(0);
 await expect(page.locator('#restoreConfirm')).toBeVisible();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('最新の登録を表示しています');
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('#reloadState')).toBeHidden();
 expect(writes).toBe(1);
 expect(server.visited.art.deleted).toBe(false);
});
test('cancel final confirmation does not write',async({page})=>{
 let writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST')writes++;
  return route.fulfill(response({revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}}));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreNo').click();
 await expect(page.locator('#restoreConfirm')).toBeHidden();
 expect(writes).toBe(0);
});

test('final restore refuses changed server revision without POST',async({page})=>{
 let writes=0,reads=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST'){writes++;return route.abort();}
  reads++;
  const revision=reads===1?1:2;
  return route.fulfill(response({revision,favs:{art:{revision:1,deleted:true,value:null}},visited:{}}));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('登録状況が変わりました');
 expect(writes).toBe(0);
});
test('final restore uncertain POST never retries or announces success',async({page})=>{
 let writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().url().endsWith('/issue'))return route.fulfill(response({token:'synthetic'}));
  if(route.request().method()==='POST')expect(route.request().url()).toMatch(/review\/keep\/consume$/);
  if(route.request().method()==='POST'){writes++;return route.abort('failed');}
  return route.fulfill(response({revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}}));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('保存できたか確認できません');
 await expect(page.locator('#restoreYes')).toBeDisabled();
 await expect(page.locator('#reloadState')).toBeVisible();
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 expect(writes).toBe(1);
});

test('confirmed restore with failed automatic refresh offers manual fallback',async({page})=>{
 let server={revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}};
 let reads=0,writes=0;
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().url().endsWith('/issue'))return route.fulfill(response({token:'synthetic'}));
  if(route.request().method()==='POST')expect(route.request().url()).toMatch(/review\/keep\/consume$/);
  if(route.request().method()==='POST'){
   writes++;
   const payload=route.request().postDataJSON();
   server={revision:2,favs:{art:{revision:2,deleted:false,value:payload.local_value}},visited:{}};
   return route.fulfill(response(server));
  }
  reads++;
  // Initial staging and review read, pre-write read, verification read succeed.
  // The subsequent in-place UI refresh fails; no POST must be repeated.
  if(reads>=4)return route.abort('failed');
  return route.fulfill(response(server));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('保存しましたが、最新の表示を確認できません');
 await expect(page.locator('#reloadState')).toBeVisible();
 expect(writes).toBe(1);
});

test('uncertain restore shows current server state automatically without a second write',async({page})=>{
 let writes=0;
 let server={revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}};
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().url().endsWith('/issue'))return route.fulfill(response({token:'synthetic'}));
  if(route.request().method()==='POST')expect(route.request().url()).toMatch(/review\/keep\/consume$/);
  if(route.request().method()==='POST'){
   writes++;
   const payload=route.request().postDataJSON();
   server={revision:2,favs:{art:{revision:2,deleted:false,value:payload.local_value}},visited:{}};
   return route.abort('failed'); // Simulate a committed write with lost response.
  }
  return route.fulfill(response(server));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('最新の登録状況を表示しています');
 await expect(page.locator('#reloadState')).toBeHidden();
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('#migrationReview')).toBeEmpty();
 expect(writes).toBe(1);
});

test('failed fresh-state refresh removes old action listeners and never writes',async({page})=>{
 let reads=0,writes=0;
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST'){writes++;return route.fulfill({status:500,body:'{}'});}
  reads++;
  if(reads>1)return route.abort('failed');
  return route.fulfill(response({revision:0,favs:{},visited:{}}));
 });
 await page.goto(url);
 await expect(page.locator('#favBtn')).toBeEnabled();
 const refreshed=await page.evaluate(()=>window.__draftStagingRefresh());
 expect(refreshed).toBe(false);
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 await page.locator('#favBtn').dispatchEvent('click');
 await page.locator('#visitedBtn').dispatchEvent('click');
 expect(writes).toBe(0);
});

test('out-of-order refresh responses cannot overwrite newer button state',async({page})=>{
 let reads=0;
 let releaseOld;
 const oldPending=new Promise(resolve=>{releaseOld=resolve;});
 await page.route('**/api/private-subscribers/v2/**',async route=>{
  if(route.request().method()==='POST')return route.fulfill({status:500,body:'{}'});
  reads++;
  if(reads===2){
   await oldPending;
   return route.fulfill(response({revision:1,favs:{},visited:{}})).catch(()=>{});
  }
  return route.fulfill(response(reads>=3
   ?{revision:2,favs:{art:{revision:2,deleted:false,value:true}},visited:{}}
   :{revision:1,favs:{},visited:{}}));
 });
 await page.goto(url);
 await expect(page.locator('#favBtn')).toBeEnabled();
 const old=page.evaluate(()=>window.__draftStagingRefresh());
 await expect.poll(()=>reads).toBe(2);
 const newer=await page.evaluate(()=>window.__draftStagingRefresh());
 expect(newer).toBe(true);
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
 releaseOld();
 expect(await old).toBe(false);
 await expect(page.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('#favBtn')).toBeEnabled();
});

test('lost reply after a write displays current state from both browser contexts',async({browser})=>{
 const first=await browser.newContext();
 const second=await browser.newContext();
 let server={revision:0,favs:{},visited:{}};
 const writes=[];
 try{
  for(const [context,kind] of [[first,'favs'],[second,'visited']]){
   await context.route('**/api/private-subscribers/v2/**',route=>{
    const request=route.request();
    if(request.method()==='GET')return route.fulfill(response(server));
    const {base_revision,changes}=request.postDataJSON();
    writes.push(kind);
    if(base_revision!==server.revision)return route.fulfill({status:409,body:'{}'});
    const revision=server.revision+1;
    server={...server,revision,[kind]:{art:{revision,deleted:false,value:changes[kind].art.set}}};
    return kind==='visited'?route.abort('failed'):route.fulfill(response(server));
   });
  }
  const a=await first.newPage(),b=await second.newPage();
  await a.goto(url);
  await b.goto(url);
  await a.locator('#favBtn').click();
  await expect(a.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
  await b.locator('#visitedBtn').click(); // Old revision can only refresh.
  await expect(b.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
  await b.locator('#visitedBtn').click();
  await expect(b.locator('#notice')).toHaveText('この展示は現在「観た」に登録されています。');
  await expect(b.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
  await expect(b.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
  expect(writes).toEqual(['favs','visited']);
 }finally{
  await first.close();
  await second.close();
 }
});

test('installed worker never caches private state and an old controller cannot supply it offline',async({browser})=>{
 const http=require('node:http'),fs=require('node:fs');
 const worker=fs.readFileSync(path.resolve(__dirname,'../static/sw.js'),'utf8');
 let privateReads=0;
 const server=http.createServer((req,res)=>{
  const send=(type,body)=>{res.setHeader('Content-Type',type);res.end(body);};
  if(req.url==='/worker.js')return send('text/javascript',worker);
  if(req.url==='/legacy.js')return send('text/javascript',
   "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));"+
   "self.addEventListener('fetch',e=>{if(new URL(e.request.url).pathname.includes('private-subscribers'))e.respondWith(new Response(JSON.stringify({revision:8,favs:{},visited:{}}),{headers:{'Content-Type':'application/json','Cache-Control':'no-store'}}));});");
  if(req.url==='/api/private-subscribers/v2/state'){
   privateReads++;
   res.setHeader('Cache-Control','no-store');
   return send('application/json',JSON.stringify({revision:1,favs:{},visited:{}}));
  }
  send('text/html','<!doctype html><title>Offline worker rehearsal</title>');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 try{
  for(const script of ['/worker.js','/legacy.js']){
   const context=await browser.newContext();
   try{
    const page=await context.newPage();
    await page.goto(origin);
    await page.evaluate(async script=>{
     await navigator.serviceWorker.register(script);
     await navigator.serviceWorker.ready;
     if(!navigator.serviceWorker.controller)await new Promise(resolve=>
      navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));
    },script);
    for(const file of ['draft_versioned_sync.js','draft_authenticated_state.js'])
     await page.addScriptTag({path:path.resolve(__dirname,'../static/js',file)});
    if(script==='/worker.js'){
     expect(await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).status)).toBe('ready');
     expect(await page.evaluate(async()=>!!await caches.match('/api/private-subscribers/v2/state'))).toBe(false);
    }
    await context.setOffline(true);
    expect(await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).status))
      .toBe(script==='/worker.js'?'unavailable':'worker_update_required');
   }finally{await context.close();}
  }
  expect(privateReads).toBe(1);
 }finally{await new Promise(resolve=>server.close(resolve));}
});
