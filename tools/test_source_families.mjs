import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/sourceDesigner.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {createSourceStems,SOURCE_FAMILIES,DEFAULT_SOURCE_CONTROLS}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
assert.equal(SOURCE_FAMILIES.length,6)
const rate=8000,mixes=[]
for(const family of SOURCE_FAMILIES) {
 const stems=createSourceStems(DEFAULT_SOURCE_CONTROLS,rate,family.id)
 assert.equal(stems.length,3)
 const mix=Float32Array.from(stems[0][0],(_,i)=>stems.reduce((sum,stem)=>sum+stem[0][i],0))
 let energy=0,peak=0
 for(const value of mix){assert.ok(Number.isFinite(value));energy+=value*value;peak=Math.max(peak,Math.abs(value))}
 assert.ok(peak<.701)
 assert.ok(Math.abs(Math.sqrt(energy/mix.length)-.13)<.015)
 for(const stem of stems)for(const channel of stem) {
  assert.equal(channel.length,5*rate)
  let maximumStep=0
  for(let i=1;i<channel.length;i++)maximumStep=Math.max(maximumStep,Math.abs(channel[i]-channel[i-1]))
  assert.ok(Math.abs(channel[0]-channel.at(-1))<=maximumStep*1.1+1e-6,`${family.id} loop boundary`)
 }
 const frequencies=[1,2,3,4,5,6,7,8,2.01,2.73,4.17,1.414,3.414].map(ratio=>Math.round(174.8*ratio*5)/5)
 const signature=frequencies.map(frequency=>{
  let real=0,imaginary=0
  for(let i=0;i<mix.length;i++){const phase=2*Math.PI*frequency*i/rate;real+=mix[i]*Math.cos(phase);imaginary+=mix[i]*Math.sin(phase)}
  return real*real+imaginary*imaginary
 })
 mixes.push({id:family.id,mix,signature})
}
for(let a=0;a<mixes.length;a++)for(let b=a+1;b<mixes.length;b++) {
 const x=mixes[a],y=mixes[b]
 let difference=0,dot=0,xx=0,yy=0
 for(let i=0;i<x.mix.length;i++)difference+=(x.mix[i]-y.mix[i])**2
 for(let i=0;i<x.signature.length;i++){dot+=x.signature[i]*y.signature[i];xx+=x.signature[i]**2;yy+=y.signature[i]**2}
 assert.ok(Math.sqrt(difference/x.mix.length)>.02,`${x.id}/${y.id} waveform diversity`)
 assert.ok(dot/Math.sqrt(xx*yy)<.998,`${x.id}/${y.id} spectral diversity`)
}
assert.throws(()=>createSourceStems(DEFAULT_SOURCE_CONTROLS,rate,'unknown'))
console.log('Six source families have distinct spectra, finite stereo loops and comparable source energy.')
const bowed=mixes.find(item=>item.id==='bowed'),rounded=mixes.find(item=>item.id==='rounded'),airy=mixes.find(item=>item.id==='airy')
assert.ok(rounded.signature[2]/rounded.signature[0]>3*bowed.signature[2]/bowed.signature[0],'Rounded electronic needs a clearly stronger hollow odd-harmonic character')
let airStep=0,airEnergy=0
for(let i=1;i<airy.mix.length;i++){airStep+=(airy.mix[i]-airy.mix[i-1])**2;airEnergy+=airy.mix[i]**2}
assert.ok(Math.sqrt(airStep/airEnergy)<.55,'Air should retain a smooth tonal core rather than being dominated by rough high-frequency texture')
