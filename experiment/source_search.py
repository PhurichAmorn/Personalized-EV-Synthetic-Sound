"""In-memory source discovery; independent of native-profile search and participant records."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
from itertools import combinations
import math,random,threading
import numpy as np
from experiment.source_render_queue import SourceRenderer,trim_cache

POLICY='source-diversity-preference-model-bt-playoff-v1'
MAX_COMPARISONS=14  # Rated discovery pairs.
FINALIST_COUNT=4
PLAYOFF_PAIRS=FINALIST_COUNT*(FINALIST_COUNT-1)//2  # Full round-robin: 6.
TOTAL_STEPS=MAX_COMPARISONS+PLAYOFF_PAIRS  # 20 listening steps.
RATING_PRIOR=4
RATING_PRIOR_WEIGHT=2
MIN_AUDIO_DISTANCE=.10  # Provisional spectral separation, not a perceptual guarantee.
METHODS=('bowed','rounded','vocal','glass','resonant','airy')
COMPANION_SUB_FAMILIES=('bowed','glass','airy')  # Sub-octave pad tuning was listener-checked only for these.
BOUNDS={'rootRatio':(.8,1.4),'tilt':(-.6,.6),'formantScale':(.65,1.45),'fmRatio':(1.2,4.),'fmIndex':(.2,2.5),'stretch':(.75,1.3),'noiseCenter':(500.,1900.),'noiseWidth':(180.,750.)}
# Must match sourceDesigner defaults at the fixed character=.5 renderer setting.
APPLICABLE={'bowed':('tilt',),'rounded':('tilt',),'vocal':('tilt','formantScale'),'glass':('stretch',),'resonant':('fmRatio','fmIndex'),'airy':('noiseCenter','noiseWidth')}
PREFERENCE_PRIOR_STRENGTH=4.0
PREFERENCE_EXPLORATION=1.25

def preference_features(recipe):
    layers=recipe['layers'];total=sum(layer['gain'] for layer in layers) or 1
    methods=tuple(sum(layer['gain'] for layer in layers if layer['method']==method)/total for method in METHODS)
    return np.array([*(float(layers[0]['method']==method) for method in METHODS),*methods,
                     *(float(len(layers)==count) for count in (1,2,3)),
                     float(np.mean([layer['shape'].get('companionSub',0.) for layer in layers]))])

def preference_model(candidates):
    rows=[];ratings=[]
    for candidate in candidates.values():
        for rating in candidate.get('ratings',[]):
            rows.append(preference_features(candidate['recipe']));ratings.append(rating-RATING_PRIOR)
    if not rows:return None
    design=np.stack(rows);gram=design.T@design+PREFERENCE_PRIOR_STRENGTH*np.eye(design.shape[1])
    covariance=np.linalg.inv(gram)
    weights=covariance@design.T@np.asarray(ratings)
    return weights,covariance,len(ratings)

def preference_summary(candidates):
    model=preference_model(candidates)
    if not model:return {'version':1,'training_ratings':0,'feature_weights':{}}
    weights,_,count=model
    names=[*(f'foundation:{method}' for method in METHODS),*(f'layer_mix:{method}' for method in METHODS),*(f'layers:{count}' for count in (1,2,3)),'companion:sub_octave']
    return {'version':1,'training_ratings':count,'feature_weights':dict(zip(names,map(float,weights)))}

def make_recipe(rng,method=None):
    roles=['foundation'] if method else ['foundation']+['character','texture'][:rng.choice([0,1,2,2])]
    layers=[]
    for index,role in enumerate(roles):
        kind=method or rng.choice(METHODS)
        shape={} if method else {key:rng.uniform(*BOUNDS[key]) for key in APPLICABLE[kind]}
        if not method:
            shape['rootRatio']=rng.uniform(.85,1.15) if index==0 else rng.uniform(.8,1.4)
            if kind in COMPANION_SUB_FAMILIES:shape['companionSub']=rng.choice((0.,1.))
        layer={'role':role,'method':kind,'gain':1. if index==0 else rng.uniform(.1,.5 if index==1 else .25),'shape':shape}
        if not method:layer['controls']={'body':rng.uniform(.2,.95),'character':rng.uniform(.1,.9),'ensemble':rng.uniform(.15,.9),'movement':.5}
        layers.append(layer)
    return {'version':1,'seed':0 if method else rng.randrange(2**30),'layers':layers}

def make_broad_recipe(rng,foundation,layer_count,auxiliaries=None):
    methods=[foundation]+(list(auxiliaries) if auxiliaries is not None else rng.sample([method for method in METHODS if method!=foundation],layer_count-1))
    layers=[]
    for index,(role,method) in enumerate(zip(['foundation','character','texture'],methods)):
        shape={key:rng.uniform(*BOUNDS[key]) for key in APPLICABLE[method]}
        shape['rootRatio']=rng.uniform(.85,1.15) if index==0 else rng.uniform(.8,1.4)
        if method in COMPANION_SUB_FAMILIES:shape['companionSub']=rng.choice((0.,1.))
        layers.append({'role':role,'method':method,'gain':1. if index==0 else rng.uniform(.1,.5 if index==1 else .25),'shape':shape,'controls':{'body':rng.uniform(.2,.95),'character':rng.uniform(.1,.9),'ensemble':rng.uniform(.15,.9),'movement':.5}})
    return {'version':1,'seed':rng.randrange(2**30),'layers':layers}

class SourceDiscovery:
    def __init__(self,renderer=None):
        self.renderer=renderer or SourceRenderer();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='source-discovery')
        self.lock=threading.RLock();self.epoch=0;self.active=False;self.busy=False;self.error='';self.candidates={};self.pair=[];self.history=[];self.favourites=[];self.notes={};self.tried=set();self.quarantine=[];self.final=None;self.rng=random.Random();self.completed=0;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[]
    def close(self):
        self.epoch+=1
        if hasattr(self.renderer,'close'):self.renderer.close()
        self.executor.shutdown(wait=False,cancel_futures=True)
    def snapshot(self):
        with self.lock:
            def public(ident):
                c=self.candidates[ident]
                return {k:c[k] for k in ['id','label','recipe','urls','traces'] if k in c}
            return {'active':self.active,'busy':self.busy,'error':self.error,'completed':self.completed,'pair':[public(x) for x in self.pair],'heard':list(self.tried),'selected':self.selected,'favourites':[dict(public(x),note=self.notes.get(x,'')) for x in self.favourites],'final':self.final,'finalists':[dict(public(x),**self._finalist_summary(x,strength)) for x,strength in self._bt_order()],'stage':self.stage,'step':self.completed+len(self.playoff_history),'totalSteps':TOTAL_STEPS,'playoffDone':len(self.playoff_history),'playoffTotal':PLAYOFF_PAIRS,'quarantined':len(self.quarantine),'policy':POLICY,'checkpoint':self.stage!='discovery','maxComparisons':MAX_COMPARISONS}
    def start(self):
        with self.lock:
            if self.busy:raise ValueError('Wait for source preparation to finish')
            self.epoch+=1;self.active=True;self.error='';self.candidates={};self.pair=[];self.history=[];self.favourites=[];self.notes={};self.tried=set();self.quarantine=[];self.completed=0;self.final=None;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[]
            self.seed=random.SystemRandom().randrange(2**31);self.rng=random.Random(self.seed)
            self._prepare()
    def _proposals(self):
        if self.completed<3:
            references=[make_recipe(self.rng,m) for m in METHODS[2*self.completed:2*self.completed+2]]
            return references+[make_recipe(self.rng) for _ in range(12)]
        family_count={method:0 for method in METHODS};structure_count={count:0 for count in (1,2,3)}
        recent=set()
        for row in self.history:
            for ident in row['pair']:
                recipe=self.candidates[ident]['recipe'];family_count[recipe['layers'][0]['method']]+=1;structure_count[len(recipe['layers'])]+=1
        for row in self.history[-2:]:
            recent.update(self.candidates[ident]['recipe']['layers'][0]['method'] for ident in row['pair'])
        families=list(METHODS);self.rng.shuffle(families);families.sort(key=lambda method:(family_count[method],method in recent))
        structures=[1,2,3];self.rng.shuffle(structures);structures.sort(key=lambda count:structure_count[count])
        layer_count=structures[0];auxiliaries=self.rng.sample([method for method in METHODS if method not in families[:4]],layer_count-1)
        proposals=[make_broad_recipe(self.rng,family,layer_count,auxiliaries) for family in families[:4] for _ in range(2)]
        model=preference_model(self.candidates)
        if model:
            weights,covariance,_=model
            proposals.sort(key=lambda recipe:(
                preference_features(recipe)@weights+PREFERENCE_EXPLORATION*math.sqrt(max(0.,preference_features(recipe)@covariance@preference_features(recipe))),
                self.rng.random()),reverse=True)
            # Exposure floor: the least-exposed family always takes one slot (ties keep model order); the model only
            # steers the other slot, so one early low rating cannot starve a family.
            first=min(range(len(proposals)),key=lambda i:(family_count[proposals[i]['layers'][0]['method']],i))
            proposals.insert(0,proposals.pop(first))
        return proposals
    def _prepare(self):
        self.busy=True;self.error='';self.pair=[];self.tried.clear();self.selected=None;token=self.epoch
        proposals=self._proposals()
        def work():
            accepted=[];attempts=0
            anchor=None
            if self.completed>=3 and self.completed%2==1:
                target=proposals[0]['layers']
                target_aux=[layer['method'] for layer in target[1:]]
                eligible=[ident for ident,data in self.candidates.items() if len(data.get('ratings',[]))<3 and ident not in self.excluded and len(data['recipe']['layers'])==len(target) and [layer['method'] for layer in data['recipe']['layers'][1:]]==target_aux]
                if eligible:
                    anchor=max(eligible,key=lambda ident:(self._score(ident),-len(self.candidates[ident].get('ratings',[])),self.rng.random()))
            quarantine_start=len(self.quarantine);similarity_start=len(self.diversity_skips)
            need=1 if anchor else 2;queue=list(proposals)
            def render(recipe):
                try:return self.renderer(recipe)
                except Exception as exc:
                    with self.lock:
                        if token==self.epoch:self.quarantine.append({'recipe':recipe,'reason':str(exc)})
            while queue and attempts<8 and len(accepted)<need:
                if token!=self.epoch:return
                # Render the still-missing sounds of the pair at once; batch members have distinct families,
                # so accepting one never invalidates another (one foundation family per pair, as before).
                taken={self.candidates[ident]['recipe']['layers'][0]['method'] for ident in accepted+([anchor] if anchor else [])}
                queue=[recipe for recipe in queue if recipe['layers'][0]['method'] not in taken]
                batch=[]
                for recipe in queue:
                    if len(batch)==min(need-len(accepted),8-attempts):break
                    if recipe['layers'][0]['method'] not in {r['layers'][0]['method'] for r in batch}:batch.append(recipe)
                if not batch:break
                for recipe in batch:queue.remove(recipe)
                attempts+=len(batch)
                with ThreadPoolExecutor(len(batch)) as pool:clips=list(pool.map(render,batch))
                for recipe,clip in zip(batch,clips):
                    if clip is None:continue
                    with self.lock:
                        if token!=self.epoch:return
                        if clip['id'] in accepted or clip['id'] in self.excluded:continue
                        seen={i for row in self.history for i in row['pair']}
                        if clip['id'] in seen or clip['id'] in self.candidates:continue
                        # Compare audio independently of recipe distance, including recent trials.
                        recent=list(dict.fromkeys(i for row in self.history[-2:] for i in row['pair']))
                        references=accepted+recent+([anchor] if anchor else [])
                        distances=[]
                        for ident in references:
                            other=self.candidates[ident]
                            if clip.get('audio_descriptor') and other.get('audio_descriptor'):
                                a=np.sqrt(np.maximum(clip['audio_descriptor'],0));b=np.sqrt(np.maximum(other['audio_descriptor'],0))
                                distances.append(float(np.linalg.norm(a-b)/math.sqrt(2)))
                        if distances and min(distances)<MIN_AUDIO_DISTANCE:
                            self.diversity_skips.append({'id':clip['id'],'recipe':recipe,'distance':min(distances),'reason':'Too similar to current or recent audio'})
                            continue
                        self.candidates[clip['id']]=clip;accepted.append(clip['id'])
            with self.lock:
                if token!=self.epoch:return
                self.busy=False
                if len(accepted)<(1 if anchor else 2):
                    failures=self.quarantine[quarantine_start:]
                    similar=len(self.diversity_skips)-similarity_start
                    self.error=f'Could not prepare a distinct checked pair: {len(accepted)} ready, {similar} too similar, {len(failures)} rendering/check failures. '
                    if failures:self.error+='Last failure: '+failures[-1]['reason'][:300]+'. '
                    self.error+='Retry tries fresh replacements; no checks are bypassed.'
                    return
                if anchor:
                    other=accepted[0]
                    if self.candidates[anchor]['recipe']['layers'][0]['method']!=self.candidates[other]['recipe']['layers'][0]['method']:
                        accepted.append(anchor)
                if len(accepted)<2:
                    self.busy=False;self.error='Could not prepare a distinct checked pair with a returning sound. Retry preparation.';return
                self.rng.shuffle(accepted);self.pair=accepted;self.tried=set();self.selected=None
                protected=set(self.favourites+self.pair)
            if isinstance(self.renderer,SourceRenderer):
                with self.lock:trim_cache(set(self.favourites+self.pair))
        self.executor.submit(work)
    def heard(self,ident,context=None):
        with self.lock:
            if ident not in self.candidates:raise ValueError('Unknown source candidate')
            self.selected=ident
            if context is not None and not isinstance(context,dict):raise ValueError('Invalid audition context')
            if context and context.get('candidateId',ident)!=ident:raise ValueError('Audition source does not match candidate')
            if context and context.get('volume',1)<=.001:raise ValueError('Listening volume is muted')
            condition=tuple((context or {}).get(key) for key in ['input','style','response','volume','spatial'])
            if self.hearing_context!=condition:self.tried.clear();self.hearing_context=condition
            self.auditions.append({'id':ident,'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
            if ident in self.pair:self.tried.add(ident)
    def _score(self,ident):
        ratings=self.candidates[ident].get('ratings',[])
        return (sum(ratings)+RATING_PRIOR*RATING_PRIOR_WEIGHT)/(len(ratings)+RATING_PRIOR_WEIGHT)
    def _rank_finalists(self):
        heard={ident for row in self.history for ident in row['pair']}
        # Ties break by a seeded shuffle, so the same session always gets the same finalists (sets iterate in arbitrary order).
        ids=sorted(heard);random.Random(getattr(self,'seed',0)).shuffle(ids);position={ident:n for n,ident in enumerate(ids)}
        ranked=sorted(heard,key=lambda ident:(self._score(ident),len(self.candidates[ident].get('ratings',[])),-position[ident]),reverse=True)
        self.finalists=[]
        for ident in ranked:
            candidate=self.candidates[ident]
            distinct=True
            for selected in self.finalists:
                other=self.candidates[selected]
                if candidate.get('audio_descriptor') and other.get('audio_descriptor'):
                    a=np.sqrt(np.maximum(candidate['audio_descriptor'],0));b=np.sqrt(np.maximum(other['audio_descriptor'],0))
                    if float(np.linalg.norm(a-b)/math.sqrt(2))<MIN_AUDIO_DISTANCE:distinct=False;break
            if distinct:self.finalists.append(ident)
            if len(self.finalists)==FINALIST_COUNT:break
        # Always fill all finalist slots if renderer omitted descriptors in local test/offline results.
        for ident in ranked:
            if ident not in self.finalists:self.finalists.append(ident)
            if len(self.finalists)==FINALIST_COUNT:break
    def _start_playoff(self):
        self.playoff_queue=[list(pair) for pair in combinations(self.finalists,2)];self.rng.shuffle(self.playoff_queue)
        for pair in self.playoff_queue:self.rng.shuffle(pair)
        self._next_playoff()
    def _next_playoff(self):
        self.busy=False;self.tried.clear();self.selected=None
        if self.playoff_queue:self.stage='playoff';self.pair=self.playoff_queue.pop(0)
        else:self.stage='done';self.active=False;self.pair=[]
    def _bt_order(self):
        """Bradley-Terry strengths for finalists from playoff choices (MM, Hunter 2004).
        Each finalist also plays one virtual game vs a fixed-strength neutral item, won in
        proportion to its shrunk 1-7 rating: a weak prior that breaks ties and covers skipped pairs."""
        # ponytail: fixed 200 MM iterations, no confidence intervals; use choix if CIs needed.
        items=self.finalists;n=len(items)
        if not n:return []
        index={ident:i for i,ident in enumerate(items)}
        wins=np.zeros((n,n))
        for row in self.playoff_history:
            a,b=index[row['pair'][0]],index[row['pair'][1]]
            share={'A':1.,'B':0.,'equal':.5}[row['choice']]
            wins[a,b]+=share;wins[b,a]+=1-share
        prior=np.array([(self._score(ident)-1)/6 for ident in items])
        games=wins+wins.T;total_wins=wins.sum(1)+prior;strength=np.ones(n)
        for _ in range(200):
            denominator=(games/(strength[:,None]+strength[None,:])).sum(1)+1/(strength+1)
            strength=total_wins/denominator
        order=sorted(range(n),key=lambda i:(strength[i],prior[i]),reverse=True)
        return [(items[i],float(strength[i])) for i in order]
    def _finalist_summary(self,ident,strength):
        rows=[row for row in self.playoff_history if ident in row['pair']]
        wins=sum(1. if row['winner']==ident else .5 if row['winner'] is None else 0. for row in rows)
        return {'strength':strength,'wins':wins,'games':len(rows),'score':self._score(ident),'ratingCount':len(self.candidates[ident].get('ratings',[]))}
    def playoff_feedback(self,choice,context=None):
        with self.lock:
            if not self.active or self.stage!='playoff' or len(self.pair)!=2:raise ValueError('No final-round pair')
            if choice not in ('A','B','equal'):raise ValueError('Choose Prefer A, Like both equally, or Prefer B')
            if not isinstance(context,(dict,type(None))):raise ValueError('Invalid audition context')
            pair=self.pair.copy();winner={'A':pair[0],'B':pair[1]}.get(choice)
            self.playoff_history.append({'pair':pair,'choice':choice,'winner':winner,'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
            self._next_playoff()
    def feedback(self,ratings,context=None):
        with self.lock:
            if not self.active or self.busy or self.stage!='discovery' or len(self.pair)!=2:raise ValueError('No ready candidate pair')
            if not isinstance(ratings,dict) or set(ratings)!={'A','B'} or any(type(value) is not int or not 1<=value<=7 for value in ratings.values()):raise ValueError('Rate both sounds from 1 to 7')
            if not isinstance(context,(dict,type(None))):raise ValueError('Invalid audition context')
            if context and (context.get('input') not in ('live','simulated') or context.get('style') not in ('steady','rise','evolving')):raise ValueError('Invalid audition context')
            pair=self.pair.copy()
            score_by_id={pair[0]:ratings['A'],pair[1]:ratings['B']}
            self.history.append({'pair':pair,'ratings':dict(ratings),'ratings_by_candidate':score_by_id,'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
            for ident,value in score_by_id.items():self.candidates[ident].setdefault('ratings',[]).append(value)
            self.completed+=1
            if self.completed>=MAX_COMPARISONS:
                self._rank_finalists();self._start_playoff()
                return
            self._prepare()
    def bookmark(self,ident,enabled,note=None):
        with self.lock:
            if ident not in self.candidates or type(enabled) is not bool:raise ValueError('Invalid favourite')
            if note is not None and (not isinstance(note,str) or len(note)>300):raise ValueError('Note must be at most 300 characters')
            if enabled and ident not in self.favourites:self.favourites.append(ident)
            if not enabled:self.favourites=[x for x in self.favourites if x!=ident]
            if note is not None:
                self.notes[ident]=note
    def finish(self,ident=None):
        with self.lock:
            if ident is not None and ident not in self.finalists:raise ValueError('Choose one of the ranked finalists')
            if self.active and self.stage=='discovery' and self.history:self._rank_finalists()
            self.active=False;self.pair=[];self.playoff_queue=[];self.stage='done' if self.finalists else self.stage;self.final=ident;self.epoch+=1;self.busy=False
            if hasattr(self.renderer,'cancel'):self.renderer.cancel()
    def export(self):
        with self.lock:return deepcopy({'format':'ev-source-discovery-v3','policy':POLICY,'seed':getattr(self,'seed',None),'history':self.history,'auditions':self.auditions,'favourites':self.favourites,'notes':self.notes,'final':self.final,'finalists':[dict(id=ident,**self._finalist_summary(ident,strength)) for ident,strength in self._bt_order()],'playoff_history':self.playoff_history,'preference_model':preference_summary(self.candidates),'candidates':self.candidates,'quarantine':self.quarantine,'diversity_skips':self.diversity_skips,'note':'14 rated pairs pick 4 diverse finalists by 1–7 rating shrunk toward neutral 4 (prior weight 2). A 6-pair round-robin final round orders them by Bradley-Terry strength; ratings enter only as one virtual game per finalist. Final choice stays explicit. Later candidate proposals use a regularized model of foundation family, layer mix, and layer count, with an exploration bonus. Explicit export only; no automatic participant record.'})
