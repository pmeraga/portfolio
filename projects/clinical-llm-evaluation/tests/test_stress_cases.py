"""Stress-generator checks use only synthetic references, never model predictions."""
from collections import Counter, defaultdict
from fractions import Fraction
import unittest

from src.generate_stress import FAMILIES, MAX_NOTE_CHARS, generate_stress


class TestStressCases(unittest.TestCase):
    def test_counts_references_and_determinism(self):
        rows = generate_stress(1)
        self.assertEqual(len(rows), 72)
        self.assertEqual(Counter(row['family'] for row in rows), {f:24 for f in FAMILIES})
        self.assertEqual(rows, generate_stress(1))
        groups = defaultdict(list)
        for row in rows:
            groups[row['pair_id']].append(row)
        for group in groups.values():
            self.assertEqual({row['variant'] for row in group}, {'control','challenge','rescue'})
            self.assertEqual(len({(type(row['gold']),row['gold']) for row in group}),1)
            self.assertEqual(len({row['question'] for row in group}),1)

    def test_dose_reference_is_independently_recomputed(self):
        for round_index in (1,4,8,15):
            for row in generate_stress(round_index):
                if row['family'] != 'dose_arithmetic':
                    continue
                total = sum(Fraction(order['strength_mg']) * Fraction(order['tablets'])
                            for order in row['tablet_orders'])
                liquid = row['solution_order']
                total += Fraction(liquid['mass_mg']) / Fraction(liquid['per_ml']) * Fraction(liquid['volume_ml'])
                self.assertEqual(Fraction(row['reference_total_fraction']),total)
                self.assertAlmostEqual(row['gold'],float(total))
                for order in row['tablet_orders']:
                    self.assertIn(order['strength_mg']+' mg per tablet',row['note'])

    def test_rounds_are_disjoint_and_difficulty_is_bounded(self):
        first, second = generate_stress(1),generate_stress(2)
        self.assertFalse({row['id'] for row in first} & {row['id'] for row in second})
        self.assertFalse({row['note'] for row in first} & {row['note'] for row in second})
        for n in (1,2,8,30,1000):
            rows=generate_stress(n)
            self.assertTrue(all(len(row['note']) <= MAX_NOTE_CHARS for row in rows))
            self.assertTrue(all(row['stress_level']==min(n,8) for row in rows))
        self.assertGreater(max(len(row['note']) for row in generate_stress(8)),
                           max(len(row['note']) for row in first))

    def test_target_drug_does_not_predict_boolean_gold(self):
        for family in ('patient_attribution','temporal_conflicts'):
            labels=defaultdict(set)
            for row in generate_stress(1):
                if row['family']==family:
                    labels[row['target_drug']].add(row['gold'])
            self.assertTrue(all(value=={True,False} for value in labels.values()))

    def test_attribution_and_temporal_reordering_preserve_sources(self):
        groups=defaultdict(dict)
        for row in generate_stress(8):
            groups[row['pair_id']][row['variant']]=row
        for variants in groups.values():
            challenge,rescue=variants['challenge'],variants['rescue']
            if challenge['family']=='dose_arithmetic':
                continue
            self.assertEqual(Counter(challenge['note'].splitlines()),Counter(rescue['note'].splitlines()))
            target=(challenge['expected_target_fact'] if challenge['family']=='patient_attribution'
                    else challenge['expected_final_fact'])
            self.assertEqual(challenge['note'].count(target),1)
            self.assertEqual(rescue['note'].count(target),1)
            if challenge['family']=='temporal_conflicts':
                self.assertTrue(rescue['note'].endswith(target))

    def test_invalid_round_rejected(self):
        for value in (0,-1,True,1.5,'1'):
            with self.assertRaises(ValueError):
                generate_stress(value)


if __name__=='__main__':
    unittest.main()
