import unittest
from naming import NameEntry,clean_name
from progress import Run


class NamingTests(unittest.TestCase):
    def test_korean_composition_is_committed_before_confirmation(self):
        e=NameEntry();e.edit('루')
        self.assertEqual(e.confirm(),'')
        e.insert('루네아')
        self.assertEqual(e.confirm(),'루네아')

    def test_backspace_does_not_delete_text_during_ime_composition(self):
        e=NameEntry();e.insert('별');e.edit('빛');e.backspace()
        self.assertEqual(e.text,'별')
        e.edit('');e.backspace()
        self.assertEqual(e.text,'')

    def test_name_is_normalized_safe_and_limited(self):
        self.assertEqual(clean_name('  별빛_123\n<>'),'별빛_123')
        self.assertEqual(len(clean_name('가'*30)),10)
        self.assertEqual(clean_name('루네아'),'루네아')

    def test_name_round_trips_and_old_saves_still_load(self):
        r=Run(nickname='별빛검사')
        self.assertEqual(Run.from_dict(r.data()).display_name,'별빛검사')
        data=r.data();data.pop('nickname')
        self.assertEqual(Run.from_dict(data).display_name,'소년')
