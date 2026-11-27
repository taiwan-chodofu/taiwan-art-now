const test=require('node:test'),assert=require('node:assert/strict');
const {restore}=require('../static/js/draft_authenticated_guarded_restore.js');
const value={title:'A',museum:'M'};
function fixture(){
 const data={taiwan_art_favs:'{}',taiwan_art_visited:'{}'};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const state={revision:3,favs:{a:{deleted:false,revision:2,value}},visited:{}};
 const fetchImpl=async()=>({status:200,ok:true,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>state});
 const locks={request:(_name,_options,fn)=>fn()};
 return {data,storage,state,fetchImpl,locks,expectedRevision:3,reviewedCandidates:[{kind:'favs',key:'a',value,item_revision:2}],decision:{kind:'favs',key:'a',choice:'restore'},confirmed:true};
}
test('explicit confirmed restoration preserves independent seen map',async()=>{
 const x=fixture();const r=await restore(x);
 assert.equal(r.status,'restored_under_cooperative_lock');
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,'A');
 assert.deepEqual(JSON.parse(x.data.taiwan_art_visited),{});
});
test('no consent cannot read or write',async()=>{
 const x=fixture();let calls=0;x.confirmed=false;x.fetchImpl=async()=>{calls++;throw Error('must not fetch');};
 assert.equal((await restore(x)).status,'not_authorized');assert.equal(calls,0);
 assert.equal(x.data.taiwan_art_favs,'{}');
});
test('authentication failure prevents local writes',async()=>{
 const x=fixture();x.fetchImpl=async()=>({status:401,ok:false});
 assert.equal((await restore(x)).status,'unauthorized');assert.equal(x.data.taiwan_art_favs,'{}');
});
test('changed server revision prevents restoration',async()=>{
 const x=fixture();x.state.revision=4;
 assert.equal((await restore(x)).status,'stale_server');assert.equal(x.data.taiwan_art_favs,'{}');
});
test('explicit server deletion prevents resurrection',async()=>{
 const x=fixture();x.state.favs.a={deleted:true,revision:3,value:null};
 assert.equal((await restore(x)).status,'stale_review');assert.equal(x.data.taiwan_art_favs,'{}');
});
