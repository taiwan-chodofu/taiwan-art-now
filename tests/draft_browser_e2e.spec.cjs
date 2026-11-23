const { test, expect } = require('@playwright/test');
const path = require('node:path');

async function boot(page) {
  await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
  await page.evaluate(() => {
    localStorage.removeItem('taiwan_art_favs');
    localStorage.removeItem('taiwan_art_visited');
    document.body.innerHTML = '<button id="fav">観たい</button><button id="visited">観た</button><p id="status"></p>';
  });
  for (const name of ['draft_legacy_snapshot.js', 'draft_legacy_writer.js', 'draft_action_commit.js']) {
    await page.addScriptTag({ path: path.resolve(__dirname, '../static/js', name) });
  }
  await page.evaluate(() => {
    window._uiEvents = [];
    const adapter = TanDraftActionCommit.create({
      storage: localStorage, locks: navigator.locks,
      onCommitted({kind, action}) {
        document.getElementById('status').textContent = kind + ':' + action;
        window._uiEvents.push('committed');
      },
      onFailure(result) {
        document.getElementById('status').textContent = 'error:' + result.status;
        window._uiEvents.push('failed');
      },
      onBusy(busy) { document.querySelectorAll('button').forEach(b => b.disabled = busy); }
    });
    const fav = {title:'台南展覽',museum:'Museum',dates:'2026',url:'/e/a',region:'臺南',event:''};
    const visited = {date:'2026-11-23T01:02:03.000Z',title:'台南展覽',museum:'Museum',dates:'2026',url:'/e/a',region:'臺南'};
    document.getElementById('fav').onclick = async () => {
      const exists = JSON.parse(localStorage.getItem('taiwan_art_favs') || '{}').a;
      await adapter.commit({kind:'favs',key:'a',action:exists?'remove':'set',value:fav});
    };
    document.getElementById('visited').onclick = async () => {
      const exists = JSON.parse(localStorage.getItem('taiwan_art_visited') || '{}').a;
      await adapter.commit({kind:'visited',key:'a',action:exists?'remove':'set',value:visited});
    };
  });
}
test('real Chromium: favorite add/remove persists and UI follows write', async ({page}) => {
  await boot(page);
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('favs:set');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('taiwan_art_favs')).a.title)).toBe('台南展覽');
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('favs:remove');
  expect(await page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))))).toEqual([]);
});
test('real Chromium: visited object add/remove independent from favorites', async ({page}) => {
  await boot(page);
  await page.locator('#fav').click();
  await page.locator('#visited').click();
  await expect(page.locator('#status')).toHaveText('visited:set');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('taiwan_art_visited')).a.date)).toBe('2026-11-23T01:02:03.000Z');
  await page.locator('#visited').click();
  await expect(page.locator('#status')).toHaveText('visited:remove');
  expect(await page.evaluate(() => Boolean(JSON.parse(localStorage.getItem('taiwan_art_favs')).a))).toBe(true);
});
test('real Chromium: storage failure never displays saved success', async ({page}) => {
  await boot(page);
  await page.evaluate(() => {
    const proto = Storage.prototype;
    const original = proto.setItem;
    proto.setItem = function(k,v) {
      if (k === 'taiwan_art_favs') throw new DOMException('quota','QuotaExceededError');
      return original.call(this,k,v);
    };
  });
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('error:unavailable');
  expect(await page.evaluate(() => localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(() => window._uiEvents)).toEqual(['failed']);
});
test('real Chromium: two tabs serialize independent favorite additions', async ({browser}) => {
  const context = await browser.newContext();
  try {
    const a = await context.newPage(), b = await context.newPage();
    await boot(a); await boot(b);
    await Promise.all([
      a.evaluate(() => TanDraftActionCommit.create({storage:localStorage,locks:navigator.locks,onCommitted(){},onFailure(){}}).commit({kind:'favs',key:'one',action:'set',value:{title:'One',museum:'M'}})),
      b.evaluate(() => TanDraftActionCommit.create({storage:localStorage,locks:navigator.locks,onCommitted(){},onFailure(){}}).commit({kind:'favs',key:'two',action:'set',value:{title:'Two',museum:'M'}}))
    ]);
    const keys = await a.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))).sort());
    expect(keys).toEqual(['one','two']);
  } finally { await context.close(); }
});

