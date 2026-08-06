from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
F = ROOT / "figures"
D = ROOT / "data"
F.mkdir(parents=True, exist_ok=True)

ORDER = ["DirectDelta", "DoGMono", "WTMMAggregated", "WTMMLines"]
METHOD_LABELS = {
    "DirectDelta": "First difference",
    "DoGMono": "Single-scale DoG",
    "WTMMAggregated": "Multiscale maxima",
    "WTMMLines": "Maximum lines",
}
QUERY_ORDER = [
    "Q1_brief_peak",
    "Q2_temporary_high",
    "Q3_long_high",
    "Q4_temporary_low",
    "Q5_up_down_up",
    "Q6_double_peak",
]
QUERY_LABELS = {
    "Q1_brief_peak": "Q1  Brief peak",
    "Q2_temporary_high": "Q2  8-14 d episode",
    "Q3_long_high": "Q3  18-28 d episode",
    "Q4_temporary_low": "Q4  5-10 d trough",
    "Q5_up_down_up": "Q5  Rise-fall-rebound",
    "Q6_double_peak": "Q6  Double peak",
}
ABLATION_LABELS = {
    "min_scales_1": "Minimum 1 scale",
    "no_merge": "No merging",
    "default": "Default: min. 2 scales",
    "adjacent_scales_only": "Strictly adjacent scales",
    "no_persistence_weight": "No persistence weighting",
    "min_scales_3": "Minimum 3 scales",
}


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(F / f"{name}.pdf", bbox_inches="tight")
    plt.savefig(F / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close()


g = pd.read_csv(R / "performance_global_v7.csv").set_index("method").loc[ORDER].reset_index()
labels = [METHOD_LABELS[m] for m in ORDER]
err = np.vstack([g.f1_macro - g.f1_macro_ci_low, g.f1_macro_ci_high - g.f1_macro])
plt.figure(figsize=(8.4, 4.8))
plt.bar(labels, g.f1_macro, yerr=err, capsize=4)
plt.ylim(0, 1)
plt.ylabel("Localized macro F1")
plt.xticks(rotation=14, ha="right")
save("f1_macro_methods_en")

q = pd.read_csv(R / "performance_by_query_v7.csv")
pivot = q.pivot(index="query", columns="method", values="f1").loc[QUERY_ORDER, ORDER]
pivot.index = [QUERY_LABELS[value] for value in QUERY_ORDER]
ax = pivot.plot(kind="bar", figsize=(11.5, 5.5))
ax.set_ylim(0, 1)
ax.set_ylabel("Localized F1")
ax.set_xlabel("")
ax.legend(labels, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2)
plt.xticks(rotation=12, ha="right")
save("f1_by_query_en")

noise = pd.read_csv(R / "performance_by_noise_v7.csv")
plt.figure(figsize=(8.4, 4.8))
for method in ORDER:
    subset = noise[noise.method == method].sort_values("noise")
    plt.plot(subset.noise, subset.f1_macro, marker="o", label=METHOD_LABELS[method])
    plt.fill_between(subset.noise, subset.f1_ci_low, subset.f1_ci_high, alpha=0.12)
plt.ylim(0, 1)
plt.xlabel("AR(1) noise standard deviation")
plt.ylabel("Localized macro F1")
plt.legend()
save("f1_by_noise_en")

micro = pd.read_csv(R / "compiler_microbenchmark_v7_summary.csv")
for regime in ["narrow", "wide"]:
    plt.figure(figsize=(8.4, 4.8))
    subset_regime = micro[micro.gap_regime == regime]
    for length in sorted(subset_regime.pattern_length.unique()):
        subset = subset_regime[subset_regime.pattern_length == length].sort_values("n_events")
        plt.plot(subset.n_events, subset.median_ms, marker="o", label=f"{length} atoms")
        plt.fill_between(subset.n_events, subset.p05_ms, subset.p95_ms, alpha=0.12)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Number of events in the relation")
    plt.ylabel("Latency (ms, median and P05-P95)")
    plt.legend()
    save(f"compiler_microbenchmark_{regime}_en")

ablation = pd.read_csv(R / "ablation_wtmm_global_v7.csv").sort_values("f1_macro", ascending=False)
plt.figure(figsize=(9.5, 4.8))
plt.bar([ABLATION_LABELS.get(v, v) for v in ablation.variant], ablation.f1_macro)
plt.ylim(0, max(0.7, ablation.f1_macro.max() + 0.05))
plt.ylabel("Localized macro F1")
plt.xticks(rotation=18, ha="right")
save("wtmm_ablation_en")

plt.figure(figsize=(8.4, 4.8))
plt.bar(labels, g.mean_events_per_series)
plt.ylabel("Mean number of events per series")
plt.xticks(rotation=14, ha="right")
save("event_count_methods_en")

series = pd.read_csv(D / "representative_retail_series.csv")
series["date"] = pd.to_datetime(series["date"])
changes = series.index[series["effect"].diff().fillna(0.0) != 0.0].to_numpy()
plt.figure(figsize=(12, 4.5))
plt.plot(series["date"], series["sales"], linewidth=1.25, label="Daily sales")
for idx in changes:
    delta = float(series.loc[idx, "effect"] - series.loc[idx - 1, "effect"]) if idx > 0 else float(series.loc[idx, "effect"])
    marker = "^" if delta > 0 else "v"
    plt.scatter(series.loc[idx, "date"], series.loc[idx, "sales"], marker=marker, s=48)
plt.xlabel("Date")
plt.ylabel("Daily sales")
plt.title("Representative synthetic retail series and injected transitions")
plt.tight_layout()
save("representative_retail_series_en")

print("English figures written to", F)
