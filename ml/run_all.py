"""Run the whole pipeline in the right order.

    python -m ml.run_all                 # everything
    python -m ml.run_all --skip-neural   # classical models only (no torch needed)

Order matters: ml.train rewrites results/metrics.csv, so the neural scripts
(which merge their rows into it) run after it, and ml.evaluate runs last to
redraw figures and refresh results/research.json for the Research page.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

STEPS = [
    ("synthetic Indian training data", ["ml.synth"], False),
    ("import public Indian datasets", ["ml.import_public"], False),
    ("build dataset", ["ml.build_dataset"], False),
    ("NB / LR / SVM (E1-E3), save deployed model", ["ml.train"], False),
    ("simple RNN + BiLSTM (E1-E4)", ["ml.train_rnn"], True),
    ("DistilBERT (E1-E4)", ["ml.train_bert"], True),
    ("E4-E7 + figures + research.json", ["ml.evaluate"], False),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-neural", action="store_true", help="skip RNN / LSTM / DistilBERT")
    a = ap.parse_args()
    t_all = time.time()
    for name, mod, neural in STEPS:
        if neural and a.skip_neural:
            print(f"\n=== skip: {name}")
            continue
        print(f"\n=== {name}  (python -m {' '.join(mod)})", flush=True)
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", *mod])
        if r.returncode:
            sys.exit(f"step failed: {name} (exit {r.returncode})")
        print(f"=== done in {time.time() - t0:.0f}s")
    print(f"\nall steps finished in {(time.time() - t_all) / 60:.1f} min. Restart the API to load the new model.")


if __name__ == "__main__":
    main()
