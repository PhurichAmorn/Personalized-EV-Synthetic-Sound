import random,unittest
from experiment.source_search import make_recipe,SourceDiscovery

class SourceSearchTest(unittest.TestCase):
    def test_broad_recipe_follows_scheduled_family_and_layer_count(self):
        from experiment.source_search import make_broad_recipe
        recipe=make_broad_recipe(random.Random(9),'airy',3)
        self.assertEqual(len(recipe['layers']),3)
        self.assertEqual(recipe['layers'][0]['method'],'airy')
        self.assertEqual(len({layer['method'] for layer in recipe['layers']}),3)

    def test_broad_recipes_have_multiple_structures(self):
        recipes=[make_recipe(random.Random(i)) for i in range(30)]
        self.assertGreater(len({tuple(layer['method'] for layer in r['layers']) for r in recipes}),15)
        self.assertTrue(all(1<=len(r['layers'])<=3 for r in recipes))

    def test_both_sounds_of_a_pair_render_at_the_same_time(self):
        import threading,time
        running=0;peak=0;lock=threading.Lock()
        def render(recipe):
            nonlocal running,peak
            with lock:running+=1;peak=max(peak,running)
            time.sleep(.2)
            with lock:running-=1
            return {'id':str(recipe['seed'])+recipe['layers'][0]['method'],'label':'test','recipe':recipe,'urls':[],'checks':[]}
        discovery=SourceDiscovery(renderer=render);self.addCleanup(discovery.close)
        started=time.monotonic();discovery.start()
        while discovery.snapshot()['busy']:time.sleep(.01)
        self.assertEqual(len(discovery.snapshot()['pair']),2)
        self.assertEqual(peak,2)
        self.assertLess(time.monotonic()-started,.35)  # one parallel batch, not two sequential renders

    def test_finish_stops_session_and_export_is_a_copy(self):
        import hashlib,json,time
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test','urls':[],'traces':{}}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(len(d.pair),2)
        pair=d.pair.copy()
        for ident in pair:d.heard(ident)
        d.finish();self.assertFalse(d.active)
        result=d.export();result['candidates'].clear();self.assertTrue(d.candidates)

    def test_only_finalists_can_be_chosen(self):
        d=SourceDiscovery(renderer=lambda recipe: {});self.addCleanup(d.close)
        d.candidates['candidate-0']={'id':'candidate-0','label':'c','recipe':make_recipe(random.Random(0))}
        with self.assertRaises(ValueError):d.finish('unknown')
        with self.assertRaises(ValueError):d.finish('candidate-0')  # Only ranked finalists can be chosen.
        d.finalists=['candidate-0'];d.finish('candidate-0');self.assertEqual(d.final,'candidate-0')

    def test_render_failures_never_reach_the_pair(self):
        import time
        def fail(recipe):raise ValueError('signal check rejected')
        d=SourceDiscovery(renderer=fail);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(d.pair,[]);self.assertTrue(d.error);self.assertTrue(d.quarantine)

    def test_hearing_conditions_must_match_before_feedback(self):
        d=SourceDiscovery(renderer=lambda recipe:{});self.addCleanup(d.close)
        d.candidates={k:{'id':k,'label':k,'recipe':make_recipe(random.Random(i))} for i,k in enumerate(['a','b'])}
        d.pair=['a','b'];d.active=True
        ctx={'input':'live','style':'rise','volume':.7,'response':'exponential','spatial':True}
        d.heard('a',{**ctx,'candidateId':'a'})
        d.heard('b',{**ctx,'candidateId':'b','volume':.5})
        self.assertEqual(d.tried,{'b'})
        with self.assertRaises(ValueError):d.feedback('A',ctx)
        with self.assertRaises(ValueError):d.heard('a',{**ctx,'candidateId':'wrong'})
        with self.assertRaises(ValueError):d.heard('a',{**ctx,'volume':0})

    def test_synthetic_session_reaches_structural_proposals_and_exports(self):
        import hashlib,json,time
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test','urls':[],'traces':{}}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        for turn in range(8):
            deadline=time.monotonic()+3
            while d.busy and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(d.error);self.assertEqual(len(d.pair),2)
            for ident in d.pair:d.heard(ident)
            d.feedback({'A':4+turn%3,'B':4})
        d.finish()
        result=d.export()
        self.assertEqual(len(result['history']),8)
        self.assertTrue(any(c['recipe']['seed'] for c in result['candidates'].values()))

    def test_broad_search_balances_families_and_arrangements_with_capped_anchor_reuse(self):
        import hashlib,json,time
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test','urls':[],'traces':{}}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        for _ in range(9):
            deadline=time.monotonic()+3
            while d.busy and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(d.error);self.assertEqual(len(d.pair),2)
            recipes=[d.candidates[ident]['recipe'] for ident in d.pair]
            self.assertEqual(len({recipe['layers'][0]['method'] for recipe in recipes}),2)
            self.assertEqual(len({len(recipe['layers']) for recipe in recipes}),1,'Hold layer count constant within each A/B pair')
            self.assertEqual([layer['method'] for layer in recipes[0]['layers'][1:]],[layer['method'] for layer in recipes[1]['layers'][1:]],'Hold supporting families constant within each A/B pair')
            for ident in d.pair:d.heard(ident)
            d.feedback({'A':5,'B':3})
        shown=[ident for row in d.history for ident in row['pair']]
        self.assertLessEqual(max(shown.count(ident) for ident in shown),3,'Returning anchors are capped at three ratings')
        families={method:0 for method in ('bowed','rounded','vocal','glass','resonant','airy')}
        structures={count:0 for count in (1,2,3)}
        for ident in shown:
            recipe=d.candidates[ident]['recipe']
            families[recipe['layers'][0]['method']]+=1
            structures[len(recipe['layers'])]+=1
        # Exposure floor: the least-exposed family always takes a slot. Measured over 40 sessions: min 2, spread <= 2.
        self.assertGreaterEqual(min(families.values()),2,'Every foundation family keeps at least two sounds within nine pairs')
        self.assertLessEqual(max(families.values())-min(families.values()),2)
        self.assertGreater(structures[2],0);self.assertGreater(structures[3],0)
        self.assertLessEqual(max(structures.values())-min(structures.values()),2)

    def test_last_rated_pair_starts_playoff_without_preparing_another_pair(self):
        from experiment.source_search import MAX_COMPARISONS
        d=SourceDiscovery(renderer=lambda recipe: self.fail('No new pair after session limit'));self.addCleanup(d.close)
        d.active=True;d.completed=MAX_COMPARISONS-1
        d.candidates={'a':{'id':'a','label':'a','recipe':make_recipe(random.Random(1))},'b':{'id':'b','label':'b','recipe':make_recipe(random.Random(2))}}
        d.pair=['a','b']
        d.heard('a');d.heard('b')
        d.feedback({'A':5,'B':3})
        self.assertEqual(d.completed,MAX_COMPARISONS)
        self.assertEqual(d.stage,'playoff');self.assertFalse(d.busy);self.assertEqual(set(d.pair),{'a','b'})
        self.assertEqual(len(d.export()['history']),1)

    def test_playoff_round_robin_orders_finalists_by_bradley_terry(self):
        from experiment.source_search import MAX_COMPARISONS,PLAYOFF_PAIRS,FINALIST_COUNT
        d=SourceDiscovery(renderer=lambda recipe: self.fail('No new pair after discovery'));self.addCleanup(d.close)
        d.active=True;d.completed=MAX_COMPARISONS-1
        ids=['a','b','c','d','e']
        d.candidates={i:{'id':i,'label':i,'recipe':make_recipe(random.Random(n)),'ratings':[7-n]} for n,i in enumerate(ids)}
        d.history=[{'pair':['a','b']},{'pair':['c','d']},{'pair':['e','a']}]
        d.pair=['d','e'];d.heard('d');d.heard('e')
        d.feedback({'A':5,'B':3})
        self.assertEqual(d.stage,'playoff');self.assertEqual(len(d.finalists),FINALIST_COUNT)
        self.assertEqual(len(d.playoff_queue)+1,PLAYOFF_PAIRS)
        best=d.finalists[-1]  # lowest-rated finalist wins every game: playoff must override ratings
        with self.assertRaises(ValueError):d.playoff_feedback('neither')
        seen=set()
        while d.stage=='playoff':
            pair=tuple(sorted(d.pair));self.assertNotIn(pair,seen);seen.add(pair)
            d.heard(d.pair[0]);d.heard(d.pair[1])
            d.playoff_feedback('A' if d.pair[0]==best else 'B' if d.pair[1]==best else 'equal')
        self.assertEqual(len(seen),PLAYOFF_PAIRS);self.assertFalse(d.active)
        self.assertEqual(d._bt_order()[0][0],best)
        with self.assertRaises(ValueError):d.finish('unknown')
        d.finish(best);self.assertEqual(d.final,best)
        self.assertEqual(len(d.export()['playoff_history']),PLAYOFF_PAIRS)

    def test_finalist_ties_break_reproducibly_by_session_seed(self):
        def session(order):
            d=SourceDiscovery(renderer=lambda recipe:{});d.seed=123
            ids=[f'c{i}' for i in range(8)]
            d.candidates={i:{'id':i,'label':i,'recipe':make_recipe(random.Random(n)),'ratings':[6]} for n,i in enumerate(ids)}
            d.history=[{'pair':[a,b]} for a,b in zip(order[::2],order[1::2])]
            d._rank_finalists();d.close();return d.finalists
        ids=[f'c{i}' for i in range(8)]
        self.assertEqual(session(ids),session(ids[::-1]))
        self.assertEqual(len(set(session(ids))),4)

    def test_companion_tuning_is_a_listener_checked_option(self):
        from experiment.source_search import make_broad_recipe,COMPANION_SUB_FAMILIES,METHODS
        seen=set()
        for i in range(60):
            for layer in make_broad_recipe(random.Random(i),METHODS[i%6],2)['layers']:
                value=layer['shape'].get('companionSub')
                if layer['method'] in COMPANION_SUB_FAMILIES:self.assertIn(value,(0.,1.));seen.add(value)
                else:self.assertIsNone(value)
        self.assertEqual(seen,{0.,1.})
        self.assertNotIn('companionSub',make_recipe(random.Random(0),'glass')['layers'][0]['shape'],'References keep the original tuning')

    def test_failed_next_pair_cannot_reuse_previous_votes(self):
        import hashlib,json,time
        calls=0
        def render(recipe):
            nonlocal calls
            calls+=1
            if calls>2:raise ValueError('rejected')
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test'}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        for ident in d.pair:d.heard(ident)
        d.feedback({'A':5,'B':3})
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertTrue(d.error);self.assertEqual(d.pair,[])
        with self.assertRaises(ValueError):d.feedback({'A':3,'B':5})

    def test_similar_audio_is_blocked_even_when_recipes_differ(self):
        import hashlib,json,time
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test','audio_descriptor':[1.,0.,0.]}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(d.pair,[])
        self.assertTrue(d.error)

    def test_session_runs_fourteen_rated_pairs_then_six_playoff_pairs(self):
        import hashlib,json,time
        from experiment.source_search import MAX_COMPARISONS,PLAYOFF_PAIRS,FINALIST_COUNT
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test'}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        for turn in range(MAX_COMPARISONS):
            deadline=time.monotonic()+3
            while d.busy and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(d.error);self.assertEqual(len(d.pair),2);self.assertEqual(d.stage,'discovery')
            kinds=[d.candidates[i]['recipe']['layers'][0]['method'] for i in d.pair]
            self.assertEqual(len(set(kinds)),2)
            for ident in d.pair:d.heard(ident)
            d.feedback({'A':3+turn%4,'B':4+turn%3})
        self.assertEqual(d.stage,'playoff');self.assertEqual(len(d.finalists),FINALIST_COUNT)
        for _ in range(PLAYOFF_PAIRS):
            for ident in d.pair:d.heard(ident)
            d.playoff_feedback('A')
        self.assertEqual(d.stage,'done');self.assertFalse(d.active)
        self.assertEqual(len(d.playoff_history),PLAYOFF_PAIRS)
        d.finish(d._bt_order()[0][0]);self.assertIsNotNone(d.final)

    def test_recent_audio_similarity_blocks_new_ids(self):
        import hashlib,json,time
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            return {'id':ident,'recipe':recipe,'label':'test','audio_descriptor':[1.,0.,0.]}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close)
        d.active=True;d.completed=12;d.rng=random.Random(4)
        old=render(make_recipe(d.rng,'bowed'));d.candidates[old['id']]=old
        d.history=[{'pair':[old['id'],old['id']],'answer':'neither'}]
        with d.lock:d._prepare()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(d.pair,[]);self.assertTrue(d.error)
        self.assertTrue(d.diversity_skips)
        self.assertEqual(d.quarantine,[],'Similarity is not a technical failure or dislike label')

    def test_generated_sources_vary_continuous_controls_and_foundation_pitch(self):
        recipes=[make_recipe(random.Random(i)) for i in range(30)]
        self.assertGreater(len({round(r['layers'][0]['shape']['rootRatio'],2) for r in recipes}),10)
        self.assertGreater(len({round(r['layers'][0]['controls']['character'],2) for r in recipes}),10)

    def test_opening_pair_replaces_similar_reference_instead_of_retrying_forever(self):
        import hashlib,json,time
        from experiment.source_search import METHODS
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            descriptor=[0.]*7
            index=6 if recipe['seed'] else METHODS.index(recipe['layers'][0]['method'])
            if recipe['seed']==0 and recipe['layers'][0]['method']=='airy':index=4
            descriptor[index]=1.
            return {'id':ident,'recipe':recipe,'label':'test','audio_descriptor':descriptor}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        for turn in range(3):
            deadline=time.monotonic()+2
            while d.busy and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(d.error);self.assertEqual(len(d.pair),2)
            if turn<2:
                for ident in d.pair:d.heard(ident)
                d.feedback({'A':4,'B':4})
        self.assertTrue(d.diversity_skips)
        self.assertTrue(any(d.candidates[i]['recipe']['seed'] for i in d.pair),'A new varied source replaces the similar reference')
        self.assertFalse(d.quarantine,'Similarity must remain separate from signal faults')

    def test_preparation_error_identifies_similarity_not_signal_failure(self):
        import hashlib,json,time
        def render(recipe):
            return {'id':hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest(),'recipe':recipe,'label':'test','audio_descriptor':[1.,0.]}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertIn('too similar',d.error.lower())
        self.assertIn('0 rendering/check failures',d.error)

    def test_retry_offers_new_fallbacks_after_exhausted_opening_batch(self):
        import hashlib,json,time
        blocked=set();failing=True
        def render(recipe):
            ident=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32]
            if failing:blocked.add(ident)
            if ident in blocked:raise ValueError('signal check withheld this recipe')
            return {'id':ident,'recipe':recipe,'label':'test'}
        d=SourceDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertTrue(d.error);self.assertIn('signal check withheld this recipe',d.error)
        failing=False
        with d.lock:d._prepare()
        deadline=time.monotonic()+2
        while d.busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertFalse(d.error);self.assertEqual(len(d.pair),2)
        self.assertTrue(blocked.isdisjoint(d.pair))


