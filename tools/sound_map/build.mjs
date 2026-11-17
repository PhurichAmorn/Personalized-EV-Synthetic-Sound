// Bundles the app's synth for Node (generator) and the browser (listening page) into out/. Run: node tools/sound_map/build.mjs
import { createRequire } from 'node:module'
const esbuild = createRequire(new URL('../../desktop/package.json', import.meta.url))('esbuild')
const here = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')  // Windows: /C:/... -> C:/...
const node = { bundle: true, platform: 'node', format: 'esm', logLevel: 'warning' }
await esbuild.build({ ...node, entryPoints: [here + 'synth.ts'], outfile: here + 'out/synth.mjs' })
await esbuild.build({ ...node, entryPoints: [here + 'labelled.ts'], outfile: here + 'out/labelled.mjs' })
await esbuild.build({ ...node, entryPoints: [here + 'drive.ts'], outfile: here + 'out/drive.mjs' })
await esbuild.build({ ...node, entryPoints: [here + 'orchestra.ts'], outfile: here + 'out/orchestra.mjs' })
await esbuild.build({ ...node, entryPoints: [here + 'shepard.ts'], outfile: here + 'out/shepard.mjs' })
await esbuild.build({ ...node, entryPoints: [here + 'octaves.ts'], outfile: here + 'out/octaves.mjs' })
await esbuild.build({ stdin: { contents: "export { createPlainSource, roomImpulse, EXTRAS_OFF } from '../../desktop/src/plainSource'\nexport { driveSound } from './chain'", resolveDir: here, loader: 'ts' },
  bundle: true, format: 'iife', globalName: 'Synth', minify: true, outfile: here + 'out/synth.js', logLevel: 'warning' })
