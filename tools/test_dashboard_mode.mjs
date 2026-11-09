import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
function find(path,predicate) {
 const source=ts.createSourceFile(path,readFileSync(path,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 let result
 function visit(node){if(predicate(node)) result=node;ts.forEachChild(node,visit)}
 visit(source);assert.ok(result,`Missing callback in ${path}`);return result
}
const button=find('desktop/src/Dashboard.tsx',node=>ts.isJsxOpeningElement(node)&&node.tagName.getText()==='button'&&node.attributes.getText().includes('Next granular mode'))
const callback=button.attributes.properties.find(prop=>prop.name?.getText()==='onClick').initializer.expression.getText()
let mode='steady', selected=false,starts=0
const dashboard={setGranularMode:update=>mode=update(mode),setGranularSelected:value=>selected=value,sound:{current:{start:refresh=>{assert.equal(refresh,true,'Explicit mode click must refresh the player');starts++}}}}
for(const expected of ['rise','evolving','steady']) {vm.runInNewContext(`(${callback})()`,dashboard);assert.equal(mode,expected);assert.equal(selected,true)}
assert.equal(starts,3,'Every mode click must activate the audio player, including from a native theme')
const start=find('desktop/src/SteadySource.tsx',node=>ts.isPropertyAssignment(node)&&node.name.getText()==='start'&&ts.isArrowFunction(node.initializer)).initializer.getText()
let stopped=0,played=0,inputMode
const source={method:'sample',loading:false,voice:{current:{}},startRequested:{current:false},refreshRequested:{current:false},setInputMode:value=>inputMode=value,stop:()=>{stopped++;source.voice.current=null},setMethod:value=>source.method=value,play:()=>played++}
vm.runInNewContext(`(${start})()`,source)
assert.equal(stopped,1);assert.equal(source.method,'granular');assert.equal(inputMode,'driving');assert.equal(source.startRequested.current,true)
const effect=find('desktop/src/SteadySource.tsx',node=>ts.isCallExpression(node)&&node.expression.getText()==='useEffect'&&node.arguments[0]?.getText().includes("startRequested.current && method === 'granular'")).arguments[0].getText()
vm.runInNewContext(`(${effect})()`,source)
assert.equal(played,1);assert.equal(source.startRequested.current,false)
console.log('Actual mode-button callbacks activate GS, cycle all modes, and replace ordinary/manual playback with live granular playback.')
