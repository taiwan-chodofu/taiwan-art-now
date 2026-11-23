// Regression tests of the actual draft Discover template with synthetic Jinja data.
// These do not prove production readiness or safety against uncoordinated legacy tabs.
const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const raw=fs.readFileSync(path.resolve(__dirname,'../templates/discover.html'),'utf8');
function html(){
 const cards=[
 {stable_key:'a',title:'Exhibition A',museum:'Museum',region:'臺南',dates:'2026',detail_url:'/a',excerpt:'First',days_left:3},
 {stable_key:'b',title:'Exhibition B',museum:'Museum',region:'臺北',dates:'2026',detail_url:'/b',excerpt:'Second',days_left:4}
 ];
 const labels={title:'Discover',subtitle:'',back:'Back',heading:'Discover',count_left:'left',
  today_last:'Today',days_left:' days',view_details:'Details',like:'Like',seen:'Seen',
  skip:'Skip',undo:'Undo',empty:'Empty',empty_sub:'',restart:'Restart',scroll_more:'More',
  tutorial_title:'Tutorial',tutorial_like:'Like',tutorial_seen:'Seen',
  tutorial_tap:'Tap',tutorial_got_it:'OK'};
 return raw.replace(/{{\s*cards\s*\|\s*tojson\s*}}/g,JSON.stringify(cards))
  .replace(/{{\s*labels\s*\|\s*tojson\s*}}/g,JSON.stringify(labels))
  .replace(/{{\s*current_lang\s*}}/g,'ja')
  .replace(/{{\s*labels\.([a-z_]+)\s*}}/g,(_,k)=>labels[k]||'')
  .replace(/{%[\s\S]*?%}/g,'');
}
async function boot(page){
 await page.addInitScript(()=>{
  if (sessionStorage.getItem('tan_draft_test_initialized') !== '1') {
   localStorage.removeItem('taiwan_art_favs');
   localStorage.removeItem('taiwan_art_visited');
   sessionStorage.removeItem('taiwan_art_discover_deck');
   sessionStorage.setItem('tan_draft_test_initialized','1');
  }
  localStorage.setItem('taiwan_art_discover_tutorial_seen','1');
  localStorage.setItem('taiwan_art_ga_exclude','1');
 });
 await page.route('**/discover',route=>route.fulfill({status:200,contentType:'text/html',body:html()}));
 await page.goto('http://127.0.0.1:8765/discover');
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
}
test('guarded real template: quota failure keeps the current card',async({page})=>{
 await boot(page);
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem;
  Storage.prototype.setItem=function(k,v){
   if(k==='taiwan_art_favs')throw new DOMException('quota','QuotaExceededError');
   return original.call(this,k,v);
  };
 });
 await page.locator('#likeBtn').click();
 await expect(page.locator('#discoverActionError')).toContainText('保存できませんでした');
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
});
test('guarded real template: stale undo preserves a newer favorite',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({a:{title:'Updated elsewhere',museum:'Museum',dates:'2026',url:'/a',region:'臺南',event:''}})));
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverActionError')).toContainText('変更されたため');
 await expect(page.locator('#discoverActionError')).toContainText('登録状況を確認してから');
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')))).toEqual({a:{title:'Updated elsewhere',museum:'Museum',dates:'2026',url:'/a',region:'臺南',event:''}});
});

test('guarded real template: rapid second action during fly-out cannot save the same card twice',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await page.evaluate(()=>commitSwipe('visited'));
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 const saved=await page.evaluate(()=>({
  favs:JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}'),
  visited:JSON.parse(localStorage.getItem('taiwan_art_visited')||'{}')
 }));
 expect(Object.keys(saved.favs)).toEqual(['a']);
 expect(saved.visited).toEqual({});
});
test('guarded real template: immediate undo cancels delayed render and restores first card',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await page.locator('#undoBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 await page.waitForTimeout(300);
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}'))).toEqual({});
});

test('guarded real template: reload resumes the next card after a successful like',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.reload();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});
test('guarded real template: skip is not persisted as a favorite or visited entry',async({page})=>{
 await boot(page);
 await page.locator('#skipBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_visited'))).toBeNull();
 await page.locator('#undoBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
});

test('guarded real template: another tab updating a favorite prevents stale undo',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 const second=await page.context().newPage();
 await second.route('**/discover',route=>route.fulfill({status:200,contentType:'text/html',body:html()}));
 await second.goto('http://127.0.0.1:8765/discover');
 const updated={title:'Updated in tab 2',museum:'Museum',dates:'2026',url:'/a',region:'臺南',event:''};
 await second.evaluate(async value=>{
  const result=await TanDraftPageAction.commit({
   storage:localStorage,locks:navigator.locks,kind:'favs',key:'a',action:'set',value
  });
  if(result.status!=='written_under_cooperative_lock')throw Error(result.status);
 },updated);
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverActionError')).toContainText('変更されたため');
 await expect(page.locator('#discoverActionError')).toContainText('登録状況を確認してから');
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(await second.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')).a.title))
  .toBe('Updated in tab 2');
 await second.close();
});

