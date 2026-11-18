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
        self.lock=threading.RLock();self.epoch=0;self.active=False;self.busy=False;self.error='';self.candidates={};self.pair=[];self.history=[];self.tried=set();self.quarantine=[];self.final=None;self.rng=random.Random();self.completed=0;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[];self.origins={};self.check_parent=None;self.pair_mode='rating';self.acceptable=None
    def close(self):
        self.epoch+=1
        if hasattr(self.renderer,'close'):self.renderer.close()
        self.executor.shutdown(wait=False,cancel_futures=True)
    def snapshot(self):
        with self.lock:
            def public(ident):
                c=self.candidates[ident]
                return {k:c[k] for k in ['id','label','recipe','urls','traces'] if k in c}
            return {'active':self.active,'busy':self.busy,'error':self.error,'completed':self.completed,'pair':[public(x) for x in self.pair],'heard':list(self.tried),'selected':self.selected,'final':self.final,'finalists':[dict(public(x),**self._finalist_summary(x,strength)) for x,strength in self._bt_order()],'stage':self.stage,'step':self.completed+len(self.playoff_history),'totalSteps':TOTAL_STEPS,'playoffDone':len(self.playoff_history),'playoffTotal':PLAYOFF_PAIRS,'quarantined':len(self.quarantine),'policy':self.policy,'checkpoint':self.stage!='discovery','pairMode':self.pair_mode,'maxComparisons':MAX_COMPARISONS,'acceptable':self.acceptable}
    def start(self):
        with self.lock:
            if self.busy:raise ValueError('Wait for source preparation to finish')
            self.epoch+=1;self.active=True;self.error='';self.candidates={};self.pair=[];self.history=[];self.tried=set();self.quarantine=[];self.completed=0;self.final=None;self.selected=None;self.auditions=[];self.excluded=set();self.hearing_context=None;self.diversity_skips=[];self.finalists=[];self.stage='discovery';self.playoff_queue=[];self.playoff_history=[];self.origins={};self.check_parent=None;self.pair_mode='rating';self.acceptable=None
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
    def accept(self,answer):
        """Final absolute check: would the listener be happy with the chosen sound in their car (yes/no)."""
        with self.lock:
            if not self.final:raise ValueError('Choose your final sound first')
            if not isinstance(answer,bool):raise ValueError('Answer yes or no')
            self.acceptable=answer
    def export(self):
        with self.lock:return deepcopy({'format':'ev-source-discovery-v3','policy':self.policy,'seed':getattr(self,'seed',None),'history':self.history,'auditions':self.auditions,'final':self.final,'final_acceptable':self.acceptable,'finalists':[dict(id=ident,**self._finalist_summary(ident,strength)) for ident,strength in self._bt_order()],'playoff_history':self.playoff_history,'preference_model':preference_summary(self.candidates),'candidates':self.candidates,'quarantine':self.quarantine,'diversity_skips':self.diversity_skips,'note':'14 rated pairs pick 4 diverse finalists by 1–7 rating shrunk toward neutral 4 (prior weight 2). A 6-pair round-robin final round orders them by Bradley-Terry strength; ratings enter only as one virtual game per finalist. Final choice stays explicit. Later candidate proposals use a regularized model of foundation family, layer mix, and layer count, with an exploration bonus. Explicit export only; no automatic participant record.'})


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

SHARE={'A':1.,'B':0.,'equal':.5,'good':.5,'neither':.5}  # win share of the first sound; Both good / Neither say nothing about which is better
ABSOLUTE={'good':1.,'neither':0.}  # ...but they do say both are better / worse than a neutral sound
def bt_strengths(items,rows):
    """Bradley-Terry strengths (MM, Hunter 2004) from choice rows; equal = half a win each. Every item also plays one
    virtual even game against a neutral item of strength 1, so unplayed or unbeaten items stay finite."""
    index={ident:i for i,ident in enumerate(items)};n=len(items)
    if not n:return {}
    wins=np.zeros((n,n));neutral_wins=np.full(n,.5);neutral_games=np.ones(n)
    for row in rows:
        a,b=row['pair']
        if a not in index or b not in index:continue
        share=SHARE[row['choice']]
        wins[index[a],index[b]]+=share;wins[index[b],index[a]]+=1-share
        if row['choice'] in ABSOLUTE:  # Both good: each beats the neutral item; Neither: each loses to it
            for i in (index[a],index[b]):neutral_games[i]+=1;neutral_wins[i]+=ABSOLUTE[row['choice']]
    games=wins+wins.T;total=wins.sum(1)+neutral_wins;strength=np.ones(n)
    for _ in range(200):strength=total/((games/(strength[:,None]+strength[None,:])).sum(1)+neutral_games/(strength+1))
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

def fit_bayes(X,y,n,prior_var=1/FEATURE_L2):
    """Bayesian Bradley-Terry: logistic regression on feature differences with a N(0, prior_var) prior on every weight, Laplace
    approximation. Mean = the MAP weights (same as fit_preference with l2 = 1/prior_var); covariance = inverse Hessian at the MAP,
    so the model knows how sure it is about each setting (unheard settings keep the prior spread)."""
    X=np.array(X,dtype=float).reshape(-1,n);y=np.array(y,dtype=float);w=np.zeros(n);l2=1/prior_var
    for _ in range(25):
        p=1/(1+np.exp(-X@w));g=X.T@(p-y)+l2*w;H=(X*(p*(1-p))[:,None]).T@X+l2*np.eye(n)
        w-=np.linalg.solve(H,g)
    p=1/(1+np.exp(-X@w));H=(X*(p*(1-p))[:,None]).T@X+l2*np.eye(n)
    return w,np.linalg.inv(H)

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
    answers=('A','B','equal')
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
        wins=sum(1. if row['winner']==ident else .5 if row['choice'] in ('equal','good') else 0. for row in rows)
        return {'strength':strength,'wins':wins,'games':len(rows),'score':self._score(ident),'ratingCount':0}
    def _origin_text(self,pair):
        before={i for row in self.history for i in row['pair']}
        return {i:(f"Returning: {self.candidates[i].get('origin',{}).get('summary','')}" if i in before else self.candidates[i].get('origin',{}).get('summary','')) for i in pair}
    def _choice_feedback(self,choice,context):
        if choice not in self.answers:raise ValueError('Choose one of: '+', '.join(self.answers))
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


# Level search (2026-11-14): simplified base sound (Type x Brightness x Register) plus transformation effects, every control at
# 2-3 fixed settings. Sounds are built and played live in the app (desktop/src/levels.ts, labEngine.ts): no offline render.
# Every sound differs from its parent by one whole setting, so the audio near-copy gate is not needed.
import hashlib,json
LEVEL_POLICY='source-levels-v1'
LEVEL_BASE={'type':('strings','choir','glass'),'brightness':(-1,0,1),'register':(-1,0,1)}
LEVEL_FX={'chorus':(0,1,2),'reverb':(0,1,2),'vibrato':(0,1,2),'follow':(0,1),'body':(0,1),'tremolo':(0,1)}  # = LEVEL_VALUES in levels.ts
LEVEL_CONTROLS={**{('base',k):v for k,v in LEVEL_BASE.items()},**{('fx',k):v for k,v in LEVEL_FX.items()}}
LEVEL_NEUTRAL_FX={'chorus':1,'reverb':1,'vibrato':1,'follow':1,'body':0,'tremolo':0}  # close to the blind-tested mimic effects
LEVEL_NAMES={'type':{'strings':'Strings','choir':'Choir','glass':'Glass'},'brightness':{-1:'darker',0:'normal',1:'brighter'},'register':{-1:'deep',0:'middle',1:'high'}}
BASE_PAIRS=6  # pairs 1-6 look for the base sound (effects neutral); later pairs mostly change effects
BASE_MOVE_PENALTY=.5  # after BASE_PAIRS, base changes still happen, but effect changes come first unless the model favours a base change

