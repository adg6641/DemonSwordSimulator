"""발판의 빈 가장자리, 동료의 착지, 효과와 몸체의 공통 좌표 회귀 검사."""
import unittest
from types import SimpleNamespace
from campaign import Campaign
from effects import CombatEffects


class SceneGeometryTests(unittest.TestCase):
    def scene(self):
        s=Campaign.__new__(Campaign)
        s.objects=[dict(kind='platform',x=1330,y=125,w=240,visual='polish/platform_1')]
        s.assets=SimpleNamespace(clips={'polish/platform_1':dict(surface=dict(left=8,right=232))})
        s.player=object()
        return s

    def test_transparent_edge_does_not_support_feet(self):
        s=self.scene()
        p=SimpleNamespace(x=1215,y=125,vy=0)
        self.assertEqual(s.floor_beneath(p),0)
        p.x=1220
        self.assertEqual(s.floor_beneath(p),125)
        p.y=140
        self.assertEqual(s.floor_beneath(p),0)

    def test_companion_lands_on_the_same_platform(self):
        s=self.scene(); played=[]
        p=SimpleNamespace(x=1280,y=119,vy=-120,floor_y=0,motion=SimpleNamespace(play=played.append))
        s.platforms(135,p)
        self.assertEqual((p.y,p.vy,p.floor_y),(125,0,125))
        self.assertEqual(played,['lunea/land_soft'])

    def test_actor_cannot_land_outside_visible_ledge(self):
        s=self.scene()
        p=SimpleNamespace(x=1208,y=119,vy=-120,floor_y=0)
        s.platforms(135,p)
        self.assertEqual(p.y,119)
        self.assertEqual(p.floor_y,0)

    def test_one_way_platform_does_not_catch_rising_actor(self):
        s=self.scene()
        p=SimpleNamespace(x=1280,y=130,vy=120,floor_y=0)
        s.platforms(110,p)
        self.assertEqual(p.vy,120)
        self.assertEqual(p.floor_y,0)

    def test_effect_bounds_follow_facing_and_world_origin(self):
        g=dict(bounds=(0,0,100,40),origin=(0,20),scale=1,angle=0,x=10,y=0)
        self.assertEqual(CombatEffects.world_bounds(g,200,100,1),(210,80,310,120))
        self.assertEqual(CombatEffects.world_bounds(g,200,100,-1),(90,80,190,120))
        self.assertTrue(Campaign.overlap((210,80,310,120),(309,100,360,150)))
        self.assertFalse(Campaign.overlap((210,80,310,120),(311,100,360,150)))


if __name__=='__main__': unittest.main()
