"""Small GP preference model used to propose informative sound comparisons."""
import math

import numpy as np


def _kernel(a, b, length=0.35):
    delta = np.asarray(a)[:, None, :] - np.asarray(b)[None, :, :]
    return np.exp(-0.5 * np.sum(delta * delta, axis=2) / (length * length))


def select_query(pool, pairs_a, pairs_b, outcomes, anchor, seen_pairs=(), incumbent=None,
                 min_distance=0.01, kernel_length=0.35, kernel_groups=None):
    """Choose an EI challenger, or legacy entropy pairing when incumbent is absent."""
    pool = np.asarray(pool, dtype=float)
    xa, xb = np.asarray(pairs_a, dtype=float), np.asarray(pairs_b, dtype=float)
    y = np.asarray([{'A': -1., 'equal': 0., 'B': 1.}[choice] for choice in outcomes])
    anchor = np.asarray(anchor, dtype=float).reshape(1, -1)
    seen = {tuple(sorted(pair)) for pair in seen_pairs}
    def kernel(a, b):
        if kernel_groups:
            return sum(_kernel(a[:, group], b[:, group], kernel_length) for group in kernel_groups) / len(kernel_groups)
        return _kernel(a, b) if kernel_length == 0.35 else _kernel(a, b, kernel_length)

    if len(y):
        k = (kernel(xb, xb) - kernel(xb, xa)
             - kernel(xa, xb) + kernel(xa, xa))
        k.flat[::len(k) + 1] += 0.08
        try:
            chol = np.linalg.cholesky(k)
            alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y))
            cross = (kernel(xb, pool) - kernel(xb, anchor)
                     - kernel(xa, pool) + kernel(xa, anchor))
            prior = (kernel(pool, pool) - kernel(pool, anchor)
                     - kernel(anchor, pool) + kernel(anchor, anchor))
            solved = np.linalg.solve(chol, cross)
            mean = cross.T @ alpha
            covariance = prior - solved.T @ solved
            covariance = (covariance + covariance.T) * 0.5
        except np.linalg.LinAlgError:
            mean = np.zeros(len(pool))
            covariance = np.eye(len(pool))
    else:
        mean = np.zeros(len(pool))
        covariance = np.eye(len(pool))

    if incumbent is not None:
        best, best_improvement = None, -1.0
        for challenger in range(len(pool)):
            if challenger == incumbent or tuple(sorted((incumbent, challenger))) in seen:
                continue
            if np.linalg.norm(pool[challenger] - pool[incumbent]) < min_distance:
                continue
            difference = float(mean[challenger] - mean[incumbent])
            # Latent utility uncertainty excludes irreducible response noise.
            variance = max(0.0, float(covariance[challenger, challenger]
                                     + covariance[incumbent, incumbent]
                                     - 2 * covariance[challenger, incumbent]))
            deviation = math.sqrt(variance)
            if deviation > 1e-12:
                z = difference / deviation
                probability = 0.5 * (1 + math.erf(z / math.sqrt(2)))
                density = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
                improvement = difference * probability + deviation * density
            else:
                improvement = max(0.0, difference)
            if improvement > best_improvement:
                best, best_improvement = (incumbent, challenger), improvement
        return best

    best, best_entropy = None, -1.0
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            if tuple(sorted((i, j))) in seen:
                continue
            distance = float(np.linalg.norm(pool[i] - pool[j]))
            if distance < 0.12:
                continue
            variance = max(1e-6, covariance[i, i] + covariance[j, j] - 2 * covariance[i, j] + 0.08)
            deviation = math.sqrt(variance)
            difference = (mean[j] - mean[i]) / deviation
            thresholds = (-0.5, 0.5)
            cdf = [0.5 * (1 + math.erf((cut - difference) / math.sqrt(2))) for cut in thresholds]
            probabilities = [cdf[0], *(b - a for a, b in zip(cdf, cdf[1:])), 1 - cdf[-1]]
            entropy = -sum(p * math.log(max(p, 1e-12)) for p in probabilities)
            if entropy > best_entropy:
                best, best_entropy = (i, j), entropy
    return best
