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
  const request=route.request();
  if(request.method()==='GET')return route.fulfill(response(server));
  writes++;
  const body=request.postDataJSON();
  if(body.base_revision!==server.revision)return route.fulfill({status:409,body:'{}'});
  server={...server,revision:3,favs:{art:{revision:3,deleted:false,value:body.changes.favs.art.set}}};
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
  const revision=reads<=2?1:2;
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
  if(route.request().method()==='POST'){
   writes++;
   const payload=route.request().postDataJSON();
   server={revision:2,favs:{art:{revision:2,deleted:false,value:payload.changes.favs.art.set}},visited:{}};
   return route.fulfill(response(server));
  }
  reads++;
  // Initial staging read, review read, pre-write read, verification read succeed.
  // The subsequent in-place UI refresh fails; no POST must be repeated.
  if(reads>=5)return route.abort('failed');
  return route.fulfill(response(server));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('保存しましたが、最新の表示を確認できません');
 await expect(page.locator('#reloadState')).toBeVisible();
 expect(writes).toBe(1);
});

test('uncertain restore shows current server state after manual reload without a second write',async({page})=>{
 let writes=0;
 let server={revision:1,favs:{art:{revision:1,deleted:true,value:null}},visited:{}};
 await page.addInitScript(()=>{
  localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}}));
  localStorage.setItem('taiwan_art_visited','{}');
 });
 await page.route('**/api/private-subscribers/v2/**',route=>{
  if(route.request().method()==='POST'){
   writes++;
   const payload=route.request().postDataJSON();
   server={revision:2,favs:{art:{revision:2,deleted:false,value:payload.changes.favs.art.set}},visited:{}};
   return route.abort('failed'); // Simulate a committed write with lost response.
  }
  return route.fulfill(response(server));
 });
 await page.goto(url+'&review=1');
 await page.locator('#migrationReview').getByRole('button',{name:'「観たい」に戻す'}).click();
 await page.locator('#restoreYes').click();
 await expect(page.locator('#notice')).toContainText('保存できたか確認できません');
 await page.locator('#reloadState').click();
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
 const refreshed=await page.evaluate(()=>window.__draftLifecycle?.refresh?.());
 // The fixture may keep its lifecycle private: trigger its existing manual refresh control.
 if(refreshed===undefined){
  await page.locator('#reloadState').click({force:true});
 }
 await expect(page.locator('#favBtn')).toBeDisabled();
 await expect(page.locator('#visitedBtn')).toBeDisabled();
 await page.locator('#favBtn').dispatchEvent('click');
 await page.locator('#visitedBtn').dispatchEvent('click');
 expect(writes).toBe(0);
});