def level_recipe(base,fx):return {'version':2,'kind':'levels','seed':0,'base':dict(base),'fx':dict(fx)}
def level_id(recipe):return hashlib.sha256(json.dumps([recipe['base'],recipe['fx']],sort_keys=True).encode()).hexdigest()[:32]
def level_label(recipe):
    b,f=recipe['base'],recipe['fx']
    return f"{LEVEL_NAMES['type'][b['type']]} · {LEVEL_NAMES['brightness'][b['brightness']]} · {LEVEL_NAMES['register'][b['register']]} · "+' '.join(f'{k} {v}' for k,v in f.items())
def level_features(recipe):
    """One-hot of every control's setting: the model learns a value per setting (24 features)."""
    return np.array([1. if recipe[part][key]==level else 0. for (part,key),levels in LEVEL_CONTROLS.items() for level in levels])
LEVEL_FEATURE_NAMES=[f'{key}={level}' for (part,key),levels in LEVEL_CONTROLS.items() for level in levels]

class LevelDiscovery(StyleDiscovery):
    """20 direct choices over level sounds; Bradley-Terry over settings; shortlist at the end (shared with StyleDiscovery)."""
    policy=LEVEL_POLICY
    controls=LEVEL_CONTROLS  # every (part, key) the model learns
    moves=LEVEL_CONTROLS     # the ones a one-setting change may touch
    feature_names=LEVEL_FEATURE_NAMES
    def _features(self,recipe):return level_features(recipe)
    def _id(self,recipe):return level_id(recipe)
    def _label(self,recipe):return level_label(recipe)
    def _weights(self):
        rows=self._choices()
        if getattr(self,'_cache',(None,))[0]!=len(rows):
            f=lambda i:self._features(self.candidates[i]['recipe']);X,y=[],[]
            for r in rows:
                a,b=f(r['pair'][0]),f(r['pair'][1]);X.append(a-b);y.append(SHARE[r['choice']])
                if r['choice'] in ABSOLUTE:X+=[a,b];y+=[ABSOLUTE[r['choice']]]*2  # vs a neutral sound (utility 0)
            self._cache=(len(rows),fit_preference(X,y))
        return self._cache[1]
    def _predict(self,recipe):return float(self._features(recipe)@self._weights())
    def _utility(self,ident):return self._predict(self.candidates[ident]['recipe'])
    def _add(self,recipe,origin):
        ident=self._id(recipe)
        if ident not in self.candidates:self.candidates[ident]={'id':ident,'label':self._label(recipe),'recipe':recipe,'urls':[],'traces':{},'origin':origin}
        return ident
    def _allowed(self,recipe,part,key,level):return True
    def _neighbours(self,parent,base_penalty=0.):
        """Every one-setting change of a sound, best first: learned value + bonus for settings not heard yet + momentum."""
        recipe=self.candidates[parent]['recipe'];heard={i for row in self.history for i in row['pair']}
        heard_settings={(k,self.candidates[i]['recipe'][p][k]) for i in heard for (p,k) in self.moves}
        origin=self.candidates[parent].get('origin',{})
        beat_parent=origin.get('kind')=='tuned' and any(r['winner']==parent and origin['parent'] in r['pair'] for r in self._choices())
        out=[]
        number=lambda v:isinstance(v,(int,float))
        for (part,key),levels in self.moves.items():
            for level in levels:
                if level==recipe[part][key] or not self._allowed(recipe,part,key,level):continue
                child=deepcopy(recipe);child[part][key]=level
                momentum=beat_parent and origin.get('control')==key and number(level) and number(recipe[part][key]) and (level>recipe[part][key])==(origin['to']>origin['from'])
                gain=self._predict(child)-self._predict(recipe)
                value=gain+(UNTRIED if (key,level) not in heard_settings else 0)+(MOMENTUM if momentum else 0)-(base_penalty if part=='base' else 0)+self.rng.random()*.01
                reason='repeats the change that just won' if momentum else f'learned gain {gain:+.2f}' if self._choices() else 'not tried yet'
                out.append((value,child,{'kind':'tuned','parent':parent,'part':part,'control':key,'from':recipe[part][key],'to':level,'reason':reason,
                    'summary':f"{self.candidates[parent]['label'].split(' · ')[0]} from {parent[:6]}: {key} {recipe[part][key]} → {level} ({reason})"}))
        out.sort(key=lambda x:-x[0])
        return [(child,origin) for _,child,origin in out]
    def _proposals(self):
        self.check_parent=None;fx=LEVEL_NEUTRAL_FX;mid={'brightness':0,'register':0}
        start=lambda t:(level_recipe({'type':t,**mid},fx),{'kind':'base','summary':f"Starting sound: {LEVEL_NAMES['type'][t]}"})
        if self.completed==0:return [start('strings'),start('choir')]
        ranked=self._ranked()
        if self.completed==1:self.check_parent=ranked[0];return [start('glass')]
        open_ranked=[i for i in ranked if not self._settled(i)] or ranked
        best=open_ranked[0];best_type=self.candidates[best]['recipe']['base']['type']
        second=next((i for i in open_ranked[1:] if self.candidates[i]['recipe']['base']['type']!=best_type),open_ranked[1] if len(open_ranked)>1 else best)
        penalty=0. if self.completed<BASE_PAIRS else BASE_MOVE_PENALTY
        if self.completed<BASE_PAIRS:  # base phase: change only the base sound
            moves=lambda i:[m for m in self._neighbours(i) if m[1]['part']=='base']
        else:moves=lambda i:self._neighbours(i,penalty)
        if self.completed%2==0:self.check_parent=best;return moves(best)
        a,b=moves(best),moves(second)
        return [x for pair in zip(a,b) for x in pair]+a[len(b):]+b[len(a):]
    def _prepare(self):
        """Pick a pair from the proposals at once: no rendering. Never a sound already heard (except the returning parent),
        never two changes of the same sound side by side."""
        self.busy=False;self.error='';self.tried.clear();self.selected=None
        proposals=self._proposals();heard={i for row in self.history for i in row['pair']}
        pair=[self.check_parent] if self.check_parent else []
        for recipe,origin in proposals:
            ident=self._id(recipe)
            if ident in pair or ident in heard or ident in self.excluded:continue
            parent=origin.get('parent')
            if parent and any(self.candidates[i].get('origin',{}).get('parent')==parent for i in pair):continue
            pair.append(self._add(recipe,origin))
            if len(pair)==2:break
        if len(pair)<2:self.error='Could not form a new pair: every nearby sound was already heard. Finish to see your shortlist.';self.pair=[];return
        self.rng.shuffle(pair);self.pair=pair;self.pair_mode='choice'
    def direction_scores(self):return {}
    def export(self):
        data=SourceDiscovery.export(self);weights=self._weights();strengths=self._strengths()
        data['note']=('Level search: a sound is Type x Brightness x Register (simplified base) plus six effects (chorus, reverb, vibrato, pedal tone, body, tremolo) '
            'at 2-3 settings each; values in desktop/src/levels.ts. Pairs 1-2 compare the three types; pairs 3-6 change one base setting; later pairs change one '
            'setting (effects first). Even pairs: best sound vs a one-setting change of it; odd pairs: changes of the best and of the best of another type. '
            'Bradley-Terry over one-hot settings (ridge 1), fitted to every choice; a sound that beat its own changes twice is left alone. Shortlist at the end.')
        data['preference_model']={'version':'bt-levels-1','candidate_strengths':strengths,'feature_weights':{n:round(float(v),3) for n,v in zip(self.feature_names,weights)},
            'utilities':{i:round(self._utility(i),3) for i in strengths}}
        return data


