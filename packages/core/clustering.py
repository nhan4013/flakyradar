"""Group failing tests with similar stack traces using HDBSCAN over embeddings."""

import hdbscan
import numpy as np


def cluster_embeddings(embeddings: list[list[float]], min_cluster_size: int = 2) -> list[int]:
    """Returns a cluster label per embedding; -1 means noise (no cluster)."""
    if len(embeddings) < min_cluster_size:
        return [-1] * len(embeddings)
    arr = np.array(embeddings)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = arr / norms  # cosine distance ~= euclidean distance on normalized vectors
    # min_samples=1 + allow_single_cluster: failure clusters are small and often near-duplicate
    # (same bug, same stack trace) — HDBSCAN's defaults call that noise, not a cluster
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,
        allow_single_cluster=True,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(normalized)
    return labels.tolist()