def make_open_recipe_for_test():
    from experiment.source_search import make_open_recipe
    return make_open_recipe(random.Random(3),2)

class OpenDiscoveryTest(unittest.TestCase):
    def test_open_session_runs_to_finalists_with_only_open_blocks(self):
        import json,time
        from experiment.source_search import OpenDiscovery,MAX_COMPARISONS,PLAYOFF_PAIRS
        def render(recipe):
            rng=random.Random(json.dumps(recipe,sort_keys=True));d=[rng.random() for _ in range(12)];total=sum(d)
            return {'id':str(abs(hash(json.dumps(recipe,sort_keys=True)))),'label':'test','recipe':recipe,'urls':[],'checks':[],'audio_descriptor':[x/total for x in d]}
        d=OpenDiscovery(renderer=render);self.addCleanup(d.close);d.start()
        for turn in range(MAX_COMPARISONS):
            while d.busy:time.sleep(.002)
            self.assertFalse(d.error,d.error);self.assertEqual(len(d.pair),2)
            self.assertTrue(all(layer['method']=='blocks' for i in d.pair for layer in d.candidates[i]['recipe']['layers']))
            for i in d.pair:d.heard(i)
            if d.snapshot()['pairMode']=='choice':
                with self.assertRaises(ValueError):d.feedback({'A':7,'B':2})  # parent checks take a choice, not ratings
                d.feedback(choice='A')
            else:d.feedback({'A':7,'B':2})
        self.assertEqual(d.stage,'playoff');self.assertEqual(len(d.finalists),4)
        for _ in range(PLAYOFF_PAIRS):
            for i in d.pair:d.heard(i)
            d.playoff_feedback('A')
        self.assertEqual(d.stage,'done')
        result=d.export();self.assertEqual(result['policy'],'source-open-groups-gp-v4')
        origins=[c['origin'] for c in result['candidates'].values()]
        self.assertTrue(all(o['kind'] in ('new','tuned') and o['summary'] for o in origins))
        tuned=[o for o in origins if o['kind']=='tuned'];self.assertTrue(tuned)
        self.assertTrue(all(o['parent'] in result['candidates'] and o['changes'] for o in tuned))
        self.assertTrue(all(row['origin_by_candidate'] for row in result['history']))
        self.assertIn('group_trends',result['preference_model'])
        checks=[row for row in result['history'] if row['rating_source']=='choice'];self.assertTrue(checks)
        for row in checks:  # the best sound returns next to a tuning of itself, answered as a choice
            a,b=row['pair'];origins={i:result['candidates'][i]['origin'] for i in row['pair']}
            self.assertTrue(any(o.get('parent') in row['pair'] for o in origins.values()),row['origin_by_candidate'])
            self.assertEqual(row['rating_source'],'choice');self.assertEqual(len(row['inferred_rating']),1)
        self.assertTrue(all(row['rating_source'] in ('rating-1-7','choice') for row in result['history']))
        self.assertEqual(sum(result['session_metrics']['tuned_vs_parent'].values())>0,True)

    def test_spectral_tunings_must_differ_from_parent_but_time_groups_may_not(self):
        import json,time
        from experiment.source_search import OpenDiscovery,move_group
        parent=make_open_recipe_for_test()
        class Fixed(OpenDiscovery):
            def _proposals(self):  # three tunings of 'p'; every sound has the same spectrum
                out=[]
                for group in ('bright','rough','moving'):
                    child,changes=move_group(self.rng,parent,group,1);self.origins[child['seed']]={'kind':'tuned','parent':'p','group':group,'summary':group};out.append(child)
                return out
        render=lambda recipe:{'id':str(abs(hash(json.dumps(recipe,sort_keys=True)))),'label':'t','recipe':recipe,'urls':[],'checks':[],'audio_descriptor':[1/12]*12}
        d=Fixed(renderer=render);self.addCleanup(d.close)
        d.candidates={'p':{'id':'p','label':'p','recipe':parent,'ratings':[6],'audio_descriptor':[1/12]*12}}
        d.history=[{'pair':['p','p'],'ratings_by_candidate':{'p':6}}];d.active=True;d.completed=3
        d._prepare()
        while d.busy:time.sleep(.002)
        accepted=[c['origin']['group'] for i,c in d.candidates.items() if i!='p']
        self.assertEqual(accepted[:1],['rough'])  # passes: the spectrum cannot see roughness
        self.assertIn('bright',[d.origins[x['recipe']['seed']]['group'] for x in d.diversity_skips])  # spectral near-copy of its parent

    def test_tuning_step_halves_after_losses_and_settles_at_minimum(self):
        from experiment.source_search import tuning_record
        c={'p':{},'x':{}}
        rows=[{'pair':['p','x'],'ratings_by_candidate':{'p':6,'x':2}}]
        c['s1']={'origin':{'kind':'tuned','parent':'p'}};c['s2']={'origin':{'kind':'tuned','parent':'p'}}
        rows.append({'pair':['s1','s2'],'ratings_by_candidate':{'s1':4,'s2':4}})  # two losing siblings: one halving only
        self.assertEqual(tuning_record(c,rows)[0]['p'],.2)
        c['c0']={'origin':{'kind':'tuned','parent':'p'}}
        rows.append({'pair':['p','c0'],'rating_source':'choice','choice':'A','winner':'p','ratings_by_candidate':{'c0':5.}})  # choice: parent preferred
        steps,settled,counts=tuning_record(c,rows)
        self.assertEqual(steps['p'],.2);self.assertEqual(settled,{'p'});self.assertEqual(counts,{'win':0,'tie':0,'loss':3})
        c['w']={'origin':{'kind':'tuned','parent':'x'}};rows.append({'pair':['w','y'],'ratings_by_candidate':{'w':5,'y':1}})  # vs parent mean 2
        self.assertEqual(tuning_record(c|{'y':{}},rows)[2]['win'],1)

    def test_group_trends_shrink_and_follow_rating_changes(self):
        from experiment.source_search import group_trends
        tuned=lambda parent,group,direction,rating:{'ratings':[rating],'origin':{'kind':'tuned','parent':parent,'group':group,'direction':direction}}
        c={'p':{'ratings':[4]},'a':tuned('p','deep','more',6),'b':tuned('p','deep','more',6),'r':tuned('p','rough','more',1),'n':{'ratings':[7],'origin':{'kind':'new'}}}
        t=group_trends(c)
        self.assertEqual(t['deep+'],{'trend':1.0,'count':2})  # (2+2)/(2+2)
        self.assertEqual(t['rough+'],{'trend':-1.0,'count':1})  # -3/(1+2)
        self.assertEqual(set(t),{'deep+','rough+'})

    def test_group_moves_stay_in_limits_and_touch_only_their_group(self):
        from experiment.source_search import OPEN_KEYS,SOUND_GROUPS,make_open_recipe,move_group
        rng=random.Random(4);bounds={k:(lo,hi) for k,lo,hi,_ in OPEN_KEYS}
        grouped={key for members in SOUND_GROUPS.values() for key,_ in members}
        self.assertLessEqual(set(bounds),grouped,'every parameter is reachable through some group')
        a=make_open_recipe(rng)
        for _ in range(300):
            group=rng.choice(list(SOUND_GROUPS));child,changes=move_group(rng,a,group,rng.choice((1,-1)))
            self.assertEqual({k.split('.')[1] for k in changes}-{key for key,_ in SOUND_GROUPS[group]},set())
            self.assertEqual(len(child['layers']),len(a['layers']))
            for layer in child['layers']:
                for k,v in layer['shape'].items():
                    if k in bounds:self.assertTrue(bounds[k][0]-1e-9<=v<=bounds[k][1]+1e-9,(k,v))
                self.assertEqual('peak1Hz' in layer['shape'],'peak1Gain' in layer['shape'])
            a=child
        deeper,changes=move_group(rng,make_open_recipe(random.Random(1)),'deep',1)
        self.assertTrue(changes['L0.rootRatio'][1]<changes['L0.rootRatio'][0] or changes['L0.rootRatio'][0]==.4)