# Tuning search (2026-11-15): the seven starting sounds plus the agreed tuning moves (desktop/src/levels.ts tunedSound).
# The listener picks Rising or Evolving first; Space Large and the 260 Hz comfort cap stay fixed. Sounds are built live in the app.
TUNING_POLICY='source-tuning-v1'
TUNING_STARTS=('warm','voice','sparkle','synth','whine','dark')  # = STARTING_SOUNDS ids in levels.ts ('warm' = Cinematic pad family; Synth replaced Pure tone 2026-11-16)
TUNING_NAMES={'warm':'Cinematic pad','voice':'Voice','sparkle':'Sparkle','synth':'Synth','whine':'Electric whine','dark':'Dark ambience'}
TUNING_OPENING=(('sparkle','warm'),('voice','whine'),('synth','dark'))  # most different pairing: 0.58, 0.76, 0.71 apart (octave-band spectrum, capped pitch)
TUNING_MOTION_SOUND='warm'  # pair 1: this sound Rising vs Evolving; the choice sets the motion for the session
TUNING_PLAYOFF=2  # pairs 5-6: the opening winners against each other, so the search follows one branch
# Source tree level 2 (2026-11-16): each family's hand-made variants (= VARIANTS in levels.ts). After the family playoff the face meets its
# two variants, then the best of them meets the best sound of another family (runner-up check), then fine tuning.
TUNING_VARIANTS={'warm':('warm-angelic','warm-dreamy'),'voice':('voice-aah','voice-deep'),'sparkle':('sparkle-chimes','sparkle-crystal'),
    'synth':('synth-dark','synth-lead'),'whine':('whine-clear','whine-turbine'),'dark':('dark-ghost','dark-gong')}
TUNING_VARIANT_NAMES={'warm-angelic':'Angelic','warm-dreamy':'Dreamy pad','voice-aah':'Bright aah','voice-deep':'Deep ooh','sparkle-chimes':'Low chimes',
    'sparkle-crystal':'Crystal','synth-dark':'Dark synth','synth-lead':'Bright lead','whine-clear':'Clear whine','whine-turbine':'Turbine','dark-ghost':'Ghost choir','dark-gong':'Gong'}
TUNING_BIG_PAIRS=11  # fine tuning: pitch changes first (biggest), brightness and character from about pair 12
# 2nd version: Borrow, Climb and Movement dropped (too small to hear in the change test). = Tuning in levels.ts
TUNING_SOURCE={'pitch':(-1,0,1),'brightness':(-1,0,1),'character':(-1,0,1)}  # pitch step = 8 semitones (4 sounded small). Blend dropped 2026-11-16: the variants do its job, more clearly
# Change test (2026-11-15): sides that sounded small are not offered for that starting sound (= CHARACTER in levels.ts).
TUNING_LIMITS={'character':{'warm':(-1,0),'whine':(-1,0),'dark':(0,1),'sparkle':(0,1)},'brightness':{'sparkle':(-1,0)}}
# Change test 2026-11-16, Cinematic pad and Angelic: every change clear; 'less chord' loses their character but is not unpleasant, so kept
# (only 'unpleasant' changes are removed). Synth and the other variants not change-tested yet.
TUNING_FX={}  # Movement dropped after the change test (wobble/pulse small, pump not heard); recipes keep fx.movement 'still'
TUNING_MOVES={**{('base',k):v for k,v in TUNING_SOURCE.items()},**{('fx',k):v for k,v in TUNING_FX.items()}}
TUNING_CONTROLS={('base','start'):TUNING_STARTS,('base','variant'):TUNING_STARTS+tuple(v for vs in TUNING_VARIANTS.values() for v in vs),**TUNING_MOVES}  # variant = the face id for a family's own sound
# Model features: one-hot per setting, but Character is per starting sound (Warm pad 'less chord' and Dark ambience 'more ghost voice'
# are different changes; one shared feature mixed them up in the 2026-11-16 session).
TUNING_FEATURE_KEYS=[(part,key,level) for (part,key),levels in TUNING_CONTROLS.items() if key!='character' for level in levels]+[('start','character',(s,l)) for s in TUNING_STARTS for l in (-1,1)]
TUNING_FEATURE_NAMES=[f'character {s} {l:+d}' if key=='character' else f'{key}={level}' for part,key,level in TUNING_FEATURE_KEYS for s,l in [level if key=='character' else (0,0)]]
# 1: pitch floor. Roots of the starting sounds (= rootHz in levels.ts STARTING_SOUNDS). Very low notes barely play on laptop speakers and
# most headphones: Dark ambience at 48 Hz made darker / more ghost voice sound the same (pairs 16, 20 on 2026-11-16). 80 Hz keeps
# Warm pad -8 semitones (83 Hz, the listener's final pick that session) and blocks Dark ambience 48 Hz and Electric whine 62 Hz.
TUNING_ROOTS={'warm':98,'voice':147,'sparkle':233,'synth':175,'whine':98,'dark':76,  # faces, then variants (= rootHz in levels.ts)
    'warm-angelic':147,'warm-dreamy':147,'voice-aah':147,'voice-deep':110,'sparkle-chimes':147,'sparkle-crystal':185,'synth-dark':110,'synth-lead':196,
    'whine-clear':98,'whine-turbine':110,'dark-ghost':98,'dark-gong':87}
PITCH_FLOOR_HZ=80
# Pitch ceiling: the drive's top note is about 1 semitone above the root and the comfort cap stops it at 260 Hz, so a root above
# about 245 Hz is pinned at the cap for most of the drive. Sparkle +8 (370 Hz) sounded like plain Sparkle (2026-11-16, pairs 7-10).
PITCH_CEILING_HZ=200  # 245 at first; Angelic +8 (233 Hz) still sounded too high (2026-11-16), so pitch-up stops at 200 Hz
PITCH_STEP_SEMITONES=8
def tuning_root(base):
    root=TUNING_ROOTS[base.get('variant') or base['start']]
    if base.get('blend'):root*=(TUNING_ROOTS[base['blend']]/root)**base.get('mix',1/2)
    return root*2**(PITCH_STEP_SEMITONES*base['pitch']/12)
def tuning_recipe(motion,start,variant=None):
    return {'version':3,'kind':'tuning','seed':0,'motion':motion,'base':{'start':start,'variant':variant or start,'pitch':0,'brightness':0,'character':0,'blend':None,'mix':1/2},'fx':{'movement':'still'}}

