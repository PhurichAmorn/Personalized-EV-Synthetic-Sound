import assert from 'node:assert/strict'
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {execFileSync} from 'node:child_process'
const root=mkdtempSync(join(tmpdir(),'ev-source-reuse-'))
try {
 const recipe=join(root,'recipe.json'),fresh=join(root,'fresh'),reused=join(root,'reused')
 writeFileSync(recipe,JSON.stringify({version:1,seed:42,layers:[{role:'foundation',method:'airy',gain:1,shape:{noiseCenter:950,noiseWidth:400}}]}))
 execFileSync(process.execPath,['tools/render_family_evaluation.mjs','steady',fresh,recipe])
 execFileSync(process.execPath,['tools/render_family_evaluation.mjs','steady',reused,recipe,fresh])
 for(const suffix of ['source','direct','filtered','automation'])assert.deepEqual(readFileSync(join(fresh,`candidate_${suffix}.f32`)),readFileSync(join(reused,`candidate_${suffix}.f32`)),`${suffix} must remain sample-identical with reused source`)
 const meta=JSON.parse(readFileSync(join(reused,'render_manifest.json')))
 assert.equal(meta.timings[0].reused_source,true)
 console.log('Cached source stems produce sample-identical mapped audio without resynthesis.')
} finally {rmSync(root,{recursive:true,force:true})}
