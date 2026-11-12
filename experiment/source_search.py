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

def make_open_recipe(rng,layer_count=None):
    """Open pool: 1-3 'blocks' layers with every building block drawn at random; no family presets.
    Families are not inputs here; any label is derived afterward from the sound."""
    log=lambda a,b:math.exp(rng.uniform(math.log(a),math.log(b)))
    maybe=lambda p,value:value if rng.random()<p else 0.
    layers=[]
    for index,role in enumerate(['foundation','character','texture'][:layer_count or rng.choice((1,2,3))]):
        shape={'rootRatio':log(.4,2.),'slope':rng.uniform(.3,2.5),'evenGain':rng.uniform(0,1.5),'peakWidth':rng.uniform(.15,1.),'cutoff':log(400,8000),
               'inharm':maybe(.3,rng.uniform(0,.01)),'lope':maybe(.4,rng.uniform(0,1)),'drive':maybe(.4,rng.uniform(0,4)),
               'fmMix':maybe(.3,rng.uniform(0,.8)),'fmRatio':rng.uniform(.5,7),'fmIndex':rng.uniform(.2,2.5),
               'noiseMix':maybe(.3,rng.uniform(0,.8)),'noiseCenter':log(150,6000),'noiseWidth':log(50,2000),
               'amRate':maybe(.3,rng.uniform(0,40)),'amDepth':rng.uniform(0,.8),'companionSub':rng.choice((0.,1.))}
        for peak in ('peak1','peak2'):
            if rng.random()<.7:shape[peak+'Hz']=log(100,5000);shape[peak+'Gain']=rng.uniform(0,4)
        layers.append({'role':role,'method':'blocks','gain':1. if index==0 else rng.uniform(.1,.5 if index==1 else .25),'shape':shape,
                       'controls':{'body':rng.uniform(.2,.95),'character':rng.uniform(.1,.9),'ensemble':rng.uniform(.15,.9),'movement':rng.uniform(.2,.8)}})
    return {'version':1,'seed':rng.randrange(1,2**30),'layers':layers}