test('guarded real template: two tabs can save different exhibitions without losing either',async({page})=>{
 await boot(page);
 const second=await page.context().newPage();
 await second.route('**/discover',route=>route.fulfill({status:200,contentType:'text/html',body:html()}));
 await second.goto('http://127.0.0.1:8765/discover');
 await Promise.all([
  page.locator('#likeBtn').click(),
  second.evaluate(async()=>{
   const value={title:'Exhibition B',museum:'Museum',dates:'2026',url:'/b',region:'臺北',event:''};
   const result=await TanDraftPageAction.commit({
    storage:localStorage,locks:navigator.locks,kind:'favs',key:'b',action:'set',value
   });
   if(result.status!=='written_under_cooperative_lock')throw Error(result.status);
  })
 ]);
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 const saved=await second.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}'));
 expect(Object.keys(saved).sort()).toEqual(['a','b']);
 await second.close();
});

test('guarded real template: a failed favorite write can be retried without losing the card',async({page})=>{
 await boot(page);
 await page.evaluate(()=>{
  window.__originalDraftSetItem=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){
   if(key==='taiwan_art_favs')throw new DOMException('quota','QuotaExceededError');
   return window.__originalDraftSetItem.call(this,key,value);
  };
 });
 await page.locator('#likeBtn').click();
 await expect(page.locator('#discoverActionError')).toContainText('保存できませんでした');
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 await page.evaluate(()=>{Storage.prototype.setItem=window.__originalDraftSetItem;});
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await expect(page.locator('#discoverActionError')).toBeEmpty();
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});

test('guarded real template: restart clears obsolete undo without deleting saved favorite',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#skipBtn').click();
 await expect(page.locator('#restartBtn')).toBeVisible();
 await page.locator('#restartBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 expect(await page.evaluate(()=>discoverFlow.historySize())).toBe(0);
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
 await page.locator('#undoBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});

test('guarded real template: storage error is announced through an accessible alert',async({page})=>{
 await boot(page);
 const alert=page.locator('#discoverActionError');
 await expect(alert).toHaveAttribute('role','alert');
 await expect(alert).toHaveAttribute('aria-live','assertive');
 await expect(alert).toHaveAttribute('aria-atomic','true');
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){
   if(key==='taiwan_art_favs')throw new DOMException('quota','QuotaExceededError');
   return original.call(this,key,value);
  };
 });
 await page.locator('#likeBtn').click();
 await expect(alert).toContainText('保存できませんでした');
 await expect(alert).toContainText('もう一度押してください');
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
});

test('guarded real template: mobile error guidance remains visible and actions stay usable',async({page})=>{
 await page.setViewportSize({width:375,height:667});
 await boot(page);
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){
   if(key==='taiwan_art_favs')throw new DOMException('quota','QuotaExceededError');
   return original.call(this,key,value);
  };
 });
 await page.locator('#likeBtn').click();
 const alert=page.locator('#discoverActionError');
 await expect(alert).toBeVisible();
 await expect(alert).toContainText('もう一度押してください');
 await expect(alert).toHaveCSS('text-align','left');
 const bounds=await alert.boundingBox();
 expect(bounds).not.toBeNull();
 expect(bounds.x).toBeGreaterThanOrEqual(0);
 expect(bounds.x+bounds.width).toBeLessThanOrEqual(375);
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 await expect(page.locator('#likeBtn')).toBeEnabled();
 await expect(page.locator('#visitedBtn')).toBeEnabled();
});

test('guarded real template: conflict offers read-only saved-status inspection',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({a:{title:'Updated elsewhere',museum:'Museum',dates:'2026',url:'/a',region:'臺南',event:''}})));
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverConflictCheck')).toBeVisible();
 await expect(page.locator('#discoverConflictCheck')).toContainText('この端末');
 await page.locator('#discoverConflictCheck').click();
 await expect(page.locator('#discoverConflictStatus')).toContainText('Exhibition A');
 await expect(page.locator('#discoverConflictStatus')).toContainText('登録あり');
 await expect(page.locator('#discoverConflictStatus')).toContainText('この端末では');
 expect((await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')))).a.title).toBe('Updated elsewhere');
});