test('legacy cached tab bypassing Web Locks can still overwrite newer data (known blocker)', async ({browser}) => {
  const context = await browser.newContext();
  try {
    const modern = await context.newPage(), legacy = await context.newPage();
    await boot(modern); await boot(legacy);
    // Cached old code snapshots the whole map without taking the shared lock.
    const stale = await legacy.evaluate(() => localStorage.getItem('taiwan_art_favs') || '{}');
    const result = await modern.evaluate(() => TanDraftActionCommit.create({
      storage: localStorage, locks: navigator.locks,
      onCommitted(){}, onFailure(){}
    }).commit({kind:'favs',key:'newer',action:'set',value:{title:'Newer',museum:'M'}}));
    expect(result.status).toBe('written_under_cooperative_lock');
    await legacy.evaluate(raw => {
      const map = JSON.parse(raw);
      map.older = {title:'Older',museum:'M'};
      localStorage.setItem('taiwan_art_favs', JSON.stringify(map));
    }, stale);
    const keys = await modern.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))));
    // This intentionally documents the unresolved unsafe old-tab behavior.
    expect(keys).toEqual(['older']);
  } finally { await context.close(); }
});

test('real Chromium: checkpoint survives a stale whole-map overwrite for review only', async ({page}) => {
  await boot(page);
  await page.addScriptTag({path:path.resolve(__dirname,'../static/js/draft_checkpoint.js')});
  await page.addScriptTag({path:path.resolve(__dirname,'../static/js/draft_loss_detector.js')});
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('favs:set');
  const result=await page.evaluate(() => {
    const saved=TanDraftCheckpoint.capture({storage:localStorage,id:'checkpoint_browser_001'});
    const raw=localStorage.getItem('taiwan_art_favs');
    localStorage.setItem('taiwan_art_favs',JSON.stringify({old:{title:'Old',museum:'M'}}));
    const loaded=TanDraftCheckpoint.load({storage:localStorage,id:'checkpoint_browser_001'});
    const review=TanDraftLossDetector.inspect({storage:localStorage,checkpoint:loaded.snapshot});
    return {saved:saved.status,loaded:loaded.status,review,
      original:JSON.parse(raw).a.title,
      current:JSON.parse(localStorage.getItem('taiwan_art_favs')),
      checkpointExists:localStorage.getItem(TanDraftCheckpoint.PREFIX+'checkpoint_browser_001')!==null};
  });
  expect(result.saved).toBe('saved');
  expect(result.loaded).toBe('ready');
  expect(result.review.status).toBe('needs_review');
  expect(result.review.missing).toEqual([{kind:'favs',key:'a',reason:'checkpoint_entry_missing'}]);
  expect(result.original).toBe('台南展覽');
  expect(result.current.a).toBeUndefined();
  expect(result.current.old.title).toBe('Old');
  expect(result.checkpointExists).toBe(true);
});

test('real Chromium: explicitly confirmed guarded recovery restores one remote-only item', async ({page}) => {
  await boot(page);
  for (const name of ['draft_versioned_sync.js','draft_server_recovery.js','draft_recovery_verifier.js','draft_guarded_recovery.js'])
    await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
  const result=await page.evaluate(async()=>{
    localStorage.setItem('taiwan_art_favs',JSON.stringify({existing:{title:'Existing',museum:'M'}}));
    const server={revision:1,favs:{remote:{deleted:false,revision:1,value:{title:'Remote',museum:'M'}}},visited:{}};
    const reviewedCandidates=TanDraftServerRecovery.plan({storage:localStorage,serverState:server}).candidates;
    const before=localStorage.getItem('taiwan_art_favs');
    const noConsent=await TanDraftGuardedRecovery.restore({
      storage:localStorage,locks:navigator.locks,fetchFreshState:async()=>server,
      expectedRevision:1,reviewedCandidates,decision:{kind:'favs',key:'remote',choice:'restore'},confirmed:false});
    const afterNoConsent=localStorage.getItem('taiwan_art_favs');
    const yes=await TanDraftGuardedRecovery.restore({
      storage:localStorage,locks:navigator.locks,fetchFreshState:async()=>server,
      expectedRevision:1,reviewedCandidates,decision:{kind:'favs',key:'remote',choice:'restore'},confirmed:true});
    return {noConsent:noConsent.status,yes:yes.status,before,afterNoConsent,
      favs:JSON.parse(localStorage.getItem('taiwan_art_favs'))};
  });
  expect(result.noConsent).toBe('not_authorized');
  expect(result.afterNoConsent).toBe(result.before);
  expect(result.yes).toBe('restored_under_cooperative_lock');
  expect(result.favs.existing.title).toBe('Existing');
  expect(result.favs.remote.title).toBe('Remote');
});

