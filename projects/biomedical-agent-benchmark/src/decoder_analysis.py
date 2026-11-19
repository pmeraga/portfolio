"""Offline fixed-workflow technical qualification, not causal DBS efficacy.
Python >=3.10; numpy,pandas,scipy,scikit-learn,h5py.
Run: python src/decoder_analysis.py data/Shirvalkar_sEEGCLDBS_2026.zip results
Optional: --bootstrap-reps 2000 (default); --bootstrap-reps 0 skips uncertainty.
No network calls. Reads the input ZIP directly; writes all evidence and results.
The candidate is defined in workflow_charter.md. Main gate is mean AUC>=0.60.
"""

from pathlib import Path
import io
import json
import zipfile
import numpy as np
import pandas as pd
import h5py
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold


class Sources:
    def __init__(self, p):
        p = Path(p)
        self.z = zipfile.ZipFile(p) if p.is_file() else None
        self.files = (
            {Path(n).name: n for n in self.z.namelist() if not n.endswith("/")}
            if self.z
            else {n.name: n for n in p.rglob("*") if n.is_file()}
        )

    def read(self, n):
        return self.z.read(self.files[n]) if self.z else self.files[n].read_bytes()


def read_data(path):
    s = Sources(path)
    meta = pd.read_csv(io.BytesIO(s.read("longitudinal_phase_metadata.csv"))).set_index(
        "participant"
    )
    devices = {}
    audit = []
    for name in sorted(k for k in s.files if k.endswith("_ambulatory_features.h5")):
        with h5py.File(io.BytesIO(s.read(name))) as h:
            dev = str(h.attrs["device_side"])
            p = str(h.attrs["participant"])
            freq = h["frequency_hz"][:]
            psd = h["psd"][:].astype(float)
            pain = h["pain_MPQtotal"][:]
            time = h["pain_timestamp_unix"][:]
            cluster = h["cluster_row"][:]
        norm = psd[:, (freq >= 40) & (freq <= 80)].mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            v = psd / norm[:, None]
        good = (
            np.isfinite(pain) & np.isfinite(v).all(axis=1) & (norm > 0) & (cluster >= 0)
        )
        c, t, y, v = cluster[good], time[good], pain[good], v[good]
        # A repeated clinical survey must not create extra independent label units.
        frame = pd.DataFrame(v, columns=np.arange(len(freq)))
        frame["cluster"] = c
        frame["t"] = t
        frame["pain"] = y
        if frame.groupby("cluster").pain.nunique().max() > 1:
            raise ValueError("Conflicting pain scores within device survey")
        grouped = frame.groupby("cluster", sort=True).mean()
        devices[dev] = dict(
            person=p,
            c=grouped.index.to_numpy(),
            t=grouped.t.to_numpy(),
            y=grouped.pain.to_numpy(),
            v=grouped[np.arange(len(freq))].to_numpy(),
            freq=freq,
        )
        audit.append(
            dict(
                device=dev,
                n_source=len(cluster),
                n_valid=int(good.sum()),
                n_unique=len(grouped),
                duplicates_collapsed=int(good.sum()) - len(grouped),
            )
        )
    person = {}
    for p in sorted(meta.index):
        rows = pd.concat(
            [
                pd.DataFrame({"c": a["c"], "t": a["t"], "y": a["y"]})
                for a in devices.values()
                if a["person"] == p
            ],
            ignore_index=True,
        )
        if rows.groupby("c").y.nunique().max() > 1:
            raise ValueError("Conflicting bilateral pain labels for a survey")
        # Use one clock for each clinical survey across bilateral observations.
        b = rows.groupby("c").agg(t=("t", "median"), y=("y", "first"))
        person[p] = b
    return devices, person, meta, audit


def fit_band(x, y):
    if len(np.unique(y)) != 2:
        raise ValueError("Cannot train without both classes")
    mu0 = x[~y].mean(axis=0)
    mu1 = x[y].mean(axis=0)
    var = ((x[~y] - mu0) ** 2).sum(axis=0) + ((x[y] - mu1) ** 2).sum(axis=0)
    var /= len(y) - 2
    good = var > 0
    beta = np.where(good, (mu1 - mu0) / np.maximum(var, 1e-300), 0)
    auc = np.array(
        [
            roc_auc_score(y, beta[j] * x[:, j]) if good[j] else -0.5
            for j in range(x.shape[1])
        ]
    )
    j = int(np.argmax(auc))
    intercept = -0.5 * (mu1[j] ** 2 - mu0[j] ** 2) / var[j] + np.log(
        y.mean() / (1 - y.mean())
    )
    # Rank-optimal polarity is diagnostic only: the released LDA uses actual means.
    rankauc = roc_auc_score(y, x[:, j])
    return (
        j,
        float(beta[j]),
        float(intercept),
        float(auc[j]),
        int(np.sign(beta[j]) != np.sign(rankauc - 0.5)),
    )


