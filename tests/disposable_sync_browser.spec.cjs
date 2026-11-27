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

test('Discover recovers from a lost write reply on reconnect instead of staying stuck forever',async({browser})=>{
 // Before this fix, discover.html never called draft_discover_flow.js's own
 // recover()/isUncertain() -- once a write's outcome was unknown, swipe()/
 // undo() both short-circuit to {status:"unknown_commit"} permanently, so
 // the "please tap again" message would keep failing the same way with no
 // way out short of a full page reload. See DECISIONS.md 2026-11-27.
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-discover-recover-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>{
   localStorage.setItem('taiwan_art_ga_exclude','1');
   localStorage.setItem('taiwan_art_discover_tutorial_seen','1');
  });
  const page=await context.newPage();
  let lostOnce=false;
  await page.route('**/v2/changes',async route=>{
   if(lostOnce){await route.continue();return;}
   lostOnce=true;
   // The write really reaches and commits on the real server; only the
   // client's view of the response is lost, matching the established
   // "lost database write response" pattern used elsewhere in this file.
   const committed=await route.fetch();
   expect(committed.status()).toBe(200);
   await route.abort('failed');
  });
  await page.goto('https://127.0.0.1/actual-discover');
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover A');
  await page.locator('#likeBtn').click();
  await expect(page.locator('#discoverActionError')).toContainText('保存できませんでした');
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover A');
  expect(await page.evaluate(()=>discoverFlow.isUncertain())).toBe(true);
  // Retrying immediately must stay locked -- recover() has not run yet.
  await page.locator('#likeBtn').click();
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover A');
  expect(await page.evaluate(()=>discoverFlow.isUncertain())).toBe(true);
  // Reconnect: recover() does a fresh authenticated read, sees the revision
  // really did move past the uncertain write's own base revision (the lost
  // write DID commit), and only then clears the lock and the error message.
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));
  await expect(page.locator('#discoverActionError')).toHaveText('');
  expect(await page.evaluate(()=>discoverFlow.isUncertain())).toBe(false);
  // The surviving registration is preserved (set_if_absent on an existing,
  // non-deleted entry), so this swipe advances without a second write.
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.locator('#likeBtn').click();
  await expect(page.locator('.card h2')).toHaveText('Synthetic Discover B');
  expect(writes).toBe(0);
  const state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['discover-a']).toMatchObject({deleted:false});
 }finally{await context.close();}
});

test('Home and Detail stay consistent across screens for the same exhibition in one session',async({browser})=>{
 // Every prior reconnect/conflict test exercised multiple tabs of the SAME
 // template (two Home tabs, two Nearby tabs, etc). This is the first test
 // where two DIFFERENT screens -- Home and Detail -- address the exact same
 // server-side item in one session, closing the "never tested across
 // screens" gap named in docs/security/ROLLOUT_READINESS_2026-11-27.md.
 // /actual-detail?key=home-a (added for this test) lets Detail target
 // Home's own fixture key instead of its usual independent synthetic key.
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-home-detail-cross-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const home=await context.newPage(),detail=await context.newPage();
  await home.goto('https://127.0.0.1/actual-home');
  await detail.goto('https://127.0.0.1/actual-detail?key=home-a');
  await expect(detail.locator('#favBtn')).toBeEnabled();
  const favBtnHome=home.locator('span.ex-action-btn[data-action="fav"]').first();
  const cardHome=home.locator('.ex-item').first();
  const mylistBadge=home.locator('#mylistNavIcon .bn-badge');
  await expect(detail.locator('#favBtn')).not.toHaveClass(/saved/);
  // Favorite from Home; Detail (already open, opened before this write)
  // must pick it up on its own reconnect, not just on a fresh load.
  await favBtnHome.click();
  await expect(favBtnHome).toHaveClass(/active-fav/);
  await expect(detail.locator('#favBtn')).not.toHaveClass(/saved/);
  await detail.evaluate(()=>window.dispatchEvent(new Event('online')));
  await expect(detail.locator('#favBtn')).toHaveClass(/saved/);
  // Mark visited from Detail; Home must pick it up on its own reconnect.
  await detail.locator('#visitedBtn').click();
  await expect(detail.locator('#visitedBtn')).toHaveClass(/saved/);
  await expect(cardHome).not.toHaveClass(/visited-item/);
  await home.evaluate(()=>window.dispatchEvent(new Event('online')));
  await expect(cardHome).toHaveClass(/visited-item/);
  await expect(cardHome).not.toHaveClass(/favorited-item/); // visited takes precedence, per legacy _renderActions()
  await expect(mylistBadge).toHaveText('1'); // the fav itself was never removed, only visited was added alongside
  const state=await home.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:false});
  expect(state.visited['home-a']).toMatchObject({deleted:false});
 }finally{await context.close();}
});

