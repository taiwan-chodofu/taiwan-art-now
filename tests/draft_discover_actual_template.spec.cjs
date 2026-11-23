// Characterization tests of the ACTUAL Discover template, served with synthetic Jinja data.
// These document current unsafe behavior; they do not assert that it is safe.
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
  localStorage.setItem('taiwan_art_discover_tutorial_seen','1');
  localStorage.setItem('taiwan_art_ga_exclude','1');
  localStorage.removeItem('taiwan_art_favs');
  localStorage.removeItem('taiwan_art_visited');
  sessionStorage.removeItem('taiwan_art_discover_deck');
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
 await page.evaluate(()=>localStorage.setItem('taiwan_art_favs',JSON.stringify({a:{title:'Updated elsewhere'}})));
 await page.locator('#undoBtn').click();
 await expect(page.locator('#discoverActionError')).toContainText('変更されたため');
 await expect(page.locator('.card h2')).toHaveText('Exhibition B');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('taiwan_art_favs')))).toEqual({a:{title:'Updated elsewhere'}});
});
