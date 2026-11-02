# Track A: Ingest

The task, the input files, and the exact output format are defined in the [Track A specification](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/a-ingest.md).

## Approach

This solution completely eliminates the reference implementation's bottlenecks (per-line `strptime`, string decoding, generic dict keys, and heavy Python integer object allocations) while preserving 100% byte-for-byte exactness against the official reference and oracle:

1. **Byte-Level Parsing & Hour Interning**:
   - Instead of parsing RFC 3339 timestamps with `datetime.strptime`, the engine extracts the 13-byte fixed prefix `YYYY-MM-DDTHH` directly from bytes.
   - Consecutive log lines from streaming shards exhibit strong temporal locality; a single-entry cache compares `line[:13]` against `last_hbytes` with a fast memcmp, avoiding hash lookups on consecutive lines.
   - Distinct hours are interned dynamically without any hardcoded year or month range assumptions.

2. **Compact Integer Group Keys**:
   - Endpoint paths are interned on first encounter to dense integer IDs.
   - Composite keys combine `(hour_id << 24) | endpoint_id` into a single Python machine integer, giving O(1) hash table access and supporting up to 16.7 million endpoints.

3. **Compact Latency Storage**:
   - Latencies are stored in standard library `array('I')` (32-bit unsigned integers), consuming only 4 bytes per sample instead of a full 28-byte `PyLongObject` + 8-byte pointer list.
   - Peak memory RSS is reduced from 228 MB (reference) to ~60 MB.
   - Line counts are directly obtained from `len(array)` without maintaining separate increment counters in the hot loop.

4. **Nearest-Rank Percentile Engine**:
   - Strict adherence to the nearest-rank percentile formula: `rank = (p * n + 99) // 100` (1-indexed).
   - Fast paths for single-request (`n = 1`) and two-request (`n = 2`) groups bypass list conversion and sorting, drastically accelerating processing of the long tail in Zipfian distributions.

5. **Direct Total-Order Output Pipeline**:
   - Groups are sorted by `(hour_rank, endpoint_rank)` using bit-packed integer keys, eliminating secondary dictionary lookups during emission.
   - Formatted lines are written via buffered I/O with exact LF line endings.

## Dependencies

- Python 3.13 standard library only (`os`, `sys`, `array`, `argparse`).
- Zero PyPI or third-party packages (`dependency_count = 0`).

## With another 24 hours

1. Implement parallel chunk-based parsing across shards using `concurrent.futures` / multi-process memory mapping.
2. Implement in-place radix sort or introselect for percentiles when `n > 1000`.
3. Port the core inner loop to a zero-overhead Rust / C++ binary container stage while retaining the same verification test suite.
