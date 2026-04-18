# %%

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ── Load data ──────────────────────────────────────────────────────────
df = pd.read_csv("disaggregated_DLRM_trace.csv")

# ── Derived columns ────────────────────────────────────────────────────
# Instance-level duration = deletion_time - scheduled_time  (in seconds)
df["duration"] = df["deletion_time"] - df["scheduled_time"]
# Scheduling delay = scheduled_time - creation_time
df["sched_delay"] = df["scheduled_time"] - df["creation_time"]

# Keep only rows where duration is valid (both times present)
valid = df.dropna(subset=["duration"])

# ── Job (app)-level aggregation ────────────────────────────────────────
# A "job" = all instances sharing the same app_name.
# Job duration = max(deletion_time) - min(scheduled_time) across instances.
job = (
    df.dropna(subset=["scheduled_time", "deletion_time"])
    .groupby("app_name")
    .agg(
        start=("scheduled_time", "min"),
        end=("deletion_time", "max"),
        n_instances=("instance_sn", "count"),
        total_cpu=("cpu_request", "sum"),
        total_gpu=("gpu_request", "sum"),
    )
)
job["duration"] = job["end"] - job["start"]

# ── Print summary statistics ───────────────────────────────────────────
print("=== Dataset overview ===")
print(f"  Total instances:           {len(df)}")
print(f"  Instances w/ times:        {valid.shape[0]}")
print(f"  Unique apps (jobs):        {df['app_name'].nunique()}")
print(f"  Roles:                     {dict(df['role'].value_counts())}")
print()
print("=== Instance duration (deletion - scheduled) [seconds] ===")
print(valid["duration"].describe().to_string())
print()
print("=== Job duration (max deletion - min scheduled) [seconds] ===")
print(job["duration"].describe().to_string())
print()

# ── Helper: plot CDF ───────────────────────────────────────────────────
def plot_cdf(ax, data, xlabel, title, color="steelblue", log_x=False):
    sorted_data = np.sort(data)
    cdf = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
    ax.step(sorted_data, cdf, where="post", color=color, linewidth=1.5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("CDF")
    ax.set_title(title)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    if log_x:
        ax.set_xscale("log")

# ── Figure ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Disaggregated DLRM Trace — Summary Statistics", fontsize=15, y=0.98)

# 1) CDF of instance duration
plot_cdf(
    axes[0, 0],
    valid["duration"].values,
    "Instance duration (s)",
    "CDF of Instance Duration (deletion − scheduled)",
    log_x=True,
)

# 2) CDF of job duration
plot_cdf(
    axes[0, 1],
    job["duration"].values,
    "Job duration (s)",
    "CDF of Job Duration (per app)",
    color="darkorange",
    log_x=True,
)

# 3) CDF of scheduling delay (scheduled - creation)
sched_valid = df.dropna(subset=["sched_delay"])
plot_cdf(
    axes[1, 0],
    sched_valid["sched_delay"].values,
    "Scheduling delay (s)",
    "CDF of Scheduling Delay (scheduled − creation)",
    color="seagreen",
    log_x=True,
)

# 4) CDF of job size (#instances per job, all jobs including those w/o times)
job_sizes = df.groupby("app_name").size()
plot_cdf(
    axes[1, 1],
    job_sizes.values,
    "# instances per job",
    "CDF of Job Size (instances per app)",
    color="mediumpurple",
    log_x=True,
)

plt.tight_layout()
plt.show()

# %%

### DROP ROWS WITH NO TIMES ###

raw = pd.read_csv("disaggregated_DLRM_trace.csv")

# Keep only rows where all three time columns are present
traces = raw.dropna(subset=["creation_time", "scheduled_time", "deletion_time"]).copy()
traces["duration"] = traces["deletion_time"] - traces["scheduled_time"]

# Drop any rows with non-positive duration (data anomalies)
traces = traces[traces["duration"] > 0].reset_index(drop=True)
traces.to_csv("traces.csv", index=False)

print(f"Raw rows:      {len(raw)}")
print(f"Filtered rows: {len(traces)}  (dropped {len(raw) - len(traces)} w/o complete times or duration <= 0)")