import unittest
from types import SimpleNamespace

from .grammar import category, profile
from .policy import choose


def token(text, tense=None, *, mood='Ind', lemma=None, dep='', head=None, form='Fin', pos='VERB'):
    morph = {'VerbForm': [form], 'Mood': [mood], 'Tense': [tense] if tense else []}
    return SimpleNamespace(text=text, pos_=pos, morph=morph, lemma_=lemma or text, dep_=dep, head=head)


class TemporalPolicyTest(unittest.TestCase):
    def test_finite_categories(self):
        for tense, expected in [('Past', 'past'), ('Imp', 'past'), ('Pres', 'present'), ('Fut', 'future')]:
            self.assertEqual(category(token('v', tense)), expected)
        self.assertEqual(category(token('v', mood='Cnd')), 'conditional')
        self.assertIsNone(category(token('v', 'Past', form='Part')))

    def test_perfect_and_passive(self):
        participle = token('oído', 'Past', form='Part')
        auxiliary = token('he', 'Pres', lemma='haber', dep='aux', head=participle, pos='AUX')
        self.assertEqual(profile([auxiliary, participle])['categories'], ['past'])
        auxiliary.lemma_ = 'ser'
        self.assertEqual(profile([auxiliary, participle])['categories'], ['present'])
        auxiliary.lemma_ = 'haber'
        auxiliary.morph['Tense'] = ['Fut']
        self.assertEqual(profile([auxiliary, participle])['categories'], ['future'])

    def test_veto_then_next_best(self):
        pool = dict(source='A generic sentence.', candidates=[dict(name=name, translation=text) for name, text in
                    [('native', 'Vi algo.'), ('base', 'Veo algo.'), ('adapter', 'He visto algo.')]])
        profiles = {name: dict(categories=[tense]) for name, tense in [('native', 'past'), ('base', 'present'), ('adapter', 'past')]}
        result = choose(pool, dict(native=-3, base=-1, adapter=-2), profiles)
        self.assertEqual(result['selected'], 'adapter')
        self.assertEqual(result['temporal_vetoes'], [dict(name='base', missing_categories=['past'])])
        self.assertEqual(result['translation'], pool['candidates'][2]['translation'])

    def test_no_improvement_or_invalid_scores_preserves_native(self):
        pool = dict(source='Text', candidates=[dict(name='native', translation='Texto'), dict(name='base', translation='Otro')])
        profiles = {name: dict(categories=[]) for name in ['native', 'base']}
        for value in [-2, None, float('nan'), float('inf')]:
            self.assertEqual(choose(pool, dict(native=-1, base=value), profiles)['selected'], 'native')

    def test_allows_recovered_clause_with_additional_time(self):
        pool = dict(source='Text', candidates=[dict(name='native', translation='Texto'), dict(name='base', translation='Otro')])
        profiles = dict(native=dict(categories=['present']), base=dict(categories=['past', 'present']))
        self.assertEqual(choose(pool, dict(native=-2, base=-1), profiles)['selected'], 'base')


if __name__ == '__main__':
    unittest.main()
