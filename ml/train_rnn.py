"""Recurrent baselines for experiments E1-E4. Not deployed.

    python -m ml.train_rnn                          # all four, E1-E4
    python -m ml.train_rnn --arch lstm_attn --exp e3

Architectures:
    rnn         Elman RNN, classifies from the final hidden state
    rnn_attn    same RNN + additive attention pooling over all hidden states
    lstm        BiLSTM, classifies from the final forward + backward states
    lstm_attn   same BiLSTM + additive attention pooling

Attention (Bahdanau-style):  u_t = tanh(W h_t + b),  a_t = softmax(v . u_t),
c = sum_t a_t h_t, with padding masked out. Instead of relying on the last
state (which over-weights the final words), the model learns which words
matter; RecurrentClassifier.attention(text) returns those weights.

Needs torch (see requirements-bert.txt). Embeddings are trained from scratch,
so these sit between TF-IDF models (no word order) and DistilBERT
(pretrained): they model word order but know nothing beyond this dataset.

Tokens are words from ml.preprocess (URLs, phones, amounts masked), capped
at the most frequent --vocab words; unknown words map to <unk>. That makes
them word-level models, so obfuscated words become <unk> unless the
normalizer runs first. E4 measures exactly that.

Results merge into results/metrics.csv / experiments.json as models "rnn",
"rnn_attn", "lstm" and "lstm_attn", and E4 into results/robustness_rnn.csv + research.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

from ml.metrics import evaluate
from ml.obfuscate import obfuscate
from ml.preprocess import preprocess, preprocess_raw
from ml.train import RESULTS, load

ATTACKS = ["clean", "leet", "homoglyph", "spacing", "dots", "zero_width", "mixed"]
PAD, UNK = 0, 1
ARCHS = ["rnn", "rnn_attn", "lstm", "lstm_attn"]
NAMES = {"rnn": "RNN", "rnn_attn": "RNN + attention", "lstm": "BiLSTM", "lstm_attn": "BiLSTM + attention"}


class RecurrentClassifier:
    """sklearn-style wrapper (fit / predict_proba / classes_) around a PyTorch RNN or BiLSTM."""

    def __init__(self, arch="lstm", vocab=20000, emb=128, hidden=128, max_len=64, epochs=6,
                 batch_size=64, lr=2e-3, device="auto", normalizer=False, seed=42):
        import torch

        self.torch = torch
        self.arch, self.vocab_size, self.emb, self.hidden = arch, vocab, emb, hidden
        self.max_len, self.epochs, self.batch_size, self.lr = max_len, epochs, batch_size, lr
        self.normalizer, self.seed = normalizer, seed
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device

    # -- text -> ids
    def _tokens(self, text):
        return (preprocess(text) if self.normalizer else preprocess_raw(text)).split()

    def _encode(self, texts):
        ids = np.zeros((len(texts), self.max_len), dtype=np.int64)
        lens = np.ones(len(texts), dtype=np.int64)
        for i, t in enumerate(texts):
            toks = [self.stoi.get(w, UNK) for w in self._tokens(t)][: self.max_len] or [UNK]
            ids[i, : len(toks)] = toks
            lens[i] = len(toks)
        return self.torch.tensor(ids), self.torch.tensor(lens)

    def _build(self, n_classes):
        torch = self.torch
        nn = torch.nn
        V, E, H = len(self.stoi) + 2, self.emb, self.hidden
        base, attention = self.arch.removesuffix("_attn"), self.arch.endswith("_attn")

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.emb = nn.Embedding(V, E, padding_idx=PAD)
                if base == "lstm":
                    self.rnn = nn.LSTM(E, H, batch_first=True, bidirectional=True)
                    out = 2 * H
                else:  # Elman RNN, unidirectional: the classic baseline
                    self.rnn = nn.RNN(E, H, batch_first=True, nonlinearity="tanh")
                    out = H
                if attention:
                    # Additive (Bahdanau-style) attention pooling:
                    #   u_t = tanh(W h_t + b),  a_t = softmax_t(v . u_t),  c = sum_t a_t h_t
                    self.att_w = nn.Linear(out, out)
                    self.att_v = nn.Linear(out, 1, bias=False)
                self.drop = nn.Dropout(0.3)
                self.fc = nn.Linear(out, n_classes)
                self.last_attention = None

            def forward(self, x, lens):
                e = self.drop(self.emb(x))
                packed = nn.utils.rnn.pack_padded_sequence(e, lens.cpu(), batch_first=True, enforce_sorted=False)
                seq, h = self.rnn(packed)
                if attention:
                    states, _ = nn.utils.rnn.pad_packed_sequence(seq, batch_first=True, total_length=x.size(1))
                    scores = self.att_v(torch.tanh(self.att_w(states))).squeeze(-1)  # (batch, time)
                    mask = torch.arange(x.size(1), device=x.device)[None, :] < lens.to(x.device)[:, None]
                    weights = torch.softmax(scores.masked_fill(~mask, float("-inf")), dim=1)
                    self.last_attention = weights.detach()
                    pooled = (weights.unsqueeze(-1) * states).sum(dim=1)
                elif base == "lstm":
                    h = h[0]  # (h_n, c_n) -> h_n
                    pooled = torch.cat([h[-2], h[-1]], dim=1)  # forward + backward final states
                else:
                    pooled = h[-1]
                return self.fc(self.drop(pooled))

        return Net().to(self.device)

    def attention(self, text):
        """Per-token attention weights for one message (attention models only)."""
        if not self.arch.endswith("_attn"):
            raise ValueError("attention weights exist only for *_attn models")
        X, L = self._encode([text])
        self.net.eval()
        with self.torch.no_grad():
            self.net(X.to(self.device), L)
        toks = (self._tokens(text) or ["<unk>"])[: self.max_len]
        return list(zip(toks, self.net.last_attention[0, : len(toks)].cpu().numpy().round(4).tolist()))

    def fit(self, texts, y):
        torch = self.torch
        torch.manual_seed(self.seed)
        random.seed(self.seed)
        np.random.seed(self.seed)
        texts = list(texts)
        counts = Counter(w for t in texts for w in self._tokens(t))
        self.stoi = {w: i + 2 for i, (w, _) in enumerate(counts.most_common(self.vocab_size))}
        self.classes_ = sorted(set(y))
        idx = {c: i for i, c in enumerate(self.classes_)}
        X, L = self._encode(texts)
        Y = torch.tensor([idx[v] for v in y])
        self.net = self._build(len(self.classes_))
        cnt = np.bincount(Y.numpy(), minlength=len(self.classes_))
        w = torch.tensor(len(Y) / (len(cnt) * np.maximum(cnt, 1)), dtype=torch.float).to(self.device)
        loss_fn = torch.nn.CrossEntropyLoss(weight=w)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        for ep in range(self.epochs):
            self.net.train()
            perm = torch.randperm(len(Y))
            t0, total = time.time(), 0.0
            for b in range(0, len(Y), self.batch_size):
                i = perm[b:b + self.batch_size]
                logits = self.net(X[i].to(self.device), L[i])
                loss = loss_fn(logits, Y[i].to(self.device))
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                opt.step()
                total += loss.item() * len(i)
            print(f"    {self.arch} epoch {ep + 1}/{self.epochs} loss {total / len(Y):.4f} ({time.time() - t0:.0f}s)", flush=True)
        return self

    def predict_proba(self, texts):
        torch = self.torch
        X, L = self._encode(list(texts))
        self.net.eval()
        out = []
        with torch.no_grad():
            for b in range(0, len(X), 256):
                out.append(torch.softmax(self.net(X[b:b + 256].to(self.device), L[b:b + 256]), dim=-1).cpu().numpy())
        return np.vstack(out)


def run(args):
    train, dev = load("train"), load("dev_indian")
    if train is None:
        sys.exit("data/processed/train.csv not found. Run: python -m ml.build_dataset")
    tests = {n: load(n) for n in ("test_uci", "test_ms", "test_indian")}
    full = pd.concat([train, dev], ignore_index=True) if dev is not None else train
    uci = train[train["source"] == "uci"]
    rows, rob = [], []

    for arch in args.arch:
        kw = dict(arch=arch, epochs=args.epochs, device=args.device)

        def record(exp, name, df, m, secs):
            r = evaluate(m, df["text"].tolist(), df["binary"].tolist())
            rows.append({"exp": exp, "model": arch, "task": "binary", "test": name, "train_secs": round(secs, 1),
                         "char": False, "features": False, "normalizer": m.normalizer, **r})
            print(f"  {exp} {arch:<4} {name:<12} n={r['n']:<5} acc={r['accuracy']:.3f} f1={r['f1_macro']:.3f} "
                  f"recall={r.get('scam_recall', float('nan')):.3f} ece={r['ece']:.3f}")

        if {"e1", "e2"} & set(args.exp):
            print(f"\nE1/E2: {arch} on UCI ({len(uci)} rows)")
            t0 = time.time()
            m = RecurrentClassifier(**kw).fit(uci["text"].tolist(), uci["binary"].tolist())
            s = time.time() - t0
            if "e1" in args.exp:
                record("E1", "test_uci", tests["test_uci"], m, s)
            if "e2" in args.exp and tests["test_indian"] is not None:
                record("E2", "test_indian", tests["test_indian"], m, s)
                # Out-of-domain accuracy of from-scratch recurrent nets varies a lot
                # with the random seed, so E2 is also reported as mean +/- std.
                if args.e2_seeds > 1:
                    ind = tests["test_indian"]
                    accs = [rows[-1]["accuracy"]] + [
                        evaluate(RecurrentClassifier(**{**kw, "seed": args.seed + k}).fit(uci["text"].tolist(), uci["binary"].tolist()),
                                 ind["text"].tolist(), ind["binary"].tolist())["accuracy"]
                        for k in range(1, args.e2_seeds)]
                    rows[-1].update(e2_seed_mean=round(float(np.mean(accs)), 4), e2_seed_std=round(float(np.std(accs)), 4),
                                    e2_seeds=len(accs))
                    print(f"  E2 {arch} over {len(accs)} seeds: {np.mean(accs):.3f} +/- {np.std(accs):.3f}  {np.round(accs, 3)}")

        if {"e3", "e4"} & set(args.exp):
            for norm in ([False, True] if "e4" in args.exp else [False]):
                label = f"{NAMES[arch]}{' + normalizer' if norm else ''}"
                print(f"\nE3/E4: {label}, train {len(full)} rows")
                t0 = time.time()
                m = RecurrentClassifier(normalizer=norm, **kw).fit(full["text"].tolist(), full["binary"].tolist())
                s = time.time() - t0
                if "e3" in args.exp and not norm:
                    for n, df in tests.items():
                        if df is not None and len(df):
                            record("E3", n, df, m, s)
                if "e4" in args.exp:
                    tn = "test_indian" if tests["test_indian"] is not None and len(tests["test_indian"]) >= 100 else "test_ms"
                    test = tests[tn]
                    for attack in ATTACKS:
                        texts = test["text"].tolist() if attack == "clean" else \
                            [obfuscate(t, attack, seed=args.seed + i) for i, t in enumerate(test["text"])]
                        r = evaluate(m, texts, test["binary"].tolist())
                        rob.append({"config": label, "model": arch, "normalizer": norm, "attack": attack, "test": tn,
                                    "accuracy": r["accuracy"], "f1_macro": r["f1_macro"], "scam_recall": r.get("scam_recall")})
                    print("  " + "  ".join(f"{x['attack']}={x['scam_recall']:.2f}" for x in rob[-len(ATTACKS):]))
    return rows, rob


def merge_results(rows, rob, models):
    RESULTS.mkdir(exist_ok=True)
    if rows:
        exps = {r["exp"] for r in rows}
        f = RESULTS / "metrics.csv"
        old = pd.read_csv(f) if f.exists() else pd.DataFrame()
        if not old.empty:
            old = old[~(old["model"].isin(models) & old["exp"].isin(exps))]
        new = pd.DataFrame(rows).drop(columns=["labels", "confusion"], errors="ignore")
        pd.concat([old, new], ignore_index=True).to_csv(f, index=False)
        fj = RESULTS / "experiments.json"
        ex = json.loads(fj.read_text()) if fj.exists() else []
        ex = [r for r in ex if not (r.get("model") in models and r.get("exp") in exps)] + rows
        fj.write_text(json.dumps(ex, indent=2, default=float))
    fr = RESULTS / "research.json"
    research = json.loads(fr.read_text()) if fr.exists() else {}
    if rob:
        pd.DataFrame(rob).to_csv(RESULTS / "robustness_rnn.csv", index=False)
        research["robustness_rnn"] = rob
    fr.write_text(json.dumps(research, indent=2, default=float))
    print(f"\nmerged {', '.join(models)} results into {RESULTS}. Run `python -m ml.evaluate --only figs` to redraw figures.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arch", nargs="+", default=ARCHS, choices=ARCHS)
    ap.add_argument("--exp", nargs="+", default=["e1", "e2", "e3", "e4"], choices=["e1", "e2", "e3", "e4"])
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--e2-seeds", type=int, default=5, help="seeds for the E2 mean +/- std (1 = single run)")
    a = ap.parse_args()
    rows, rob = run(a)
    merge_results(rows, rob, a.arch)


if __name__ == "__main__":
    main()
