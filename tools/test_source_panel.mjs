import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const file=ts.createSourceFile('SourceCharacterPanel.tsx',readFileSync('desktop/src/SourceCharacterPanel.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let generate
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText()==='generate')generate=node.initializer;ts.forEachChild(node,visit)}visit(file)
let lastWorker,busy=false,rendered,error,received
class Worker {constructor(){lastWorker=this}terminate(){this.terminated=true}postMessage(data){this.sent=data}}
const scope={family:'bowed',Worker,URL,worker:{current:null},controls:{body:.1,character:.2,ensemble:.3,movement:.4},setBusy:value=>busy=value,setError:value=>error=value,setRendered:value=>rendered=value,sourceCallback:{current:data=>received=data}}
const code=ts.transpileModule(`globalThis.generate=${generate.getText().replace('import.meta.url',"'file:///source/'")}`,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
vm.runInNewContext(code,scope)
scope.generate('vocal')
assert.equal(lastWorker.sent.family,'vocal')
assert.ok(busy)
assert.equal(lastWorker.sent.controls.body,.1)
scope.controls.body=.9
lastWorker.onmessage({data:{stems:['rendered audio']}})
assert.equal(rendered.controls.body,.1,'Status identifies the rendered snapshot, not pending edits')
assert.deepEqual(received,['rendered audio'])
assert.ok(lastWorker.terminated&&!busy)
scope.generate();lastWorker.onerror()
assert.ok(!busy&&error.includes('failed'))
assert.equal(scope.worker.current,null)
console.log('Source panel sends snapshots, installs completed audio, reports errors and releases workers.')
