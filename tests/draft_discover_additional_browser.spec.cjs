// Draft-only Chromium regressions for Discover orchestration.
// This is NOT an assertion about the production Discover DOM.
const {test,expect}=require('@playwright/test');
const path=require('node:path');
async function setup(page){
 await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
 await page.evaluate(()=>{
  localStorage.removeItem('taiwan_art_favs');
  localStorage.removeItem('taiwan_art_visited');
  document.body.innerHTML='<div id="card">A</div><p id="error"></p>';
 });
 for(const name of ['draft_legacy_snapshot.js','draft_legacy_writer.js','draft_page_action.js','draft_page_controller.js','draft_discover_flow.js'])
  await page.addScriptTag({path:path.resolve(__dirname,'../static/js',name)});
 await page.evaluate(()=>{
  window.events=[];
  window.card={stable_key:'a',title:'A',museum:'M',dates:'2026',detail_url:'/a',region:'臺南'};
  window.flow=TanDraftDiscoverFlow.create({
   storage:localStorage,locks:navigator.locks,normalizeKey:s=>s,
   onAdvance(){window.events.push('advance');document.querySelector('#card').textContent='B';},
   onRestore(){window.events.push('restore');document.querySelector('#card').textContent='A';},
   onError:r=>{window.events.push('error');document.querySelector('#error').textContent=r.status;}
  });
 });
}
test('Discover skip advances without writing favorites or visited; undo restores card',async({page})=>{
 await setup(page);
 const result=await page.evaluate(()=>flow.swipe(card,'skip'));
 expect(result.status).toBe('skipped');
 await expect(page.locator('#card')).toHaveText('B');
 expect(await page.evaluate(()=>[localStorage.getItem('taiwan_art_favs'),localStorage.getItem('taiwan_art_visited')])).toEqual([null,null]);
 expect((await page.evaluate(()=>flow.undo())).status).toBe('skipped');
 await expect(page.locator('#card')).toHaveText('A');
 expect(await page.evaluate(()=>window.events)).toEqual(['advance','restore']);
});
test('Discover failed undo retains history and current card for retry',async({page})=>{
 await setup(page);
 expect((await page.evaluate(()=>flow.swipe(card,'like'))).status).toBe('written_under_cooperative_lock');
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({a:{title:'Changed',museum:'M'}})));
 const result=await page.evaluate(()=>flow.undo());
 expect(result.status).toBe('stale_undo');
 expect(await page.evaluate(()=>flow.historySize())).toBe(1);
 await expect(page.locator('#card')).toHaveText('B');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')).a.title)).toBe('Changed');
 expect(await page.evaluate(()=>window.events)).toEqual(['advance','error']);
});
