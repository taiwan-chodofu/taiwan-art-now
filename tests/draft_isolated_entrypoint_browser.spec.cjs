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
