"""Generate successive exploratory stress batches, with no empirical predictions.

Each round adds difficulty to three behavioral probes with explicit, invariant
reference answers. Search-until-error is exploratory selection, not confirmation.
Templates are reused; the generated contexts are not independent clinical patients.
The increasing distractor level is capped at eight to fit the fixed context window.
"""
import argparse
from datetime import date, timedelta
from fractions import Fraction
import json
from pathlib import Path
import random

from .generate_advanced import _triplet, validate

FAMILIES = ("dose_arithmetic", "patient_attribution", "temporal_conflicts")
CONTEXTS_PER_FAMILY = 8
MAX_NOTE_CHARS = 15000


def _fmt(value):
    value = Fraction(value)
    return f"{float(value):g}"


def _dose(phase, i, rng, level):
    patient = f"SYN-{phase}-DOSE-{i:03d}"
    drug = ("hydrocortisone", "metoprolol tartrate", "prednisolone", "carvedilol")[i % 4]
    # All supplied decimal operands are exact. No dose is inferred from clinical practice.
    s1 = rng.choice(("5", "12.5", "20", "25"))
    c1 = rng.choice(("1.5", "2", "2.5", "3"))
    s2 = rng.choice(("2.5", "5", "10", "12.5"))
    c2 = rng.choice(("0.5", "1.5", "2.5"))
    concentration_mass = rng.choice(("5", "10", "15"))
    concentration_volume = rng.choice(("2", "5", "10"))
    dose_volume = rng.choice(("2.5", "7.5", "12.5"))
    components = [Fraction(s1) * Fraction(c1), Fraction(s2) * Fraction(c2),
                  Fraction(concentration_mass) / Fraction(concentration_volume) * Fraction(dose_volume)]
    total = sum(components)
    prefix = (f"Synthetic one-day final prescription ledger for patient {patient}. "
              "Every scheduled order below is for the same active ingredient and remains active. "
              "The three scheduled entries are additive, not replacements. No other dose is scheduled today.")
    orders = [
        f"FINAL ACTIVE SCHEDULED ORDER A, once today at 08:00: {drug}, {s1} mg per tablet, {c1} tablets.",
        f"FINAL ACTIVE SCHEDULED ORDER B, once today at 20:00: {drug}, {s2} mg per tablet, {c2} tablets.",
        f"FINAL ACTIVE SCHEDULED ORDER C, once today at 14:00: {drug} oral solution, {concentration_mass} mg per {concentration_volume} mL; give {dose_volume} mL.",
    ]
    distractors = []
    for j in range(level + 2):
        amount = rng.choice(("10", "25", "40", "50"))
        distractors.append(
            f"HISTORICAL INACTIVE ORDER {j+1}: {drug} {amount} mg twice daily. "
            "Superseded before the displayed one-day prescription; exclude it from today's scheduled dose.")
        if j % 2 == 0:
            distractors.append(
                f"PRN ENTRY {j+1}: {drug} {amount} mg if needed; not scheduled and no administration documented today.")
    mixed = orders + distractors
    rng.shuffle(mixed)
    worksheet = (f"Reconciliation worksheet for scheduled entries only: "
                 f"A: {s1} * {c1} = {_fmt(components[0])} mg; "
                 f"B: {s2} * {c2} = {_fmt(components[1])} mg; "
                 f"C: ({concentration_mass}/{concentration_volume}) * {dose_volume} = {_fmt(components[2])} mg. "
                 f"Sum = {_fmt(total)} mg.")
    return _triplet(phase, "dose_arithmetic", i, patient,
        f"What total number of milligrams of {drug} is scheduled for this one 24-hour day? "
        "Add all FINAL ACTIVE SCHEDULED orders A, B, and C. Exclude inactive historical and PRN orders. "
        "For oral solution, multiply (mg per mL) by mL. Return one JSON number in milligrams.",
        float(total), {"control": prefix + "\n" + "\n".join(orders),
        "challenge": prefix + "\n" + "\n".join(mixed),
        "rescue": prefix + "\n" + "\n".join(orders) + "\n" + worksheet},
        answer_type="number", target_drug=drug, stress_level=level,
        tablet_orders=[{"strength_mg":s1,"tablets":c1}, {"strength_mg":s2,"tablets":c2}],
        solution_order={"mass_mg":concentration_mass,"per_ml":concentration_volume,"volume_ml":dose_volume},
        reference_total_fraction=str(total))