class TuningDiscovery(LevelDiscovery):
    """20 direct choices over tuned starting sounds. Answers: Prefer A, Prefer B, Both good, Neither.
    Same machinery as LevelDiscovery: one-setting changes, parent checks, Bradley-Terry over one-hot settings, shortlist.
    Both good / Neither also count as a win / loss against a neutral sound, so the model learns absolute good and bad."""
    policy=TUNING_POLICY
    answers=('A','B','good','neither')
    controls=TUNING_CONTROLS
    moves=TUNING_MOVES
    feature_names=TUNING_FEATURE_NAMES
    motion='rise'
    motion_pairs=0  # 1 when the session opens with the Rising vs Evolving pair
    # Simulated listeners (600 per variant, hidden linear taste, noisy answers, 2026-11-16): share of sessions whose picked sound is in the
    # listener's top 5% (+-2%). Parents by posterior mean, changes ordered by a Thompson sample: half spread 85%, full 81%. Parents by the
    # sample too: half 78%, full 61% (too much wandering for 20 pairs). Old rules 82-83%, posterior mean only 84-86%. Finalist duels in the
    # last 3 pairs: 73%, removed. Half spread kept: tied with the best, and still explores when real listeners are noisier than the simulation.
    explore=.5  # Thompson sample spread (1 = full posterior, 0 = posterior mean)
    bayes=True  # False = the earlier hand-made rules (bonus for unheard settings, momentum), kept as a baseline
    def _features(self,recipe):
        b=recipe['base']
        get=lambda part,key:b.get('variant',b['start']) if key=='variant' else recipe[part].get(key)  # sessions before the tree have no variant
        return np.array([float((b['start'],b['character'])==level) if key=='character' else float(get(part,key)==level) for part,key,level in TUNING_FEATURE_KEYS])
    def _id(self,recipe):return hashlib.sha256(json.dumps([recipe['motion'],recipe['base'],recipe['fx']],sort_keys=True).encode()).hexdigest()[:32]
    def _label(self,recipe):
        b,f=recipe['base'],recipe['fx'];v=b.get('variant',b['start']);parts=[TUNING_VARIANT_NAMES.get(v,TUNING_NAMES.get(v,v))]
        for key in ('pitch','brightness','character'):
            if b[key]:parts.append(f'{key} {b[key]:+d}')
        if b['blend']:parts.append(f"blend {TUNING_NAMES[b['blend']]}")
        if f['movement']!='still':parts.append(f['movement'])
        return ' · '.join(parts)
    def _posterior(self):
        """Mean and covariance of the setting weights (fit_bayes), refitted after every choice."""
        rows=self._choices()
        if getattr(self,'_post',(None,))[0]!=len(rows):
            f=lambda i:self._features(self.candidates[i]['recipe']);X,y=[],[]
            for r in rows:
                a,b=f(r['pair'][0]),f(r['pair'][1]);X.append(a-b);y.append(SHARE[r['choice']])
                if r['choice'] in ABSOLUTE:X+=[a,b];y+=[ABSOLUTE[r['choice']]]*2
            self._post=(len(rows),*fit_bayes(X,y,len(self.feature_names)))
        return self._post[1],self._post[2]
    def _weights(self):return self._posterior()[0]
    def _sd(self,ident):f=self._features(self.candidates[ident]['recipe']);return float(np.sqrt(f@self._posterior()[1]@f))
    def _sample(self):
        """Thompson sampling: one plausible taste drawn from the posterior; this pair is built for it. Exploration comes from
        uncertainty (settings rarely heard have a wide spread) instead of fixed bonuses."""
        mean,cov=self._posterior();rng=np.random.default_rng(self.rng.randrange(2**32))
        self._w_sample=rng.multivariate_normal(mean,cov*self.explore**2,method='cholesky') if self.explore else mean
    def _sampled(self,recipe):return float(self._features(recipe)@self._w_sample)
    def _neighbours(self,parent,base_penalty=0.):
        out=super()._neighbours(parent,base_penalty)
        if not self.bayes:return out
        for _,origin in out:origin['reason']='Thompson sample';origin['summary']=origin['summary'].rsplit(' (',1)[0]+' (Thompson sample)'
        return sorted(out,key=lambda m:-self._sampled(m[0]))
    def _ranked(self):return [i for i in super()._ranked() if self.candidates[i]['recipe']['motion']==self.motion]  # the motion not chosen drops out
    def _distinct(self,a,b):
        """Shortlist rule: two finalists must differ in starting sound or in at least two settings."""
        ba,bb=self.candidates[a]['recipe']['base'],self.candidates[b]['recipe']['base']
        return ba['start']!=bb['start'] or sum(ba[k]!=bb[k] for k in ba)>=2
    def _rank_finalists(self):
        ranked=self._ranked();eligible=[i for i in ranked if self._games(i)>=SHORTLIST_MIN_GAMES];self.finalists=[]
        for ident in eligible+[i for i in ranked if i not in eligible]:
            if all(self._distinct(ident,j) for j in self.finalists):self.finalists.append(ident)
            if len(self.finalists)==SHORTLIST:break
    def _finalist_summary(self,ident,strength):
        return {**super()._finalist_summary(ident,strength),'utility':round(self._utility(ident),3),'sd':round(self._sd(ident),3)}
    def _allowed(self,recipe,part,key,level):
        if key in ('blend','variant','start'):return False  # never changed by a tuning move
        if key in ('pitch','blend'):  # pitch floor: never move a sound lower once it is under the floor (Dark ambience may start at 76 Hz)
            root=tuning_root({**recipe['base'],key:level});now=tuning_root(recipe['base'])
            if root<PITCH_FLOOR_HZ and root<now-1e-6:return False
            if root>PITCH_CEILING_HZ and root>now+1e-6:return False  # pitch ceiling: never higher once above it
        return level in TUNING_LIMITS.get(key,{}).get(recipe['base']['start'],(level,))
    def start(self,motion=None):
        """motion None: pair 1 is the same sound Rising vs Evolving and the listener's choice sets it (Both good / Neither keep Rising)."""
        if motion not in (None,'rise','evolving'):raise ValueError('Choose Rising or Evolving')
        with self.lock:self.motion=motion or 'rise';self.motion_pairs=0 if motion else 1;self.family=None;self.tuning_check=None;super().start()
    def _proposals(self):
        self.check_parent=None;mp=self.motion_pairs;step=self.completed-mp;rows=self._choices()
        if mp and self.completed==0:
            names={'rise':'Rising','evolving':'Evolving'}
            self.rematch=[self._add(tuning_recipe(m,TUNING_MOTION_SOUND),{'kind':'motion','motion':m,'summary':f'Motion: {names[m]} ({TUNING_NAMES[TUNING_MOTION_SOUND]})'}) for m in ('rise','evolving')]
            return []
        if mp and self.completed==1:
            winner=rows[0]['winner'];self.motion=self.candidates[winner]['recipe']['motion'] if winner else 'rise'
        start=lambda name:(tuning_recipe(self.motion,name),{'kind':'base','summary':f'Starting sound: {TUNING_NAMES[name]}'})
        opening=len(TUNING_OPENING)
        if step<opening:self.rematch=[self._add(*start(name)) for name in TUNING_OPENING[step]];return []  # may repeat the motion pair's sound
        ranked=self._ranked()  # mean ranking for the playoff
        # Next two pairs: playoff between the opening winners (Both good: both go through; Neither: both out).
        winners=set()
        for r in rows[mp:mp+opening]:winners|={r['winner']} if r['winner'] else set(r['pair']) if r['choice']=='good' else set()
        winners=[i for i in ranked if i in winners]
        if step==opening and len(winners)>=2:self.rematch=winners[:2];return []
        if step==opening+1 and len(winners)>=3:
            left=[i for i in winners if i not in rows[mp+opening]['pair']]
            if left:self.rematch=[next(i for i in winners if i!=left[0]),left[0]];return []
        # Variant round: the winning family's face against its two variants (the face may be heard again).
        family=self.candidates[ranked[0]]['recipe']['base']['start'] if ranked else TUNING_STARTS[0]
        if step==opening+2 or not getattr(self,'family',None):self.family=family  # chosen once, at the variant round
        variant=lambda v:(tuning_recipe(self.motion,self.family,v),{'kind':'variant','summary':f'Variant: {TUNING_VARIANT_NAMES[v]} ({TUNING_NAMES[self.family]})'})
        own=lambda:[i for i in ranked if self.candidates[i]['recipe']['base']['start']==self.family]
        vs=TUNING_VARIANTS[self.family]
        if step==opening+2:self.rematch=[own()[0] if own() else self._add(*variant(self.family)),self._add(*variant(vs[0]))];return []
        if step==opening+3:self.rematch=[own()[0],self._add(*variant(vs[1]))];return []
        # Runner-up check: the best of this family against the best sound of another family, so the listener can still switch.
        if step==opening+4:
            other=next((i for i in ranked if self.candidates[i]['recipe']['base']['start']!=self.family),None)
            if other and own():self.rematch=[own()[0],other];return []
        # Last pair (pair 20): blind tuning check. The current best against the same variant untuned (or, if the best is untuned, against its
        # best tuned version). It looks like any other pair and counts like any other choice, so the shortlist built after it agrees with it.
        if self.completed==STYLE_PAIRS-1 and ranked:
            top=ranked[0];b=self.candidates[top]['recipe']['base'];tuned=lambda i:any(self.candidates[i]['recipe']['base'][k] for k in ('pitch','brightness','character'))
            same=lambda i:self.candidates[i]['recipe']['base'].get('variant')==b.get('variant')
            if tuned(top):plain=self._add(tuning_recipe(self.motion,b['start'],b.get('variant')),{'kind':'check','summary':'Tuning check: the same variant untuned'});pair=[top,plain]
            else:pair=[next((i for i in ranked if same(i) and tuned(i)),None),top]
            if pair[0] and pair[1] and pair[0]!=pair[1]:
                self.tuning_check={'tuned':pair[0],'untuned':pair[1]};self.rematch=pair;return []
        if self.bayes:self._sample()  # parents stay the posterior-mean best; the sample orders their changes
        # After Neither, build on other sounds: the next pair moves away instead of fine-tuning a line the listener rejected.
        last=self._choices()[-1];rejected=set(last['pair']) if last['choice']=='neither' else set()
        open_ranked=[i for i in ranked if not self._settled(i) and i not in rejected] or [i for i in ranked if i not in rejected] or ranked
        start_of=lambda i:self.candidates[i]['recipe']['base']['start']
        best=next((i for i in ranked if i not in rejected),ranked[0])  # the champion; a settled champion stays (challengers face it)
        # Tuning pairs are always the best sound against one change of it: a change that spoils the sound just loses to it. (Before, odd pairs
        # put a change of the best against a change of another family, so rejecting a bad change looked like preferring that family.)
        # Challenger pairs share the same budget adaptively (2026-11-16, listener: tuning re-confirmed one sound for ~10 pairs): once the best
        # has beaten its own changes twice (settled), every pair is a challenger; before that, tuning and challenger take turns.
        tuning_step=step-opening-5
        if self._settled(best) or tuning_step%2==1:
            challenger=self._challenger(best)
            if challenger:self.rematch=[best,challenger];return []
        big=step<TUNING_BIG_PAIRS  # coarse to fine: pitch first
        moves=lambda i:[m for m in self._neighbours(i) if not big or m[1]['control']=='pitch']
        # Fallback tail: changes of the next-ranked sounds, for when every one-setting change of the best was already heard.
        fallback=[m for i in open_ranked if i!=best for m in moves(i)]
        if not rejected:self.check_parent=best
        return moves(best)+fallback
    def skip_similar(self,ids):
        """The app measured the two sounds of the pair as too close: drop the new one(s) and pick another pair. Opening and playoff pairs are kept."""
        with self.lock:
            if not self.active or sorted(ids or [])!=sorted(self.pair):raise ValueError('Pair changed; nothing to skip')
            if self.rematch_pair:return
            heard={i for row in self.history for i in row['pair']};new=[i for i in self.pair if i not in heard]
            self.diversity_skips.append({'pair':list(self.pair),'dropped':new,'reason':'App measured the pair as too similar'})
            self.excluded|=set(new);self._prepare()
    def _challenger(self,best):
        """An untried sound to put against the best: every family face and variant, unchanged, in the session's motion. One Thompson sample
        of the listener's taste picks it, so sounds never heard (widest uncertainty) get their turn without being random. Never a sound that
        already met the best."""
        self._sample();met={i for r in self._choices() if best in r['pair'] for i in r['pair']}
        pool=[tuning_recipe(self.motion,fam,v) for fam,vs in TUNING_VARIANTS.items() for v in (fam,)+vs]
        pool=[r for r in pool if self._id(r) not in met and self._id(r)!=best and self._id(r) not in self.excluded]
        if not pool:return None
        r=max(pool,key=self._sampled);v=r['base']['variant']
        return self._add(r,{'kind':'challenger','summary':f"Challenger: {TUNING_VARIANT_NAMES.get(v,TUNING_NAMES.get(v,v))}"})
    def _prepare(self):
        self.rematch=None;super()._prepare();self.rematch_pair=bool(self.rematch)
        if self.rematch:self.error='';pair=list(self.rematch);self.rng.shuffle(pair);self.pair=pair;self.pair_mode='choice'
    def export(self):
        data=super().export();data['motion']=self.motion
        check=getattr(self,'tuning_check',None);last=self.history[-1] if self.history else None
        if check and last and set(last['pair'])=={check['tuned'],check['untuned']}:
            data['tuning_check']={**check,'choice':last['choice'],'result':'tuned' if last['winner']==check['tuned'] else 'untuned' if last['winner']==check['untuned'] else last['choice']}
        if self.bayes:
            mean,cov=self._posterior()
            data['preference_model'].update(version='bayes-bt-1',feature_sd={n:round(float(v),3) for n,v in zip(self.feature_names,np.sqrt(np.diag(cov)))})
        data['note']=('Tuning search with a source tree. Pair 1: Cinematic pad Rising vs Evolving sets the motion (Both good / Neither keep Rising). '
            'Pairs 2-4: the six family faces in their most different pairs (Sparkle vs Cinematic pad, Voice vs Electric whine, Synth vs Dark ambience). '
            'Pairs 5-6: playoff between the opening winners: the winner is the family. Pairs 7-8: the family face against its two hand-made variants. '
            'Pair 9: the best of the family against the best sound of another family (runner-up check). Pairs 10-19: tuning pairs (the best sound against one change of it: pitch +-8 semitones first, '
            'then brightness and character; never below 80 Hz, pitch-up only up to 200 Hz) and challenger pairs (the best against an untried family '
            'face or variant, unchanged, picked by a Thompson sample). They take turns; once the best has beaten its own changes twice, every pair '
            'is a challenger, so tuning lasts only while it finds something. '
            'Changes that sounded small in the change test are not offered; the app skips pairs it measures as too similar. Each sound keeps its own '
            'effects. Preference model: Bayesian Bradley-Terry over one-hot settings (family, variant, pitch, brightness, character per family), '
            'N(0,1) prior, Laplace approximation; parents by posterior mean, changes ordered by a Thompson sample (half spread). Answers: Prefer A / B; Both good (tie, both beat a neutral sound); Neither (tie, '
            'both lose to it; the next pair builds on other sounds). Shortlist of 5 by posterior mean, at least 2 choices each, any two differ in '
            'family or in at least two settings. Pair 20 is a blind tuning check (the best sound vs the same variant untuned; tuning_check in the '
            'export), counted like any other choice. The listener picks, then answers yes/no: happy with this sound in their car.')
        return data


