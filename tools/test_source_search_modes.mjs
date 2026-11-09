import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const file=ts.createSourceFile('SourceSearch.tsx',readFileSync('desktop/src/SourceSearch.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const selectors=[],effects=[];let change,ready
function visit(node){
 if(ts.isJsxOpeningElement(node)&&node.tagName.getText()==='select')selectors.push(node)
 if(ts.isVariableDeclaration(node)&&node.name.getText()==='changePlayback')change=node.initializer.getText()
 if(ts.isVariableDeclaration(node)&&node.name.getText()==='ready')ready=node.initializer.getText()
 if(ts.isCallExpression(node)&&node.expression.getText()==='useEffect')effects.push(node.arguments[0].getText())
 ts.forEachChild(node,visit)
}visit(file)
const compile=code=>ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
assert.equal(selectors.length,0,'There is no input chooser; source discovery always uses live driving')
assert.equal(change,undefined,'Do not retain obsolete input-switching logic')
const reset=effects.find(code=>code.includes('heard.current.clear()'))
const local={auditionSequence:{current:0},heard:{current:new Set(['a','b'])},setAudition(){},setReadyAudition(){}}
vm.runInNewContext(compile(`(${reset})()`),local)
assert.equal(local.heard.current.size,0,'Mode/pair changes reset hearing eligibility')
local.discovery={busy:false,pair:[{id:'a'},{id:'b'}],heard:['a','b']};local.pending=false
assert.equal(vm.runInNewContext(compile(`(${ready})`),local),false)
local.heard.current.add('a');local.heard.current.add('b')
assert.equal(vm.runInNewContext(compile(`(${ready})`),local),true)
console.log('Discovery uses live driving only and still resets hearing eligibility on mode/pair changes.')
