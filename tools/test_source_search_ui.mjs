import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const file=ts.createSourceFile('SourceSearch.tsx',readFileSync('desktop/src/SourceSearch.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let listen
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText()==='listen')listen=node.initializer.getText();ts.forEachChild(node,visit)}visit(file)
const transpiled=ts.transpileModule(`globalThis.listen=${listen}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
let ready='old',resolve,selected,error
const scope={auditionSequence:{current:0},heard:{current:new Set()},setAudition:v=>selected=v,setReadyAudition:v=>ready=v,setError:v=>error=v,onAudition:(candidate,input)=>{assert.equal(input,'driving');return new Promise(r=>resolve=r)}}
vm.runInNewContext(transpiled,scope)
const first=scope.listen({id:'a'});assert.equal(ready,null);assert.equal(selected,'a')
const resolveFirst=resolve
const second=scope.listen({id:'b'});const resolveSecond=resolve
resolveFirst(true);await first;assert.equal(ready,null,'Stale A cannot mark B ready')
resolveSecond(true);await second;assert.equal(ready,'b')
const failed=scope.listen({id:'c'});resolve(false);await failed;assert.equal(ready,null);assert.ok(error)
console.log('Source auditions wait for actual audio and discard stale completion.')