# Sound-map search (phase 1, 2026-11-16; open archive with two voices 2026-11-17): the same A/B session over a pool of generated sounds
# instead of hand-made families. Pool = tools/sound_map library: an open archive (no grid) of sounds that passed the psychoacoustic guardrail
# and the full-drive check and sound different from each other, made with the plain synth or the generic 'blocks' voice
# (desktop/src/mapVoice.ts); frozen in experiment/sound_map_pool.json. Built and played live in the app (levels.ts, kind 'map').
# Phase 2 (not built): grow new sounds around the listener's favourites between pairs.
from pathlib import Path
MAP_POLICY='source-map-v6'  # v1: plain synth, 90-box grid, features from synth settings; v2: two voices, open archive, dry;
# v3: searched effects, larger steps; v4: shortlist led by the model's best (not the champion); v5: middle-ring opening;
# v6: pair 1 = one central sound Rising vs Evolving; Evolving sessions use only sounds that also pass the guardrail in Evolving
MAP_POOL=Path(__file__).with_name('sound_map_pool.json')
def _centre(s):
    """Spectral centre: energy-weighted octave band (0 = under 100 Hz .. 7 = over 6.4 kHz), from the offline profile."""
    e=np.array(s['desc']['bands'])**2;return float(e@np.arange(len(e))/max(e.sum(),1e-12))
