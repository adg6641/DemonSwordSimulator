"""게임 창 없이 검사하는 검날·이펙트·마검파 타격 회귀 검사."""
import math
import unittest
from pathlib import Path
from effects import CombatEffects
from hit_geometry import effect_hits,blade_hits,sweep_ages


class AttackGeometryTests(unittest.TestCase):
    def test_diagonal_sword_excludes_empty_box_corner(self):
        self.assertTrue(blade_hits((0,0),(100,100),(49,49,51,51)))
        self.assertFalse(blade_hits((0,0),(100,100),(0,90,8,100)))

    def test_alpha_hole_is_not_a_hit(self):
        masks={'ring':[[[0,0,40,6],[0,34,40,40],[0,6,6,34],[34,6,40,34]]]}
        g=dict(name='ring',frame=0,bounds=(0,0,40,40),origin=(0,0),scale=1,angle=0,x=0,y=0,alpha=1)
        self.assertTrue(effect_hits(g,(0,0),1,(1,-5,4,-1),masks))
        self.assertFalse(effect_hits(g,(0,0),1,(18,-22,22,-18),masks))

    def test_rotated_flipped_effect_keeps_its_hit_pixels(self):
        masks={'strip':[[[0,0,20,4]]]}
        g=dict(name='strip',frame=0,bounds=(0,0,20,4),origin=(0,0),scale=2,angle=math.pi/2,x=8,y=0,alpha=1)
        self.assertTrue(effect_hits(g,(100,100),1,(103,78,105,82),masks))
        self.assertTrue(effect_hits(g,(100,100),-1,(95,78,97,82),masks))
        self.assertFalse(effect_hits(g,(100,100),1,(120,120,125,125),masks))

    def test_sweep_does_not_skip_narrow_targets(self):
        ages=sweep_ages(0,.2,900)
        self.assertEqual(ages[0],0)
        self.assertEqual(ages[-1],.2)
        self.assertTrue(all((b-a)*900<=6.000001 for a,b in zip(ages,ages[1:])))

    def test_wave_is_small_at_start_and_grows_by_level(self):
        folder=Path(__file__).resolve().parents[1]/'assets/effects'
        fx=CombatEffects(folder);heights=[]
        for level in range(1,8):
            height=0
            for n in range(40):
                g=fx.wave_geometry(dict(age=.15+n/120,level=level,angle=0))
                height=max(height,(g['bounds'][3]-g['bounds'][1])*g['scale'])
            heights.append(height)
        self.assertLess(heights[0],50)
        self.assertLess(heights[-1],120)
        self.assertTrue(all(a<b for a,b in zip(heights,heights[1:])))


if __name__=='__main__':unittest.main()
