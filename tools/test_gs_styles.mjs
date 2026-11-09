import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const file=ts.createSourceFile('SteadySource.tsx',readFileSync('desktop/src/SteadySource.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let apply
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText()==='applyGesture')apply=node.initializer;ts.forEachChild(node,visit)}visit(file)
const parameter=()=>({value:0,setValueAtTime(value){this.value=value}})
class Player {constructor(){this.evolution=parameter();this.cycleSpeed=parameter();this.loopHold=parameter();this.playbackRate=parameter()}setSource(buffer){this.buffer=buffer}}
const settingsRef={current:{inputMode:'simulated',response:'linear',granularMode:'evolving',evolvingSource:'transformed'}}
const source={sources:Array.from({length:4},()=>new Player()),gains:Array.from({length:4},()=>({gain:parameter()})),filter:{frequency:parameter()},drive:{gain:parameter()},expression:{gain:parameter()},authored:true}
let seenInput
const scope={generatedBuffers:{current:null},settingsRef,context:{current:{currentTime:5}},simulationStart:{current:2},simulatedDrive:time=>({time}),inputRef:{current:{wrong:true}},receivedAt:{current:0},performance:{now:()=>999999},buffers:{current:[0,1,2,3,4,5,6,7]},GranularPlayer:Player,drivingSoundTargets:(input,stale)=>{seenInput=input;assert.equal(stale,false);return {cycleSpeed:.4,rate:.8,driveGain:.3,loopHold:0,bodyGain:1,padGain:.7,glassGain:.1,airGain:1,cutoff:1500}},smoothParameter:(p,value)=>p.value=value,driveEnvelopeTarget:gain=>({gain:Math.sqrt(gain),smoothing:.2}),responseRiseSeconds:{linear:1.1}}
vm.runInNewContext(ts.transpileModule(`globalThis.apply=${apply.getText()}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,scope)
scope.apply(source,0,true)
assert.equal(seenInput.time,3,'Simulated inputs must use replay time, not live telemetry')
assert.deepEqual(source.sources.map(s=>s.buffer),[0,1,2,3],'All modes use stationary buffers by default')
assert.deepEqual(source.sources.map(s=>s.evolution.value),[1,1,1,0],'Transform tonal stems only')
settingsRef.current.evolvingSource='authored'
scope.apply(source,0,true)
assert.deepEqual(source.sources.map(s=>s.buffer),[4,5,6,7])
assert.ok(source.sources.every(s=>s.evolution.value===0),'Do not double-transform authored rises')
settingsRef.current.granularMode='rise'
scope.apply(source,0,true)
assert.deepEqual(source.sources.map(s=>s.buffer),[0,1,2,3])
console.log('Live style wiring shares source buffers, transforms Evolving only, preserves authored comparison, and isolates simulated inputs.')

scope.generatedBuffers.current=['custom-body','custom-pad','custom-glass','air']
settingsRef.current.sourceRevision=1
scope.apply(source,0,true)
assert.deepEqual(source.sources.map(s=>s.buffer),scope.generatedBuffers.current,'Generated source must replace the original stems')
scope.generatedBuffers.current=null
settingsRef.current.sourceRevision=2
scope.apply(source,0,true)
assert.deepEqual(source.sources.map(s=>s.buffer),[0,1,2,3],'Reset must restore original buffers')
let replayEffect
function findReplay(node) {
 if(ts.isCallExpression(node)&&node.expression.getText()==='useEffect'&&node.arguments[0]?.getText().includes('if (sourceReplayRequested)')) replayEffect=node.arguments[0]
 ts.forEachChild(node,findReplay)
}
findReplay(file)
let replays=0
const replayScope={sourceReplayRequested:true,settingsRef:{current:{inputMode:'simulated'}},blocked:false,setSourceReplayRequested(){},play:refresh=>{assert.equal(refresh,true);replays++}}
vm.runInNewContext(ts.transpileModule(`globalThis.replay=${replayEffect.getText()}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,replayScope)
replayScope.replay()
assert.equal(replays,1,'New source replays even after the last drive ended and there is no active voice')
replayScope.blocked=true;replayScope.replay()
assert.equal(replays,1,'Do not interrupt baseline comparison audio')

assert.deepEqual(source.sources.map(s=>s.cycleSpeed.value),[.4,.4,.4,1],'Tonal cycle-speed targets reach live players; air stays fixed')
