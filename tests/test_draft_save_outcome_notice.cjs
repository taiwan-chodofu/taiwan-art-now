const test=require("node:test");
const assert=require("node:assert/strict");
const {render}=require("../static/js/draft_save_outcome_notice.js");
function fixture(){
 class Node{
  constructor(tag){this.tag=tag;this.attributes={};this.children=[];this.textContent="";}
  setAttribute(key,value){this.attributes[key]=value;}
  appendChild(child){this.children.push(child);}
  replaceChildren(...children){this.children=children;}
 }
 return {document:{createElement:tag=>new Node(tag)},container:new Node("div")};
}
test("confirmed server save with local overwrite displays alert and safe next action",()=>{
 const {document,container}=fixture();
 const outcome=render({document,container,
  result:{status:"saved_server_local_changed",serverSaved:true}});
 assert.deepEqual(outcome,{status:"rendered",requiresReview:true});
 const notice=container.children[0];
 assert.equal(notice.attributes.role,"alert");
 assert.equal(notice.attributes["aria-live"],"assertive");
 assert.match(notice.children[2].textContent,/關閉那些頁面/);
 assert.doesNotMatch(notice.children[2].textContent,/重新整理/);
});
test("ordinary success uses polite status, not alarming alert",()=>{
 const {document,container}=fixture();
 render({document,container,result:{status:"saved"}});
 assert.equal(container.children[0].attributes.role,"status");
 assert.equal(container.children[0].attributes["aria-live"],"polite");
});
test("unknown commit never claims success and offers a read-only check",()=>{
 const {document,container}=fixture();
 render({document,container,result:{status:"unknown_commit"}});
 assert.match(container.children[0].children[0].textContent,/無法確認/);
 assert.match(container.children[0].children[2].textContent,/確認/);
});
test("unsupported status does not remove a prior warning",()=>{
 const {document,container}=fixture();
 render({document,container,result:{status:"unknown_commit"}});
 const previous=container.children[0];
 assert.equal(render({document,container,result:{status:"unavailable"}}).status,
  "unsupported_result");
 assert.equal(container.children[0],previous);
});

test("multiple affected exhibitions display their real titles, not internal IDs",()=>{
 const {document,container}=fixture();
 render({document,container,result:{
  status:"saved_server_multiple_records_unconfirmed",serverSaved:true,
  reviewItems:[{kind:"favs",key:"internal-123"},{kind:"visited",key:"internal-123"}],
  exhibitionTitles:{"favs:internal-123":"展覽甲","visited:internal-123":"展覽乙"}
 }});
 const list=container.children[0].children[3];
 assert.equal(list.tag,"ul");
 assert.deepEqual(list.children.map(row=>row.textContent),["展覽甲","展覽乙"]);
 assert.doesNotMatch(list.children.map(row=>row.textContent).join(" "),/internal-123/);
});
test("missing trusted titles do not reveal storage identifiers",()=>{
 const {document,container}=fixture();
 render({document,container,result:{
  status:"saved_server_multiple_records_unconfirmed",serverSaved:true,
  reviewItems:[{kind:"favs",key:"private-id"}]
 }});
 assert.equal(container.children[0].children[3].children[0].textContent,"展覽 1");
});
