import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
function nodes(path,predicate){const file=ts.createSourceFile(path,readFileSync(path,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),out=[];function visit(n){if(predicate(n))out.push(n);ts.forEachChild(n,visit)}visit(file);return out}
const panels=nodes('desktop/src/SourceSearch.tsx',n=>ts.isJsxOpeningElement(n)&&n.tagName.getText()==='section')
assert.ok(panels.length>=1,'New search must keep its comparison panel')
for(const panel of panels)assert.ok(panel.attributes.getText().includes('panel'),'Search panels use the existing Personalize sound design')
assert.equal(nodes('desktop/src/SourceSearch.tsx',n=>ts.isJsxOpeningElement(n)&&n.attributes.getText().includes('reference-reconstruction')).length,0,'Do not insert an experimental reference panel into Personalize sound')
const legacy=nodes('desktop/src/App.tsx',n=>ts.isConditionalExpression(n)&&n.condition.getText()==='state.search.active'&&n.whenTrue.getText().includes('Session setup'))
assert.equal(legacy.length,1,'Legacy form is reserved for an already active legacy session')
assert.ok(legacy[0].whenFalse.getText().includes('source-discovery-slot'))
const engine=nodes('desktop/src/SoundEditor.tsx',n=>ts.isJsxSelfClosingElement(n)&&n.tagName.getText()==='SteadySource')[0]
assert.ok(engine.attributes.properties.some(p=>p.name?.getText()==='headless'&&!p.initializer),'Keep the shared engine mounted without its old controls')
assert.ok(nodes('desktop/src/SteadySource.tsx',n=>ts.isIfStatement(n)&&n.expression.getText()==='headless'&&n.thenStatement.getText().includes('return null')).length)
console.log('Personalize sound uses one broad-discovery panel without duplicate legacy/template UI; the audio engine stays mounted.')
