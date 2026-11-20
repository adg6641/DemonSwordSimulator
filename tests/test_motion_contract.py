"""검은 프레임 크기와 무관한 한 자루이며, 모든 마검파는 같은 발사 기준을 쓴다."""
from pathlib import Path
from math import hypot
from types import SimpleNamespace
import unittest
from animation import Animation
from effects import CombatEffects


ROOT=Path(__file__).resolve().parents[1]/'assets'


class MotionContractTests(unittest.TestCase):
    def test_sword_length_is_identical_in_every_pose(self):
        a=Animation(ROOT/'hero')
        expected=a.weapon['handToTip']
        for name,clip in a.clips.items():
            a.play(name,start_frame=0)
            for frame in range(clip['frameCount']):
                a.elapsed=a.frame_start(frame)
                pose=a.weapon_pose
                if pose:
                    self.assertAlmostEqual(hypot(pose['tip'][0]-pose['hand'][0],pose['tip'][1]-pose['hand'][1]),expected,places=7,msg=(name,frame))

    def test_locked_weapon_uses_the_drawn_wrist_angle(self):
        a=Animation(ROOT/'hero')
        for name in ('run','slash_1','slash_2','slash_3','guard_idle','crouch_slash'):
            a.play(name)
            for frame in range(a.clip['frameCount']):
                a.elapsed=a.frame_start(frame)+.001
                self.assertAlmostEqual(a.weapon_pose['angle'],a.clip['frames'][a.frame]['weapon']['angle'])

    def test_all_wave_attacks_share_launch_plane_and_horizontal_direction(self):
        a=Animation(ROOT/'hero')
        for name in ('slash_1','slash_2','slash_3','crouch_slash','air_slash'):
            for height in (0,180):
                for facing in (-1,1):
                    fx=CombatEffects(ROOT/'effects');fx.activate()
                    a.play(name);a.elapsed=a.duration*.98
                    p=SimpleNamespace(x=300,y=height,facing=facing,animation=a)
                    fx.update(.001,p)
                    self.assertEqual(len(fx.waves),1,(name,height))
                    wave=fx.waves[0]
                    self.assertEqual((wave['x'],wave['y'],wave['angle']),(300+facing*96,height+94,0))
