const {test,expect}=require('@playwright/test');

test('two cookie sessions restore a reviewed tombstone after a lost database write response',async({browser})=>{
 const origin='https://127.0.0.1';
 const contexts=[];
 try{
  for(const session of ['browser-drill-one','browser-drill-two']){
   const context=await browser.newContext({ignoreHTTPSErrors:true});
   contexts.push(context);
   await context.addCookies([{name:'__Host-tan_session',value:session,url:origin,
    secure:true,httpOnly:true,sameSite:'Lax'}]);
  }
  const a=await contexts[0].newPage(),b=await contexts[1].newPage();
  const url=origin+'/exhibition?key=art';
  await a.goto(url);
  await a.locator('#favBtn').click();
  await expect(a.locator('#favBtn')).toHaveAttribute('aria-pressed','true');
  await a.locator('#visitedBtn').click();
  await expect(a.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
  await a.locator('#favBtn').click();
  await expect(a.locator('#favBtn')).toHaveAttribute('aria-pressed','false');
  await b.addInitScript(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({art:{title:'展示',museum:'美術館'}})));
  let issued=0,consumed=0;
  b.on('request',req=>{if(req.url().endsWith('/keep/issue'))issued++;});
  await b.route('**/review/keep/consume',async route=>{
   consumed++;
   const committed=await route.fetch();
   expect(committed.status()).toBe(200);
   await route.abort('failed');
  });
  await b.goto(url+'&review=1');
  await b.getByRole('button',{name:'「観たい」に戻す'}).click();
  await b.locator('#restoreYes').click();
  await expect(b.locator('#notice')).toHaveText('最新の登録状況を表示しています。');
  for(const page of [b,a]){
   if(page===a)await page.reload();
   for(const selector of ['#favBtn','#visitedBtn'])
    await expect(page.locator(selector)).toHaveAttribute('aria-pressed','true');
  }
  const state=await a.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.revision).toBe(4);
  expect(state.favs.art).toEqual({revision:4,deleted:false,value:{title:'展示',museum:'美術館'}});
  expect(state.visited.art.revision).toBe(2);
  expect([issued,consumed]).toEqual([1,1]);
 }finally{await Promise.all(contexts.map(context=>context.close()));}
});

