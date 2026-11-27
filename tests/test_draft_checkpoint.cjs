const test=require("node:test");
const assert=require("node:assert/strict");
const checkpoint=require("../static/js/draft_checkpoint.js");
const {inspect}=require("../static/js/draft_loss_detector.js");
const fav={title:"A",museum:"M",region:"臺南",event:"Biennial"};
const visit={date:"2026-11-23T01:02:03.000Z",title:"A",museum:"M"};
function fixture(){
 const data={taiwan_art_favs:JSON.stringify({a:fav}),
   taiwan_art_visited:JSON.stringify({v:visit})};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 return {data,storage};
}
const id="checkpoint_00001";
test("captures both legacy maps in a separate verified key",()=>{
 const x=fixture(),r=checkpoint.capture({storage:x.storage,id});
 assert.equal(r.status,"saved");
 assert.equal(x.data.taiwan_art_favs,JSON.stringify({a:fav}));
 assert.deepEqual(checkpoint.load({storage:x.storage,id}).snapshot.favs.a,fav);
 assert.deepEqual(checkpoint.load({storage:x.storage,id}).snapshot.visited.v,visit);
});
test("append-only checkpoint refuses replacement",()=>{
 const x=fixture();
 assert.equal(checkpoint.capture({storage:x.storage,id}).status,"saved");
 const saved=x.data[checkpoint.PREFIX+id];
 x.data.taiwan_art_favs="{}";
 assert.equal(checkpoint.capture({storage:x.storage,id}).status,"already_exists");
 assert.equal(x.data[checkpoint.PREFIX+id],saved);
});
test("stale legacy tab overwrite is detected using checkpoint without automatic restore",()=>{
 const x=fixture();
 checkpoint.capture({storage:x.storage,id});
 x.data.taiwan_art_favs=JSON.stringify({older:{title:"Old",museum:"M"}});
 const saved=checkpoint.load({storage:x.storage,id});
 const report=inspect({storage:x.storage,checkpoint:saved.snapshot});
 assert.equal(report.status,"needs_review");
 assert.deepEqual(report.missing,[{kind:"favs",key:"a",reason:"checkpoint_entry_missing"}]);
 assert.equal(JSON.parse(x.data.taiwan_art_favs).older.title,"Old");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a,undefined);
});
test("quota failure never reports checkpoint saved",()=>{
 const x=fixture();x.storage.setItem=()=>{throw Error("quota");};
 assert.equal(checkpoint.capture({storage:x.storage,id}).status,"unavailable");
 assert.equal(x.data[checkpoint.PREFIX+id],undefined);
});
test("silent dropped write returns uncertain_write",()=>{
 const x=fixture();x.storage.setItem=()=>{};
 assert.equal(checkpoint.capture({storage:x.storage,id}).status,"uncertain_write");
});
test("invalid legacy data never produces a checkpoint",()=>{
 const x=fixture();x.data.taiwan_art_favs="{broken";
 assert.equal(checkpoint.capture({storage:x.storage,id}).status,"invalid_local");
 assert.equal(x.data[checkpoint.PREFIX+id],undefined);
});
test("tampered checkpoint cannot be loaded",()=>{
 const x=fixture();checkpoint.capture({storage:x.storage,id});
 x.data[checkpoint.PREFIX+id]='{"favs":{"a":false},"visited":{}}';
 assert.equal(checkpoint.load({storage:x.storage,id}).status,"invalid_checkpoint");
});
test("invalid id cannot write arbitrary storage key",()=>{
 const x=fixture();
 assert.equal(checkpoint.capture({storage:x.storage,id:"../../other"}).status,"invalid_request");
 assert.deepEqual(Object.keys(x.data).sort(),["taiwan_art_favs","taiwan_art_visited"]);
});
