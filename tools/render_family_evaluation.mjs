/** Offline source/Rise evaluation; app generators, grain core, map and trace are reused. */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import {createHash} from 'node:crypto'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
import {SourceLoopEngine} from '../desktop/public/audio/granular-processor.mjs'
async function moduleAt(path) {
 const code=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
 return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
}
const designerCode=ts.transpileModule(readFileSync('desktop/src/sourceDesigner.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const designerUrl=`data:text/javascript;base64,${Buffer.from(designerCode).toString('base64')}`
const {createSourceStems,SOURCE_FAMILIES,DEFAULT_SOURCE_CONTROLS,PITCH_TRAVEL,engineStageFor}=await import(designerUrl)
const recipeCode=ts.transpileModule(readFileSync('desktop/src/sourceRecipe.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace("'./sourceDesigner'",JSON.stringify(designerUrl))
const {renderRecipe}=await import(`data:text/javascript;base64,${Buffer.from(recipeCode).toString('base64')}`)
const recipe=process.argv[4]?JSON.parse(readFileSync(process.argv[4],'utf8')):null
const sourceDirectory=process.argv[5]
if(sourceDirectory&&!recipe)throw Error('Reused stems require a source recipe')
const {drivingSoundTargets,responseRiseSeconds}=await moduleAt('desktop/src/drivingSoundMapping.ts')
const {driveEnvelopeTarget}=await moduleAt('desktop/src/audioAutomation.ts')
const {simulatedDrive}=await moduleAt('desktop/src/simulatedDrive.ts')
const mode=process.argv[2]??'rise'
if(!['steady','rise','evolving'].includes(mode)) throw Error('Expected steady, rise or evolving')
const root=process.argv[3]??'artifacts/audiobox_family_eval_2026-11-06',rate=48000,frames=22*rate
mkdirSync(root,{recursive:true})
function wav(path) {
 const bytes=readFileSync(path)
 for(let offset=12;offset<bytes.length;) {
  const size=bytes.readUInt32LE(offset+4)
  if(bytes.toString('ascii',offset,offset+4)==='data')return [0,1].map(c=>Float32Array.from({length:size/8},(_,i)=>bytes.readFloatLE(offset+8+i*8+c*4)))
  offset+=8+size+size%2
 }
 throw Error('Missing WAV samples')
}
const air=wav('desktop/public/audio/original_steady_air.wav')
const meta={rate,controls:DEFAULT_SOURCE_CONTROLS,mode,response:'exponential',frames,source_sha256:createHash('sha256').update(readFileSync('desktop/src/sourceDesigner.ts')).digest('hex'),families:recipe?[{id:'candidate',label:'Composed source'}]:SOURCE_FAMILIES,approximation:'Offline equivalent; filter targets updated each 10 ms, scalar smoothing approximates WebAudio automation. Chorus and IR processing finalized offline; not a bit-identical browser capture.'}
for(const {id} of recipe?[{id:'candidate'}]:SOURCE_FAMILIES) {
 const sourceStarted=performance.now()
 const stems=[...(sourceDirectory?[0,1,2].map(i=>wav(`${sourceDirectory}/stem-${i}.wav`)):recipe?renderRecipe(recipe,rate):createSourceStems(DEFAULT_SOURCE_CONTROLS,rate,id)),air]
 meta.timings??=[]
 const timing={id,source_seconds:(performance.now()-sourceStarted)/1000,reused_source:!!sourceDirectory,drive_seconds:0};meta.timings.push(timing)
 const driveStarted=performance.now()
 if(recipe) for(let s=0;s<4;s++){
  const data=new Float32Array(rate*5*2);for(let i=0;i<rate*5;i++){data[2*i]=stems[s][0][i];data[2*i+1]=stems[s][1][i]}
  const header=Buffer.alloc(44);header.write('RIFF');header.writeUInt32LE(36+data.byteLength,4);header.write('WAVEfmt ',8);header.writeUInt32LE(16,16);header.writeUInt16LE(3,20);header.writeUInt16LE(2,22);header.writeUInt32LE(rate,24);header.writeUInt32LE(rate*8,28);header.writeUInt16LE(8,32);header.writeUInt16LE(32,34);header.write('data',36);header.writeUInt32LE(data.byteLength,40);writeFileSync(`${root}/stem-${s}.wav`,Buffer.concat([header,Buffer.from(data.buffer)]))
 }
 const source=new Float32Array(5*rate*2)
 for(let i=0;i<5*rate;i++)for(let c=0;c<2;c++)source[2*i+c]=stems.reduce((sum,stem)=>sum+stem[c][i],0)
 writeFileSync(`${root}/${id}_source.f32`,Buffer.from(source.buffer))
 const stage=engineStageFor(recipe?recipe.layers[0].method:id,recipe?recipe.layers[0].shape:{})
 if(stage)(meta.effects??={})[id]={chorus:stage.chorus,room:stage.room}  // finalize applies the same shared chorus/room settings as the app
 const engines=stems.map((stem,i)=>{const engine=new SourceLoopEngine(stem,rate);if(i<3)engine.setEngine(stage);return engine})  // engine stage after the player, not on air
 const direct=new Float32Array(frames*2),filtered=new Float32Array(frames*2),automation=new Float32Array(frames*2)
 const travel=PITCH_TRAVEL[recipe?recipe.layers[0].method:id]??1
 let pitch=drivingSoundTargets(simulatedDrive(0),false,'exponential',mode,travel).rate,target,previousTarget=0,gain=0,targetGain=0,smoothing=.18
 const layers=[1,.65,.1,1]
 for(let i=0;i<frames;i++) {
  if(i%480===0) {
   target=drivingSoundTargets(simulatedDrive(i/rate),false,'exponential',mode,travel)
   const envelope=driveEnvelopeTarget(target.driveGain,responseRiseSeconds.exponential,target.driveGain<previousTarget)
   targetGain=envelope.gain;smoothing=envelope.smoothing;previousTarget=target.driveGain
  }
  pitch+=(target.rate-pitch)*(1-Math.exp(-1/(.35*rate)))
  gain+=(targetGain-gain)*(1-Math.exp(-1/(smoothing*rate)))
  const targets=[target.bodyGain,target.padGain,target.glassGain,stage?0:target.airGain]  // styles with a stage: no air layer (see SteadySource)
  for(let stem=0;stem<4;stem++) {
   layers[stem]+=(targets[stem]-layers[stem])*(1-Math.exp(-1/(.15*rate)))
   const left=engines[stem].sample(stem===3?1:pitch,stem===3?0:target.loopHold,stem<3&&mode==='evolving'?1:0,stem<3?target.cycleSpeed:1),right=engines[stem].right
   const output=stem===1||stem===2?filtered:direct
   output[2*i]+=left*layers[stem];output[2*i+1]+=right*layers[stem]
  }
  automation[2*i]=gain*gain;automation[2*i+1]=target.cutoff
 }
 for(const [name,data] of Object.entries({direct,filtered,automation}))writeFileSync(`${root}/${id}_${name}.f32`,Buffer.from(data.buffer))
 if(!source.every(Number.isFinite)||!direct.every(Number.isFinite)||!filtered.every(Number.isFinite))throw Error('Non-finite render')
 timing.drive_seconds=(performance.now()-driveStarted)/1000
 console.log('Rendered',id,JSON.stringify(timing))
}
writeFileSync(`${root}/render_manifest.json`,JSON.stringify(meta,null,2))