test('real Chromium: fresh tombstone and existing local record block restoration', async ({page}) => {
  await boot(page);
  for (const name of ['draft_versioned_sync.js','draft_server_recovery.js','draft_recovery_verifier.js','draft_guarded_recovery.js'])
    await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
  const result=await page.evaluate(async()=>{
    const server={revision:2,favs:{remote:{deleted:false,revision:1,value:{title:'Remote',museum:'M'}}},visited:{}};
    const reviewedCandidates=TanDraftServerRecovery.plan({storage:localStorage,serverState:server}).candidates;
    const request=()=>({storage:localStorage,locks:navigator.locks,fetchFreshState:async()=>server,
      expectedRevision:2,reviewedCandidates,decision:{kind:'favs',key:'remote',choice:'restore'},confirmed:true});
    server.favs.remote={deleted:true,revision:2,value:null};
    const tombstone=await TanDraftGuardedRecovery.restore(request());
    server.favs.remote={deleted:false,revision:1,value:{title:'Remote',museum:'M'}};
    localStorage.setItem('taiwan_art_favs',JSON.stringify({remote:{title:'Local',museum:'M'}}));
    const existing=await TanDraftGuardedRecovery.restore(request());
    return {tombstone:tombstone.status,existing:existing.status,
      favs:JSON.parse(localStorage.getItem('taiwan_art_favs'))};
  });
  expect(result.tombstone).toBe('stale_review');
  expect(result.existing).toBe('stale_review');
  expect(result.favs.remote.title).toBe('Local');
});

async function bootAdditive(page, favs) {
  await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
  await page.evaluate(favs => {
    localStorage.setItem('taiwan_art_favs', JSON.stringify(favs));
    localStorage.setItem('taiwan_art_visited', '{}');
  }, favs);
  for (const name of [
    'draft_legacy_snapshot.js', 'draft_versioned_sync.js',
    'draft_authenticated_state.js', 'draft_additive_merge.js',
    'draft_additive_retry.js'
  ]) await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
}

test('real Chromium: two independent devices retain both favorites after stale CAS retry', async ({browser}) => {
  const aContext=await browser.newContext(), bContext=await browser.newContext();
  try {
    const a=await aContext.newPage(), b=await bContext.newPage();
    const one={title:'First',museum:'M'}, two={title:'Second',museum:'M'};
    await bootAdditive(a,{one}); await bootAdditive(b,{two});
    let revision=0, entries={};
    const calls=[];
    let firstReads=0,releaseInitialReads;
    const initialReadsReady=new Promise(resolve=>{releaseInitialReads=resolve;});
    const exchange=async (path,opts) => {
      calls.push({path,method:opts.method});
      if(opts.method==='GET'){
        if(firstReads<2){
          const snapshot={revision,favs:{...entries},visited:{}};
          firstReads++;
          if(firstReads===2)releaseInitialReads();
          await initialReadsReady;
          return {status:200,body:snapshot};
        }
        return {status:200,body:{revision,favs:{...entries},visited:{}}};
      }
      const data=JSON.parse(opts.body);
      if(data.base_revision!==revision)return {status:409,body:{error:'stale_revision'}};
      revision++;
      for(const [key,change] of Object.entries(data.changes.favs))
        entries[key]={value:change.set,deleted:false,revision};
      return {status:200,body:{revision,favs:entries,visited:{}}};
    };
    await a.exposeFunction('draftExchange',exchange);
    await b.exposeFunction('draftExchange',exchange);
    const runner=() => TanDraftAdditiveRetry.run({
      storage:localStorage,
      fetchImpl:async(path,opts)=>{
        const result=await window.draftExchange(path,opts);
        return {ok:result.status>=200&&result.status<300,status:result.status,
          headers:{get:k=>k==='content-type'?'application/json':
            k==='cache-control'?'no-store':null},
          json:async()=>result.body};
      }
    });
    const [ar,br]=await Promise.all([a.evaluate(runner),b.evaluate(runner)]);
    expect(ar.status).toBe('saved');
    expect(br.status).toBe('saved');
    expect(revision).toBe(2);
    expect(Object.keys(entries).sort()).toEqual(['one','two']);
    expect([ar.retried,br.retried].filter(Boolean)).toHaveLength(1);
    expect(await a.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))))).toEqual(['one']);
    expect(await b.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))))).toEqual(['two']);
  } finally {await aContext.close();await bContext.close();}
});

