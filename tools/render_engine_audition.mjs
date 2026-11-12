/** Render engine-note source variants (original app synthesis, family 'engine') to WAV, plus a continuous pitch-shifted rev sweep. Usage: node tools/render_engine_audition.mjs [outdir] */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const load=async path=>{const code=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
 return import(`data:text/javascript;base64,${Buffer.from(code.replace("'./sourceDesigner'",JSON.stringify(`data:text/javascript;base64,${Buffer.from(ts.transpileModule(readFileSync('desktop/src/sourceDesigner.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText).toString('base64')}`))).toString('base64')}`)}
const {renderRecipe}=await load('desktop/src/sourceRecipe.ts')
const out=process.argv[2]??'.cache/ice_source';mkdirSync(out,{recursive:true})
const rate=48000,MAX_RATE=+(process.argv[3]??1.2)  // app mapping tops out near 1.9 (+11 semitones from -10)
const voice=(shape,controls,gain=1)=>({role:'foundation',method:'engine',gain,shape,controls:{movement:.3,...controls}})
const variants={
 soft_sport:{layers:[voice({rootRatio:1,lope:.3,drive:.8,tilt:0},{body:.7,character:.45,ensemble:.5})]},
 mellow:{layers:[voice({rootRatio:.9,lope:.25,drive:.4,tilt:-.1},{body:.8,character:.3,ensemble:.55})]},
 deep_growl:{layers:[voice({rootRatio:.8,lope:.6,drive:1.2,tilt:-.15},{body:.85,character:.35,ensemble:.6})]},
 round_gt:{layers:[voice({rootRatio:1,lope:.15,drive:0,tilt:-.2},{body:.75,character:.4,ensemble:.5})]},
}
const custom=process.argv[4]?JSON.parse(readFileSync(process.argv[4],'utf8')):null  // optional {name: recipe}
for(const [name,{layers}] of Object.entries(custom??variants)){
 const [a,b,c]=renderRecipe({version:1,seed:0,layers},rate)
 const n=rate*5,loop=new Float32Array(n*2)
 for(let i=0;i<n;i++)for(let ch=0;ch<2;ch++)loop[2*i+ch]=a[ch][i]+b[ch][i]+c[ch][i]
 // continuous rev: playback rate glides .55 -> MAX_RATE over 8 s (exponential), then back down over 4 s
 const len=Math.floor(rate*12),data=new Float32Array(len*2);let pos=0
 for(let i=0;i<len;i++){const t=i/rate,x=t<8?t/8:1-(t-8)/4,r=.55*Math.pow(MAX_RATE/.55,Math.min(1,Math.max(0,x)))
  const k=Math.floor(pos),f=pos-k;for(let ch=0;ch<2;ch++)data[2*i+ch]=loop[2*(k%n)+ch]*(1-f)+loop[2*((k+1)%n)+ch]*f;pos+=r}
 let peak=0;for(const v of data)peak=Math.max(peak,Math.abs(v));for(let i=0;i<data.length;i++)data[i]*=.7/peak
 const pcm=Buffer.alloc(data.length*2);data.forEach((v,i)=>pcm.writeInt16LE(Math.round(v*32767),i*2))
 const h=Buffer.alloc(44);h.write('RIFF');h.writeUInt32LE(36+pcm.length,4);h.write('WAVEfmt ',8);h.writeUInt32LE(16,16);h.writeUInt16LE(1,20);h.writeUInt16LE(2,22);h.writeUInt32LE(rate,24);h.writeUInt32LE(rate*4,28);h.writeUInt16LE(4,32);h.writeUInt16LE(16,34);h.write('data',36);h.writeUInt32LE(pcm.length,40)
 writeFileSync(`${out}/${name}_sweep.wav`,Buffer.concat([h,pcm]));console.log(`${out}/${name}_sweep.wav`)
}