def _attribution(phase, i, rng, level):
    patient = f"SYN-{phase}-P{1000+i}"
    drug = ("amoxicillin", "cephalexin", "doxycycline", "azithromycin")[i % 4]
    gold = (i // 4 + i % 4) % 2 == 0
    fact = (f"SIGNED ALLERGY INTERVIEW — subject ID {patient}, the target patient: "
            + (f"personal allergy to {drug} is documented, with hives after exposure."
               if gold else f"the target patient specifically denies any personal allergy to {drug}."))
    base = (f"Synthetic chart compilation. Answer about subject ID {patient} only. "
            "The compilation includes identified relatives and separate people's records; their facts are not the target patient's facts.")
    unrelated = []
    for j in range(level * 3 + 2):
        other = f"{patient}-OTHER-{j:02d}"
        status = f"no known {drug} allergy" if gold else f"{drug} allergy, reaction hives"
        relationship = ("mother", "brother", "spouse", "unrelated patient")[j % 4]
        unrelated.append(
            f"IMPORTED RECORD {j+1} — subject ID {other}; relationship to target: {relationship}. "
            f"This separate subject's allergy review states {status}. "
            f"This record does not describe subject ID {patient}.")
    rng.shuffle(unrelated)
    challenge = unrelated[:]
    challenge.insert(rng.randrange(1, len(challenge)), fact)
    return _triplet(phase, "patient_attribution", i, patient,
        f"Does subject ID {patient}, the target patient, have a personal documented allergy to {drug}? "
        "Base the answer on the signed interview for that exact subject ID.", gold,
        {"control":base+"\n"+fact,
         "challenge":base+"\n"+"\n".join(challenge),
         "rescue":base+"\n"+fact+"\n"+"\n".join(unrelated)},
        target_drug=drug, stress_level=level, expected_target_fact=fact)


def _temporal(phase, i, rng, level, round_index):
    patient = f"SYN-{phase}-TIME-{i:03d}"
    episode = f"E{round_index:03d}-{i:03d}"
    drug = ("metformin", "lisinopril", "atorvastatin", "apixaban")[i % 4]
    gold = (i // 4 + i % 4) % 2 == 0
    day = date(2020 + round_index % 50, 1, 1) + timedelta(days=round_index % 360 + i)
    final = (f"{day.isoformat()} 18:45 — SIGNED FINAL RECONCILIATION, patient {patient}, episode {episode}: "
             + (f"continue {drug} after this discharge; active on this episode's final medication list."
                if gold else f"discontinue {drug} after this discharge; not active on this episode's final medication list."))
    base = (f"Synthetic timestamped medication ledger for target patient {patient}. "
            f"The question concerns discharge episode {episode} on {day.isoformat()}. "
            "Each entry identifies its patient and episode; display order is not chronological.")
    entries = []
    for j in range(level * 2 + 2):
        event_time = f"{8+j//6:02d}:{(j*7)%60:02d}"
        earlier = "temporarily held" if j % 2 else "listed active pending final review"
        entries.append(
            f"{day.isoformat()} {event_time} — SIGNED INTERIM NOTE, patient {patient}, episode {episode}: "
            f"{drug} {earlier}; defer post-discharge status to the signed final reconciliation.")
    for j in range(level + 1):
        old_day = day - timedelta(days=30 + j)
        other_episode = f"PRIOR-{episode}-{j}"
        old_status = "discontinued" if gold else "continued and active"
        entries.append(
            f"{old_day.isoformat()} 19:00 — ARCHIVED FINAL RECONCILIATION, patient {patient}, "
            f"episode {other_episode}: {drug} was {old_status} for that separate earlier discharge.")
    entries.append(final)
    challenge = entries[:]
    rng.shuffle(challenge)
    if challenge[-1] == final:
        challenge[0], challenge[-1] = challenge[-1], challenge[0]
    ordered = sorted(entries)  # ISO dates/times sort chronologically.
    return _triplet(phase, "temporal_conflicts", i, patient,
        f"Is {drug} active after discharge from episode {episode} on {day.isoformat()} for patient {patient}, "
        "according to that episode's SIGNED FINAL RECONCILIATION? Ignore other episodes and interim statuses.",
        gold, {"control":base+"\n"+final,
               "challenge":base+"\n"+"\n".join(challenge),
               "rescue":base+"\n"+"\n".join(ordered)},
        target_drug=drug, stress_level=level, target_episode=episode,
        expected_final_fact=final)


def generate_stress(round_index):
    """Return 72 matched prompts from three families for a new exploratory round."""
    if type(round_index) is not int or round_index < 1:
        raise ValueError("Stress round_index must be a positive integer")
    phase = f"stress_round_{round_index:03d}"
    level = min(round_index, 8)
    rng = random.Random(20261027000 + round_index)
    rows = []
    for i in range(CONTEXTS_PER_FAMILY):
        rows.extend(_dose(phase, i, rng, level))
        rows.extend(_attribution(phase, i, rng, level))
        rows.extend(_temporal(phase, i, rng, level, round_index))
    rng.shuffle(rows)
    validate(rows)
    if any(len(row["note"]) > MAX_NOTE_CHARS for row in rows):
        raise ValueError("Generated stress note exceeds fixed context budget")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, required=True, dest="round_index")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        rows = generate_stress(args.round_index)
    except ValueError as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in rows))
    print(f"Wrote {len(rows)} exploratory prompts; max note length {max(len(r['note']) for r in rows)} characters.")


if __name__ == "__main__":
    main()
