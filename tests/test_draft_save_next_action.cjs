const test=require("node:test");
const assert=require("node:assert/strict");
const {mount}=require("../static/js/draft_save_next_action.js");
test("deleted exhibition offers navigation only, without mutation",()=>{
 const children=[];
 const container={appendChild:x=>children.push(x)};
 const doc={createElement:tag=>({tag,attributes:{},setAttribute(k,v){this.attributes[k]=v;}})};
 const result=mount({container,document:doc,
  result:{status:"saved_server_record_deleted",serverSaved:true},
  exhibitionUrl:"/exhibition/123"});
 assert.equal(result.status,"rendered");
 assert.equal(children.length,1);
 assert.equal(children[0].tag,"a");
 assert.equal(children[0].attributes.href,"/exhibition/123");
 assert.equal(children[0].textContent,"查看展覽");
});
test("reject external, protocol-relative, or invalid links",()=>{
 const container={appendChild(){throw Error("must not append");}};
 const doc={createElement:()=>({})};
 for(const exhibitionUrl of ["https://evil.example","//evil.example","javascript:alert(1)","/a\nb"]){
  assert.equal(mount({container,document:doc,
   result:{status:"saved_server_record_deleted",serverSaved:true},
   exhibitionUrl}).status,"invalid_url");
 }
});
test("no action if deletion not confirmed",()=>{
 const container={appendChild(){throw Error("must not append");}};
 assert.equal(mount({container,document:{createElement:()=>({})},
  result:{status:"saved_server_record_deleted"},
  exhibitionUrl:"/exhibition/123"}).status,"not_applicable");
});