# Heard traits the model learns over, each scaled to 0..1: (name, getter, low, high, log scale). Same for both voices.
MAP_FEATURES=(('pitch',lambda s:s['rootHz'],80,200,1),('sharpness',lambda s:s['drive']['S'],.3,1.,0),('roughness',lambda s:s['drive']['R'],0,.3,0),
    ('pulsing',lambda s:s['drive']['F'],0,.4,0),('inharmonic',lambda s:s['desc']['inharm'],0,1,0),('centre',_centre,1,6,0),
    ('blocks',lambda s:float(s['voice']['kind']=='blocks'),0,1,0),('chorus',lambda s:s['fx'].get('chorus',0),0,2,0),
    ('vibrato',lambda s:s['fx'].get('vibDepth',0),0,8,0))
# Each feature enters as z and z^2 (z = 2x-1 in -1..1), so the model can learn "middle pitch is best", not only "higher is better".
MAP_FEATURE_NAMES=[f'{n}{p}' for n,*_ in MAP_FEATURES for p in ('','^2')]
MAP_OPENING=3      # pairs 1-3: six sounds spread around the middle ring of the pool
MAP_RING=(30,70)   # middle ring: percentiles of distance from the pool centre
MAP_PLAYOFF=2      # pairs 4-5: the opening winners against each other

def map_unit(sound):
    """Feature values of a pool sound, 0..1."""
    out=[]
    for _,get,lo,hi,log in MAP_FEATURES:
        v=min(max(get(sound),lo),hi);out.append(math.log(v/lo)/math.log(hi/lo) if log else (v-lo)/(hi-lo))
    return np.array(out)

def map_gap(a,b,step):
    """How different two pool sounds are, in 'distinct' steps on their most different heard trait (>= 1: distinct; = generate.gap)."""
    x,y=a['desc'],b['desc'];spectrum=float(np.linalg.norm(np.array(x['bands'])-np.array(y['bands']))/math.sqrt(2))
    return max(spectrum/step['spectrum'],abs(x['pitch']-y['pitch'])/step['pitch'],abs(x['inharm']-y['inharm'])/step['inharm'],
               abs(x['R']-y['R'])/step['R'],abs(x['F']-y['F'])/step['F'],
               *(abs(x.get(k,0)-y.get(k,0))/step[k] for k in ('chorus','vib') if k in step))

def map_recipe(sound,motion='rise'):
    """Pool sound -> live recipe (desktop/src/levels.ts MapRecipe v5): its voice and effects as the full-drive check played them."""
    return {'version':5,'kind':'map','seed':0,'motion':motion,'cell':sound['id'],'voice':sound['voice'],'fx':sound['fx']}

def load_map_pool(path=MAP_POOL):
    data=json.loads(Path(path).read_text())
    return data,[{**s,'unit':map_unit(s)} for s in data['sounds']]