test('Home silently migrates a pre-existing legacy favorite into the server on first load',async({browser})=>{
 // Closes the gap recorded in DECISIONS.md 2026-11-27: without this wiring,
 // an existing user's local favorite would never appear once this screen's
 // isolated-sync flag is on. No click happens in this test at all -- the
 // migration itself must be what produces the favorited state below.
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-home-migration-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>{
   localStorage.setItem('taiwan_art_ga_exclude','1');
   localStorage.setItem('taiwan_art_favs',JSON.stringify({'home-a':{title:'Legacy Title',museum:'Legacy Museum'}}));
  });
  const page=await context.newPage();
  await page.goto('https://127.0.0.1/actual-home');
  const favBtn=page.locator('span.ex-action-btn[data-action="fav"]').first();
  const mylistBadge=page.locator('#mylistNavIcon .bn-badge');
  await expect(favBtn).toHaveClass(/active-fav/);
  await expect(mylistBadge).toHaveText('1');
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_legacy_server_migration_v1'))).toBe('1');
  const state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:false});
  expect(state.favs['home-a'].value.title).toBe('Legacy Title');
  // The one-time guard must prevent a second migration attempt on reload.
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.reload();
  await expect(favBtn).toHaveClass(/active-fav/);
  expect(writes).toBe(0);
 }finally{await context.close();}
});

test('Home surfaces a legacy favorite the server already deleted elsewhere for explicit review',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  await context.addCookies([{name:'__Host-tan_session',value:'browser-home-migration-review-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const page=await context.newPage();
  await page.goto('https://127.0.0.1/actual-home');
  const favBtn=page.locator('span.ex-action-btn[data-action="fav"]').first();
  // Produce a real server-side tombstone for home-a through ordinary use.
  await favBtn.click();
  await expect(favBtn).toHaveClass(/active-fav/);
  await favBtn.click();
  await expect(favBtn).not.toHaveClass(/active-fav/);
  // Simulate this same browser also still holding stale local data from
  // before it ever talked to the server (e.g. the pre-cutover legacy page).
  await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',
   JSON.stringify({'home-a':{title:'Legacy Title',museum:'Legacy Museum'}})));
  await page.reload();
  const restoreBtn=page.getByRole('button',{name:'「観たい」に戻す'});
  await expect(restoreBtn).toBeVisible();
  await restoreBtn.click();
  await expect(favBtn).toHaveClass(/active-fav/);
  // draft_simple_review_ui.js disables the row's buttons on decision but does
  // not remove it (removal is only exposed per-section, which would be wrong
  // if other items were still pending review) -- a known, documented UX
  // rough edge, not a correctness issue.
  await expect(restoreBtn).toBeDisabled();
  const state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:false});
  expect(state.favs['home-a'].value.title).toBe('Legacy Title');
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
  const mylistBadge=page.locator('#mylistNavIcon .bn-badge');
  await expect(mylistBadge).toHaveCount(0);
  await favBtn.click();
  await expect(favBtn).toHaveClass(/active-fav/);
  await expect(card).toHaveClass(/favorited-item/);
  expect(page.url()).toContain('/actual-home'); // clicking never navigated to the detail page
  expect(writes).toBe(1);
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_messenger_prompted'))).toBe('1');
  await expect(mylistBadge).toHaveText('1');
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
  await expect(mylistBadge).toHaveCount(0); // tombstoned fav must not count toward the badge
  state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.favs['home-a']).toMatchObject({deleted:true});
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 }finally{await context.close();}
});

