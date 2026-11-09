import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const compile=path=>ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const generator=`data:text/javascript;base64,${Buffer.from(compile('desktop/src/sourceDesigner.ts')).toString('base64')}`
const {SOURCE_FAMILIES,DEFAULT_SOURCE_CONTROLS}=await import(generator)
let result,options
globalThis.self={postMessage:(data,transfer)=>{result=data;options=transfer}}
const worker=compile('desktop/src/sourceDesigner.worker.ts').replace("'./sourceDesigner'",JSON.stringify(generator))
await import(`data:text/javascript;base64,${Buffer.from(worker).toString('base64')}`)
for(const family of SOURCE_FAMILIES) {
 self.onmessage({data:{controls:DEFAULT_SOURCE_CONTROLS,family:family.id}})
 assert.ok(!result.error,result.error)
 assert.equal(options.transfer.length,6)
 let peak=0,energy=0
 for(let c=0;c<2;c++)for(let i=0;i<48000*5;i++) {
  const sample=result.stems.reduce((sum,stem)=>sum+stem[c][i],0)
  assert.ok(Number.isFinite(sample));peak=Math.max(peak,Math.abs(sample));energy+=sample*sample
 }
 assert.ok(peak<=.701)
 const rms=Math.sqrt(energy/(48000*10))
 assert.ok(rms>.115&&rms<.131)
 assert.ok(Math.abs(rms-.13)<1e-5||peak>.699,'Only peak limiting may reduce target RMS')
}
self.onmessage({data:{controls:DEFAULT_SOURCE_CONTROLS,family:'unknown'}})
assert.ok(result.error.includes('Unknown source family'))
console.log('All six families render through the actual worker at 48 kHz with stereo transfer, RMS/headroom checks and invalid-family errors.')
