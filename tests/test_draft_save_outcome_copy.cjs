const test=require("node:test");
const assert=require("node:assert/strict");
const {forResult}=require("../static/js/draft_save_outcome_copy.js");
test("verified save reports a straightforward success",()=>{
 const copy=forResult({status:"saved",revision:3});
 assert.equal(copy.requiresReview,false);
 assert.match(copy.heading,/已儲存/);
});
test("post-commit local overwrite gives explicit safe next steps",()=>{
 const copy=forResult({status:"saved_server_local_changed",serverSaved:true,revision:3});
 assert.equal(copy.requiresReview,true);
 assert.match(copy.heading,/展覽已成功儲存/);
 assert.match(copy.action,/關閉那些頁面/);
 assert.match(copy.action,/不需要再次儲存/);
 assert.doesNotMatch(copy.action,/瀏覽器資料|舊分頁|同步|伺服器/);
 assert.doesNotMatch(copy.action,/重新整理/);
});
test("lost checkpoint keeps page open and warns against deleting records",()=>{
 const copy=forResult({status:"saved_server_local_review_required",serverSaved:true});
 assert.equal(copy.requiresReview,true);
 assert.match(copy.action,/保留這個頁面/);
 assert.match(copy.action,/不要刪除紀錄/);
});
test("unverified POST does not falsely claim a successful save",()=>{
 const copy=forResult({status:"unknown_commit"});
 assert.match(copy.heading,/無法確認/);
 assert.doesNotMatch(copy.detail,/已成功儲存/);
});
test("unverified or unknown statuses cannot use confirmed-commit copy",()=>{
 assert.equal(forResult({status:"saved_server_local_changed"}),null);
 assert.equal(forResult({status:"saved_server_local_review_required",serverSaved:false}),null);
 assert.equal(forResult({status:"unavailable"}),null);
 assert.equal(forResult(null),null);
});

test("server re-verification produces a calm notice without demanding tab cleanup",()=>{
 const copy=forResult({status:"saved_server_verified_local_changed",serverSaved:true});
 assert.equal(copy.requiresReview,false);
 assert.match(copy.heading,/成功儲存/);
 assert.doesNotMatch(copy.action,/關閉|刪除|重新整理/);
 assert.equal(forResult({status:"saved_server_verified_local_changed"}),null);
});

test("deleted exhibition offers a clear choice to save again",()=>{
 const copy=forResult({status:"saved_server_record_deleted",serverSaved:true});
 assert.match(copy.heading,/不在清單中/);
 assert.match(copy.action,/重新加入/);
 assert.doesNotMatch(copy.action,/同步|伺服器|確認前先不要/);
});
test("changed and missing records do not claim current save success",()=>{
 for(const status of ["saved_server_record_different","saved_server_record_unconfirmed"]){
  const copy=forResult({status,serverSaved:true});
  assert.equal(copy.requiresReview,true);
  assert.doesNotMatch(copy.heading,/成功儲存/);
 }
});

test("multiple uncertain records never describe one exhibition as missing",()=>{
 const copy=forResult({status:"saved_server_multiple_records_unconfirmed",serverSaved:true});
 assert.match(copy.heading,/部分展覽/);
 assert.doesNotMatch(copy.heading,/這筆展覽/);
 assert.equal(copy.requiresReview,true);
 assert.equal(forResult({status:"saved_server_multiple_records_unconfirmed"}),null);
});
