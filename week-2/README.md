# Data Layout: `data-15m.json`

This file contains a Grafana/InfluxDB query export with model usage metrics aggregated in 15-minute windows.

## Top-Level Structure

```json
{
  "request": { ... },   // Original query metadata
  "response": { ... }   // Query results
}
```

## Request

Contains the InfluxDB query configuration:
- **Query**: Fetches `network_data` measurements from the `metrics` bucket
- **Time range**: Unix timestamps in `from`/`to` fields (milliseconds)
- **Aggregation**: 15-minute windows with count aggregation, grouped by `model_key`

## Response

```json
{
  "results": {
    "A": {
      "status": 200,
      "frames": [ ... ]  // Array of data frames, one per model
    }
  }
}
```

### Frames

Each frame represents usage data for a single model:

```json
{
  "schema": {
    "fields": [
      { "name": "Time", "type": "time" },
      { "name": "Value", "type": "number", "labels": { "model_key": "..." } }
    ]
  },
  "data": {
    "values": [
      [1767730500000, 1767733200000, ...],  // Timestamps (ms since epoch)
      [1, 5, 12, ...]                        // Request counts per window
    ]
  }
}
```

### Model Key Format

The `model_key` label identifies the model:

```
<class_path>:{"repo_id": "<huggingface_repo>", "revision": <revision>}
```

Examples:
- `nnsight.modeling.language.LanguageModel:{"repo_id": "EleutherAI/gpt-j-6b", "revision": null}`
- `nnsight.modeling.huggingface.HuggingFaceModel:{"repo_id": "google/mt5-base", "revision": null}`

## Quick Access in Python

```python
import json

with open("data-15m.json") as f:
    data = json.load(f)

frames = data["response"]["results"]["A"]["frames"]

for frame in frames:
    model_key = frame["schema"]["fields"][1]["labels"]["model_key"]
    timestamps, counts = frame["data"]["values"]
    # timestamps are in milliseconds since epoch
    # counts are request counts per 15-minute window
```
