import unittest
from campaign_data import PLATFORM_ROUTES,PAGES,page_objects
from navigation import jump_reach


class RegionRoutesTests(unittest.TestCase):
    def test_each_region_has_a_different_route_silhouette(self):
        profiles=[tuple((y,w) for route in routes for _,y,w in route) for routes in PLATFORM_ROUTES]
        self.assertEqual(len(set(profiles)),8)
        self.assertGreater(len({len(p) for p in profiles}),1)

    def test_all_static_routes_can_be_climbed_with_normal_jump(self):
        for stage,routes in enumerate(PLATFORM_ROUTES):
            for route in routes:
                self.assertGreater(jump_reach(route[0][1]),0)
                for a,b in zip(route,route[1:]):
                    x,y,w=a;nx,ny,nw=b
                    gap=max(0,abs(nx-x)-(w+nw)/2+12)
                    self.assertLessEqual(gap+42,jump_reach(ny-y),(stage,a,b))

    def test_rewards_and_portals_have_support_and_unique_ids(self):
        for stage,pages in enumerate(PAGES):
            for page,region in enumerate(pages):
                objects=page_objects(stage,page)
                self.assertEqual(len(objects),len({o['id'] for o in objects}))
                if region!='explore':continue
                floors=[o for o in objects if o['kind']=='platform' and not o.get('motion')]
                for o in objects:
                    if o['kind'] not in {'camp','event','record','chest','door','lever'} or o['y']==0:continue
                    self.assertTrue(any(abs(p['y']-o['y'])<1 and abs(p['x']-o.get('actor_x',o['x']))<p['w']/2-12 for p in floors),(stage,o))
