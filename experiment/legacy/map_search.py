"""Sound map sessions (legacy, moved here 2026-11-27): Region map, Style map and Heard map searches over the generated sound pool
(tools/sound_map). No longer offered in the app (the app offers Best guess and Building blocks); kept for the record and for
tools/benchmark_sound_map.py. Their base class SoundMapDiscovery stays in experiment/source_search.py: Building blocks inherits from it."""
import random

import numpy as np

from experiment.source_search import *  # noqa: F401,F403  (the base classes and MAP_* constants these sessions build on)

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
    opening_pairs=MAP_OPENING  # HeardMapDiscovery on a grid pool: 2 (pitch only)
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
        if step<self.opening_pairs:
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
        if self.rematch or self.completed==self.pairs-1:return options
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
MAP_FINE_PAIRS=3  # phase 2: pairs 17-19 fine-tune the champion with its checked variations (pair 20 stays the top-two confirmation)
MAP_OPPOSITE={'brighter':'darker','darker':'brighter','deeper':'higher','higher':'deeper','fuller':'thinner','thinner':'fuller',
              'smoother':'shimmer','shimmer':'smoother','body+':'body-','body-':'body+'}
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
    def _load(self):
        fresh=self.pool is None;super()._load()
        if fresh:  # phase 2: checked variations of each pool sound (tools/sound_map/variations.py), playable but never in the phase-1 space
            lim=self.pool_meta['limits']
            for parent in self.pool:
                for v in parent.get('variations',[]):
                    v['unit']=map_unit(v);self.by_cell[v['id']]=v;self.region[v['id']]=self.region[parent['id']]
                    if all(v['driveEvolving'][k]<=lim[k] for k in 'SRF'):self.evolving_ok.add(v['id'])
    def move_trends(self):
        """Phase 2: +1 for each move of a variation that won (and -1 for its opposite), -1 for each move of one that lost."""
        trend={}
        for r in self._choices():
            if not r.get('winner'):continue
            for i in r['pair']:
                move=self.by_cell.get(self.candidates[i]['recipe']['cell'],{}).get('move')
                for m in (move.split('+') if move else []):
                    m=m.rstrip('2')  # ladder: two steps brighter counts as brighter
                    sign=1 if i==r['winner'] else -1;trend[m]=trend.get(m,0)+sign
                    if m in MAP_OPPOSITE:trend[MAP_OPPOSITE[m]]=trend.get(MAP_OPPOSITE[m],0)-sign
        return trend
    def _proposals(self):
        options=super()._proposals()
        if self.rematch or not self.pairs-1-MAP_FINE_PAIRS<=self.completed<self.pairs-1 or self.champion is None:return options
        # Phase 2 (pairs 17-19): the champion against a variation of it (or of its parent, when the champion is itself a variation);
        # layer swaps last, then moves that have been winning, then the model's Thompson sample. Winner stays as before.
        here=self.by_cell[self.candidates[self.champion]['recipe']['cell']];parent=self.by_cell.get(here.get('parent'),here)
        heard={i for r in self._choices() for i in r['pair']}|self.excluded;trend=self.move_trends();self._sample()
        step2=lambda v:(v.get('move') or '').endswith('2') and not (v['move'] or '').startswith('swap')
        left=[v for v in [parent,*parent.get('variations',[])] if v['id']!=here['id'] and (self.motion=='rise' or v['id'] in self.evolving_ok)
              and self._id(map_recipe(v,self.motion)) not in heard and (not step2(v) or here.get('move')==v['move'][:-1] or not any(w.get('move')==v['move'][:-1] for w in parent.get('variations',[])))]
        # ladder: 2 steps only after 1 won (or when the parent has no checked first step: then 2 steps is its first)
        if not left:return options  # no variations (pool without phase 2): the phase-1 challenger
        # layer swaps last: they change the least (0.29-0.36 'distinct' steps) and twice took 11 plays to call (2026-11-20)
        score=lambda v:(not (v.get('move') or '').startswith('swap'),sum(trend.get(m,0) for m in v['move'].split('+')) if v.get('move') else 0,self._sampled(map_recipe(v,self.motion)))
        left.sort(key=score,reverse=True)
        return [(map_recipe(v,self.motion),{'kind':'variation','cell':v['id'],'from':parent['id'],'move':v.get('move','original'),
                 'summary':f"Variation of {parent['id']}: {v.get('move','original')}"}) for v in left]
    def _regions(self):
        names=[n for n in MAP_STYLE_NAMES if any(map_style(s)==n for s in self.pool)]
        if len(names)<2:return super()._regions()  # not a layered pool: k-means regions
        self.region_names=names;label=np.array([names.index(map_style(s)) if map_style(s) in names else 0 for s in self.pool]);units=np.array([s['unit'] for s in self.pool])
        typical=[int(min(np.flatnonzero(label==k),key=lambda i:np.linalg.norm(units[i]-units[label==k].mean(0)))) for k in range(len(names))]
        return label,typical
    def _features(self,recipe):
        style=map_style(self.by_cell[recipe['cell']]);return np.concatenate([super()._features(recipe),[float(style==n) for n in MAP_STYLE_NAMES]])
    def export(self):
        data=super().export();data['phase2']={'pairs':MAP_FINE_PAIRS,'move_trends':self.move_trends(),
            'variations_heard':{i:{'parent':self.by_cell[c['recipe']['cell']].get('parent'),'move':self.by_cell[c['recipe']['cell']].get('move')}
                                for i,c in self.candidates.items() if self.by_cell.get(c['recipe'].get('cell'),{}).get('move')}}
        split=self._split_note()
        if split:data['note']=data['note'].replace(f'The pool is split into {self.n_regions} regions (k-means on the 9 traits).',split)
        return data
    def _split_note(self):return f'The pool is split by texture style ({", ".join(self.region_names)}); the model also learns the style.' if self.region_names else None

