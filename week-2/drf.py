# %% DRF simulation
import heapq
from collections import defaultdict, deque
import pandas as pd
import numpy as np

traces = pd.read_csv("traces.csv")

# ── Cluster constants ──────────────────────────────────────────────────
NUM_CPUS = 4096
NUM_GPUS = 64

CLUSTER = np.array([NUM_CPUS, NUM_GPUS], dtype=float)

# ── Event types (DEPART < ARRIVE so departures are processed first) ───
DEPART = 0
ARRIVE = 1


def dominant_share(alloc):
    """Dominant share = max resource fraction across dimensions."""
    return float(np.max(alloc / CLUSTER))


def run_drf(traces: pd.DataFrame):
    """
    Discrete-event simulation of Dominant Resource Fairness.

    Each app_name is a 'user'. Instances are tasks submitted by that user.
    Resources considered: CPU, GPU.

    At every scheduling point the algorithm picks the user with the
    *smallest* dominant share and, if the cluster can fit one of their
    pending instances, allocates it.
    """

    # ── Build arrival events ───────────────────────────────────────────
    events: list[tuple] = []
    seq = 0  # tiebreaker for heap ordering
    for _, row in traces.iterrows():
        inst = {
            "instance_sn": row["instance_sn"],
            "app_name": row["app_name"],
            "cpu": float(row["cpu_request"]),
            "gpu": float(row["gpu_request"]),
            "duration": float(row["duration"]),
            "creation_time": float(row["creation_time"]),
            "original_scheduled": float(row["scheduled_time"]),
        }
        heapq.heappush(events, (inst["creation_time"], ARRIVE, seq, inst))
        seq += 1

    # ── State ──────────────────────────────────────────────────────────
    pending: dict[str, deque] = defaultdict(deque)   # app → queue of instances
    app_alloc: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(2))  # app → [cpu, gpu]
    used = np.zeros(2)  # cluster-wide [cpu, gpu]

    # ── Logging ────────────────────────────────────────────────────────
    sched_log: list[dict] = []
    util_log: list[dict] = []
    LOG_INTERVAL = 300  # seconds between utilization snapshots
    last_log_t = -LOG_INTERVAL

    def log_util(t):
        nonlocal last_log_t
        if t - last_log_t >= LOG_INTERVAL:
            util_log.append({"time": t, "cpu_util": used[0] / NUM_CPUS, "gpu_util": used[1] / NUM_GPUS})
            last_log_t = t

    # ── Scheduling sub-routine ─────────────────────────────────────────
    def try_schedule(t):
        """Greedily schedule pending instances using DRF ordering."""
        progress = True
        while progress:
            progress = False
            apps = [a for a, q in pending.items() if q]
            if not apps:
                break
            # Sort apps by dominant share (ascending)
            apps.sort(key=lambda a: dominant_share(app_alloc[a]))

            for app in apps:
                inst = pending[app][0]
                demand = np.array([inst["cpu"], inst["gpu"]])
                if np.all(used + demand <= CLUSTER):
                    pending[app].popleft()
                    # Allocate resources
                    app_alloc[app] += demand
                    used[:] += demand
                    # Schedule departure event
                    nonlocal seq
                    finish_t = t + inst["duration"]
                    heapq.heappush(events, (finish_t, DEPART, seq, inst))
                    seq += 1
                    # Record
                    sched_log.append({
                        "instance_sn": inst["instance_sn"],
                        "app_name": inst["app_name"],
                        "drf_scheduled": t,
                        "original_scheduled": inst["original_scheduled"],
                        "drf_wait": t - inst["creation_time"],
                        "original_wait": inst["original_scheduled"] - inst["creation_time"],
                    })
                    progress = True
                    break  # re-evaluate dominant shares

    # ── Main event loop ────────────────────────────────────────────────
    n_events = 0
    while events:
        cur_t = events[0][0]

        # Process *all* events at this timestamp
        while events and events[0][0] == cur_t:
            _, etype, _, inst = heapq.heappop(events)
            n_events += 1
            if etype == DEPART:
                demand = np.array([inst["cpu"], inst["gpu"]])
                app_alloc[inst["app_name"]] -= demand
                used[:] -= demand
            else:  # ARRIVE
                pending[inst["app_name"]].append(inst)

        try_schedule(cur_t)
        log_util(cur_t)

    print(f"\nSimulation done — processed {n_events} events")
    return pd.DataFrame(sched_log), pd.DataFrame(util_log)


sched_df, util_df = run_drf(traces)

# %% Results
print(f"\n{'='*55}")
print(f" DRF Simulation Results")
print(f" Cluster: {NUM_CPUS} CPUs, {NUM_GPUS} GPUs")
print(f"{'='*55}")
print(f"Instances scheduled: {len(sched_df)}")

print(f"\n--- DRF wait time (drf_scheduled − creation) [seconds] ---")
print(sched_df["drf_wait"].describe().to_string())

print(f"\n--- Original wait time (scheduled − creation) [seconds] ---")
print(sched_df["original_wait"].describe().to_string())

print(f"\n--- CPU utilisation ---")
print(util_df["cpu_util"].describe().to_string())

print(f"\n--- GPU utilisation ---")
print(util_df["gpu_util"].describe().to_string())

# Per-app fairness snapshot: dominant shares at end of simulation
print(f"\n--- Per-app dominant share (final snapshot, top 10) ---")
app_stats = (
    sched_df.groupby("app_name")
    .agg(n_instances=("instance_sn", "count"), avg_wait=("drf_wait", "mean"))
    .sort_values("n_instances", ascending=False)
)
print(app_stats.head(10).to_string())

# %% Plot utilisation over time
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle(f"DRF Cluster Simulation  ({NUM_CPUS} CPUs, {NUM_GPUS} GPUs)", fontsize=14)

axes[0].fill_between(util_df["time"], util_df["cpu_util"], alpha=0.4, color="steelblue")
axes[0].plot(util_df["time"], util_df["cpu_util"], linewidth=0.8, color="steelblue")
axes[0].set_xlabel("Time (s)")
axes[0].set_ylabel("Utilisation")
axes[0].set_title("CPU Utilisation")
axes[0].set_ylim(0, 1.05)
axes[0].grid(True, alpha=0.3)

axes[1].fill_between(util_df["time"], util_df["gpu_util"], alpha=0.4, color="darkorange")
axes[1].plot(util_df["time"], util_df["gpu_util"], linewidth=0.8, color="darkorange")
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("Utilisation")
axes[1].set_title("GPU Utilisation")
axes[1].set_ylim(0, 1.05)
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
