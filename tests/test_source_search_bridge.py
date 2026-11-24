import unittest
from unittest.mock import Mock
from backend.bridge import DesktopBridge

class SourceSearchBridgeTest(unittest.TestCase):
    def setUp(self):
        self.controller=Mock(soundSweepActive=False)
        self.controller.search.active=False
        self.bridge=DesktopBridge(self.controller)
        for search in self.bridge.searches.values():search.close()
        self.discovery=Mock(active=False,busy=False);self.map=Mock(active=False,busy=False)
        self.bridge.searches={'tuning':self.discovery,'map':self.map};self.bridge.source_discovery=self.discovery
        self.bridge.snapshot=lambda:{'sourceDiscovery':'state'}

    def test_commands_forward_ids_and_explicit_export(self):
        self.bridge.command('sourceDiscoveryStart',{})
        self.discovery.start.assert_called_once()
        self.discovery.export.return_value={'format':'ev-source-discovery-v1'}
        self.assertEqual(self.bridge.command('sourceDiscoveryExport',{}),self.discovery.export.return_value)
        with self.assertRaises(ValueError):self.bridge.command('sourceDiscoveryBookmark',{'id':'a','enabled':True})  # favourites removed

    def test_start_chooses_the_search_per_session(self):
        self.bridge.command('sourceDiscoveryStart',{'search':'map'})
        self.map.start.assert_called_once();self.discovery.start.assert_not_called()
        self.assertIs(self.bridge.source_discovery,self.map);self.assertIs(self.bridge.history.discovery,self.map)
        with self.assertRaises(ValueError):self.bridge.command('sourceDiscoveryStart',{'search':'other'})

    def test_native_and_source_trials_are_mutually_exclusive(self):
        self.controller.search.active=True
        with self.assertRaises(ValueError):self.bridge.command('sourceDiscoveryStart',{})
        self.controller.search.active=False;self.discovery.active=True
        for command in ['searchStart','searchRestore','tracePreview','sweep']:
            with self.assertRaises(ValueError):self.bridge.command(command,{})

    def test_vehicle_start_is_idempotent(self):
        self.controller.running=False
        def start():self.controller.running=True
        self.controller.toggle.side_effect=start
        self.bridge.command('vehicleStart',{})
        self.bridge.command('vehicleStart',{})
        self.controller.toggle.assert_called_once()


class BlockBuilderTest(unittest.TestCase):
    """Sound Lab's block builder: the same _recipe a session plays, reached through two bridge commands."""
    def setUp(self):
        self.bridge=DesktopBridge(Mock(soundSweepActive=False))

    def tearDown(self):
        for search in self.bridge.searches.values():search.close()

    def test_options_and_build(self):
        options=self.bridge.handle('blockOptions',{}) if hasattr(self.bridge,'handle') else self.bridge._block_options()
        self.assertIn('glass',options['tops']);self.assertEqual(len(options['pitches']),5)
        built=self.bridge._block_build({'blocks':{'top':'bell','buzz':2,'chord':'on'},'motion':'evolving'})
        self.assertEqual(built['recipe']['motion'],'evolving');self.assertEqual(built['recipe']['blocks']['top'],'bell');self.assertEqual(built['recipe']['kind'],'map')

    def test_partner_not_allowed_for_the_top_is_dropped(self):
        built=self.bridge._block_build({'blocks':{'top':'electric','partner':'glass'}})
        self.assertIsNone(built['recipe']['blocks']['partner'])
