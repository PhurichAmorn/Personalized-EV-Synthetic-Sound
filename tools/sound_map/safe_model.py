"""Fit a pass/fail model from generate.py trial logs (*.trials.jsonl).
Usage: safe_model.py trials.jsonl [more.jsonl ...]
Prints cross-validated AUC, the genes that matter most, and the safe range of each.
Numeric genes only (strings skipped); logistic regression with L2, numpy only."""
import json, sys
import numpy as np

def load(paths):
    rows = [json.loads(l) for p in paths for l in open(p)]
    keys = sorted(k for k, v in rows[0]['g'].items() if isinstance(v, (int, float)) and 'Seed' not in k)
    X = np.array([[r['g'].get(k, 0) for k in keys] for r in rows], float)
    return keys, X, np.array([r['pass'] for r in rows], float)

def fit(X, y, lam=1.0, steps=400):
    w = np.zeros(X.shape[1] + 1)
    A = np.c_[X, np.ones(len(X))]
    for _ in range(steps):  # ponytail: plain gradient descent, fine at ~1e3-1e4 rows
        p = 1 / (1 + np.exp(-A @ w))
        g = A.T @ (p - y) / len(y) + lam * np.r_[w[:-1], 0] / len(y)
        w -= 0.5 * g
    return w

def predict(w, X):
    return 1 / (1 + np.exp(-(np.c_[X, np.ones(len(X))] @ w)))

def auc(p, y):
    r = p.argsort().argsort() + 1
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

if __name__ == '__main__':
    keys, X, y = load(sys.argv[1:])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    idx = np.random.default_rng(0).permutation(len(y)); folds = np.array_split(idx, 5)
    out = np.zeros(len(y))
    for f in folds:
        tr = np.setdiff1d(idx, f); out[f] = predict(fit(Z[tr], y[tr]), Z[f])
    print(f'{len(y)} tries, {int(y.sum())} passed ({y.mean():.0%}); cross-validated AUC {auc(out, y):.2f} (0.5 = no better than chance)')
    w = fit(Z, y)
    print('genes that matter most (+ helps pass, - hurts):')
    for i in np.argsort(-abs(w[:-1]))[:10]:
        print(f'  {keys[i]:12s} {w[i]:+.2f}   passing 10-90%: {np.percentile(X[y == 1, i], 10):.3g} .. {np.percentile(X[y == 1, i], 90):.3g}')
    for thr in (.3, .5):  # what a pre-filter would do
        keep = out >= thr
        print(f'pre-filter p>={thr}: keeps {keep.mean():.0%} of tries, {y[keep].mean():.0%} of kept pass, {y[keep].sum() / y.sum():.0%} of all passers kept')
