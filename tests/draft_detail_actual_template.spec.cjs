// Staging-only Chromium harness using the real detail template's updateBtns function
// and real button markup. The deployed handlers remain untouched.
const {test,expect}=require('@playwright/test');
const fs=require('node:fs'),path=require('node:path');
const raw=fs.readFileSync(path.resolve(__dirname,'../templates/exhibition_detail_page.html'),'utf8');
function html(){
 const begin=raw.indexOf('    function updateBtns() {');
 const end=raw.indexOf('    updateBtns();',begin);
 if(begin<0||end<0)throw Error('real detail template function not found');
 const update=raw.slice(begin,end).replace(/{% if current_lang == "zh" %}[^]*?{% elif current_lang == "ja" %}([^]*?){% else %}[^]*?{% endif %}/g,'$1');
 const buttons=['visited','fav'].map(kind=>{
  const id=kind==='visited'?'visited':'fav';
  const match=raw.match(new RegExp('<button class="action-btn" id="'+id+'Btn"[\\s\\S]*?<\\/button>'));
  if(!match)throw Error('real detail button missing '+kind);
  return match[0].replace(/{%[^]*?%}/g,'');
 }).join('');
 return '<!doctype html><meta charset="utf-8"><div id="detailSaveError" role="alert" aria-live="assertive" hidden></div>'+buttons+
 '<script>var exId="ex_1";function _getVisited(){return JSON.parse(localStorage.getItem("taiwan_art_visited")||"{}")}'+
 'function _getFavs(){return JSON.parse(localStorage.getItem("taiwan_art_favs")||"{}")}'+update+'</script>';
}
async function boot(page){
 await page.route('**/detail-staging',r=>r.fulfill({status:200,contentType:'text/html',body:html()}));
 await page.goto('http://127.0.0.1:8765/detail-staging');
 for(const file of ['draft_legacy_snapshot.js','draft_legacy_writer.js','draft_page_action.js','draft_page_controller.js','draft_detail_action_adapter.js','draft_detail_failure_copy.js'])
  await page.addScriptTag({url:'http://127.0.0.1:8765/static/js/'+file});
 await page.evaluate(()=>{
  localStorage.removeItem('taiwan_art_favs');localStorage.removeItem('taiwan_art_visited');
  window.__events=[];
  window.__adapter=TanDraftDetailActionAdapter.create({
   storage:localStorage,locks:navigator.locks,key:exId,
   metadata:{title:'展覽',museum:'M',dates:'2026',url:'/ex'},
   now:()=> '2026-11-23T00:00:00.000Z',
   onRender:()=>{__events.push('render');document.getElementById('detailSaveError').hidden=true;updateBtns();},
   onAnalytics:()=>__events.push('analytics'),
   onNotify:()=>__events.push('notify'),
   onFailure:({status})=>{__events.push('failure');const el=document.getElementById('detailSaveError');el.textContent=TanDraftDetailFailureCopy.message(status,'ja');el.hidden=false;}
  });
  window.toggleVisited=()=>__adapter.toggle('visited');
  window.toggleFav=()=>__adapter.toggle('favs');
  updateBtns();
 });
}
test('real detail buttons: saved state follows verified persistence; want survives seen',async({page})=>{
 await boot(page);
 await page.locator('#favBtn').click();
 await expect(page.locator('#favBtn')).toHaveClass(/saved/);
 await page.locator('#visitedBtn').click();
 await expect(page.locator('#visitedBtn')).toHaveClass(/saved/);
 await page.locator('#visitedBtn').click();
 await expect(page.locator('#visitedBtn')).not.toHaveClass(/saved/);
 await expect(page.locator('#favBtn')).toHaveClass(/saved/);
 expect(await page.evaluate(()=>__events)).toEqual(['render','analytics','notify','render','analytics','notify','render','analytics','notify']);
});
test('real detail buttons: quota error leaves buttons unchanged and sends no analytics or sync',async({page})=>{
 await boot(page);
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem;
  Storage.prototype.setItem=function(k,v){
   if(k==='taiwan_art_favs')throw new DOMException('quota','QuotaExceededError');
   return original.call(this,k,v);
  };
 });
 await page.locator('#favBtn').click();
 await expect(page.locator('#favBtn')).not.toHaveClass(/saved/);
 await expect.poll(()=>page.evaluate(()=>__events)).toEqual(['failure']);
 await expect(page.locator('#detailSaveError')).toBeVisible();
 await expect(page.locator('#detailSaveError')).toContainText('端末の空き容量');
 expect(await page.evaluate(()=>localStorage.getItem('taiwan_art_favs'))).toBeNull();
});

test('real detail staging: navigation away while save is pending suppresses stale callbacks',async({page})=>{
 await boot(page);
 await page.evaluate(()=>{
  window.__releaseLock=null;
  const gate=new Promise(resolve=>{window.__releaseLock=resolve;});
  window.__events=[];
  window.__adapter=TanDraftDetailActionAdapter.create({
   storage:localStorage,
   locks:{request:async(_name,_options,fn)=>{await gate;return fn();}},
   key:exId,metadata:{title:'展覽',museum:'M',dates:'2026',url:'/ex'},
   onRender:()=>{__events.push('render');updateBtns();},
   onAnalytics:()=>__events.push('analytics'),
   onNotify:()=>__events.push('notify'),
   onFailure:()=>__events.push('failure')
  });
  window.toggleFav=()=>__adapter.toggle('favs');
  window.__pending=window.toggleFav();
  window.addEventListener('pagehide',()=>window.__adapter.dispose(),{once:true});
 });
 await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
 await page.evaluate(()=>window.__releaseLock());
 expect(await page.evaluate(()=>window.__pending)).toMatchObject({status:'written_under_cooperative_lock'});
 expect(await page.evaluate(()=>window.__events)).toEqual([]);
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')).ex_1.title)).toBe('展覽');
});

test('real detail staging: actual navigation disposes adapter before pending write completes',async({page})=>{
 await boot(page);
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem;
  window.__savedWrites=[];
  Storage.prototype.setItem=function(k,v){
   if(k==='taiwan_art_favs')window.__savedWrites.push(v);
   return original.call(this,k,v);
  };
  window.addEventListener('pagehide',()=>window.__adapter.dispose(),{once:true});
 });
 await page.goto('http://127.0.0.1:8765/');
 await page.goBack();
 await expect(page.locator('#favBtn')).toBeVisible();
 // A fresh page has no stale callbacks; its persisted storage remains available.
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')||'{}'))).toEqual({});
});
