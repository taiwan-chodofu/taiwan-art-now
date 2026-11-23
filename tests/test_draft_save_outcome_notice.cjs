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
 assert.match(notice.children[2].textContent,/關閉其他開著的舊分頁/);
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
