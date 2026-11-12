"""Autosaved source-discovery history, kept locally under experiment_data/ (untracked), plus on-demand preview renders."""
from datetime import datetime
from pathlib import Path
import json,re,shutil,threading,uuid
from experiment import source_render_queue as queue

ROOT=Path(__file__).resolve().parents[1]/'experiment_data/source_history'
ID=re.compile(r'[0-9a-f]{32}')

class SourceHistory:
    def __init__(self,discovery,root=ROOT):
        self.discovery=discovery;self.root=root;self.session=None;self.created=None
        self.preview={};self.keys=set();self.token=0;self.lock=threading.Lock()
    def begin(self):
        self.session=uuid.uuid4().hex;self.created=datetime.now().astimezone().isoformat(timespec='seconds')  # computer's own clock and zone
    def save(self):
        """Write the running session. Called after every command that changes it; sessions with no saved rating are skipped."""
        if not self.session or not self.discovery.completed:return
        self.root.mkdir(parents=True,exist_ok=True)
        data={**self.discovery.export(),'id':self.session,'created':self.created}
        for candidate in data['candidates'].values():candidate.pop('urls',None);candidate.pop('traces',None)  # cache paths; previews are regenerated
        temp=self.root/f'{self.session}.tmp';temp.write_text(json.dumps(data));temp.replace(self.root/f'{self.session}.json')
    def _read(self,ident):
        if not ID.fullmatch(ident):raise ValueError('Unknown history entry')
        return json.loads((self.root/f'{ident}.json').read_text())
    def listing(self):
        rows=[]
        for path in self.root.glob('*.json'):
            try:d=json.loads(path.read_text());rows.append({'id':d['id'],'created':d['created'],'completed':len(d['history']),'final':d['final'],'finalists':len(d['finalists']),'done':bool(d['finalists'])})
            except (OSError,ValueError,KeyError):continue
        return sorted(rows,key=lambda row:row['created'],reverse=True)
    def get(self,ident):return self._read(ident)
    def delete(self,ident):
        if not ID.fullmatch(ident):raise ValueError('Unknown history entry')
        (self.root/f'{ident}.json').unlink(missing_ok=True)
        return True
    def render(self,ident,candidate):
        """Start rendering one saved sound in the background; the result appears in snapshot()['historyPreview']. Nothing is kept: clear() removes it."""
        recipe=self._read(ident)['candidates'][candidate]['recipe']
        self.clear()
        with self.lock:self.token+=1;token=self.token;self.preview={'session':ident,'candidate':candidate,'status':'rendering'}
        def work():
            try:result=self.discovery.renderer(recipe);state={'status':'ready','url':result['traces']['rise'],'key':result['id']}
            except Exception as exc:state={'status':'error','error':str(exc)[:300]}
            with self.lock:
                if token!=self.token:  # replaced or cleared meanwhile
                    if 'key' in state:self._remove(state['key'])
                    return
                self.preview={**self.preview,**state}
        threading.Thread(target=work,daemon=True).start()
    def _remove(self,key):
        if key not in self.discovery.candidates:shutil.rmtree(queue.CACHE/key,ignore_errors=True)  # a running session may still use it
    def clear(self):
        with self.lock:
            self.token+=1;key=self.preview.get('key');self.preview={}
        if key:self._remove(key)