test('real Chromium: remote tombstone after stale revision stops all further POSTs', async ({page}) => {
  const fav={title:'Keep?',museum:'M'};
  await bootAdditive(page,{deleted:fav});
  const result=await page.evaluate(async()=>{
    let gets=0,posts=0;
    const outcome=await TanDraftAdditiveRetry.run({
      storage:localStorage,
      fetchImpl:async(path,opts)=>{
        let status=200,body;
        if(opts.method==='GET'){
          gets++;
          body=gets===1?{revision:0,favs:{},visited:{}}:
            {revision:1,favs:{deleted:{deleted:true,revision:1,value:null}},visited:{}};
        }else{posts++;status=409;body={error:'stale_revision'};}
        return {status,ok:status===200,
          headers:{get:k=>k==='content-type'?'application/json':
            k==='cache-control'?'no-store':null},
          json:async()=>body};
      }
    });
    return {outcome,gets,posts,local:JSON.parse(localStorage.getItem('taiwan_art_favs'))};
  });
  expect(result.outcome.status).toBe('needs_review');
  expect(result.outcome.review[0].key).toBe('deleted');
  expect(result.posts).toBe(1);
  expect(result.gets).toBe(2);
  expect(result.local.deleted.title).toBe('Keep?');
});

test('real Chromium: stale cached tab overwrite is detected against checkpoint, never silently repaired', async ({browser}) => {
  const context=await browser.newContext();
  try {
    const modern=await context.newPage(), legacy=await context.newPage();
    await boot(modern); await boot(legacy);
    for(const name of ['draft_checkpoint.js','draft_loss_detector.js'])
      await modern.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
    const stale=await legacy.evaluate(()=>localStorage.getItem('taiwan_art_favs')||'{}');
    const saved=await modern.evaluate(async()=>{
      const committed=await TanDraftActionCommit.create({
        storage:localStorage,locks:navigator.locks,onCommitted(){},onFailure(){}
      }).commit({kind:'favs',key:'new',action:'set',value:{title:'New',museum:'M'}});
      const checkpoint=TanDraftCheckpoint.capture({storage:localStorage,id:'cached_tab_review_001'});
      return {committed:committed.status,checkpoint:checkpoint.status};
    });
    expect(saved).toEqual({committed:'written_under_cooperative_lock',checkpoint:'saved'});
    await legacy.evaluate(raw=>{
      const old=JSON.parse(raw);
      old.legacy={title:'Legacy',museum:'M'};
      localStorage.setItem('taiwan_art_favs',JSON.stringify(old));
    },stale);
    const report=await modern.evaluate(()=>{
      const loaded=TanDraftCheckpoint.load({storage:localStorage,id:'cached_tab_review_001'});
      return {status:loaded.status,
        report:TanDraftLossDetector.inspect({storage:localStorage,checkpoint:loaded.snapshot}),
        current:JSON.parse(localStorage.getItem('taiwan_art_favs'))};
    });
    expect(report.status).toBe('ready');
    expect(report.report.status).toBe('needs_review');
    expect(report.report.missing).toEqual([{kind:'favs',key:'new',reason:'checkpoint_entry_missing'}]);
    expect(report.report.additions).toEqual([{kind:'favs',key:'legacy'}]);
    expect(report.current.new).toBeUndefined();
    expect(report.current.legacy.title).toBe('Legacy');
  }finally{await context.close();}
});