def nested_iid(x, y, seed=42):
    pred = np.full(len(y), np.nan)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(x, y):
        j, b, i, _, _ = fit_band(x[tr], y[tr])
        pred[te] = b * x[te, j] + i
    return pred, float(roc_auc_score(y, pred))


def evaluate(
    devices, persons, meta, shift_hours=10, transform="relative", outlier=None, seed=42
):
    # Cross-clock offset is a SOURCE sensitivity, never an endpoint correction.
    cut = {
        p: pd.Timestamp(meta.loc[p, "stage3_onset_datetime"]).value / 1e9
        + shift_hours * 3600
        for p in persons
    }
    end = {
        p: pd.Timestamp(meta.loc[p, "endpoint_datetime"]).value / 1e9
        + shift_hours * 3600
        for p in persons
    }
    limits = {}
    for p, a in persons.items():
        q = a[(a.t < cut[p]) & (a.t <= end[p])].y.to_numpy()
        limits[p] = np.percentile(q, [30, 70])
    out = []
    preds = {}
    for dev, a in devices.items():
        p = a["person"]
        v = a["v"]
        freq = a["freq"]
        times = persons[p].loc[a["c"], "t"].to_numpy()
        keep = times <= end[p]
        if transform == "log":
            v = np.log(np.maximum(v, 1e-12))
        x = np.array(
            [
                v[:, (freq >= c - 2.5) & (freq <= c + 2.5)].mean(axis=1)
                for c in range(51)
            ]
        ).T
        lo, hi = limits[p]
        y = a["y"] > hi
        eligible = ((a["y"] <= lo) | (a["y"] > hi)) & keep
        tr = (times < cut[p]) & eligible
        te = (times >= cut[p]) & eligible
        if outlier is not None:
            # Threshold estimated in calibration ONLY; apply unchanged to future data.
            band = (a["freq"] >= 45) & (a["freq"] < 55)
            q = a["v"][:, band].mean(axis=1)
            m = q[tr].mean()
            sd = q[tr].std(ddof=1)
            accept = np.abs(q - m) <= outlier * sd
            tr &= accept
            te &= accept
            eligible &= accept
        row = dict(
            device=dev,
            person=p,
            low_threshold=float(lo),
            high_threshold=float(hi),
            n_train=int(tr.sum()),
            n_test=int(te.sum()),
            train_low=int((tr & ~y).sum()),
            train_high=int((tr & y).sum()),
            test_low=int((te & ~y).sum()),
            test_high=int((te & y).sum()),
        )
        if (
            min(row["train_low"], row["train_high"]) < 5
            or min(row["test_low"], row["test_high"]) < 2
        ):
            row["not_estimable"] = True
            out.append(row)
            continue
        j, b, i, trainauc, flip = fit_band(x[tr], y[tr])
        score = b * x[te, j] + i
        fauc = float(roc_auc_score(y[te], score))
        rpred, rauc = nested_iid(x[eligible], y[eligible], seed)
        row.update(
            hz=j,
            lda_train_auc=trainauc,
            forward_auc=fauc,
            iid_auc=rauc,
            rank_direction_conflict=flip,
        )
        out.append(row)
        preds[dev] = pd.DataFrame(
            dict(
                cluster=a["c"][te],
                timestamp=times[te],
                label=y[te].astype(int),
                score=score,
            )
        )
    table = pd.DataFrame(out)
    if any(r.get("not_estimable", False) for r in out):
        raise ValueError(
            "At least one side lacks class support; do not silently drop it from qualification."
        )
    patient = table.groupby("person")[["forward_auc", "iid_auc"]].mean()
    macro = patient.mean().to_dict()
    # These quantify source-person variability only, not new-patient clinical efficacy.
    from itertools import product

    boot = np.array(
        [
            patient.iloc[list(ids)].mean().to_numpy()
            for ids in product(range(len(patient)), repeat=len(patient))
        ]
    )
    ci = np.quantile(boot, [0.025, 0.975], axis=0)
    return dict(
        per_device=out,
        per_person=patient.to_dict(orient="index"),
        macro=macro,
        source_person_resampling_interval=dict(
            forward=ci[:, 0].tolist(), iid=ci[:, 1].tolist()
        ),
        total_test_rows=int(table.n_test.sum()),
        total_test_high=int(table.test_high.sum()),
        clock_shift_hours=shift_hours,
        transform=transform,
        outlier_train_sd=outlier,
    ), preds


def weighted_auc(y, score, weights):
    # Exact weighted Mann-Whitney form, including tied scores.
    _, group = np.unique(score, return_inverse=True)
    pos = np.bincount(group, weights=weights * y)
    neg = np.bincount(group, weights=weights * (1 - y))
    if pos.sum() == 0 or neg.sum() == 0:
        return np.nan
    return float((pos * (np.cumsum(neg) - 0.5 * neg)).sum() / (pos.sum() * neg.sum()))


