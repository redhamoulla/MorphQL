"""Rebuild the eight English figures used by the MorphoQL manuscript."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(parents=True, exist_ok=True)

METHODS = ["First difference", "Single-scale DoG", "Multiscale maxima", "Maximum lines"]


def finish(name: str, *, legend: bool = False) -> None:
    if legend:
        plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(OUT / name, format="pdf", bbox_inches="tight")
    plt.close()


# Global macro F1.
f1 = np.array([0.461629, 0.586510, 0.573447, 0.603860])
lo = np.array([0.431074, 0.551826, 0.544037, 0.574989])
hi = np.array([0.491414, 0.619826, 0.604437, 0.632062])
plt.figure(figsize=(7.2, 4.1))
x = np.arange(len(METHODS))
plt.bar(x, f1, yerr=np.vstack([f1 - lo, hi - f1]), capsize=4)
plt.xticks(x, METHODS, rotation=18, ha="right")
plt.ylabel("Localized macro F1")
plt.ylim(0, 0.72)
finish("f1_macro_methods_en.pdf")

# Event cardinality.
events = [107.008, 46.375, 46.147, 49.888]
plt.figure(figsize=(7.2, 4.0))
plt.bar(x, events)
plt.xticks(x, METHODS, rotation=18, ha="right")
plt.ylabel("Mean events per series")
finish("event_count_methods_en.pdf")

# F1 by query.
queries = ["Q1 brief peak", "Q2 8–14 d", "Q3 18–28 d", "Q4 5–10 d trough", "Q5 +→−→+", "Q6 double peak"]
by_query = np.array([
    [0.592, 0.544, 0.207, 0.525, 0.475, 0.426],
    [0.492, 0.703, 0.584, 0.696, 0.661, 0.383],
    [0.384, 0.728, 0.769, 0.677, 0.639, 0.243],
    [0.430, 0.751, 0.779, 0.733, 0.693, 0.237],
])
plt.figure(figsize=(9.2, 4.6))
qx = np.arange(len(queries))
width = 0.19
for i, label in enumerate(METHODS):
    plt.bar(qx + (i - 1.5) * width, by_query[i], width, label=label)
plt.xticks(qx, queries, rotation=18, ha="right")
plt.ylabel("Localized F1")
plt.ylim(0, 0.9)
finish("f1_by_query_en.pdf", legend=True)

# F1 by noise level with conditional bootstrap intervals.
noise = np.array([6.0, 12.0, 20.0])
noise_f1 = np.array([
    [0.617546, 0.485941, 0.171686],
    [0.778043, 0.602836, 0.326477],
    [0.725183, 0.589014, 0.376495],
    [0.741974, 0.632468, 0.422727],
])
noise_lo = np.array([
    [0.580134, 0.439233, 0.126715],
    [0.736456, 0.549240, 0.278301],
    [0.681848, 0.543005, 0.329589],
    [0.699780, 0.588671, 0.377089],
])
noise_hi = np.array([
    [0.652924, 0.528187, 0.212197],
    [0.815000, 0.647921, 0.376004],
    [0.762376, 0.630929, 0.422943],
    [0.777910, 0.672161, 0.465409],
])
plt.figure(figsize=(7.2, 4.3))
for i, label in enumerate(METHODS):
    plt.errorbar(noise, noise_f1[i], yerr=np.vstack([noise_f1[i] - noise_lo[i], noise_hi[i] - noise_f1[i]]), marker="o", capsize=3, label=label)
plt.xlabel("Noise standard deviation")
plt.ylabel("Macro F1")
plt.xticks(noise)
plt.ylim(0.05, 0.88)
finish("f1_by_noise_en.pdf", legend=True)

# Maximum-line ablation.
variants = ["Minimum 1 scale", "No merging", "Default: 2 scales", "Adjacent scales", "No persistence weight", "Minimum 3 scales"]
ablation = [0.623242, 0.599118, 0.599003, 0.592198, 0.584355, 0.558745]
abl_lo = [0.587055, 0.564552, 0.566157, 0.561298, 0.551008, 0.531549]
abl_hi = [0.657309, 0.631464, 0.630047, 0.621639, 0.615014, 0.583641]
y = np.arange(len(variants))
plt.figure(figsize=(7.8, 4.5))
plt.barh(y, ablation, xerr=np.vstack([np.array(ablation) - np.array(abl_lo), np.array(abl_hi) - np.array(ablation)]), capsize=3)
plt.yticks(y, variants)
plt.xlabel("Macro F1")
plt.xlim(0.50, 0.68)
plt.gca().invert_yaxis()
finish("wtmm_ablation_en.pdf")

# Compiler microbenchmark. Missing cells are intentionally omitted.
n_events = np.array([100, 500, 1000, 3000, 10000])
narrow = {
    2: [1.617, 8.922, 20.008, 81.062, 590.046],
    3: [1.605, 9.414, 22.833, 118.171, np.nan],
    4: [1.658, 10.759, 26.852, 157.243, np.nan],
}
wide = {
    2: [1.833, 10.049, 22.100, 93.167, 728.407],
    3: [3.911, 24.380, 58.945, np.nan, np.nan],
    4: [12.945, 89.149, 294.376, np.nan, np.nan],
}
for regime, data, filename in [
    ("Narrow gaps", narrow, "compiler_microbenchmark_narrow_en.pdf"),
    ("Wide gaps", wide, "compiler_microbenchmark_wide_en.pdf"),
]:
    plt.figure(figsize=(6.3, 4.3))
    for length, values in data.items():
        vals = np.asarray(values, dtype=float)
        mask = np.isfinite(vals)
        plt.plot(n_events[mask], vals[mask], marker="o", label=f"{length} atoms")
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Events in relation")
    plt.ylabel("Median execution time (ms)")
    plt.title(regime)
    plt.grid(True, which="both", alpha=0.25)
    finish(filename, legend=True)

# Representative synthetic retail-like series.
rng = np.random.default_rng(91000)
days = np.arange(365)
weekday = np.array([-42, -24, -10, 4, 24, 52, -6], dtype=float)
sales = 220 + weekday[days % 7] + 11 * np.sin(2 * np.pi * days / 365) + 0.025 * days
noise_state = np.zeros(365)
innov = rng.normal(0, 12, 365)
for i in range(1, 365):
    noise_state[i] = 0.32 * noise_state[i - 1] + innov[i]
sales = sales + noise_state
sales[68:80] += 72
sales[134:138] += 92
sales[230:254] += 64
plt.figure(figsize=(10.0, 3.8))
plt.plot(days, sales, linewidth=1.0)
plt.xlabel("Day")
plt.ylabel("Sales")
plt.xlim(0, 364)
finish("representative_retail_series_en.pdf")

print(f"Generated {len(list(OUT.glob('*_en.pdf')))} English PDF figures in {OUT}")
