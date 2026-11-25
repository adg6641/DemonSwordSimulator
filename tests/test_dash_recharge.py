from pathlib import Path
import unittest

from pico2d import SDLK_LSHIFT, SDLK_RSHIFT, SDLK_c
from player import Player
from progress import Run


class DashRechargeTests(unittest.TestCase):
    def setUp(self):
        self.player = Player(Path(__file__).resolve().parents[1] / 'assets/hero')

    def advance(self, seconds):
        for _ in range(round(seconds * 120)):
            self.player.update(1/120, set())

    def test_dash_skill_recharge_has_five_second_start_and_one_second_floor(self):
        run = Run()
        for rank, seconds in enumerate((5, 5, 4, 3, 2, 1, 1)):
            run.skills['dash'] = rank
            self.assertEqual(run.dash_recharge, seconds)

    def test_ground_and_air_share_the_same_cooldown(self):
        p = self.player
        p.press(SDLK_LSHIFT, set())
        self.assertEqual(p.dash_cooldown, 5)
        first_position = p.dash_echoes[0][1:3]
        self.advance(.5)
        self.assertEqual(p.dash_echoes.maxlen, 6)
        self.assertEqual(first_position, (220.0, 0.0))
        p.y = 285
        p.press(SDLK_RSHIFT, set())
        self.assertNotEqual(p.mode, 'dash')
        self.assertAlmostEqual(p.dash_cooldown, 4.5)
        self.advance(4.51)
        p.y = 285
        p.press(SDLK_RSHIFT, set())
        self.assertEqual(p.animation.name, 'dash_air')
        self.assertEqual(p.dash_cooldown, 5)

    def test_queued_dash_cooldown_leaves_post_dash_slash_available(self):
        p = self.player
        p.press(SDLK_LSHIFT, set())
        p.press(SDLK_c, set())
        self.assertNotEqual(p.animation.name, 'dash_slash')
        self.advance(.33)
        p.press(SDLK_c, set())
        self.assertEqual(p.animation.name, 'dash_slash')
        self.assertGreater(p.dash_cooldown, 4)