test('guarded real template: conflict inspector reports missing local registration without modifying data',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs','{}'));
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverConflictCheck')).toBeVisible();
 await page.locator('#discoverConflictCheck').click();
 await expect(page.locator('#discoverConflictStatus')).toContainText('登録なし');
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBe('{}');
});
test('guarded real template: malformed local registration data is not rewritten by conflict inspection',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({a:{title:'Updated elsewhere',museum:'Museum',dates:'2026',url:'/a',region:'臺南',event:''}})));
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverConflictCheck')).toBeVisible();
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs','{broken'));
 await page.locator('#discoverConflictCheck').click();
 await expect(page.locator('#discoverConflictStatus')).toContainText('読み取れませんでした');
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBe('{broken');
});

test('draft Discover: changing filters never deletes Want or Seen',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').first().click();
 // The existing session deck order is preserved: B was next before A.
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
 expect(await page.evaluate(()=>discoverFlow.historySize())).toBe(0);
});
test('draft Discover: Seen-only is hidden from browse and unbookmarked, Want stays saved',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#visitedBtn').click();
 await expect(page.locator('#emptyState')).toBeVisible();
 await page.locator('#discoverModePicker button').nth(1).click();
 await expect(page.locator('#emptyState')).toBeVisible();
 const saved=await page.evaluate(()=>({
  favs:JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}'),
  visited:JSON.parse(localStorage.getItem('taiwan_art_visited')||'{}')
 }));
 expect(Object.keys(saved.favs)).toEqual(['a']);
 expect(Object.keys(saved.visited)).toEqual(['b']);
});
test('draft Discover: restart in unbookmarked mode does not show saved Want',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await page.locator('#skipBtn').click();
 await expect(page.locator('#emptyState')).toBeVisible();
 await page.locator('#restartBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});

test('draft Discover: unbookmarked selection survives reload without exposing Want',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await expect(page.locator('#discoverModePicker button').nth(1)).toHaveAttribute('aria-pressed','true');
 await page.reload();
 await expect(page.locator('#discoverModePicker button').nth(1)).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});
test('draft Discover: selected mode persists only for the current tab session',async({page})=>{
 await boot(page);
 await page.locator('#discoverModePicker button').nth(1).click();
 await expect(page.locator('#discoverModePicker button').nth(1)).toHaveAttribute('aria-pressed','true');
 await page.reload();
 await expect(page.locator('#discoverModePicker button').nth(1)).toHaveAttribute('aria-pressed','true');
 await page.locator('#discoverModePicker button').first().click();
 await page.reload();
 await expect(page.locator('#discoverModePicker button').first()).toHaveAttribute('aria-pressed','true');
});

test('draft Discover: filter click during fly-out is rejected and saved action completes',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 // During animation, mode must remain browse and the current action must finish.
 await page.locator('#discoverModePicker button').nth(1).click();
 await expect(page.locator('#discoverModePicker button').first()).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});
test('draft Discover: mode switch clears obsolete Undo without removing saved Want',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 expect(await page.evaluate(()=>discoverFlow.historySize())).toBe(0);
 await page.locator('#undoBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});

test('draft Discover: skipped exhibition does not reappear after filter toggle',async({page})=>{
 await boot(page);
 await page.locator('#skipBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await page.locator('#discoverModePicker button').first().click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(await page.evaluate(()=>discoverFlow.historySize())).toBe(0);
});

test('draft Discover: reload in unbookmarked mode does not permanently discard hidden Want',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await page.reload();
 await expect(page.locator('#discoverModePicker button').nth(1)).toHaveAttribute('aria-pressed','true');
 await page.locator('#discoverModePicker button').first().click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});
test('draft Discover: a skipped card stays skipped even after reload and mode toggles',async({page})=>{
 await boot(page);
 await page.locator('#skipBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await page.reload();
 await page.locator('#discoverModePicker button').first().click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
});

test('draft Discover: restart in unbookmarked does not lose hidden Want when returning to browse',async({page})=>{
 await boot(page);
 await page.locator('#likeBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').nth(1).click();
 await page.locator('#skipBtn').click();
 await expect(page.locator('#emptyState')).toBeVisible();
 await page.locator('#restartBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#discoverModePicker button').first().click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
 expect(Object.keys(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}')))).toEqual(['a']);
});

test('draft Discover: empty remaining session stays empty after reload',async({page})=>{
 await boot(page);
 await page.locator('#skipBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 await page.locator('#skipBtn').click();
 await expect(page.locator('#emptyState')).toBeVisible();
 await page.reload();
 await expect(page.locator('#emptyState')).toBeVisible();
 await page.locator('#restartBtn').click();
 await expect(page.locator('.card h2')).toHaveText('Exhibition A');
});