test('legacy migration survives a lost reply and a second device preserves independent flags and tombstones',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-migration-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  const page=await context.newPage();
  await page.goto('https://127.0.0.1/exhibition?key=migration');
  for(const file of ['draft_additive_merge','draft_loss_detector','draft_additive_retry'])
   await page.addScriptTag({url:'/static/js/'+file+'.js'});
  await page.evaluate(()=>{
   localStorage.setItem('taiwan_art_favs',JSON.stringify({migration:{title:'展示',museum:'美術館'}}));
   localStorage.setItem('taiwan_art_visited',JSON.stringify({migration:'2026-11-23T00:00:00.000Z'}));
  });
  const original=await page.evaluate(()=>({...localStorage}));
  let writes=0;
  await page.route('**/v2/changes',async route=>{
   writes++;
   const result=await route.fetch();
   expect(result.status()).toBe(200);
   await route.abort('failed');
  });
  const uncertain=await page.evaluate(()=>TanDraftAdditiveRetry.run({storage:localStorage,fetchImpl:fetch}));
  expect(uncertain.status).toBe('unknown_commit');
  expect(writes).toBe(1);
  expect(await page.evaluate(()=>({...localStorage}))).toEqual(original);
  await page.unroute('**/v2/changes');
  page.on('request',request=>{if(request.method()==='POST')writes++;});
  const reconciled=await page.evaluate(()=>TanDraftAdditiveRetry.run({storage:localStorage,fetchImpl:fetch}));
  expect(reconciled.status).toBe('up_to_date');
  expect(writes).toBe(1);
  const saved=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(saved.favs.migration.deleted).toBe(false);
  expect(saved.visited.migration.value).toBe('2026-11-23T00:00:00.000Z');

  // A separate browser session deletes want while preserving seen.
  const other=await browser.newContext({ignoreHTTPSErrors:true});
  try{
   await other.addCookies([{name:'__Host-tan_session',value:'browser-migration-other',
    url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
   const second=await other.newPage();
   await second.goto('https://127.0.0.1/exhibition?key=migration');
   await second.locator('#favBtn').click();
   await expect(second.locator('#favBtn')).toHaveAttribute('aria-pressed','false');
   await expect(second.locator('#visitedBtn')).toHaveAttribute('aria-pressed','true');
   const conflict=await page.evaluate(()=>TanDraftAdditiveRetry.run({storage:localStorage,fetchImpl:fetch}));
   expect(conflict.status).toBe('needs_review');
   expect(conflict.review).toEqual([{kind:'favs',key:'migration',reason:'explicit_deletion_conflict'}]);
   expect(writes).toBe(1);
   expect(await page.evaluate(()=>({...localStorage}))).toEqual(original);
   const latest=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
   expect(latest.favs.migration.deleted).toBe(true);
   expect(latest.visited.migration).toEqual(saved.visited.migration);
  }finally{await other.close();}
 }finally{await context.close();}
});

test('complete detail template uses one authenticated writer and preserves legacy storage',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-detail-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>{
   localStorage.setItem('taiwan_art_ga_exclude','1');
   localStorage.setItem('taiwan_art_favs','{"legacy":{"title":"Old","museum":"M"}}');
  });
  const page=await context.newPage();
  let writes=0,legacyWrites=0;
  page.on('request',request=>{
   if(request.method()==='POST'){
    if(request.url().endsWith('/v2/changes'))writes++;
    else legacyWrites++;
   }
  });
  await page.goto('https://127.0.0.1/actual-detail');
  await expect(page.locator('#favBtn')).toBeEnabled();
  expect(await page.evaluate(()=>typeof toggleFav)).toBe('undefined');
  await page.locator('#favBtn').click();
  await expect(page.locator('#favBtn')).toHaveClass(/saved/);
  await page.locator('#visitedBtn').click();
  await expect(page.locator('#visitedBtn')).toHaveClass(/saved/);
  await page.locator('#favBtn').click();
  await expect(page.locator('#favBtn')).not.toHaveClass(/saved/);
  await expect(page.locator('#visitedBtn')).toHaveClass(/saved/);
  expect([writes,legacyWrites]).toEqual([3,0]);
  await expect(page.locator('#favText')).toHaveText('「観たい」に戻す');
  let consumes=0;
  await page.route('**/review/keep/consume',async route=>{
   consumes++;
   const response=await route.fetch();
   expect(response.status()).toBe(200);
   await route.abort('failed');
  });
  await page.locator('#favBtn').click();
  await expect(page.locator('#favBtn')).toHaveClass(/saved/);
  await expect(page.locator('#visitedBtn')).toHaveClass(/saved/);
  await expect(page.locator('#syncNotice')).toHaveText('この展示は現在「観たい」に登録されています。');
  expect(consumes).toBe(1);
  expect(writes).toBe(3);
  await page.unroute('**/review/keep/consume');
  await page.locator('#favBtn').click();
  await expect(page.locator('#favText')).toHaveText('「観たい」に戻す');
  // Refresh the second tab to the same tombstone, then change the first.
  const second=await context.newPage();
  await second.goto('https://127.0.0.1/actual-detail?lang=zh');
  await expect(second.locator('#favText')).toHaveText('重新加入「想看」');
  await page.locator('#favBtn').click();
  await expect(page.locator('#favBtn')).toHaveClass(/saved/);
  let stalePosts=0;
  second.on('request',r=>{if(r.method()==='POST')stalePosts++;});
  await second.locator('#favBtn').click();
  await expect(second.locator('#favBtn')).toHaveClass(/saved/);
  expect(stalePosts).toBe(0);
  await second.close();
  expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs'))))
   .toEqual({legacy:{title:'Old',museum:'M'}});
 }finally{await context.close();}
});

test('full nearby page shares one revision across multiple exhibitions and restores explicitly',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-nearby-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const page=await context.newPage();
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.goto('https://127.0.0.1/actual-nearby');
  const a=page.locator('[data-action="fav"][data-key="nearby-a"]');
  const b=page.locator('[data-action="visited"][data-key="nearby-b"]');
  expect(await page.evaluate(()=>typeof toggleAction)).toBe('undefined');
  await a.click();
  await expect(a).toHaveAttribute('aria-pressed','true');
  await b.click();
  await expect(b).toHaveAttribute('aria-pressed','true');
  await a.click();
  await expect(a).toHaveText('重新加入「想看」');
  await expect(b).toHaveAttribute('aria-pressed','true');
  await a.click();
  await expect(a).toHaveAttribute('aria-pressed','true');
  await expect(b).toHaveAttribute('aria-pressed','true');
  expect(writes).toBe(3);
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
  const state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.revision).toBe(4);
  expect(state.visited['nearby-b'].revision).toBe(2);
 }finally{await context.close();}
});