def block_uncertainty(frames, reps=2000):
    rng = np.random.default_rng(7102)
    out = {}
    for blockdays in [1, 7, 30]:
        prepared = {}
        for person in ["P1", "P2", "P3", "P4", "P5"]:
            fs = {d: f for d, f in frames.items() if d[:2] == person}
            origin = min(f.timestamp.min() for f in fs.values())
            labels = {
                d: np.floor((f.timestamp - origin) / (86400 * blockdays))
                .astype(int)
                .to_numpy()
                for d, f in fs.items()
            }
            ids = np.unique(np.concatenate(list(labels.values())))
            prepared[person] = (
                ids,
                {d: np.searchsorted(ids, b) for d, b in labels.items()},
                fs,
            )
        values = []
        bad_by = {p: 0 for p in prepared}
        for _ in range(reps):
            people = []
            for person, (ids, blockix, fs) in prepared.items():
                sample = rng.choice(ids, len(ids), replace=True)
                counts = np.array([(sample == k).sum() for k in ids])
                aucs = []
                for d, f in fs.items():
                    weights = counts[blockix[d]]
                    a = weighted_auc(f.label.to_numpy(), f.score.to_numpy(), weights)
                    if not np.isfinite(a):
                        break
                    aucs.append(a)
                if len(aucs) != len(fs):
                    bad_by[person] += 1
                    people.append(np.nan)
                else:
                    people.append(float(np.mean(aucs)))
            if np.isfinite(people).all():
                values.append(float(np.mean(people)))
        out[str(blockdays)] = dict(
            resamples=reps,
            complete_class_support=len(values),
            undefined_by_person=bad_by,
            conditional_interval=np.quantile(values, [0.025, 0.975]).tolist()
            if values
            else None,
            qualification="Interval conditions on every side retaining both labels. Undefined replicates must be disclosed; this is not an unconditional coverage guarantee.",
        )
    return out


def main():
    import argparse
    import hashlib

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_zip")
    ap.add_argument("out", nargs="?", default="qualification_results")
    ap.add_argument("--bootstrap-reps", type=int, default=2000)
    a = ap.parse_args()
    target = Path(a.out)
    target.mkdir(parents=True, exist_ok=True)
    dev, pers, meta, audit = read_data(a.input_zip)
    primary, preds = evaluate(dev, pers, meta)
    cases = {}
    for label, shift, transform, outlier in [
        ("clock11", 11, "relative", None),
        ("clock_minus24", -14, "relative", None),
        ("clock_plus24", 34, "relative", None),
        ("log_normalized_psd", 10, "log", None),
        ("training4SD", 10, "relative", 4),
    ]:
        case, _ = evaluate(dev, pers, meta, shift, transform, outlier)
        cases[label] = case
    uncertainty = (
        block_uncertainty(preds, a.bootstrap_reps) if a.bootstrap_reps else None
    )
    decision = (
        "Qualify the candidate for this technical benchmark."
        if primary["macro"]["forward_auc"] >= 0.60
        else "Do not qualify the frozen workflow; require recalibration and prospective validation."
    )
    src = Sources(a.input_zip)
    hashes = {
        n: hashlib.sha256(src.read(n)).hexdigest()
        for n in src.files
        if n.endswith((".h5", ".csv", ".xlsx"))
    }
    support = {}
    for person in pers:
        frames = [f for d, f in preds.items() if dev[d]["person"] == person]
        combined = pd.concat(frames).groupby("cluster").label.first()
        support[person] = dict(
            distinct_low=int((combined == 0).sum()),
            distinct_high=int((combined == 1).sum()),
            distinct_total=len(combined),
        )
    out = dict(
        recommendation=decision,
        qualification_gate=0.60,
        source_audit=audit,
        distinct_monitoring_support=support,
        primary=primary,
        sensitivities=cases,
        temporal_block_uncertainty=uncertainty,
        source_sha256=hashes,
        interpretation="Fixed five-participant workflow qualification only; not causal efficacy, a new-patient guarantee or an optimal-decoder claim.",
    )
    (target / "analysis.json").write_text(json.dumps(out, indent=2) + "\n")
    pd.DataFrame(primary["per_device"]).to_csv(
        target / "device_evidence.csv", index=False
    )
    for d, frame in preds.items():
        frame.to_csv(target / f"{d}_forward_predictions.csv", index=False)
    print(
        json.dumps(
            dict(
                recommendation=decision,
                forward_auc=primary["macro"]["forward_auc"],
                random_cv_auc=primary["macro"]["iid_auc"],
                source_audit=audit,
                uncertainty=uncertainty,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
