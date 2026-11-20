"""낮은 곳으로 낙하한 착지와 위 발판 착지를 구분한다."""
import unittest
from types import SimpleNamespace

from campaign import Campaign
from player import Player


class LandingMotionTests(unittest.TestCase):
    def player(self, origin, peak, floor):
        p=Player.__new__(Player)
        p.floor_y=floor
        p.flight_origin_y=origin
        p.flight_peak_y=peak
        p.in_flight=True
        p.move_time=1
        p.crouching=False
        p.animation=SimpleNamespace(name='fall')
        p._action=lambda name,*args,**kwargs:setattr(p.animation,'name',name)
        return p

    def test_jump_to_higher_platform_uses_light_landing(self):
        p=self.player(0,164,120)
        p.land(0,-440)
        self.assertEqual(p.animation.name,'land_upper')
        self.assertEqual(p.last_ground_y,120)
        self.assertFalse(p.in_flight)

    def test_drop_from_higher_platform_uses_deep_landing(self):
        p=self.player(400,400,0)
        p.land(0,-1300)
        self.assertEqual(p.animation.name,'land_drop')

    def test_ordinary_same_floor_jump_is_soft(self):
        p=self.player(0,164,0)
        p.land(0,-850)
        self.assertEqual(p.animation.name,'land_soft')

    def test_moving_landing_keeps_running_variant(self):
        for origin,floor,expected in [(0,120,'land_upper_run'),(400,0,'land_drop_run')]:
            p=self.player(origin,max(origin,164),floor)
            p.land(1,-600)
            self.assertEqual(p.animation.name,expected)

    def test_tracking_keeps_departure_height_after_floor_changes(self):
        p=self.player(0,0,0)
        p.y,p.vy,p.last_ground_y,p.in_flight=390,-100,400,False
        p.track_flight()
        p.y=200
        p.track_flight()
        self.assertEqual((p.flight_origin_y,p.flight_peak_y),(400,390))

    def test_platform_passes_collision_speed_before_zeroing_it(self):
        scene=Campaign.__new__(Campaign)
        scene.objects=[dict(kind='platform',x=100,y=120,w=220)]
        scene.solid_platforms=lambda:scene.objects
        scene.platform_span=lambda obj:(-10,210)
        seen=[]
        scene.player=SimpleNamespace(x=100,y=118,vy=-650,floor_y=0,mode='free',
                                     animation=SimpleNamespace(name='fall'),previous_direction=1,
                                     land=lambda direction,speed:seen.append((direction,speed)))
        # 직전 프레임이 발판에서 1픽셀만 위였어도 실제 낙하면 착지한다.
        scene.platforms(121)
        self.assertEqual(seen,[(1,-650)])
        self.assertEqual((scene.player.y,scene.player.vy),(120,0))

    def test_hurt_landing_records_contact_without_restarting_hurt(self):
        scene=Campaign.__new__(Campaign)
        scene.objects=[dict(kind='platform',x=100,y=120,w=220)]
        scene.solid_platforms=lambda:scene.objects
        scene.platform_span=lambda obj:(-10,210)
        p=SimpleNamespace(x=100,y=118,vy=-650,floor_y=0,mode='hurt',in_flight=True,
                          animation=SimpleNamespace(name='hurt'))
        scene.player=p
        scene.platforms(121)
        self.assertFalse(p.in_flight)
        self.assertEqual((p.last_ground_y,p.animation.name),(120,'hurt'))


if __name__=='__main__':unittest.main()
