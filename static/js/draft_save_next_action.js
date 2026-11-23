/* DRAFT ONLY: explicit user choice for a deleted exhibition.
 * Navigation only; never automatically restores a server deletion.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveNextAction=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 function mount({container,document:doc,result,exhibitionUrl}={}){
  if(!container||!doc||typeof doc.createElement!=="function"||
     !result||result.status!=="saved_server_record_deleted"||
     result.serverSaved!==true)return {status:"not_applicable"};
  if(typeof exhibitionUrl!=="string"||
     !/^\/(?!\/)[^\r\n]*$/.test(exhibitionUrl))return {status:"invalid_url"};
  const link=doc.createElement("a");
  link.setAttribute("href",exhibitionUrl);
  link.textContent="查看展覽";
  link.setAttribute("aria-label","查看展覽，決定是否重新加入清單");
  container.appendChild(link);
  return {status:"rendered"};
 }
 return {mount};
});
