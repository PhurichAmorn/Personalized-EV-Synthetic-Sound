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

    def test_favourites_do_not_come_from_feedback(self):
        discovery=SourceDiscovery(renderer=lambda recipe: {'id':str(recipe['seed']), 'label':'test','recipe':recipe,'urls':[], 'checks':[]})
        self.addCleanup(discovery.close)
        discovery.candidates={'a':{'id':'a','recipe':make_recipe(random.Random(1)),'label':'a'},'b':{'id':'b','recipe':make_recipe(random.Random(2)),'label':'b'}}
        discovery.pair=['a','b'];discovery.active=True
        with self.assertRaises(ValueError):discovery.feedback('A')
        discovery.heard('a');discovery.heard('b')
        discovery.bookmark('a',True);discovery.bookmark('a',True)
        self.assertEqual(len(discovery.favourites),1)
        discovery.bookmark('a',False);self.assertEqual(discovery.favourites,[])

    def test_finish_keeps_bookmarks_and_export_is_a_copy(self):
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
        d.bookmark(pair[0],True)
        d.finish();self.assertFalse(d.active)
        self.assertIn(pair[0],d.favourites)
        result=d.export();self.assertEqual(result['favourites'],d.favourites)
        result['favourites'].clear();self.assertEqual(len(d.favourites),1)

    def test_favourites_have_no_small_hard_limit(self):
        d=SourceDiscovery(renderer=lambda recipe: {});self.addCleanup(d.close)
        for i in range(12):
            ident=f'candidate-{i}';d.candidates[ident]={'id':ident,'label':ident,'recipe':make_recipe(random.Random(i))}
            d.bookmark(ident,True)
        self.assertEqual(len(d.favourites),12)
        d.bookmark('candidate-0',True,note='Warm and full')
        self.assertEqual(len(d.favourites),12)
        self.assertEqual(d.notes['candidate-0'],'Warm and full')
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
            if turn==0:d.bookmark(d.pair[0],True)
            d.feedback({'A':4+turn%3,'B':4})
        d.finish()
        result=d.export()
        self.assertEqual(len(result['history']),8)
        self.assertEqual(len(result['favourites']),1)
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
        d.heard('a');d.heard('b');d.bookmark('a',True)
        d.feedback({'A':5,'B':3})
        self.assertEqual(d.completed,MAX_COMPARISONS)
        self.assertEqual(d.stage,'playoff');self.assertFalse(d.busy);self.assertEqual(set(d.pair),{'a','b'})
        self.assertEqual(d.favourites,['a']);self.assertEqual(len(d.export()['history']),1)

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

    def test_invalid_note_does_not_change_favourites(self):
        d=SourceDiscovery(renderer=lambda recipe:{});self.addCleanup(d.close)
        d.candidates={'a':{'id':'a','label':'a','recipe':make_recipe(random.Random(1))}}
        with self.assertRaises(ValueError):d.bookmark('a',True,'x'*301)
        self.assertEqual(d.favourites,[])

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
