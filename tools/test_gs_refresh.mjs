import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const source=ts.createSourceFile('SteadySource.tsx',readFileSync('desktop/src/SteadySource.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
let play
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText()==='play') play=node.initializer;ts.forEachChild(node,visit)}
visit(source)
const callback=ts.transpileModule(`globalThis.callback=${play.getText()}`,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const parameter=()=>({value:0,setValueAtTime(){},linearRampToValueAtTime(){},cancelAndHoldAtTime(){},setTargetAtTime(){}})
const node=()=>({gain:parameter(),frequency:parameter(),Q:parameter(),connect(){},disconnect(){}})
let resume,fetches=0,stopOptions=[],started=[],contexts=0,closed=0
const timers=[]
const audio={currentTime:0,resume:()=>new Promise(resolve=>resume=resolve),decodeAudioData:async bytes=>({id:bytes}),createGain:node,createAnalyser:node,destination:{},close:async()=>{closed++},createBiquadFilter:node,createConvolver:node,audioWorklet:{addModule:async()=>{}}}
const scope={externalSourceUrls:{current:null},generatedSource:{current:null},generatedBuffers:{current:null},simulationStart:{current:0},setSimulationTime(){},createChorus:()=>({input:node(),output:node(),dispose(){}}),window:{setTimeout:callback=>timers.push(callback)},AudioContext:class {constructor(){contexts++;return audio}},playing:true,loading:false,request:{current:0},voice:{current:{}},buffers:{current:['old']},context:{current:audio},analyser:{current:node()},workletReady:{current:Promise.resolve()},method:'granular',granularMode:'steady',settingsRef:{current:{method:'granular',inputMode:'driving',response:'linear',granularMode:'steady',evolvingSource:'transformed'}},controls:{current:{spatial:true,volume:.7,climb:0}},STEMS:['body','pad','glass','air'],setLoading(){},setError(){},setPlaying(){},onPlay(){},playingCallback:{current(){}},applyGesture(){},fetch:async(url,options)=>{fetches++;assert.equal(options?.cache,'no-store');return {ok:true,arrayBuffer:async()=>url}},GranularPlayer:class {constructor(audio,buffer){this.buffer=buffer}connect(){}start(){started.push(this.buffer.id)}stop(){}},stop:preserve=>{stopOptions.push(preserve);scope.voice.current=null;scope.request.current++}}
vm.runInNewContext(callback,scope)
const running=scope.callback(true)
assert.equal(typeof resume,'function','Refresh must reload instead of toggling off or returning while already playing')
scope.settingsRef.current.granularMode='evolving'
resume()
await running
assert.deepEqual(stopOptions,[true],'Refresh must keep native audio muted while replacing the player')
assert.equal(contexts,1,'Refresh must replace the old audio context/worklet')
assert.equal(timers.length,1)
timers[0]()
assert.equal(closed,1,'Old audio context is released after its fade')
assert.equal(fetches,9,'Refresh must bypass previously decoded buffers')
assert.equal(started.length,4)
assert.ok(started.every(url=>url.includes('original_steady_')),'Transformed Evolving must use the same stationary source after a mode change during loading')
assert.equal(scope.voice.current.granularMode,'evolving')
console.log('GS refresh reloads audio without HTTP/decoded cache and resolves the newest mode after asynchronous loading.')