class StyleDiscoveryTest(unittest.TestCase):
    def render(self,recipe):
        import json
        rng=random.Random(json.dumps(recipe,sort_keys=True));d=[rng.random() for _ in range(12)];t=sum(d)
        return {'id':str(abs(hash(json.dumps(recipe,sort_keys=True)))),'label':'t','recipe':recipe,'urls':[],'checks':[],'audio_descriptor':[x/t for x in d]}

    def test_session_opening_choices_tuning_and_shortlist(self):
        import time
        from experiment.source_search import StyleDiscovery,STYLES,OPENING_PAIRS,OPENING_SEVENTH,STYLE_PAIRS,SHORTLIST
        d=StyleDiscovery(renderer=self.render);self.addCleanup(d.close);d.start()
        style=lambda i:d.candidates[i]['recipe']['layers'][0]['method']
        for turn in range(STYLE_PAIRS):
            while d.busy:time.sleep(.002)
            self.assertFalse(d.error,d.error);self.assertEqual(len(d.pair),2);self.assertEqual(d.snapshot()['pairMode'],'choice')
            with self.assertRaises(ValueError):d.feedback({'A':5,'B':3})  # ratings are not accepted any more
            for i in d.pair:d.heard(i)
            styles=[style(i) for i in d.pair]
            if turn<len(OPENING_PAIRS):self.assertEqual(set(styles),set(OPENING_PAIRS[turn]))
            if turn==len(OPENING_PAIRS):self.assertIn(OPENING_SEVENTH,styles)
            # Simulated taste: prefers Choir, and the deeper the better (each 'more deep' step wins)
            o=lambda i:d.candidates[i].get('origin',{})
            score=lambda i:(style(i)=='vocal')*2-d.candidates[i]['recipe']['layers'][0]['shape'].get('rootRatio',1.)
            a,b=d.pair;d.feedback(choice='A' if score(a)>score(b) else 'B' if score(b)>score(a) else 'equal')
        heard=[i for row in d.history for i in row['pair']]
        self.assertEqual({style(i) for i in heard[:8]},set(STYLES),'every base style heard in the opening')
        tuned=[d.candidates[i]['origin'] for i in heard if d.candidates[i].get('origin',{}).get('kind')=='tuned']
        self.assertTrue(all(o['changes'] and o['reason'] for o in tuned))
        # Direction learning: 'more deep' keeps winning its parent checks, so it scores highest (checked on the export below).
        self.assertEqual(d.stage,'done');self.assertFalse(d.active);self.assertEqual(d.playoff_history,[])
        self.assertTrue(1<=len(d.finalists)<=SHORTLIST)
        d.finish(d.finalists[0]);self.assertEqual(d.final,d.finalists[0])
        result=d.export();self.assertEqual(result['policy'],'source-style-explore-v1')
        self.assertEqual(result['preference_model']['style_ranking'][0]['style'],'vocal')
        # The preference model learns that deeper helps for this listener (who only cares about pitch). Chained moves can share
        # some credit (a known limit of a linear model over chains), so only the sign is checked.
        scores={(x['group'],x['direction']):x['score'] for x in result['preference_model']['direction_scores']}
        self.assertGreater(scores[('deep','more')],0);self.assertLess(scores[('deep','less')],0)
        self.assertTrue(all(row['rating_source']=='choice' and row['origin_by_candidate'] for row in result['history']))

    def test_momentum_repeats_a_move_that_beat_its_parent_and_losers_go_last(self):
        from experiment.source_search import StyleDiscovery,style_recipe,tune_style
        d=StyleDiscovery(renderer=self.render);self.addCleanup(d.close)
        parent=style_recipe('glass');d.candidates['P']={'id':'P','recipe':parent}
        child,_=tune_style(random.Random(1),parent,'deep',1);d.candidates['C']={'id':'C','recipe':child,'origin':{'kind':'tuned','parent':'P','group':'deep','direction':'more','step':.5}}
        loser,_=tune_style(random.Random(2),parent,'full',-1);d.candidates['L']={'id':'L','recipe':loser,'origin':{'kind':'tuned','parent':'P','group':'full','direction':'less','step':.5}}
        d.history=[{'pair':['P','C'],'rating_source':'choice','choice':'B','winner':'C'},{'pair':['P','L'],'rating_source':'choice','choice':'A','winner':'P'}]
        scores=d.direction_scores();self.assertGreater(scores[('deep','more')][0],0);self.assertLess(scores[('full','less')][0],0)
        order=[(d._origin_for(r)['group'],d._origin_for(r)['direction'],d._origin_for(r)['reason']) for r in d._tunings('C')]
        self.assertEqual(order[0][:2],('deep','more'));self.assertEqual(order[0][2],'repeats the move that just improved it')
        self.assertIn(order[-1][:2],{('full','less'),('deep','less')})  # losers (and the opposite of a winner) go last

    def test_feature_model_shares_evidence_and_settled_sounds_are_left_alone(self):
        from experiment.source_search import StyleDiscovery,style_recipe,tune_style
        d=StyleDiscovery(renderer=self.render);self.addCleanup(d.close)
        cl,ch=style_recipe('airy'),style_recipe('vocal');d.candidates={'CL':{'id':'CL','recipe':cl},'CH':{'id':'CH','recipe':ch}}
        rows=[]
        for n in range(3):  # Cluster beats three of its own tunings in a row...
            t,_=tune_style(random.Random(n),cl,'full',1);d.candidates[f't{n}']={'id':f't{n}','recipe':t,'origin':{'kind':'tuned','parent':'CL','group':'full','direction':'more','step':.5}}
            rows.append({'pair':['CL',f't{n}'],'rating_source':'choice','choice':'A','winner':'CL'})
        deeper,_=tune_style(random.Random(9),ch,'deep',1);d.candidates['CH2']={'id':'CH2','recipe':deeper,'origin':{'kind':'tuned','parent':'CH','group':'deep','direction':'more','step':.5}}
        rows+=[{'pair':['CH','CL'],'rating_source':'choice','choice':'A','winner':'CH'},{'pair':['CH','t0'],'rating_source':'choice','choice':'A','winner':'CH'}]
        d.history=rows
        # ...but Choir beat Cluster directly: a brand-new, never-compared deeper Choir already ranks above Cluster.
        self.assertGreater(d._utility('CH2'),d._utility('CL'))
        self.assertTrue(d._settled('CL'));self.assertFalse(d._settled('CH'))

    def test_bradley_terry_orders_by_choices(self):
        from experiment.source_search import bt_strengths
        rows=[{'pair':['a','b'],'choice':'A'},{'pair':['b','c'],'choice':'A'},{'pair':['a','c'],'choice':'equal'},{'pair':['c','b'],'choice':'B'}]
        s=bt_strengths(['a','b','c','d'],rows)
        self.assertGreater(s['a'],s['b']);self.assertGreater(s['b'],s['c']);self.assertAlmostEqual(s['d'],1.,places=6)

    def test_tuning_moves_one_group_within_range(self):
        from experiment.source_search import tune_style,style_recipe,STYLE_GROUPS,STYLE_RANGES
        rng=random.Random(1)
        for group in STYLE_GROUPS:
            for direction in (1,-1):
                child,changes=tune_style(rng,style_recipe('vocal'),group,direction)
                self.assertEqual(set(changes),{k for k,_ in STYLE_GROUPS[group]} & set(changes))
                for key,(old,new) in changes.items():self.assertTrue(STYLE_RANGES[key][0]<=new<=STYLE_RANGES[key][1])
        child,changes=tune_style(rng,style_recipe('vocal'),'deep',1)
        self.assertLess(child['layers'][0]['shape']['rootRatio'],1.);self.assertNotEqual(child['seed'],0)
