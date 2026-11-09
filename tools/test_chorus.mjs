import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/audioAutomation.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {createChorus}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const nodes=[]
function node(kind) {
 const n={kind,gain:{value:1},frequency:{value:440},delayTime:{value:0},connections:[],stopped:false,disconnected:false,connect(...args){this.connections.push(args)},disconnect(){this.disconnected=true},start(){this.started=true},stop(){this.stopped=true}}
 nodes.push(n);return n
}
const chorus=createChorus({createGain:()=>node('gain'),createChannelSplitter:channels=>{assert.equal(channels,2);return node('split')},createChannelMerger:channels=>{assert.equal(channels,2);return node('merge')},createDelay:maximum=>{assert.equal(maximum,.05);return node('delay')},createOscillator:()=>node('oscillator')})
const delays=nodes.filter(n=>n.kind==='delay'),oscillators=nodes.filter(n=>n.kind==='oscillator')
assert.deepEqual(delays.map(n=>n.delayTime.value),[.018,.023])
assert.deepEqual(oscillators.map(n=>n.frequency.value),[.28,.33])
assert.ok(oscillators.every(n=>n.started))
for(const delay of delays) assert.equal(delay.connections[0][0].kind,'merge','No feedback into delays')
const split=nodes.find(n=>n.kind==='split')
assert.deepEqual(split.connections.map(connection=>connection[1]),[0,1],'Preserve separate stereo channels')
assert.equal(chorus.input.connections.length,2,'Retain direct sound alongside chorus')
chorus.dispose()
assert.ok(nodes.every(n=>n.disconnected),'Release all chorus nodes')
assert.ok(oscillators.every(n=>n.stopped),'Stop modulation after voice ends')
console.log('Stereo chorus has short independent modulation, a dry path, no feedback, and complete cleanup.')