test('actual Home mylist panel marks visited and removes through the authenticated writer',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  // Dedicated session, distinct from browser-home-session above: that test
  // ends with home-a's fav tombstoned, and reusing its session here would
  // make this test's first fav click resurrect a tombstone (a different,
  // already-covered code path) instead of registering a fresh fav.
  await context.addCookies([{name:'__Host-tan_session',value:'browser-home-mylist-session',
   url:'https://127.0.0.1',secure:true,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('taiwan_art_ga_exclude','1'));
  const page=await context.newPage();
  let writes=0;
  page.on('request',r=>{if(r.url().endsWith('/v2/changes')&&r.method()==='POST')writes++;});
  await page.goto('https://127.0.0.1/actual-home');
  const favBtn=page.locator('span.ex-action-btn[data-action="fav"]').first();
  // Favorite the exhibition from the main list first, like a real user would.
  await favBtn.click();
  // click() resolves on dispatch, not once the write settles -- wait for the
  // class only onState sets post-write before checking writes synchronously,
  // same as the toggleAction test above.
  await expect(favBtn).toHaveClass(/active-fav/);
  expect(writes).toBe(1);
  // Open the mylist panel through its real entry point.
  await page.locator('#mylistNavBtn').click();
  await expect(page.locator('#favsContent')).toContainText('Synthetic Home Exhibition');
  // "Seen" link inside the mylist item (ja: "✓ 観た").
  await page.getByRole('link',{name:'✓ 観た'}).click();
  await expect(page.locator('#favsContent')).not.toContainText('Synthetic Home Exhibition'); // moved out of the want-to-go tab
  expect(writes).toBe(2);
  let state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.visited['home-a']).toMatchObject({deleted:false});
  expect(state.visited['home-a'].value).toMatchObject({title:'Synthetic Home Exhibition',museum:'Synthetic Museum'});
  // The main list's own visited button must reflect the mylist-driven change.
  await expect(page.locator('span.ex-action-btn[data-action="visited"]').first()).toHaveClass(/active-visited/);
  // Switch to the Seen tab and remove it from there.
  await page.getByRole('button',{name:'✓ 観た',exact:false}).first().click();
  await expect(page.locator('#favsContent')).toContainText('Synthetic Home Exhibition');
  await page.getByRole('link',{name:'削除'}).click();
  await expect(page.locator('#favsContent')).not.toContainText('Synthetic Home Exhibition');
  expect(writes).toBe(3);
  state=await page.evaluate(async()=>(await TanDraftAuthenticatedState.read({fetchImpl:fetch})).state);
  expect(state.visited['home-a']).toMatchObject({deleted:true});
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 }finally{await context.close();}
});

test('actual connect-devices page completes the full browser-claim handshake against real Postgres',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 try{
  const page=await context.newPage();
  await page.goto('https://127.0.0.1/actual-connect-devices');
  await expect(page.locator('#step1')).toHaveClass(/active/);
  await page.locator('#startBtn').click();
  await expect(page.locator('#step2')).toHaveClass(/active/);
  const pending=await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_private_claim_pending')));
  expect(typeof pending.messenger_code).toBe('string');
  expect(typeof pending.browser_secret).toBe('string');
  expect(await page.locator('#messengerLink').getAttribute('href'))
   .toBe('https://m.me/61591281572640?ref='+encodeURIComponent(pending.messenger_code));
  // Confirming before Meta has verified anything must fail closed, not
  // silently succeed or crash.
  await page.locator('#confirmBtn').click();
  await expect(page.locator('#notice')).toContainText('まだ確認できていません');
  await expect(page.locator('#step2')).toHaveClass(/active/);
  // Simulate the signature-verified Meta webhook (test-only route; the real
  // one is covered separately by test_flask_webhook_http.py /
  // test_try_mark_meta_verified.py).
  const verifyResult=await page.request.post('https://127.0.0.1/actual-mark-verified',{
   data:{messenger_code:pending.messenger_code,sender_id:'synthetic-connect-sender'}});
  expect((await verifyResult.json()).ok).toBe(true);
  await page.locator('#confirmBtn').click();
  await expect(page.locator('#step3')).toHaveClass(/active/);
  expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_private_claim_pending'))).toBeNull();
  const cookies=await context.cookies();
  expect(cookies.some(c=>c.name==='__Host-tan_session')).toBe(true);
 }finally{await context.close();}
});