test('nearby reconnect refreshes another tabs changes with GET only',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-nearby-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const first=await context.newPage(),second=await context.newPage();
  await first.goto('https://127.0.0.1/actual-nearby');
  const selector='[data-action="fav"][data-key="nearby-a"]';
  await expect(first.locator(selector)).toBeEnabled();
  if(await first.locator(selector).getAttribute('aria-pressed')!=='true')await first.locator(selector).click();
  await expect(first.locator(selector)).toHaveAttribute('aria-pressed','true');
  await second.goto('https://127.0.0.1/actual-nearby');
  await second.locator(selector).click();
  await expect(second.locator(selector)).toHaveAttribute('aria-pressed','false');
  let reads=0,writes=0;
  first.on('request',r=>{
   if(r.url().endsWith('/v2/state'))reads++;
   if(r.method()==='POST')writes++;
  });
  await first.evaluate(()=>{
   window.dispatchEvent(new Event('online'));
   window.dispatchEvent(new Event('online'));
  });
  await expect(first.locator(selector)).toHaveText('重新加入「想看」');
  expect([reads,writes]).toEqual([1,0]);
  await second.locator(selector).click();
  await expect(second.locator(selector)).toHaveAttribute('aria-pressed','true');
  await first.evaluate(()=>{
   window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));
   window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));
  });
  await expect(first.locator(selector)).toHaveAttribute('aria-pressed','true');
  expect([reads,writes]).toEqual([2,0]);
 }finally{await context.close();}
});

test('Discover server flow preserves existing seen across database-backed save and undo',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-discover-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  const page=await context.newPage();
  await page.goto('https://127.0.0.1/exhibition?key=discover');
  await page.addScriptTag({url:'/static/js/draft_discover_flow.js'});
  const result=await page.evaluate(async()=>{
   const card={stable_key:'discover',title:'Art',museum:'M',dates:'2026',detail_url:'/a',region:'臺南'};
   const flow=TanDraftDiscoverFlow.create({fetchImpl:fetch,normalizeKey:key=>key});
   await flow.swipe(card,'visited');
   await flow.swipe(card,'like');
   const undo=await flow.undo();
   const afterUndo=(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state;
   const preserved=await flow.swipe(card,'visited');
   await flow.undo();
   return {undo,afterUndo,preserved};
  });
  expect(result.undo.status).toBe('written_under_cooperative_lock');
  expect(result.afterUndo.favs.discover.deleted).toBe(true);
  expect(result.afterUndo.visited.discover.deleted).toBe(false);
  expect(result.preserved.preservedExisting).toBe(true);
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 }finally{await context.close();}
});

test('actual Discover template swipes and undoes through the authenticated writer, not legacy storage',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-discover-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>{
   localStorage.setItem('taiwan_art_ga_exclude','1');
   // Otherwise the first-visit tutorial overlay covers the action buttons
   // and every click() hangs until Playwright's own action timeout.
   localStorage.setItem('taiwan_art_discover_tutorial_seen','1');
  });
  const page=await context.newPage();
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.goto('https://127.0.0.1/actual-discover');
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover A');
  await page.locator('#likeBtn').click();
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover B');
  expect(writes).toBe(1);
  let state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['discover-a']).toMatchObject({deleted:false});
  await page.locator('#undoBtn').click();
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover A');
  expect(writes).toBe(2);
  state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['discover-a']).toMatchObject({deleted:true});
  await page.locator('#skipBtn').click();
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover B');
  expect(writes).toBe(2); // skip never writes
  await page.locator('#visitedBtn').click();
  await expect(page.locator('#emptyState')).toBeVisible();
  expect(writes).toBe(3);
  state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.visited['discover-b']).toMatchObject({deleted:false});
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 }finally{await context.close();}
});

test('actual Home template toggles fav/visited through the authenticated writer without navigating away',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-home-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const page=await context.newPage();
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.goto('https://127.0.0.1/actual-home');
  const favBtn=page.locator('span.ex-action-btn[data-action="fav"]').first();
  const visitedBtn=page.locator('span.ex-action-btn[data-action="visited"]').first();
  const card=page.locator('.ex-item').first();
  await favBtn.click();
  await expect(favBtn).toHaveClass(/active-fav/);
  await expect(card).toHaveClass(/favorited-item/);
  expect(page.url()).toContain('/actual-home'); // clicking never navigated to the detail page
  expect(writes).toBe(1);
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_messenger_prompted'))).toBe('1');
  await visitedBtn.click();
  await expect(visitedBtn).toHaveClass(/active-visited/);
  await expect(card).toHaveClass(/visited-item/);
  await expect(card).not.toHaveClass(/favorited-item/); // visited takes precedence, per legacy _renderActions()
  expect(writes).toBe(2);
  let state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:false});
  expect(state.visited['home-a']).toMatchObject({deleted:false});
  await favBtn.click(); // toggle fav back off
  await expect(favBtn).not.toHaveClass(/active-fav/);
  expect(writes).toBe(3);
  state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:true});
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 }finally{await context.close();}
});