class SoundMapDiscovery(TuningDiscovery):
    """20 direct choices over the generated sound map. Opening: six sounds spread across the map; playoff of the opening winners;
    then the best sound (posterior mean) against a challenger from the pool picked by a Thompson sample of the listener's taste.
    Same answers, model (Bayesian Bradley-Terry, here over audible features), shortlist and export as TuningDiscovery."""
    policy=MAP_POLICY
    feature_names=MAP_FEATURE_NAMES
    def __init__(self,renderer=None,pool_path=MAP_POOL):
        super().__init__(renderer);self.pool_path=pool_path;self.pool_meta=None;self.pool=None
    def _load(self):
        if self.pool is None:
            if not Path(self.pool_path).exists():raise ValueError('Sound map pool missing: run tools/sound_map/generate.py and drive.py library first')
            self.pool_meta,self.pool=load_map_pool(self.pool_path);self.by_cell={s['id']:s for s in self.pool}
            # Evolving check results (tools/sound_map/drive.py pool) narrow Evolving sessions to sounds that pass in Evolving too.
            # ponytail: without them every pool sound may play Evolving unchecked (gated in Rising only); run drive.py pool to gate it.
            lim=self.pool_meta['limits'];checked=any('driveEvolving' in s for s in self.pool)
            self.evolving_ok={s['id'] for s in self.pool if not checked or ('driveEvolving' in s and all(s['driveEvolving'][k]<=lim[k] for k in 'SRF'))}
    def start(self,motion=None):
        """motion None: pair 1 is one central sound Rising vs Evolving; the choice sets the motion."""
        self._load()
        with self.lock:self.champion=None;self.confirm=None;super().start(motion or (None if self.evolving_ok else 'rise'))
    def _space(self):return self.pool if self.motion=='rise' else [s for s in self.pool if s['id'] in self.evolving_ok]
    def _unit(self,recipe):return self.by_cell[recipe['cell']]['unit']
    def _features(self,recipe):z=2*self._unit(recipe)-1;return np.ravel(np.column_stack([z,z*z]))
    def _id(self,recipe):  # motion in the key only when Evolving, so Rising ids stay as in v1-v5
        return hashlib.sha256(json.dumps([recipe.get('voice',recipe.get('plain')),recipe['fx']]+([recipe['motion']] if recipe.get('motion')=='evolving' else []),sort_keys=True).encode()).hexdigest()[:32]
    def _label(self,recipe):
        s=self.by_cell[recipe['cell']]
        return f"{'Blocks' if s['voice']['kind']=='blocks' else 'Plain synth'} · {s['rootHz']:.0f} Hz · sharpness {s['drive']['S']:.2f}{' · Evolving' if recipe.get('motion')=='evolving' else ''} ({recipe['cell']})"
    def _distinct(self,a,b):return self.candidates[a]['recipe']['cell']!=self.candidates[b]['recipe']['cell']
    def _spread(self,count):
        """Opening sounds from the middle ring of the pool (distance from the pool centre between the 30th and 70th percentile), spread
        around the ring by farthest-point from a random first sound: different from each other, but not the odd sounds at the rim."""
        space=self._space();units=np.array([s['unit'] for s in space]);r=np.linalg.norm(units-units.mean(0),axis=1)
        ring=np.flatnonzero((r>=np.percentile(r,MAP_RING[0]))&(r<=np.percentile(r,MAP_RING[1])))
        if len(ring)<count:ring=np.argsort(np.abs(r-np.median(r)))[:count]
        picked=[int(ring[self.rng.randrange(len(ring))])]
        while len(picked)<count:
            gap=np.min(np.linalg.norm(units[ring][:,None,:]-units[picked][None,:,:],axis=2),axis=1);picked.append(int(ring[np.argmax(gap)]))
        return [space[i] for i in picked]
    def _set_motion(self,rows):winner=rows[0]['winner'];self.motion=self.candidates[winner]['recipe']['motion'] if winner else 'rise'  # Both good / Neither: Rising
    def _add_sound(self,sound,kind,summary):return self._add(map_recipe(sound,self.motion),{'kind':kind,'cell':sound['id'],'from':sound.get('from'),'summary':summary})
    def _proposals(self):
        self.check_parent=None;mp=self.motion_pairs;step=self.completed-mp;rows=self._choices()
        if mp and self.completed==0:  # the pool sound nearest the centre that passes in both modes
            both=[s for s in self.pool if s['id'] in self.evolving_ok];centre=np.mean([s['unit'] for s in self.pool],axis=0)
            s=min(both,key=lambda s:np.linalg.norm(s['unit']-centre));names={'rise':'Rising','evolving':'Evolving'}
            self.rematch=[self._add(map_recipe(s,m),{'kind':'motion','motion':m,'cell':s['id'],'summary':f"Motion: {names[m]} ({s['id']})"}) for m in ('rise','evolving')]
            return []
        if mp and self.completed==1:self._set_motion(rows)
        rows=rows[mp:]  # the opening and playoff count from the first pair after the motion pair
        if step==0:self.opening=[self._add_sound(s,'opening',f"Opening: {s['id']}") for s in self._spread(2*MAP_OPENING)]
        if step<MAP_OPENING:self.rematch=self.opening[2*step:2*step+2];return []
        ranked=self._ranked()
        winners=set()
        for r in rows[:MAP_OPENING]:winners|={r['winner']} if r['winner'] else set(r['pair']) if r['choice']=='good' else set()
        winners=[i for i in ranked if i in winners]
        if step==MAP_OPENING and len(winners)>=2:self.rematch=winners[:2];return []
        if step==MAP_OPENING+1 and len(winners)>=3:
            left=[i for i in winners if i not in rows[MAP_OPENING]['pair']]
            if left:self.rematch=[winners[0] if winners[0]!=left[0] else winners[1],left[0]];return []
        # Champion vs challenger (winner stays). A challenger that wins becomes champion and defends in the next pair; the model's
        # ranking only picks the first champion and the one after Neither (the best sound outside the rejected pair). Before
        # (2026-11-16 session): the champion was always the posterior-mean best, so a challenger that won was never heard again.
        rejected=set(rows[-1]['pair']) if rows and rows[-1]['choice']=='neither' else set()
        last=rows[-1] if rows else {}
        if self.champion is None or rejected:self.champion=next((i for i in ranked if i not in rejected),ranked[0])
        elif self.champion in last.get('pair',()) and last.get('winner') not in (None,self.champion):self.champion=last['winner']
        best=self.champion
        # Last pair: confirmation. The podium's #1 against #2 as they stand (model order among sounds heard at least twice), so the last
        # answer decides which of the top two leads. v3: the champion against the strongest sound it had not just met.
        if self.completed==STYLE_PAIRS-1:
            self._rank_finalists()
            if len(self.finalists)>=2:self.confirm={'first':self.finalists[0],'second':self.finalists[1]};self.rematch=self.finalists[:2];return []
        self._sample();heard={i for r in self._choices() for i in r['pair']};here=self.by_cell[self.candidates[best]['recipe']['cell']]
        pool=[s for s in self._space() if self._id(map_recipe(s,self.motion)) not in heard|self.excluded
              and map_gap(s,here,self.pool_meta['distinct'])>=1]  # never a near-copy of the best
        pool.sort(key=lambda s:-self._sampled(map_recipe(s,self.motion)))
        self.check_parent=best
        return [(map_recipe(s,self.motion),{'kind':'challenger','cell':s['id'],'from':s.get('from'),'summary':f"Challenger: {s['id']} (Thompson sample)"}) for s in pool]
    def _rank_finalists(self):
        """Shortlist as the tuning search: the model's best sounds among those heard at least twice lead. The confirmation pair's winner
        is still recorded as champion (export) but no longer forced to #1 (v3 did): in simulation one noisy last game often put a weaker
        sound first, while the model weighs every answer."""
        super()._rank_finalists();rows=self._choices();last=rows[-1] if rows else {}
        if self.confirm and set(last.get('pair',()))=={self.confirm['first'],self.confirm['second']} and last.get('winner'):self.champion=last['winner']
    def _bt_order(self):
        strength=dict(super()._bt_order());return [(i,strength[i]) for i in self.finalists]  # keep the shortlist order (champion first)
    def export(self):
        data=LevelDiscovery.export(self);mean,cov=self._posterior()
        data.update(motion=self.motion,pool={k:self.pool_meta.get(k) for k in ('created','source','limits')} if self.pool_meta else None,
                    champion=self.champion,confirmation=self.confirm)
        data['preference_model'].update(version='bayes-bt-map-2',feature_sd={n:round(float(v),3) for n,v in zip(self.feature_names,np.sqrt(np.diag(cov)))})
        data['note']=('Sound-map search (phase 1, v5). Pool: generated sounds from tools/sound_map: an open archive (no grid) of sounds made with the '
            'plain synth or the blocks voice (FM, noise band, waveshaper, amplitude modulation, inharmonic partials, resonant peaks), each kept only '
            'if it passed the guardrail (sharpness, roughness, pulsing, crowding) and the full 22 s Rising drive check and sounds different from all '
            'others (spectrum, pitch, inharmonicity, roughness, pulsing, chorus or vibrato; pool "distinct" steps). Effects searched per sound: tone, resonance, tremolo, reverb, chorus, vibrato (engine, up to 8 cents; half the sounds dry), body EQ. Rising only. Pairs 1-3: six sounds spread as far '
            'apart as the middle ring of the pool allows (distance from the pool centre between its 30th and 70th percentile; farthest-point in feature space from a random first sound). Pairs 4-5: playoff of the opening winners. Pairs 6-19: '
            'the champion against a challenger: the unheard pool sound with the highest Thompson-sampled utility (half spread), never a near-copy of '
            'the champion. Winner stays: a challenger that wins becomes champion and defends next. The first champion, and the champion after Neither '
            '(taken from outside the rejected pair), is the posterior-mean best. Pair 20: confirmation, shortlist #1 against #2 as they stand '
            '(champion and confirmation in the export). Shortlist: sounds heard at least twice, in model order (the confirmation winner is not forced first). Model: Bayesian Bradley-Terry '
            f'over {len(MAP_FEATURES)} heard traits (pitch, sharpness, roughness, pulsing, inharmonicity, spectral centre, voice, chorus, vibrato), each as z '
            'and z^2 so a middle value can be best; N(0,1) prior, Laplace approximation. Answers, shortlist and yes/no as the tuning search.')
        return data

MAP_REGIONS=6      # regions of the pool (k-means on the heard traits)
MAP_EXPLORE=10     # pairs 1-10 compare regions; pairs 11-19 search inside the listener's two best regions
MAP_FOCUS=.7       # share of focus challengers from the best region (the rest from the runner-up)

def map_regions(units,k=MAP_REGIONS,seed=0):
    """k-means (best of 20 seeded starts) on pool feature values: region label per sound and each region's most typical sound (closest to its centre)."""
    rng=np.random.default_rng(seed);best=None
    for _ in range(20):
        c=units[rng.choice(len(units),k,replace=False)]
        for _ in range(50):
            label=np.argmin(((units[:,None]-c[None])**2).sum(2),1);c=np.array([units[label==j].mean(0) if (label==j).any() else c[j] for j in range(k)])
        sse=float(((units-c[label])**2).sum())
        if best is None or sse<best[0]:best=(sse,label,c)
    _,label,c=best
    typical=[int(np.flatnonzero(label==j)[np.argmin(((units[label==j]-c[j])**2).sum(1))]) for j in range(k)]
    return label,typical

