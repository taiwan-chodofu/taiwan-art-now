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