class SourceDiscovery:
    policy=POLICY
    distinct_families=True  # one foundation family per pair; off for the open pool (every layer is 'blocks')
    max_attempts=8  # renders tried per pair before giving up
    def __init__(self,renderer=None):
        self.renderer=renderer or SourceRenderer();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='source-discovery')
        self.lock=threading.RLock();self.epoch=0;self.active=False;self.busy=False;self.error='';self.candidates={};self.pair=[];self.history=[];self.tried=set();self.quarantine=[];self.final=None;self.rng=random.Random();self.completed=0;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[];self.origins={};self.check_parent=None;self.pair_mode='rating'
    def close(self):
        self.epoch+=1
        if hasattr(self.renderer,'close'):self.renderer.close()
        self.executor.shutdown(wait=False,cancel_futures=True)
    def snapshot(self):
        with self.lock:
            def public(ident):
                c=self.candidates[ident]
                return {k:c[k] for k in ['id','label','recipe','urls','traces'] if k in c}
            return {'active':self.active,'busy':self.busy,'error':self.error,'completed':self.completed,'pair':[public(x) for x in self.pair],'heard':list(self.tried),'selected':self.selected,'final':self.final,'finalists':[dict(public(x),**self._finalist_summary(x,strength)) for x,strength in self._bt_order()],'stage':self.stage,'step':self.completed+len(self.playoff_history),'totalSteps':TOTAL_STEPS,'playoffDone':len(self.playoff_history),'playoffTotal':PLAYOFF_PAIRS,'quarantined':len(self.quarantine),'policy':self.policy,'checkpoint':self.stage!='discovery','pairMode':self.pair_mode,'maxComparisons':MAX_COMPARISONS}
    def start(self):
        with self.lock:
            if self.busy:raise ValueError('Wait for source preparation to finish')
            self.epoch+=1;self.active=True;self.error='';self.candidates={};self.pair=[];self.history=[];self.tried=set();self.quarantine=[];self.completed=0;self.final=None;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[];self.origins={};self.check_parent=None;self.pair_mode='rating'
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
    def _origin_for(self,recipe):return self.origins.get(recipe['seed'])
    def _anchor(self,proposals):
        """A returning rated sound for this pair, or None. Family trial: every other pair after the opening."""
        anchor=None
        if self.completed>=3 and self.completed%2==1:
            target=proposals[0]['layers']
            target_aux=[layer['method'] for layer in target[1:]]
            eligible=[ident for ident,data in self.candidates.items() if len(data.get('ratings',[]))<3 and ident not in self.excluded and len(data['recipe']['layers'])==len(target) and [layer['method'] for layer in data['recipe']['layers'][1:]]==target_aux]
            if eligible:
                anchor=max(eligible,key=lambda ident:(self._score(ident),-len(self.candidates[ident].get('ratings',[])),self.rng.random()))
        return anchor
    def _prepare(self):
        self.busy=True;self.error='';self.pair=[];self.tried.clear();self.selected=None;token=self.epoch
        proposals=self._proposals()
        def work():
            accepted=[];attempts=0
            anchor=self._anchor(proposals)
            quarantine_start=len(self.quarantine);similarity_start=len(self.diversity_skips)
            need=1 if anchor else 2;queue=list(proposals)
            def render(recipe):
                try:return self.renderer(recipe)
                except Exception as exc:
                    with self.lock:
                        if token==self.epoch:self.quarantine.append({'recipe':recipe,'reason':str(exc)})
            while queue and attempts<self.max_attempts and len(accepted)<need:
                if token!=self.epoch:return
                # Render the still-missing sounds of the pair at once; batch members have distinct families,
                # so accepting one never invalidates another (one foundation family per pair, as before).
                batch=[]
                if self.distinct_families:
                    taken={self.candidates[ident]['recipe']['layers'][0]['method'] for ident in accepted+([anchor] if anchor else [])}
                    queue=[recipe for recipe in queue if recipe['layers'][0]['method'] not in taken]
                for recipe in queue:
                    if len(batch)==min(need-len(accepted),self.max_attempts-attempts):break
                    if not self.distinct_families or recipe['layers'][0]['method'] not in {r['layers'][0]['method'] for r in batch}:batch.append(recipe)
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
                        # A tuned sound must also differ audibly from its parent, except for groups that change the sound over time
                        # (roughness, movement): this spectrum descriptor cannot see those, so they keep the full step instead.
                        origin=self._origin_for(recipe) or {};parent=origin.get('parent')
                        if parent:references=[i for i in references if i!=parent]+([] if origin.get('group') in TIME_GROUPS else [parent])
                        distances=[]
                        for ident in references:
                            other=self.candidates[ident]
                            if clip.get('audio_descriptor') and other.get('audio_descriptor'):
                                a=np.sqrt(np.maximum(clip['audio_descriptor'],0));b=np.sqrt(np.maximum(other['audio_descriptor'],0))
                                distances.append(float(np.linalg.norm(a-b)/math.sqrt(2)))
                        # Never two tunings of the same sound side by side: compare a tuning with its parent (parent check) or another sound.
                        if parent and any(self.candidates[i].get('origin',{}).get('parent')==parent for i in accepted):
                            self.diversity_skips.append({'id':clip['id'],'recipe':recipe,'distance':None,'reason':'Second tuning of the same sound in one pair'})
                            continue
                        if distances and min(distances)<MIN_AUDIO_DISTANCE:
                            self.diversity_skips.append({'id':clip['id'],'recipe':recipe,'distance':min(distances),'reason':'Too similar to current or recent audio'})
                            continue
                        if self._origin_for(recipe):clip['origin']=self._origin_for(recipe)
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
                    if not self.distinct_families or self.candidates[anchor]['recipe']['layers'][0]['method']!=self.candidates[other]['recipe']['layers'][0]['method']:
                        accepted.append(anchor)
                if len(accepted)<2:
                    self.busy=False;self.error='Could not prepare a distinct checked pair with a returning sound. Retry preparation.';return
                self.rng.shuffle(accepted);self.pair=accepted;self.tried=set();self.selected=None
                self.pair_mode='choice' if getattr(self,'always_choice',False) or (anchor and getattr(self,'parent_check_mode','rating')=='choice') else 'rating'
            if isinstance(self.renderer,SourceRenderer):
                with self.lock:trim_cache(set(self.candidates))  # keep this session's sounds so finalists can replay
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
    def feedback(self,ratings=None,context=None,choice=None):
        with self.lock:
            if not self.active or self.busy or self.stage!='discovery' or len(self.pair)!=2:raise ValueError('No ready candidate pair')
            if self.pair_mode=='choice':return self._choice_feedback(choice,context)
            if not isinstance(ratings,dict) or set(ratings)!={'A','B'} or any(type(value) is not int or not 1<=value<=7 for value in ratings.values()):raise ValueError('Rate both sounds from 1 to 7')
            if not isinstance(context,(dict,type(None))):raise ValueError('Invalid audition context')
            if context and (context.get('input') not in ('live','simulated') or context.get('style') not in ('steady','rise','evolving')):raise ValueError('Invalid audition context')
            pair=self.pair.copy()
            score_by_id={pair[0]:ratings['A'],pair[1]:ratings['B']}
            self.history.append({'pair':pair,'rating_source':'rating-1-7','ratings':dict(ratings),'ratings_by_candidate':score_by_id,'origin_by_candidate':self._origin_text(pair),'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
            for ident,value in score_by_id.items():self.candidates[ident].setdefault('ratings',[]).append(value)
            self._after_pair()
    def _origin_text(self,pair):
        return {i:(f'Returning sound {i[:6]}, rated before {self.candidates[i]["ratings"]} (parent check)' if self.candidates[i].get('ratings') else self.candidates[i].get('origin',{}).get('summary','')) for i in pair}
    def _choice_feedback(self,choice,context):
        """Parent-check pair answered as a direct choice. The parent keeps its ratings; the tuned sound gets an inferred
        rating of the parent's mean +1 / 0 / -1 so the GP and finalist scores can use it (marked as inferred in the trace)."""
        if choice not in ('A','B','equal'):raise ValueError('Choose Prefer A, Like both equally, or Prefer B')
        if not isinstance(context,(dict,type(None))):raise ValueError('Invalid audition context')
        if context and (context.get('input') not in ('live','simulated') or context.get('style') not in ('steady','rise','evolving')):raise ValueError('Invalid audition context')
        pair=self.pair.copy();winner={'A':pair[0],'B':pair[1]}.get(choice)
        parent=next(i for i in pair if self.candidates[i].get('ratings'));child=next(i for i in pair if i!=parent)
        base=sum(self.candidates[parent]['ratings'])/len(self.candidates[parent]['ratings'])
        inferred=min(7.,max(1.,base+(0 if winner is None else 1 if winner==child else -1)))
        self.history.append({'pair':pair,'rating_source':'choice','choice':choice,'winner':winner,'ratings_by_candidate':{child:inferred},'inferred_rating':{child:inferred},
                             'origin_by_candidate':self._origin_text(pair),'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
        self.candidates[child].setdefault('ratings',[]).append(inferred)
        self._after_pair()
    def _after_pair(self):
        self.completed+=1
        if self.completed>=MAX_COMPARISONS:
            self._rank_finalists();self._start_playoff()
            return
        self._prepare()
    def finish(self,ident=None):
        with self.lock:
            if ident is not None and ident not in self.finalists:raise ValueError('Choose one of the ranked finalists')
            if self.active and self.stage=='discovery' and self.history:self._rank_finalists()
            self.active=False;self.pair=[];self.playoff_queue=[];self.stage='done' if self.finalists else self.stage;self.final=ident;self.epoch+=1;self.busy=False
            if hasattr(self.renderer,'cancel'):self.renderer.cancel()
    def export(self):
        with self.lock:return deepcopy({'format':'ev-source-discovery-v3','policy':self.policy,'seed':getattr(self,'seed',None),'history':self.history,'auditions':self.auditions,'final':self.final,'finalists':[dict(id=ident,**self._finalist_summary(ident,strength)) for ident,strength in self._bt_order()],'playoff_history':self.playoff_history,'preference_model':preference_summary(self.candidates),'candidates':self.candidates,'quarantine':self.quarantine,'diversity_skips':self.diversity_skips,'note':'14 rated pairs pick 4 diverse finalists by 1–7 rating shrunk toward neutral 4 (prior weight 2). A 6-pair round-robin final round orders them by Bradley-Terry strength; ratings enter only as one virtual game per finalist. Final choice stays explicit. Later candidate proposals use a regularized model of foundation family, layer mix, and layer count, with an exploration bonus. Explicit export only; no automatic participant record.'})


# Open pool search: no families. Parameters are scaled to [0, 1] (log scale for frequencies) so mutation and the GP treat them alike.
OPEN_POLICY='source-open-groups-gp-v4'
OPEN_KEYS=(('rootRatio',.4,2.,1),('slope',.3,2.5,0),('evenGain',0,1.5,0),('peakWidth',.15,1.,0),('cutoff',400,8000,1),('inharm',0,.01,0),('lope',0,1,0),('drive',0,4,0),
           ('fmMix',0,.8,0),('fmRatio',.5,7,0),('fmIndex',.2,2.5,0),('noiseMix',0,.8,0),('noiseCenter',150,6000,1),('noiseWidth',50,2000,1),('amRate',0,40,0),('amDepth',0,.8,0),
           ('peak1Hz',100,5000,1),('peak1Gain',0,4,0),('peak2Hz',100,5000,1),('peak2Gain',0,4,0))
OPEN_SWITCHES=('inharm','lope','drive','fmMix','noiseMix','amRate')  # blocks a mutation may switch on or off
OPEN_EXPLORATION=1.0

def _unit(key,value,lo,hi,log):return (math.log(value/lo)/math.log(hi/lo)) if log else (value-lo)/(hi-lo)
def _from_unit(key,u,lo,hi,log):return lo*(hi/lo)**u if log else lo+u*(hi-lo)

def open_vector(recipe):
    """Foundation layer parameters and ensemble/movement in [0, 1] plus layer count and support-layer gain; absent peaks count as zero gain."""
    shape=recipe['layers'][0]['shape']
    values=[_unit(k,shape.get(k,lo if k.endswith('Gain') else (lo*hi)**.5 if log else (lo+hi)/2),lo,hi,log) for k,lo,hi,log in OPEN_KEYS]
    controls=recipe['layers'][0]['controls']
    return np.array([*values,controls['ensemble'],controls['movement'],(len(recipe['layers'])-1)/2,sum(layer['gain'] for layer in recipe['layers'][1:])])

# Sound groups: a tuned sound moves ONE perceptual group by a clearly audible step and leaves the rest alone.
# Every OPEN_KEYS parameter belongs to a group, so nothing is out of reach; random newcomers still cover the whole space.
# Names follow listener timbre dimensions (mass/depth, luminance/brightness, texture/roughness; Zacharakis et al. 2014).
SOUND_GROUPS={
    'deep':(('rootRatio',-1),('peak1Hz',-1),('evenGain',1)),
    'bright':(('cutoff',1),('slope',-1),('peak2Hz',1),('peak2Gain',1)),
    'resonant':(('peak1Gain',1),('peakWidth',-1)),
    'rough':(('drive',1),('amDepth',1),('amRate',1)),
    'metallic':(('fmMix',1),('fmIndex',1),('fmRatio',1),('inharm',1)),
    'airy':(('noiseMix',1),('noiseWidth',1),('noiseCenter',1)),
    'moving':(('lope',1),('ensemble',1),('movement',1)),
}
GROUP_STEP=.3  # fraction of each parameter's range; big enough to hear. ponytail: fixed step, shrink when a direction is settled if sessions overshoot
_BOUNDS={k:(lo,hi,log) for k,lo,hi,log in OPEN_KEYS}|{'ensemble':(0,1,0),'movement':(0,1,0)}

def move_group(rng,recipe,group,direction,step=GROUP_STEP):
    """Copy of recipe with one sound group pushed more (+1) or less (-1) on every layer; returns (child, changes)."""
    switches=[key for key,_ in SOUND_GROUPS[group] if key in OPEN_SWITCHES]
    if direction<0 and switches and not any(recipe['layers'][0]['shape'].get(key) for key in switches):return recipe,{}  # "less" of a feature that is off: inaudible
    child=deepcopy(recipe);child['seed']=rng.randrange(1,2**30);changes={}
    for index,layer in enumerate(child['layers']):
        for key,sign in SOUND_GROUPS[group]:
            lo,hi,log=_BOUNDS[key];where=layer['controls'] if key in ('ensemble','movement') else layer['shape']
            if key.startswith('peak') and key not in where:  # absent peak = zero gain at the middle frequency, as in open_vector
                where[key[:5]+'Hz']=(100*5000)**.5;where[key[:5]+'Gain']=0.
            old=where[key];new=_from_unit(key,min(1.,max(0.,_unit(key,old,lo,hi,log)+sign*direction*step)),lo,hi,log)
            if abs(new-old)>1e-9:where[key]=new;changes[f'L{index}.{key}']=[round(old,4),round(new,4)]
    return child,changes

def open_model(candidates,queries,length=.9,noise=.6):
    """GP regression on ratings (centred at 4, scaled /3) over open_vector; returns mean and std for queries."""
    # ponytail: fixed RBF length/noise, no hyperparameter fitting; tune against the benchmark once a library exists.
    rows=[(open_vector(c['recipe']),r) for c in candidates.values() for r in c.get('ratings',[]) if c['recipe']['layers'][0]['method']=='blocks']
    q=np.stack([open_vector(r) for r in queries])
    if not rows:return np.zeros(len(q)),np.ones(len(q))
    x=np.stack([v for v,_ in rows]);y=np.array([(r-RATING_PRIOR)/3 for _,r in rows])
    k=lambda a,b:np.exp(-.5*((a[:,None,:]-b[None,:,:])**2).sum(2)/length**2)
    K=k(x,x)+noise**2*np.eye(len(x));Ks=k(q,x);L=np.linalg.cholesky(K)
    alpha=np.linalg.solve(L.T,np.linalg.solve(L,y));v=np.linalg.solve(L,Ks.T)
    return Ks@alpha,np.sqrt(np.maximum(1-(v*v).sum(0),1e-9))

GROUP_PRIOR=2  # virtual zero-change tunings per group/direction; one noisy rating cannot swing the trend

def group_trends(candidates):
    """Per group and direction ('deep+', 'rough-'): mean of (tuned sound's rating - its parent's mean rating), shrunk toward 0.
    Carries a lesson such as 'deeper helps' over to other parents, which the distance-based GP cannot do."""
    deltas={}
    for c in candidates.values():
        origin=c.get('origin',{})
        if origin.get('kind')!='tuned' or not c.get('ratings') or not candidates.get(origin['parent'],{}).get('ratings'):continue
        parent=candidates[origin['parent']]['ratings']
        key=origin['group']+('+' if origin['direction']=='more' else '-')
        deltas.setdefault(key,[]).append(sum(c['ratings'])/len(c['ratings'])-sum(parent)/len(parent))
    return {key:{'trend':round(sum(v)/(len(v)+GROUP_PRIOR),3),'count':len(v)} for key,v in sorted(deltas.items())}

MIN_GROUP_STEP=.2  # smallest step; 0.1-0.15 steps sounded like copies in the 2026-11-10 20:33 session
TIME_GROUPS=('rough','moving')  # change the sound over time; the spectrum gate cannot hear them, so they always use GROUP_STEP
PARENT_CHECK_MODE='choice'  # parent-check pairs ask Prefer A / Like both equally / Prefer B; 'rating' = legacy 1-7 sliders

def tuning_record(candidates,history):
    """Replays the session: each tuned sound vs its parent (same-pair rating when the parent was re-rated alongside it,
    otherwise the parent's mean rating so far). Loss halves that parent's step (1/5 success rule idea, Rechenberg);
    a loss at the smallest step marks the parent as settled. Returns steps, settled parents and win/tie/loss counts."""
    steps,settled,counts,given={},set(),{'win':0,'tie':0,'loss':0},{}
    for row in history:
        scores=row['ratings_by_candidate'];halved=set()
        for ident in row['pair']:
            origin=candidates[ident].get('origin',{})
            if origin.get('kind')!='tuned':continue
            parent=origin['parent']
            if row.get('choice') and parent in row['pair']:result={'equal':'tie',None:'tie'}.get(row['choice']) or ('win' if row['winner']==ident else 'loss')
            else:
                if ident not in scores:continue
                reference=scores[parent] if parent in scores else (sum(given[parent])/len(given[parent]) if given.get(parent) else None)
                if reference is None:continue
                result='win' if scores[ident]>reference else 'tie' if scores[ident]==reference else 'loss'
            counts[result]+=1
            if result=='loss' and parent not in halved:  # at most one halving per pair, so two losing siblings do not skip a level
                halved.add(parent)
                if steps.get(parent,GROUP_STEP)<=MIN_GROUP_STEP+1e-9:settled.add(parent)
                steps[parent]=max(MIN_GROUP_STEP,steps.get(parent,GROUP_STEP)/2)
        for ident,value in scores.items():given.setdefault(ident,[]).append(value)
    return steps,settled,counts

class OpenDiscovery(SourceDiscovery):
    """Open-pool search. Opening: random open recipes. Then each pair = one exploit (one sound group of a best-rated
    sound moved, highest GP upper bound) + one explore (the random newcomer the GP is least sure of),
    so sessions can move away from where they started and never lose coverage."""
    policy=OPEN_POLICY
    distinct_families=False
    parent_check_mode=PARENT_CHECK_MODE
    def _proposals(self):
        rated=[ident for ident,c in self.candidates.items() if c.get('ratings')]
        immigrants=[make_open_recipe(self.rng) for _ in range(8)]
        for recipe in immigrants:self.origins[recipe['seed']]={'kind':'new','summary':'New random sound (not tuned from another)'}
        self.check_parent=None
        if self.completed<3 or not rated:return immigrants
        parents=sorted(rated,key=lambda ident:(self._score(ident),self.rng.random()),reverse=True)[:3]
        steps,settled,_=tuning_record(self.candidates,self.history)
        # Parent check (pairs 5, 8, 11, 14): the current best sound returns next to one tuning of itself, so the comparison is
        # direct and a lucky first rating gets re-checked. Skipped once that sound is settled (lost even at the smallest step).
        self.check_parent=parents[0] if (self.completed-3)%3==1 and parents[0] not in settled and len(self.candidates[parents[0]]['ratings'])<3 else None
        if self.check_parent:parents=[self.check_parent]
        children=[]
        for parent in parents:
            for group in SOUND_GROUPS:
                step=GROUP_STEP if group in TIME_GROUPS else steps.get(parent,GROUP_STEP)
                for direction in (1,-1):
                    child,changes=move_group(self.rng,self.candidates[parent]['recipe'],group,direction,step)
                    if not changes:continue  # already at the limit in that direction
                    word='more' if direction>0 else 'less';score=self._score(parent)
                    self.origins[child['seed']]={'kind':'tuned','parent':parent,'parent_score':round(score,2),'group':group,'direction':word,'step':step,'changes':changes,
                                                 'summary':f'Tuned from {parent[:6]} (score {score:.1f}): {word} {group}, step {step:.0%}, {len(changes)} parameters changed'+(' (shown next to its parent)' if self.check_parent else '')}
                    children.append(child)
        mean,std=open_model(self.candidates,children+immigrants)
        ucb=mean+OPEN_EXPLORATION*std
        trends=group_trends(self.candidates)  # rating points; GP works in (rating-4)/3
        for i,child in enumerate(children):
            origin=self.origins[child['seed']];ucb[i]+=trends.get(origin['group']+('+' if origin['direction']=='more' else '-'),{}).get('trend',0)/3
        exploit=sorted(range(len(children)),key=lambda i:ucb[i],reverse=True)
        explore=sorted(range(len(immigrants)),key=lambda i:std[len(children)+i],reverse=True)
        # _prepare renders the first two, then falls back down the list on render/check failures or near-duplicates.
        # Alternating keeps the pair mixed: a failed tuning is usually replaced by the next-best tuning, a failed newcomer by
        # the next item (rarely two tunings side by side, which is still a fair comparison).
        exploit=[children[i] for i in exploit];explore=[immigrants[i] for i in explore]
        if self.check_parent:return exploit+explore  # parent fills one slot; newcomers only if every tuning fails
        return [x for pair in zip(exploit,explore) for x in pair]+exploit[len(explore):]
    def _anchor(self,proposals):
        return getattr(self,'check_parent',None) if self.completed>=3 else None
    def export(self):
        data=super().export()
        data['note']='Open pool (generic building blocks, no families). 14 rated pairs: 3 opening pairs of random sounds, then each pair = one tuned sound (one sound group of a best-rated sound moved, chosen by a GP upper bound plus group trends) + one random newcomer chosen for GP uncertainty; pairs 5, 8, 11, 14 instead show the best sound next to a tuning of itself, answered as a direct choice (rating_source choice; the tuned sound gets an inferred rating of parent mean +1/0/-1). The step starts at 0.3 and halves at most once per pair after a loss (min 0.2); rough and moving keep 0.3. Every tuning except rough/moving must pass the 0.10 audio gate against its parent. Each candidate origin says how it was made. 4 diverse finalists, 6-pair Bradley-Terry final round; final choice stays explicit. Explicit export only.'
        data['preference_model']={'version':'open-gp-groups-1','training_ratings':sum(len(c.get('ratings',[])) for c in self.candidates.values()),
                                  'group_trends':group_trends(self.candidates),
                                  'group_trends_note':'Mean rating change of a tuned sound vs its parent, per group and direction, shrunk toward 0 (prior weight 2). Positive = the listener liked that change.'}
        steps,settled,counts=tuning_record(self.candidates,self.history)
        best=max((v for row in self.history for v in row['ratings_by_candidate'].values()),default=None)
        data['session_metrics']={'tuned_vs_parent':counts,'best_rating':best,
                                 'best_rating_first_pair':next((n for n,row in enumerate(self.history,1) if best in row['ratings_by_candidate'].values()),None),
                                 'parent_steps':steps,'settled_parents':sorted(settled),
                                 'note':'tuned_vs_parent: tuned sound rating vs its parent (same pair when shown together, else parent mean so far). Steps halve at most once per pair after a loss (min 0.2).'}
        return data


# Base-style exploration (docs/system/interactive_algorithm.md, "Planned direction"). Stage 1: opening over the seven
# base styles, a direct choice on every pair, exploration by tuned versions only, Bradley-Terry ranking, final round.
STYLE_POLICY='source-style-explore-v1'
STYLES={'bowed':'Strings','rounded':'Pure tone','vocal':'Choir','glass':'Glass','airy':'Cluster','evolution':'Electric','supersonic':'Jet'}
# Opening: six styles in contrasting pairs, then the seventh against the style preferred so far (re-checks the leader).
# ponytail: fixed contrast pairs and a fixed seventh style; pick them from measured distances if the style set changes often.
OPENING_PAIRS=(('bowed','vocal'),('airy','supersonic'),('rounded','evolution'))
OPENING_SEVENTH='glass'
OPENING_STEPS=len(OPENING_PAIRS)+1
# Stage-1 tuning moves use settings every style has (pitch and the four source controls); per-style groups come in stage 2.
STYLE_GROUPS={'deep':(('rootRatio',-1),('body',1)),'bright':(('character',1),),'full':(('ensemble',1),),'moving':(('movement',1),)}
STYLE_RANGES={'rootRatio':(.5,1.8),'body':(0,1),'character':(0,1),'ensemble':(0,1),'movement':(0,1)}
PITCH_STEP=1.26  # pitch moves are musical: x or / 1.26 (about 4 semitones) per full step, so 'deeper again' keeps working
STILL_STYLES=('evolution','supersonic')  # these ignore the four source controls (measured distance 0.00); pitch moves only until stage 2
STYLE_STEP=.5  # fraction of the range; 0.3 moved bright/full/moving only 0.03-0.09 in audio distance (gate is 0.10)
def style_moves(style):
    """(group, direction, step) moves that audibly change this style."""
    if style in STILL_STYLES:return [('deep',d,s) for s in (STYLE_STEP,.3) for d in (1,-1)]
    return [(g,d,STYLE_STEP) for g in STYLE_GROUPS for d in (1,-1)]
DEFAULT_CONTROLS={'body':.7,'character':.5,'ensemble':.65,'movement':.5}  # = RECIPE_DEFAULT_CONTROLS in sourceRecipe.ts
STYLE_PAIRS=TOTAL_STEPS  # all 20 steps explore; no final round (it only confirmed the discovery ranking, 2026-11-11 session)
SHORTLIST=5  # ranked sounds offered at the end: top 3 shown, #4-5 behind "Show more"
SHORTLIST_MIN_GAMES=2  # a sound needs this many choices to be ranked (one opening win is not enough evidence)
DIRECTION_PRIOR=2  # virtual zero-effect results per move: one choice cannot decide a direction
MOMENTUM=1.  # bonus for repeating the move that just improved the sound
UNTRIED=.3  # bonus for a move not yet tried on this sound

def style_recipe(style):
    """The style exactly as Sound Lab plays it (seed 0 = no phase offset, default controls)."""
    return {'version':1,'seed':0,'layers':[{'role':'foundation','method':style,'gain':1.,'shape':{}}]}

def tune_style(rng,recipe,group,direction,step=STYLE_STEP):
    """Copy of a single-layer style recipe with one group moved by step x range; returns (child, changes) or (recipe, {})."""
    child=deepcopy(recipe);child['seed']=rng.randrange(1,2**30);layer=child['layers'][0]
    controls=layer.setdefault('controls',dict(DEFAULT_CONTROLS));shape=layer['shape'];changes={}
    for key,sign in STYLE_GROUPS[group]:
        lo,hi=STYLE_RANGES[key];where=shape if key=='rootRatio' else controls
        old=where.get(key,1. if key=='rootRatio' else DEFAULT_CONTROLS[key])
        moved=old*PITCH_STEP**(sign*direction*step/STYLE_STEP) if key=='rootRatio' else old+sign*direction*step*(hi-lo)
        new=min(hi,max(lo,moved))
        if abs(new-old)>1e-9:where[key]=round(new,4);changes[key]=[round(old,4),round(new,4)]
    return (child,changes) if changes else (recipe,{})

def bt_strengths(items,rows):
    """Bradley-Terry strengths (MM, Hunter 2004) from choice rows; equal = half a win each. Every item also plays one
    virtual even game against a neutral item of strength 1, so unplayed or unbeaten items stay finite."""
    index={ident:i for i,ident in enumerate(items)};n=len(items)
    if not n:return {}
    wins=np.zeros((n,n))
    for row in rows:
        a,b=row['pair']
        if a not in index or b not in index:continue
        share={'A':1.,'B':0.,'equal':.5}[row['choice']]
        wins[index[a],index[b]]+=share;wins[index[b],index[a]]+=1-share
    games=wins+wins.T;total=wins.sum(1)+.5;strength=np.ones(n)
    for _ in range(200):strength=total/((games/(strength[:,None]+strength[None,:])).sum(1)+1/(strength+1))
    return {ident:float(strength[index[ident]]) for ident in items}

FEATURE_L2=1.  # ridge strength of the preference model: with few choices, effects stay small until evidence builds up
SETTLE_WINS=2  # a sound that beats its own tunings this many times in a row is left alone for a while

def lineage(candidates,ident):
    """(style, {group: net steps}) of a sound: walks its tuning chain back to the base style; 'more' = +1, 'less' = -1."""
    steps={g:0 for g in STYLE_GROUPS};origin=candidates[ident].get('origin',{})
    while origin.get('kind')=='tuned':
        steps[origin['group']]+=1 if origin['direction']=='more' else -1
        origin=candidates.get(origin['parent'],{}).get('origin',{})
    return candidates[ident]['recipe']['layers'][0]['method'],steps

def style_features(candidates,ident):
    """Style (one-hot over the seven styles) and net group steps: what the sound is made of."""
    style,steps=lineage(candidates,ident)
    return np.array([1. if style==s else 0. for s in STYLES]+[float(steps[g]) for g in STYLE_GROUPS])

def fit_preference(diffs,targets,l2=FEATURE_L2):
    """Bradley-Terry over features (logistic regression on feature differences, ridge l2), fitted by Newton steps.
    targets: 1 = first sound chosen, 0 = second, 0.5 = liked equally."""
    X=np.array(diffs,dtype=float);y=np.array(targets,dtype=float);w=np.zeros(X.shape[1])
    if not len(X):return w
    for _ in range(25):
        p=1/(1+np.exp(-X@w));g=X.T@(p-y)+l2*w;H=(X*(p*(1-p))[:,None]).T@X+l2*np.eye(len(w))
        w-=np.linalg.solve(H,g)
    return w

class StyleDiscovery(SourceDiscovery):
    """Seven base styles, direct choices, tuned versions around the listener's lean, Bradley-Terry ranking."""
    policy=STYLE_POLICY
    distinct_families=False
    always_choice=True
    max_attempts=20  # after several steps in one direction many tunings resemble recent sounds; try more before giving up
    def _origin_for(self,recipe):return self.origins.get((recipe['seed'],recipe['layers'][0]['method']))
    def _note(self,recipe,origin):self.origins[(recipe['seed'],recipe['layers'][0]['method'])]=origin
    def _choices(self):return [row for row in self.history if row.get('rating_source')=='choice']
    def _strengths(self):
        heard=list(dict.fromkeys(i for row in self.history for i in row['pair']))
        return bt_strengths(heard,self._choices())
    def _weights(self):
        """Preference model: one Bradley-Terry over what sounds are made of (style + net group steps), fitted to every choice.
        A deeper Choir inherits all evidence about Choir and about 'deeper', instead of starting from zero as a new sound."""
        rows=self._choices()
        if getattr(self,'_cache',(None,))[0]!=len(rows):
            diffs=[style_features(self.candidates,r['pair'][0])-style_features(self.candidates,r['pair'][1]) for r in rows]
            self._cache=(len(rows),fit_preference(diffs,[{'A':1.,'B':0.,'equal':.5}[r['choice']] for r in rows]))
        return self._cache[1]
    def _utility(self,ident):return float(style_features(self.candidates,ident)@self._weights())
    def _score(self,ident):
        """1-7 scale for the shared finalist code: predicted win probability against a neutral sound."""
        return 1+6/(1+math.exp(-self._utility(ident)))
    def _ranked(self):
        heard=list(dict.fromkeys(i for row in self.history for i in row['pair']));strengths=self._strengths()
        return sorted(heard,key=lambda i:(round(self._utility(i),6),strengths.get(i,1.),self.rng.random()),reverse=True)
    def _settled(self,ident):
        """True if the sound beat its own tunings in its last SETTLE_WINS parent checks: stop re-testing it for now."""
        checks=[r for r in self._choices() if ident in r['pair'] and any(self.candidates[i].get('origin',{}).get('parent')==ident for i in r['pair'] if i!=ident)]
        return len(checks)>=SETTLE_WINS and all(r['winner']==ident for r in checks[-SETTLE_WINS:])
    def _proposals(self):
        self.check_parent=None
        if self.completed<len(OPENING_PAIRS):
            a,b=OPENING_PAIRS[self.completed]
            recipes=[style_recipe(a),style_recipe(b)]
            for r in recipes:self._note(r,{'kind':'style','style':r['layers'][0]['method'],'summary':f"Base style: {STYLES[r['layers'][0]['method']]}"})
            return recipes
        ranked=self._ranked()
        if self.completed==len(OPENING_PAIRS):
            self.check_parent=ranked[0]
            r=style_recipe(OPENING_SEVENTH);self._note(r,{'kind':'style','style':OPENING_SEVENTH,'summary':f'Base style: {STYLES[OPENING_SEVENTH]}'})
            return [r]
        # A sound that keeps beating its tunings is left alone; build on the next-ranked sound instead.
        open_ranked=[i for i in ranked if not self._settled(i)] or ranked
        best=open_ranked[0];best_style=self.candidates[best]['recipe']['layers'][0]['method']
        second=next((i for i in open_ranked[1:] if self.candidates[i]['recipe']['layers'][0]['method']!=best_style),open_ranked[1] if len(open_ranked)>1 else ranked[1])
        parent_check=(self.completed-OPENING_STEPS)%2==0
        if parent_check:self.check_parent=best
        # Fallback tail: tunings of the next-ranked sounds, so a pair can still form if every tuning of the best is a near-copy.
        others=[i for i in ranked if i not in (best,second)][:2]
        fallback=[x for parent in others for x in self._tunings(parent)]
        if parent_check:return self._tunings(best)+fallback
        a,b=self._tunings(best),self._tunings(second)
        return [x for pair in zip(a,b) for x in pair]+a[len(b):]+b[len(a):]+fallback
    def _tunings(self,parent):
        """Tuned versions of a sound, untried group/direction moves first, in random order."""
        recipe=self.candidates[parent]['recipe'];style=recipe['layers'][0]['method']
        # Direction learning: momentum (repeat the move that just improved this sound), then learned move scores, then a
        # small bonus for moves not yet tried on this sound; moves that keep losing go last.
        tried={(c['origin']['group'],c['origin']['direction']) for c in self.candidates.values() if c.get('origin',{}).get('parent')==parent}
        scores=self.direction_scores();origin=self.candidates[parent].get('origin',{})
        beat_parent=origin.get('kind')=='tuned' and any(row['winner']==parent and origin['parent'] in row['pair'] for row in self._choices())
        momentum=(origin['group'],origin['direction']) if beat_parent else None
        word=lambda d:'more' if d>0 else 'less'
        def value(move):
            key=(move[0],word(move[1]))
            return scores.get(key,(0.,0))[0]+(MOMENTUM if key==momentum else 0)+(UNTRIED if key not in tried else 0)+self.rng.random()*.01
        moves=sorted(style_moves(style),key=value,reverse=True)
        out=[]
        for group,direction,step in moves:
            child,changes=tune_style(self.rng,recipe,group,direction,step)
            if not changes:continue
            label=word(direction)
            key=(group,label);score,n=scores.get(key,(0.,0))
            reason='repeats the move that just improved it' if key==momentum else f'learned effect {score:+.2f} from {n} choice(s)' if n else 'not tried yet'
            self._note(child,{'kind':'tuned','parent':parent,'style':style,'group':group,'direction':label,'step':step,'changes':changes,'reason':reason,
                              'summary':f'{STYLES.get(style,style)} tuned from {parent[:6]}: {label} {group} ({reason})'})
            out.append(child)
        return out
    def _anchor(self,proposals):return getattr(self,'check_parent',None)
    def direction_scores(self):
        """Per move (group, direction): the preference model's learned effect of one step (from every choice, not only
        parent checks), and how many choices involved a sound with that group changed. Positive = the listener likes it."""
        w=self._weights()[len(STYLES):];rows=self._choices();out={}
        for k,group in enumerate(STYLE_GROUPS):
            n=sum(any(lineage(self.candidates,i)[1][group] for i in r['pair']) for r in rows)
            if n:out[(group,'more')]=(float(w[k]),n);out[(group,'less')]=(float(-w[k]),n)
        return out
    def _after_pair(self):
        self.completed+=1
        if self.completed>=STYLE_PAIRS:  # no final round: rank, then the listener picks from the shortlist
            self._rank_finalists();self.stage='done';self.active=False;self.pair=[];self.busy=False
            return
        self._prepare()
    def _games(self,ident):return sum(ident in row['pair'] for row in self._choices())
    def _rank_finalists(self):
        """Shortlist: strongest sounds with enough evidence, kept audibly distinct (0.10 audio gate)."""
        ranked=self._ranked();eligible=[i for i in ranked if self._games(i)>=SHORTLIST_MIN_GAMES];self.finalists=[]
        for ident in eligible+[i for i in ranked if i not in eligible]:
            a=self.candidates[ident].get('audio_descriptor')
            close=any(a and self.candidates[j].get('audio_descriptor') and float(np.linalg.norm(np.sqrt(np.maximum(a,0))-np.sqrt(np.maximum(self.candidates[j]['audio_descriptor'],0)))/math.sqrt(2))<MIN_AUDIO_DISTANCE for j in self.finalists)
            if not close:self.finalists.append(ident)
            if len(self.finalists)==SHORTLIST:break
    def _finalist_summary(self,ident,strength):
        rows=[row for row in self._choices() if ident in row['pair']]
        wins=sum(1. if row['winner']==ident else .5 if row['winner'] is None else 0. for row in rows)
        return {'strength':strength,'wins':wins,'games':len(rows),'score':self._score(ident),'ratingCount':0}
    def _origin_text(self,pair):
        before={i for row in self.history for i in row['pair']}
        return {i:(f"Returning: {self.candidates[i].get('origin',{}).get('summary','')}" if i in before else self.candidates[i].get('origin',{}).get('summary','')) for i in pair}
    def _choice_feedback(self,choice,context):
        if choice not in ('A','B','equal'):raise ValueError('Choose Prefer A, Like both equally, or Prefer B')
        if not isinstance(context,(dict,type(None))):raise ValueError('Invalid audition context')
        if context and (context.get('input') not in ('live','simulated') or context.get('style') not in ('steady','rise','evolving')):raise ValueError('Invalid audition context')
        pair=self.pair.copy();winner={'A':pair[0],'B':pair[1]}.get(choice)
        self.history.append({'pair':pair,'rating_source':'choice','choice':choice,'winner':winner,'ratings_by_candidate':{},
                             'origin_by_candidate':self._origin_text(pair),'context':context or {},'time':datetime.now(timezone.utc).isoformat()})
        self._after_pair()
    def export(self):
        data=super().export()
        strengths=self._strengths();style_rows=[]
        for row in self._choices():
            a,b=(self.candidates[i]['recipe']['layers'][0]['method'] for i in row['pair'])
            if a!=b:style_rows.append({'pair':[a,b],'choice':row['choice']})
        styles=bt_strengths(list(STYLES),style_rows)
        data['note']='Base-style exploration (stage 1 + direction learning). All 20 steps are discovery pairs; no final round. Pairs 1-4: all seven base styles (three contrasting pairs, then the seventh against the style preferred so far). Pairs 5-14 alternate a parent check (best sound vs a tuned version of it) and tuned versions of the best sound and the best sound of another style; a tuning moves one group (deep, bright, full, moving) by 0.5 of its range; Electric and Jet get pitch moves only until per-style groups exist. One Bradley-Terry preference model over what sounds are made of (style one-hot + net group steps along the tuning chain, ridge 1) is fitted to every choice; it ranks sounds, picks which to build on, and gives each move its learned effect. A sound that beat its own tunings in its last 2 parent checks is left alone. Moves are chosen by momentum (repeat a move that beat its parent), learned effect and a bonus for untried moves. Pitch moves are x or / 1.26 per step. Every pair is a direct choice; sounds are ranked by Bradley-Terry over all choices, and the listener picks from a shortlist of up to 5 distinct sounds with at least 2 choices each.'
        weights=self._weights()
        data['preference_model']={'version':'bt-features-1','candidate_strengths':strengths,
                                  'feature_weights':{**{f'style:{s}':round(float(v),3) for s,v in zip(STYLES,weights)},**{f'steps:{g}':round(float(v),3) for g,v in zip(STYLE_GROUPS,weights[len(STYLES):])}},
                                  'utilities':{i:round(self._utility(i),3) for i in strengths},
                                  'direction_scores':sorted(({'group':g,'direction':d,'score':round(v,3),'results':n} for (g,d),(v,n) in self.direction_scores().items()),key=lambda x:-x['score']),
                                  'style_ranking':sorted(({'style':s,'name':STYLES[s],'strength':round(v,3)} for s,v in styles.items()),key=lambda x:-x['strength']),
                                  'note':'Bradley-Terry over discovery choices; equal = half a win; each item has one virtual even game vs a neutral item. Style ranking uses only choices between different styles.'}
        return data