class RegionMapDiscovery(SoundMapDiscovery):
    """Sound map, broad then narrow. The pool is split into MAP_REGIONS regions. Pairs 1-3: each region's most typical sound (the same
    opening for every listener). Pairs 4-10: two regions per pair, picked by a Thompson sample of each region's win rate, each played by
    the model's Thompson-sampled best unheard sound of that region. Pairs 11-19: winner stays, challengers from the best region
    (MAP_FOCUS) or the runner-up; every two Neither answers in this stage open the next region. Pair 20 and shortlist as SoundMapDiscovery."""
    policy='source-map-regions-1'
    def _load(self):
        fresh=self.pool is None;super()._load()
        if fresh:
            label,typical=self._regions()
            self.region={s['id']:int(k) for s,k in zip(self.pool,label)};self.typical=[self.pool[i] for i in typical];self.n_regions=len(typical)
    def _regions(self):return map_regions(np.array([s['unit'] for s in self.pool]))
    region_names=None  # names per region for the export (styles); None: numbered
    def _region_record(self,rows):
        """Wins and losses per region over all answers: Both good is a win for both sounds' regions, Neither a loss for both."""
        w,l=np.zeros(self.n_regions),np.zeros(self.n_regions);reg=lambda i:self.region[self.candidates[i]['recipe']['cell']]
        for r in rows:
            a,b=r['pair']
            if reg(a)==reg(b):continue  # same region: says nothing about which region (a 2026-11-18 session ended with electric 14-14 from such pairs)
            if r['choice']=='good':w[reg(a)]+=1;w[reg(b)]+=1
            elif r['choice']=='neither':l[reg(a)]+=1;l[reg(b)]+=1
            elif r.get('winner'):w[reg(r['winner'])]+=1;l[reg(b if r['winner']==a else a)]+=1
        return w,l
    def _map_rows(self):return self._choices()[self.motion_pairs:]  # answers after the Rising vs Evolving pair
    def focus_regions(self,rows=None):
        """Regions in order of win rate (posterior mean, Beta(2,2) prior); the first two plus one more per two Neither answers after the region stage."""
        rows=self._map_rows() if rows is None else rows;w,l=self._region_record(rows)
        order=[int(k) for k in np.lexsort((-(w+l),-(w+2)/(w+l+4)))]  # prior 2 wins + 2 losses: a region with 2 lucky wins must not outrank one with 18-5 (2026-11-18)
        return order[:2+sum(r['choice']=='neither' for r in rows[MAP_EXPLORE:])//2]
    def _proposals(self):
        mp=self.motion_pairs
        if mp and self.completed==0:return super()._proposals()  # pair 1: Rising vs Evolving
        if mp and self.completed==1:self._set_motion(self._choices())
        self.check_parent=None;step=self.completed-mp;rows=self._map_rows();space=self._space()
        if step<MAP_OPENING:
            # Opening pairs: each typical sound with the one most different from it among those left.
            if step==0:  # Evolving: each region's typical sound among those that also pass in Evolving
                left=[min([s for s in space if self.region[s['id']]==self.region[t['id']]] or [t],key=lambda s:np.linalg.norm(s['unit']-t['unit'])) for t in self.typical];order=[]
                while left:
                    a=left.pop(0)
                    if left:b=max(left,key=lambda s:np.linalg.norm(s['unit']-a['unit']));left.remove(b)
                    else:b=max([s for s in space if s not in order and s is not a],key=lambda s:np.linalg.norm(s['unit']-a['unit']))  # odd region count: the sound most unlike the last one
                    order+=[a,b]
                while len(order)<2*MAP_OPENING:  # fewer regions than opening slots: the unheard sound most unlike those already in, and its opposite
                    rest=[s for s in space if s not in order]
                    a=max(rest,key=lambda s:min(np.linalg.norm(s['unit']-o['unit']) for o in order));rest.remove(a)
                    order+=[a,max(rest,key=lambda s:np.linalg.norm(s['unit']-a['unit']))]
                self.opening=[self._add_sound(s,'opening',f"Opening: region {self.region[s['id']]+1} ({s['id']})") for s in order]
            self.rematch=self.opening[2*step:2*step+2];return []
        if step<MAP_EXPLORE:
            w,l=self._region_record(rows);heard={i for r in self._choices() for i in r['pair']}|self.excluded;self._sample()
            pair=[]
            for k in sorted(range(self.n_regions),key=lambda k:-self.rng.betavariate(w[k]+1,l[k]+1)):
                left=[s for s in space if self.region[s['id']]==k and self._id(map_recipe(s,self.motion)) not in heard]
                if left:pair.append(max(left,key=lambda s:self._sampled(map_recipe(s,self.motion))))
                if len(pair)==2:break
            if len(pair)==2:
                self.rematch=[self._add_sound(s,'region',f"Region {self.region[s['id']]+1}: {s['id']} (Thompson sample)") for s in pair];return []
        options=super()._proposals()
        if self.rematch or self.completed==STYLE_PAIRS-1:return options
        focus=self.focus_regions(rows);best=[focus[0]] if self.rng.random()<MAP_FOCUS else focus[1:]
        for regions in (best,focus):
            kept=[o for o in options if self.region[o[1]['cell']] in regions]
            if kept:return kept
        return options
    def export(self):
        data=super().export();w,l=self._region_record(self._map_rows())
        data.update(regions={'count':self.n_regions,'names':self.region_names,'explore':MAP_EXPLORE,'focus':[k+1 for k in self.focus_regions()],
                             'wins':w.astype(int).tolist(),'losses':l.astype(int).tolist(),
                             'by_sound':{i:self.region[c['recipe']['cell']]+1 for i,c in self.candidates.items() if c['recipe'].get('cell') in self.region}})
        data['note']=data['note'].replace('Sound-map search (phase 1, v5).','Sound-map search (phase 1, regions v1). The pool is split into '
            f'{MAP_REGIONS} regions (k-means on the 9 traits). Pairs 1-3: each region\'s most typical sound. Pairs 4-{MAP_EXPLORE}: two regions per pair '
            '(Thompson sample of region win rates), each played by the model\'s best guess in that region. Pairs '
            f'{MAP_EXPLORE+1}-19: winner stays, challengers from the best region ({MAP_FOCUS:.0%}) or the runner-up; two Neither answers open the '
            'next region. Below: the v5 description, of which pair 20, the challenger rule, model and shortlist still apply.')
        return data

# Styles (2026-11-18): five texture families of the layered (stack) voice, = tools/sound_map/generate.py STYLES (stackVoice.ts STACK_TEXTURES ids).
MAP_STYLES={'electric':(9,10,11),'strings':(1,7,8),'glass':(3,4),'choir':(6,),'plain':(0,2)}
MAP_STYLE_NAMES=(*MAP_STYLES,'blend')
def map_style(sound):
    """Texture family of at least half the layers and more than any other family (= generate.style_of), else 'blend'; None for other voices.
    Blend is kept as its own style: the owner's favourite of 2026-11-18 was one (hollow, strings, plain, plain synth, electric)."""
    if sound['voice']['kind']!='stack':return None
    st=sound['voice']['stack'];layers=st['timbres'][:st['layers']]
    count=sorted(((sum(t in fam for t in layers),name) for name,fam in MAP_STYLES.items()),reverse=True)
    return count[0][1] if 2*count[0][0]>=len(layers) and count[0][0]>count[1][0] else 'blend'

class StyleMapDiscovery(RegionMapDiscovery):
    """Regions session with the pool's texture styles as regions (instead of k-means): pairs 1-3 play each style's most typical sound,
    pairs 4-10 compare styles, pairs 11-19 stay in the best style (MAP_FOCUS) or the runner-up. The model also learns the style
    (one-hot, beside the 9 traits). Blend (no family leads) is a style of its own. Styles with no pool sound are left out."""
    policy='source-map-styles-1'
    feature_names=MAP_FEATURE_NAMES+[f'style:{n}' for n in MAP_STYLE_NAMES]
    def _regions(self):
        names=[n for n in MAP_STYLE_NAMES if any(map_style(s)==n for s in self.pool)]
        if len(names)<2:return super()._regions()  # not a layered pool: k-means regions
        self.region_names=names;label=np.array([names.index(map_style(s)) if map_style(s) in names else 0 for s in self.pool]);units=np.array([s['unit'] for s in self.pool])
        typical=[int(min(np.flatnonzero(label==k),key=lambda i:np.linalg.norm(units[i]-units[label==k].mean(0)))) for k in range(len(names))]
        return label,typical
    def _features(self,recipe):
        style=map_style(self.by_cell[recipe['cell']]);return np.concatenate([super()._features(recipe),[float(style==n) for n in MAP_STYLE_NAMES]])
    def export(self):
        data=super().export()
        data['note']=data['note'].replace(f'The pool is split into {self.n_regions} regions (k-means on the 9 traits).',
            f'The pool is split by texture style ({", ".join(self.region_names or [])}); the model also learns the style.')
        return data
