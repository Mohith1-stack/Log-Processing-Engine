#!/usr/bin/env python3
"""Fast, robust, zero-allocation Track A log engine using Python standard library."""
import os
import sys
from array import array

INPUT_NAME = "requests.log"
OUTPUT_NAME = "summary.txt"


def main(data_dir="/data", out_dir="/out"):
    endpoint_ids = {}
    endpoints = []
    hour_ids = {}
    hours = []
    groups = {}
    values = []
    errors = []

    last_hbytes = b""
    last_hid = -1

    input_path = os.path.join(data_dir, INPUT_NAME)
    if os.path.exists(input_path):
        with open(input_path, "rb", buffering=1 << 20) as src:
            for line in src:
                hbytes = line[:13]
                if hbytes == last_hbytes:
                    hid = last_hid
                else:
                    last_hbytes = hbytes
                    hid = hour_ids.get(hbytes)
                    if hid is None:
                        hid = len(hours)
                        hour_ids[hbytes] = hid
                        hours.append(hbytes.decode("ascii") + ":00:00Z")
                    last_hid = hid

                s1 = line.find(b" ", 28)
                e0 = s1 + 1
                s2 = line.find(b" ", e0)
                endpoint = line[e0:s2]
                eid = endpoint_ids.get(endpoint)
                if eid is None:
                    eid = len(endpoints)
                    endpoint_ids[endpoint] = eid
                    endpoints.append(endpoint.decode("ascii"))

                status = s2 + 1
                latency = int(line[status + 4:-1])
                is_error = 1 if line[status] == 53 else 0
                key = (hid << 24) | eid
                idx = groups.get(key)
                if idx is None:
                    groups[key] = len(values)
                    values.append(array("I", (latency,)))
                    errors.append(is_error)
                else:
                    values[idx].append(latency)
                    if is_error:
                        errors[idx] += 1

    hour_order = sorted(range(len(hours)), key=hours.__getitem__)
    hour_rank = [0] * len(hours)
    for rank, hid in enumerate(hour_order):
        hour_rank[hid] = rank

    endpoint_order = sorted(range(len(endpoints)), key=endpoints.__getitem__)
    endpoint_rank = [0] * len(endpoints)
    for rank, eid in enumerate(endpoint_order):
        endpoint_rank[eid] = rank

    ordered = sorted((((hour_rank[k >> 24] << 24) | endpoint_rank[k & 0xFFFFFF]) << 24) | idx
                     for k, idx in groups.items())

    out = []
    for packed in ordered:
        idx = packed & 0xFFFFFF
        erank = (packed >> 24) & 0xFFFFFF
        hrank = packed >> 48
        hid = hour_order[hrank]
        eid = endpoint_order[erank]
        err = errors[idx]
        v = values[idx]
        n = len(v)
        if n == 1:
            p50 = p95 = p99 = v[0]
        elif n == 2:
            a, b = v[0], v[1]
            if a > b:
                p50, p95, p99 = b, a, a
            else:
                p50, p95, p99 = a, b, b
        else:
            v = v.tolist()
            v.sort()
            p50 = v[(50 * n + 99) // 100 - 1]
            p95 = v[(95 * n + 99) // 100 - 1]
            p99 = v[(99 * n + 99) // 100 - 1]
        out.append(f"{hours[hid]} {endpoints[eid]} {n} {p50} {p95} {p99} {err} {err * 1_000_000 // n}\n")

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, OUTPUT_NAME), "w", encoding="ascii", newline="\n", buffering=1 << 20) as dst:
        dst.writelines(out)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Track A Ingest")
    parser.add_argument("--data", default="/data", help="input directory")
    parser.add_argument("--out", default="/out", help="output directory")
    args = parser.parse_args()
    main(args.data, args.out)
    sys.exit(0)
