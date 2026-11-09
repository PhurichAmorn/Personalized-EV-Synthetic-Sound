import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const compile=p=>ts.transpileModule(readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const url=`data:text/javascript;base64,${Buffer.from(compile('desktop/src/sourceDesigner.ts')).toString('base64')}`
const code=compile('desktop/src/sourceRecipe.ts').replace("'./sourceDesigner'",JSON.stringify(url))
const {renderRecipe,validateRecipe}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const recipe={version:1,seed:42,layers:[{role:'foundation',method:'bowed',gain:1,shape:{tilt:.2}},{role:'character',method:'vocal',gain:.35,shape:{formantScale:1.25}},{role:'texture',method:'glass',gain:.2,shape:{stretch:1.15}}]}
const stems=renderRecipe(recipe,8000)
assert.deepEqual(stems,renderRecipe(recipe,8000))
for(const stem of stems)for(const channel of stem){assert.equal(channel.length,40000);assert.ok(channel.every(Number.isFinite));let step=0;for(let i=1;i<channel.length;i++)step=Math.max(step,Math.abs(channel[i]-channel[i-1]));assert.ok(Math.abs(channel[0]-channel.at(-1))<step*1.1)}
assert.throws(()=>validateRecipe({...recipe,layers:[...recipe.layers,recipe.layers[1]]}))
assert.throws(()=>renderRecipe({...recipe,layers:[{...recipe.layers[0],shape:{fmIndex:99}}]},8000))
const {createSourceStems,DEFAULT_SOURCE_CONTROLS}=await import(url)
assert.deepEqual(createSourceStems(DEFAULT_SOURCE_CONTROLS,8000,'bowed'),createSourceStems(DEFAULT_SOURCE_CONTROLS,8000,'bowed',{}),'Legacy family output stays unchanged with no structural parameters')
console.log('Composable recipes validate roles/shape limits and generate repeatable periodic stereo sources.')
const light={...recipe,layers:[{...recipe.layers[0],controls:{body:.2,character:.1,ensemble:.15,movement:.5}}]}
const rich={...recipe,layers:[{...recipe.layers[0],controls:{body:.95,character:.9,ensemble:.9,movement:.5}}]}
const lightAudio=renderRecipe(light,8000),richAudio=renderRecipe(rich,8000)
let sourceDifference=0
for(let i=0;i<40000;i++)sourceDifference+=(lightAudio[0][0][i]-richAudio[0][0][i])**2
assert.ok(Math.sqrt(sourceDifference/40000)>.005,'Recipe-level body, harmonics and ensemble controls must alter source audio')
assert.throws(()=>renderRecipe({...light,layers:[{...light.layers[0],controls:{...light.layers[0].controls,body:2}}]},8000))
