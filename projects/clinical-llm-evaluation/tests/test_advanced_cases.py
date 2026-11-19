import copy
import unittest
from collections import Counter, defaultdict

from src.generate_advanced import FAMILIES, VARIANTS, generate, validate


class TestAdvancedCases(unittest.TestCase):
    def test_phase_sizes_and_determinism(self):
        pilot = generate("advanced_pilot")
        confirmation = generate("advanced_confirm")
        self.assertEqual(len(pilot), 252)
        self.assertEqual(len(confirmation), 1260)
        self.assertEqual(pilot, generate("advanced_pilot"))
        self.assertFalse({r["id"] for r in pilot} & {r["id"] for r in confirmation})
        self.assertFalse({r["note"] for r in pilot} & {r["note"] for r in confirmation})

    def test_triplets_preserve_gold_question_and_types(self):
        pairs = defaultdict(list)
        rows = generate("advanced_pilot")
        self.assertEqual(Counter(r["family"] for r in rows), {f: 36 for f in FAMILIES})
        for r in rows:
            pairs[r["pair_id"]].append(r)
        for group in pairs.values():
            self.assertEqual({r["variant"] for r in group}, set(VARIANTS))
            self.assertEqual(len({r["question"] for r in group}), 1)
            self.assertEqual(len({(type(r["gold"]), r["gold"]) for r in group}), 1)

    def test_numeric_gold_from_schedule(self):
        rows = generate("advanced_confirm")
        values = set()
        for r in rows:
            if r["family"] == "dose_arithmetic":
                self.assertEqual(r["gold"], r["scheduled_tablet_strength_mg"] * r["scheduled_tablets_per_day"])
                self.assertEqual(r["answer_type"], "number")
                values.add(r["gold"])
        self.assertGreater(len(values), 10)

    def test_lab_labels_recompute_from_supplied_conversion(self):
        lab = [r for r in generate("advanced_confirm") if r["family"] == "lab_units"]
        self.assertEqual({r["gold"] for r in lab}, {True, False})
        for r in lab:
            self.assertEqual(r["gold"], r["latest_glucose_mmol_l"] * 18 > r["threshold_mg_dl"])
            self.assertIn("1 mmol/L glucose = 18 mg/dL", r["question"])

    def test_boolean_families_have_both_labels(self):
        for family in FAMILIES:
            if family != "dose_arithmetic":
                self.assertEqual({r["gold"] for r in generate("advanced_pilot") if r["family"] == family}, {True, False})

    def test_drug_identity_does_not_predict_label(self):
        for phase in ("advanced_pilot", "advanced_confirm"):
            groups = defaultdict(set)
            for row in generate(phase):
                if "target_drug" in row:
                    groups[(row["family"], row["target_drug"])].add(row["gold"])
            self.assertTrue(groups)
            for key, labels in groups.items():
                self.assertEqual(labels, {True, False}, key)

    def test_strict_threshold_equality_is_false(self):
        equality = [r for r in generate("advanced_pilot")
                    if r["family"] == "lab_units"
                    and r["latest_glucose_mmol_l"] * 18 == r["threshold_mg_dl"]]
        self.assertGreaterEqual(len(equality), 6)
        self.assertTrue(all(r["gold"] is False for r in equality))

    def test_temporal_rescue_reorders_identical_entries(self):
        groups = defaultdict(dict)
        for r in generate("advanced_pilot"):
            if r["family"] == "temporal_conflicts":
                groups[r["pair_id"]][r["variant"]] = r
        for group in groups.values():
            challenge = group["challenge"]["note"].splitlines()[1:]
            rescue = group["rescue"]["note"].splitlines()[1:]
            self.assertEqual(sorted(challenge), sorted(rescue))
            self.assertNotEqual(challenge, rescue)
            self.assertIn("18:00", rescue[-1])

    def test_radiology_rescue_moves_identical_current_report(self):
        groups = defaultdict(dict)
        for r in generate("advanced_pilot"):
            if r["family"] == "radiology_context":
                groups[r["pair_id"]][r["variant"]] = r
        for group in groups.values():
            challenge = group["challenge"]["note"].splitlines()[1:]
            rescue = group["rescue"]["note"].splitlines()[1:]
            self.assertEqual(Counter(challenge), Counter(rescue))
            self.assertTrue(rescue[-1].startswith("FINAL SIGNED"))
            self.assertGreater(len(group["challenge"]["note"].split()), 800)

    def test_validation_rejects_label_and_pair_corruption(self):
        rows = generate("advanced_pilot", 2)
        invalid = copy.deepcopy(rows)
        invalid[0]["gold"] = not invalid[0]["gold"]
        with self.assertRaises(ValueError):
            validate(invalid)
        with self.assertRaises(ValueError):
            validate(rows[:-1])
        with self.assertRaises(ValueError):
            validate(rows + rows[:1])

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            generate("unknown")
        with self.assertRaises(ValueError):
            generate("advanced_pilot", 1)


if __name__ == "__main__":
    unittest.main()
