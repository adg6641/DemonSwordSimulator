import copy
import tempfile
import unittest
from pathlib import Path
from progress import Run, SaveStore


class ProgressTests(unittest.TestCase):
    def prepared(self, companion):
        run = Run(trust=2, erosion=1, records=['night', 'moon', 'return'], companion=companion)
        run.pacts = ['secret', 'memory', 'plan'] if companion else []
        return run

    def test_nine_disjoint_endings_and_hp_zero_priority(self):
        found = set()
        for companion in (False, True):
            run = self.prepared(companion)
            for choice, digit in [('restore', 1), ('journey', 2), ('moon', 3), ('crown', 4)]:
                self.assertEqual(run.resolve_ending(choice), ('D' if companion else 'S')+str(digit))
                found.add(run.resolve_ending(choice))
                self.assertIsNone(run.resolve_ending(choice, alive=False))
        run.hidden_entry = True
        self.assertEqual(run.resolve_ending('crown'), 'H1')
        self.assertIsNone(run.resolve_ending('restore', alive=False))
        self.assertEqual(len(found|{'H1'}), 9)

    def test_bundled_growth_only_at_milestones(self):
        run = Run()
        self.assertFalse(run.all_magic())
        self.assertEqual(run.gain_xp(119),0)
        self.assertEqual(run.gain_xp(1),1)
        self.assertEqual((run.level,run.unspent,run.skill_points),(2,1,0))
        self.assertTrue(run.choose_bundle('magic'))
        self.assertEqual((run.skills['wave'],run.skills['dash']),(1,0))
        self.assertEqual((run.spent['magic'],run.spent['focus']),(2,2))
        self.assertTrue(run.all_magic())
        for level in range(3,10):
            run.gain_xp(run.xp_needed)
            self.assertEqual((run.level,run.unspent),(level,0))
        run.gain_xp(run.xp_needed)
        self.assertEqual((run.level,run.unspent),(10,1))
        self.assertTrue(run.choose_bundle('balance'))
        self.assertFalse(run.all_magic())

    def test_level_100_is_saved_and_does_not_overflow(self):
        run=Run()
        run.gain_xp(10**9)
        self.assertEqual((run.level,run.xp,run.unspent),(100,0,11))
        self.assertEqual(Run.from_dict(run.data()).level,100)
        self.assertEqual(run.gain_xp(10**9),0)

    def test_solo_has_no_companion_requirements(self):
        run = self.prepared(False)
        self.assertEqual(run.missing_restore(), [])
        run.companion = True
        self.assertEqual(len(run.missing_restore()), 3)
        run.pacts = ['secret', 'memory', 'plan']
        run.fracture = True
        self.assertIn('부적 균열 복구', run.missing_restore())

    def test_erosion_is_danger_not_automatic_ending(self):
        run = self.prepared(True)
        run.erosion = 3
        self.assertIsNone(run.resolve_ending('restore'))
        self.assertEqual(run.resolve_ending('journey'), 'D2')
        self.assertEqual(run.resolve_ending('moon'), 'D3')
        self.assertFalse(run.ending)

    def test_bundles_unlock_skills_and_add_related_stats(self):
        for path, skills in [('physical', (1, 0)), ('magic', (0, 1)), ('balance', (1, 1))]:
            run = Run()
            run.gain_xp(run.xp_needed)
            self.assertTrue(run.choose_bundle(path))
            self.assertEqual((run.skills['dash'], run.skills['wave']), skills)
            self.assertEqual(run.unspent,0)
            self.assertFalse(run.choose_bundle(path))
            self.assertEqual(run.path,path)
        self.assertFalse(Run().choose_bundle('magic'))

    def test_old_save_keeps_stats_and_migrates_pending_choices(self):
        data=Run(level=22,path='magic',spent=dict(attack=0,magic=9,vitality=0,focus=4)).data()
        del data['progression_version']
        del data['growth_builds']
        data.update(unspent=31,skill_points=14,xp=400)
        run=Run.from_dict(data)
        self.assertEqual(run.spent,data['spent'])
        self.assertEqual((run.unspent,run.skill_points),(2,0))
        self.assertEqual(run.growth_builds['magic'],1)
        self.assertEqual(Run.from_dict(run.data()).data(),run.data())

    def test_checkpoint_rolls_back_rewards_and_story_together(self):
        with tempfile.TemporaryDirectory() as folder:
            store, run = SaveStore(folder), self.prepared(True)
            run.killed = ['2:enemy:0']
            run.broken = ['2:crate']
            store.save(run, 2800, 0, 76, 50, [dict(uid='2:enemy:1', hp=25, x=3100)])
            expected = copy.deepcopy(store.checkpoint)
            run.gain_xp(200)
            run.killed.append('2:enemy:1')
            run.erosion = 3
            point = store.restore()
            self.assertEqual(point, expected)
            point['run']['records'].clear()
            self.assertEqual(store.restore(), expected)
            reloaded = SaveStore(folder)
            self.assertEqual(reloaded.restore(), expected)
            run.ending = 'D2'
            store.finish(run)
            store.finish(run)
            self.assertEqual(len(store.history), 1)
            self.assertIsNone(SaveStore(folder).checkpoint)

    def test_bad_save_is_readable_failure_not_crash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'userdata'
            path.mkdir()
            (path/'save.json').write_text('{broken', encoding='utf8')
            store = SaveStore(folder)
            self.assertIsNone(store.checkpoint)
            self.assertTrue(store.error)


if __name__ == '__main__':
    unittest.main()
