import unittest
from types import SimpleNamespace
from campaign import Campaign


class ContactDistanceTests(unittest.TestCase):
    def scene(self, facing=1):
        scene=Campaign.__new__(Campaign)
        scene.player=SimpleNamespace(x=120*facing,y=0,facing=facing,mode='combo',
                                     animation=SimpleNamespace(name='slash_1'),collision_height=180)
        scene.enemies=[]
        scene.objects=[dict(kind='crate',id='crate',x=190*facing,y=0)]
        scene.run=SimpleNamespace(broken=[],stage=0,page=0)
        scene.contact_target=None
        return scene

    def test_combo_stops_before_a_solid_target_in_both_directions(self):
        for facing in (1,-1):
            scene=self.scene(facing)
            scene.keep_attack_distance(100*facing)
            self.assertEqual(scene.player.x,109*facing)

    def test_unobstructed_combo_keeps_its_forward_step(self):
        scene=self.scene()
        scene.objects=[]
        scene.keep_attack_distance(100)
        self.assertEqual(scene.player.x,120)

    def test_target_on_another_platform_does_not_block_the_step(self):
        scene=self.scene()
        scene.objects[0]['y']=240
        scene.keep_attack_distance(100)
        self.assertEqual(scene.player.x,120)
