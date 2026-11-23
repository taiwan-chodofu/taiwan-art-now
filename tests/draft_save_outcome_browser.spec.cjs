const {test,expect}=require("@playwright/test");
const path=require("node:path");
async function boot(page){
 await page.goto("http://127.0.0.1:8765/tests/draft_browser_fixture.html");
 await page.setViewportSize({width:390,height:844});
 for(const name of ["draft_save_outcome_copy.js","draft_save_outcome_notice.js"])
  await page.addScriptTag({path:path.resolve(__dirname,"../static/js",name)});
 await page.evaluate(()=>{
  document.body.innerHTML='<main style="max-width:100%;overflow-wrap:anywhere"><div id="notice"></div></main>';
 });
}
test("mobile Chromium: confirmed save is a polite success, not a blocking alert",async({page})=>{
 await boot(page);
 const rendered=await page.evaluate(()=>TanDraftSaveOutcomeNotice.render({
  container:document.getElementById("notice"),document,
  result:{status:"saved_server_verified_local_changed",serverSaved:true}
 }));
 expect(rendered).toEqual({status:"rendered",requiresReview:false});
 const notice=page.locator("#notice section");
 await expect(notice).toHaveAttribute("role","status");
 await expect(notice).toHaveAttribute("aria-live","polite");
 await expect(notice).toContainText("展覽已成功儲存");
 await expect(notice).not.toContainText("舊分頁");
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test("mobile Chromium: missing trusted records remain a warning",async({page})=>{
 await boot(page);
 await page.evaluate(()=>TanDraftSaveOutcomeNotice.render({
  container:document.getElementById("notice"),document,
  result:{status:"saved_server_local_review_required",serverSaved:true}
 }));
 const notice=page.locator("#notice section");
 await expect(notice).toHaveAttribute("role","alert");
 await expect(notice).toHaveAttribute("aria-live","assertive");
 await expect(notice).toContainText("其他紀錄需要確認");
});
test("mobile Chromium: ambiguous POST never claims saved and invalid result preserves warning",async({page})=>{
 await boot(page);
 const state=await page.evaluate(()=>{
  const container=document.getElementById("notice");
  const first=TanDraftSaveOutcomeNotice.render({
   container,document,result:{status:"unknown_commit"}});
  const before=container.textContent;
  const invalid=TanDraftSaveOutcomeNotice.render({
   container,document,result:{status:"saved_server_verified_local_changed"}});
  return {first,invalid,before,after:container.textContent};
 });
 expect(state.first.requiresReview).toBe(true);
 expect(state.invalid.status).toBe("unsupported_result");
 expect(state.after).toBe(state.before);
 await expect(page.locator("#notice section")).toHaveAttribute("role","alert");
 await expect(page.locator("#notice")).not.toContainText("展覽已成功儲存");
});
