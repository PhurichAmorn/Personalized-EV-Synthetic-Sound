import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const file=ts.createSourceFile('AudioStressPool.tsx',readFileSync('desktop/src/AudioStressPool.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let select,attach
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText()==='selectClip')select=node.initializer;if(ts.isVariableDeclaration(node)&&node.name.getText()==='attachPlayer')attach=node.initializer.arguments[0];ts.forEachChild(node,visit)}visit(file)
let paused=0,selected
const player={current:null},scope={player,setSelected:value=>selected=value}
const compile=(name,node)=>ts.transpileModule(`globalThis.${name}=${node.getText()}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
vm.runInNewContext(compile('attach',attach),scope)
const audio={volume:1,pause:()=>paused++}
scope.attach(audio);assert.equal(audio.volume,.2)
vm.runInNewContext(compile('select',select),scope)
scope.select('ufo');assert.equal(paused,1);assert.equal(selected,'ufo')
scope.attach(null);assert.equal(paused,2,'Unmount releases playing preview')
let autoPlay=false
function check(node){if(ts.isJsxAttribute(node)&&node.name.getText().toLowerCase()==='autoplay')autoPlay=true;ts.forEachChild(node,check)}check(file)
assert.equal(autoPlay,false,'No automatic playback of abrasive sounds')
console.log('Stress pool starts quiet, pauses on selection/unmount, and never auto-plays.')
