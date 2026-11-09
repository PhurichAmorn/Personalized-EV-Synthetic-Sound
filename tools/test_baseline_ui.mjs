import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
function find(path,predicate) {
 const file=ts.createSourceFile(path,readFileSync(path,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 let result
 function visit(node){if(predicate(node))result=node;ts.forEachChild(node,visit)}
 visit(file);assert.ok(result);return result
}
const stage=find('desktop/src/BaselineComparison.tsx',node=>ts.isVariableDeclaration(node)&&node.name.getText()==='changeStage').initializer.getText()
const code=ts.transpileModule(`globalThis.callback=${stage}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
let choice={source:'recorded',renderer:'granular',scene:'drive',space:'hall'},selected
const scope={setStage:value=>selected=value,setChoice:update=>choice=update(choice)}
vm.runInNewContext(code,scope);scope.callback('source')
assert.equal(selected,'source');assert.equal(choice.renderer,'sample');assert.equal(choice.scene,'neutral');assert.equal(choice.space,'dry')
scope.callback('renderer');assert.equal(choice.space,'dry');assert.equal(choice.scene,'drive')
const panel=find('desktop/src/SoundEditor.tsx',node=>ts.isJsxSelfClosingElement(node)&&node.tagName.getText()==='BaselineComparison')
const play=panel.attributes.properties.find(prop=>prop.name?.getText()==='onPlay').initializer.expression.getText()
let sourcePlaying=true,baselineActive=false,stopped=0,owner=null
vm.runInNewContext(`(${play})()`,{source:{current:{stop:()=>stopped++}},setSourcePlaying:value=>sourcePlaying=value,setBaselineActive:value=>baselineActive=value,setPreviewOwner:value=>owner=value})
assert.equal(owner,'baseline');assert.equal(stopped,1);assert.equal(sourcePlaying,false);assert.equal(baselineActive,true)
console.log('Comparison stages isolate the intended factor and baseline playback stops live GS.')

const stress=find('desktop/src/SoundEditor.tsx',node=>ts.isJsxSelfClosingElement(node)&&node.tagName.getText()==='AudioStressPool')
const stressPlay=stress.attributes.properties.find(prop=>prop.name?.getText()==='onPlay').initializer.expression.getText()
vm.runInNewContext(`(${stressPlay})()`,{source:{current:{stop:()=>stopped++}},setSourcePlaying:value=>sourcePlaying=value,setBaselineActive:value=>baselineActive=value,setPreviewOwner:value=>owner=value})
assert.equal(owner,'stress');assert.equal(baselineActive,true);assert.equal(sourcePlaying,false)
for(const [element,other] of [[panel,'stress'],[stress,'baseline']]) {
 const blocked=element.attributes.properties.find(prop=>prop.name?.getText()==='blocked').initializer.expression.getText()
 assert.equal(vm.runInNewContext(blocked,{sourcePlaying:false,previewOwner:other}),true,'Other preview owns audio')
}
