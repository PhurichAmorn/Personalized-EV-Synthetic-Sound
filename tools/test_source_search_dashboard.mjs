import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
function find(path,predicate){const file=ts.createSourceFile(path,readFileSync(path,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let result;function visit(node){if(predicate(node))result=node;ts.forEachChild(node,visit)}visit(file);assert.ok(result);return result}
const editor='desktop/src/SoundEditor.tsx'
const panel=find(editor,n=>ts.isJsxSelfClosingElement(n)&&n.tagName.getText()==='SourceSearch')
const hidden=panel.attributes.properties.find(p=>p.name?.getText()==='hidden').initializer.expression.getText()
assert.equal(vm.runInNewContext(hidden,{personalizeOpen:true}),false,'Discovery must be visible inside Personalize sound')
assert.equal(vm.runInNewContext(hidden,{personalizeOpen:false}),true,'Discovery must stay off the ordinary dashboard and Sound Lab')
const engine=find(editor,n=>ts.isJsxSelfClosingElement(n)&&n.tagName.getText()==='SteadySource')
const play=engine.attributes.properties.find(p=>p.name?.getText()==='onPlay').initializer.expression.getText()
let activated=0
vm.runInNewContext(`(${play})()`,{setBaselineActive(){},setPreviewOwner(){},setSourcePlaying(){},onSourceSelected:()=>activated++})
assert.equal(activated,1,'Candidate playback must select GS in the dashboard')
console.log('Source discovery opens in Personalize sound and uses the shared dashboard GS player.')
const autoPlay=find('desktop/src/Dashboard.tsx',n=>ts.isCallExpression(n)&&n.expression.getText()==='useEffect'&&n.arguments[0]?.getText().includes('sound.current?.start(true)')).arguments[0].getText()
let starts=0
const drive={granularSelected:true,state:{running:true,starting:false,search:{active:false},soundSweepActive:false,sourceDiscovery:{active:true}},sound:{current:{start:()=>starts++}}}
vm.runInNewContext(`(${autoPlay})()`,drive);assert.equal(starts,0,'Auto-start must not replace a trial candidate')
drive.state.sourceDiscovery.active=false
vm.runInNewContext(`(${autoPlay})()`,drive);assert.equal(starts,1)
drive.state.starting=true
vm.runInNewContext(`(${autoPlay})()`,drive);assert.equal(starts,1,'Wait for vehicle startup before original GS playback')
const autoStart=find('desktop/src/App.tsx',n=>ts.isCallExpression(n)&&n.expression.getText()==='useEffect'&&n.arguments[0]?.getText().includes('startVehicle()')).arguments[0].getText()
let requests=0
const app={page:'dashboard',state:{running:false,starting:false,soundSweepActive:false,audioError:''},vehicleStartPending:{current:false},startVehicle:()=>requests++}
vm.runInNewContext(`(${autoStart})()`,app);assert.equal(requests,0,'Vehicle must not auto-start on ordinary dashboard load')
app.page='search';vm.runInNewContext(`(${autoStart})()`,app);assert.equal(requests,1,'Opening Personalize sound auto-starts vehicle')
app.state.running=true
vm.runInNewContext(`(${autoStart})()`,app);assert.equal(requests,1)
app.state.running=false;app.state.audioError='Device unavailable'
vm.runInNewContext(`(${autoStart})()`,app);assert.equal(requests,1,'Audio failures must not cause repeated auto-start attempts')
const startVehicle=find('desktop/src/App.tsx',n=>ts.isFunctionDeclaration(n)&&n.name?.getText()==='startVehicle').getText()
assert.match(startVehicle,/vehicleStartPending\.current/,'Start helper must guard duplicate effect calls')
assert.match(startVehicle,/command<State>\('toggle'\)/,'Start helper must use long-standing bridge command so it works with an already running backend')
assert.match(readFileSync('desktop/src/App.tsx','utf8'),/sourceDiscovery\?\.completed/,'Completed broad-discovery results remain protected from accidental close')
const dashboardSource=readFileSync('desktop/src/Dashboard.tsx','utf8')
assert.match(dashboardSource,/!personalizeOpen\s*&&\s*<>[\s\S]*?className="start-button"/,'Dashboard start control must be hidden only while Personalize sound is open')
assert.match(readFileSync('desktop/src/style.css','utf8'),/\.dashboard-controls\.personalize-active \.start-controls \{ flex-basis: 0/,'Personalize panel must use space freed by hidden start controls')

const attach=find(editor,n=>ts.isCallExpression(n)&&n.expression.getText()==='useEffect'&&n.arguments[0]?.getText().includes('host.appendChild')).arguments[0].getText()
let attachments=0,removals=0
const container={remove:()=>removals++},host={appendChild:element=>{assert.equal(element,container);attachments++}}
const dom={personalizeOpen:true,discoveryContainer:container,document:{getElementById:id=>{assert.equal(id,'source-discovery-slot');return host}}}
let cleanup=vm.runInNewContext(`(${attach})()`,dom)
assert.equal(attachments,1);cleanup()
dom.personalizeOpen=false
cleanup=vm.runInNewContext(`(${attach})()`,dom)
assert.equal(attachments,1);cleanup()
dom.personalizeOpen=true
cleanup=vm.runInNewContext(`(${attach})()`,dom)
assert.equal(attachments,2,'Reopening attaches the same portal container without remounting trial controls');cleanup()
assert.equal(removals,3)
const target=find('desktop/src/App.tsx',n=>ts.isJsxSelfClosingElement(n)&&n.attributes.getText().includes('id="source-discovery-slot"'))
assert.ok(target)
