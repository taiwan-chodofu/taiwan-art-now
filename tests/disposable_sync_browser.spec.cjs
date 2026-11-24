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