MAP_GRID=[f'{r}-{b}' for r in ('deep','middle','high') for b in ('dark','bright')]
MAP_REPEATS={11:'clear'}  # completed pairs -> repeat kind: pair 12 replays an opening pair (grid: pair 3, the pitch winner vs middle). 2026-11-20: the
# second repeat (closest call, pair 16) was dropped: it cut into the champion run
MAP_BALANCED_S=.55  # acum: grid opening pitch pairs match brightness here, a level every band reaches (deep .46-.82, middle .44-.85, high .45-1.0)
MAP_REPEAT_GAP=5  # a repeat comes at least 5 pairs after its original, so memory does not decide it

class HeardMapDiscovery(StyleMapDiscovery):
    """StyleMapDiscovery (opening, focus, phase 2 variations) split by what is heard, with no style input to the model. Styles dropped as
    the session split on 2026-11-19: on a blind same/different test the listener could not tell styles apart (4/12, chance 6) once
    register and brightness were matched; the sound's style stays in the pool data. A grid pool (build_pool.py --grid: every sound has a
    'cell', deep/middle/high body note x dark/bright) is split by its cells; any other pool by k-means on the heard traits."""
    policy='source-map-heard-1'
    feature_names=MAP_FEATURE_NAMES
    repeats=();_repeat_order=None
    def _regions(self):
        if not all('cell' in s for s in self.pool):return RegionMapDiscovery._regions(self)
        self.region_names=[c for c in MAP_GRID if any(s['cell']==c for s in self.pool)]
        label=np.array([self.region_names.index(s['cell']) for s in self.pool]);units=np.array([s['unit'] for s in self.pool])
        typical=[int(min(np.flatnonzero(label==k),key=lambda i:np.linalg.norm(units[i]-units[label==k].mean(0)))) for k in range(len(self.region_names))]
        return label,typical
    def _split_note(self):
        if not self.region_names:return None
        return (f'The pool is split into a grid ({", ".join(self.region_names)}): body note deep/middle/high x dark/bright. Opening, pitch only '
                f'(2026-11-20, replaces the six typical sounds): deep vs high, then that winner vs middle (balanced brightness, about {MAP_BALANCED_S} acum, '
                'other traits near the pool middle; a pitch answer counts for both cells of each band). No dark vs bright pair: brightness is left to '
                'exploring and the tuning copies.')
    def start(self,motion=None):
        with self.lock:self.repeats=[];self._repeat_order=None
        super().start(motion)
    def _grid(self):return all('cell' in s for s in self.pool)
    def _sound(self,ident):return self.by_cell[self.candidates[ident]['recipe']['cell']]
    def _cell(self,ident):return self.region_names[self.region[self.candidates[ident]['recipe']['cell']]]  # a variation: its parent's cell
    def _balanced(self,band):
        """The band's sound with brightness at MAP_BALANCED_S, pitch at the band's median and every other trait nearest the pool's middle."""
        here=[s for s in self._space() if s['cell'].startswith(band+'-')]
        target=np.mean([s['unit'] for s in self.pool],axis=0);target[1]=(MAP_BALANCED_S-.3)/.7  # sharpness unit (MAP_FEATURES: .3-1 acum)
        target[0]=float(np.median([s['unit'][0] for s in here]))  # pitch: the band's middle, not its edge
        near=[s for s in here if abs(s['drive']['S']-MAP_BALANCED_S)<=.03] or sorted(here,key=lambda s:abs(s['drive']['S']-MAP_BALANCED_S))[:3]  # brightness first
        weight=np.ones(len(target));weight[0]=4  # then pitch, then the other traits
        return min(near,key=lambda s:float(weight@(s['unit']-target)**2))
    @property
    def opening_pairs(self):return 2 if self._grid() else MAP_OPENING
    def _kept(self,row):return row['winner'] if row.get('winner') else max(row['pair'],key=self._utility)  # Both good / Neither: the model's higher
    def _grid_opening(self,step,rows):
        """Grid opening, pitch only (2026-11-20). Pair 2: deep vs high, pair 3: that winner vs middle, all three with balanced brightness
        (MAP_BALANCED_S) and other traits near the pool middle. Both good: the model's higher of the two goes on (both stay in play: the
        model learns both beat a neutral sound). Neither on pair 2: the one nearer middle in pitch goes on. The dark vs bright pair 4 was
        dropped: in the brightness listening check (2026-11-20) the owner heard sharpness gaps under about 0.09 acum as the same and
        marked every step from 0.42 to 0.86 acum acceptable, and the middle band's typical dark and bright sounds were only 0.08 apart.
        Brightness is left to exploring and to the tuning copies."""
        if step==0:sounds=[self._balanced('deep'),self._balanced('high')]
        else:
            r=rows[0];mid=self._balanced('middle')
            keep=self._kept(r) if r['choice']!='neither' else min(r['pair'],key=lambda i:abs(self._sound(i)['unit'][0]-mid['unit'][0]))
            sounds=[self._sound(keep),mid]
        return [self._add_sound(s,'pitch',f"Opening (pitch): {s['cell']} ({s['id']})") for s in sounds]
    def _region_record(self,rows):
        """Grid: a pitch pair (pair 2, 3 and the replay) counts for both cells of each band, not only the matched sound's cell."""
        if not self._grid():return super()._region_record(rows)
        w,l=np.zeros(self.n_regions),np.zeros(self.n_regions)
        def cells(i,pitch):
            c=self._cell(i);return {k for k,n in enumerate(self.region_names) if n.split('-')[0]==c.split('-')[0]} if pitch else {self.region_names.index(c)}
        for r in rows:
            a,b=r['pair'];pitch=all(self.candidates[i].get('origin',{}).get('kind')=='pitch' for i in (a,b));A,B=cells(a,pitch),cells(b,pitch)
            if A==B:continue
            for k in (A|B if r['choice'] in ('good','neither') else ()):(w if r['choice']=='good' else l)[k]+=1
            if r.get('winner'):
                for k in (A if r['winner']==a else B):w[k]+=1
                for k in (B if r['winner']==a else A):l[k]+=1
        return w,l
    def _proposals(self):
        mp=self.motion_pairs;step=self.completed-mp
        if self._grid() and 0<=step<self.opening_pairs and not (mp and self.completed==0):
            if mp and self.completed==1:self._set_motion(self._choices())
            self.check_parent=None;self.rematch=self._grid_opening(step,self._map_rows());return []
        options=super()._proposals()  # first, so the champion still follows the last focus answer
        kind=MAP_REPEATS.get(self.completed)
        if self.rematch or kind is None:return options
        rows=self._choices();done={r['of'] for r in self.repeats}
        old=[(n,r) for n,r in enumerate(rows) if n<=self.completed-MAP_REPEAT_GAP and n>=self.motion_pairs and n not in done
             and len(set(r['pair']))==2 and not any(r['pair']==x['pair'][::-1] for x in self.repeats)]
        # 'clear': grid: the pitch pair with the middle (pair 3), which always holds the listener's pitch choice; deep vs high (pair 2) can be
        # two sounds they both reject (2026-11-20: answered deep then high, after middle beat both). Other pools: the first opening pair.
        old=[(n,r) for n,r in old if n==self.motion_pairs+(1 if self._grid() else 0)];key=lambda nr:nr[0]
        if not old:return options
        n,row=min(old,key=key)
        self.repeats.append({'at':self.completed,'of':n,'kind':kind,'pair':row['pair'][::-1]})
        if self.champion_starts and self.champion_starts[-1]['pair']==self.completed+1:self.champion_starts[-1]['pair']+=1  # it defends from the pair after the repeat
        self._repeat_order=row['pair'][::-1];self.rematch=list(row['pair']);return []
    def _prepare(self):
        super()._prepare()
        if self._repeat_order and set(self.pair)==set(self._repeat_order):self.pair=list(self._repeat_order)  # repeat: A and B swapped
        self._repeat_order=None
    def export(self):
        data=super().export();rows=self._choices()
        same=lambda a,b:(a['winner'] is not None and a['winner']==b['winner']) or (a['winner'] is None and a['choice']==b['choice'])
        data['repeats']=[{**r,'first':rows[r['of']]['choice'],'again':rows[r['at']]['choice'],'agree':same(rows[r['of']],rows[r['at']])}
                         for r in self.repeats if r['at']<len(rows)]
        data['note']+=(f' Repeats: pairs {", ".join(str(k+1) for k in sorted(MAP_REPEATS))} replay an earlier pair (A and B swapped, at least '
                       f'{MAP_REPEAT_GAP} pairs later): grid: pair 3 (pitch winner vs middle), else the first opening pair; both answers count, and agreement is exported.')
        return data
    def focus_regions(self,rows=None):
        """Grid: the best cell first, then the runner-up and every neighbour of the best cell (one step in register or in brightness), so
        the focus stage can cross a cell line where the taste sits near it (soft cells, 2026-11-19). Far cells only via Neither answers."""
        order=super().focus_regions(rows)
        if not self.region_names:return order
        reg=lambda k:self.region_names[k].split('-');R=('deep','middle','high');(r0,b0)=reg(order[0])
        near=[k for k in range(self.n_regions) if k not in order and ((reg(k)[0]==r0)!=(reg(k)[1]==b0)) and abs(R.index(reg(k)[0])-R.index(r0))<=1]
        return order+near
    def _features(self,recipe):return RegionMapDiscovery._features(self,recipe)
