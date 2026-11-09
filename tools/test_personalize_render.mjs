import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const require=createRequire(new URL('../desktop/package.json',import.meta.url))
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
const code=ts.transpileModule(readFileSync('desktop/src/SourceSearch.tsx','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText
const scope={exports:{},require};vm.runInNewContext(code,scope)
const Search=scope.exports.default
const candidate=id=>({id,label:`Rounded · variant ${id}`,recipe:{version:1,seed:1,layers:[]},urls:[],traces:{}})
const base={hidden:false,onCommand(){},onContext:()=>({}),onAudition:async()=>true,onStop(){},playing:false,running:false,activity:false,mode:'rise',onModeChange(){}}
const state={active:false,busy:false,error:'',completed:0,pair:[],heard:[],selected:null,favourites:[],final:null,quarantined:0,checkpoint:false}
for(const active of [false,true]){
 const html=renderToStaticMarkup(React.createElement(Search,{...base,discovery:{...state,active,pair:active?[candidate('a'),candidate('b')]:[]}}))
 assert.equal((html.match(/>Session setup</g)||[]).length,0)
 assert.ok(!html.includes('<select'),'Discovery always uses live driving input')
 assert.equal((html.match(/>Broad sound discovery</g)||[]).length,1)
 assert.equal((html.match(/<section /g)||[]).length,1)
 assert.ok(!html.includes('source-search-session'))
 assert.ok(!html.includes('reference-reconstruction')&&!html.includes('Original granular template'))
 if(active){assert.ok(html.includes('Sound A')&&html.includes('Sound B'));assert.ok(html.includes('Technical problem'));assert.equal((html.match(/class="source-favourite-star"/g)||[]).length,2);assert.ok(html.includes('aria-label="Save favourite"'))}
 else assert.ok(html.includes('Start session'))
}
const saved=renderToStaticMarkup(React.createElement(Search,{...base,discovery:{...state,favourites:[candidate('saved')]}}))
assert.equal((saved.match(/<section /g)||[]).length,2)
assert.ok(saved.includes('Choose as final')&&saved.includes('Optional note'))
console.log('Actual React markup renders one comparison panel and optional favourites, without a separate session card or duplicate template panels.')
const starred=renderToStaticMarkup(React.createElement(Search,{...base,discovery:{...state,active:true,pair:[candidate('a'),candidate('b')],favourites:[candidate('a')]}}))
assert.match(starred,/<button[^>]*class="source-favourite-star"[^>]*aria-label="Remove favourite"[^>]*aria-pressed="true"/)
const complete=renderToStaticMarkup(React.createElement(Search,{...base,discovery:{...state,completed:20,maxComparisons:20}}))
assert.ok(complete.includes('Broad sound discovery complete · 20 comparisons'))
assert.ok(!complete.includes('Sound A')&&!complete.includes('Sound B'),'Completed discovery must not show another comparison')
