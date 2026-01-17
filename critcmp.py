#!/usr/bin/env python3

# Thanks to Claude (Opus 4.5) for writing this to my specifications.

import sys
import re
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='Baseline file followed by candidate files')
args = parser.parse_args()

# Hardcoded allocator ordering (excluding 'default' which is always first and 'smalloc' which is always last)
ALLOCATOR_ORDER = ['jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc']

def parse_time(time_str):
    """Parse a time string like '72.624 µs' or '151.08 ms' and return nanoseconds."""
    match = re.match(r'([\d.]+)\s*(\S+)', time_str)
    if not match:
        raise ValueError(f"Cannot parse time: {time_str}")
    value = float(match.group(1))
    unit = match.group(2)
    multipliers = {
        'ns': 1,
        'µs': 1_000,
        'us': 1_000,
        'ms': 1_000_000,
        's': 1_000_000_000,
    }
    if unit not in multipliers:
        raise ValueError(f"Unknown time unit: {unit}")
    return value * multipliers[unit]

def format_time(ns):
    """Format nanoseconds back to a human-readable string with fixed width."""
    if ns >= 1_000_000_000:
        return f"{ns / 1_000_000_000:>8.2f} s "
    elif ns >= 1_000_000:
        return f"{ns / 1_000_000:>8.2f} ms"
    elif ns >= 1_000:
        return f"{ns / 1_000:>8.2f} µs"
    else:
        return f"{ns:>8.2f} ns"

def parse_file(filename):
    """Parse a criterion output file and return dict of test_name -> time_in_ns."""
    results = {}
    with open(filename, 'r', encoding="utf-8") as f:
        content = f.read()

    pattern = r'(\S+)\s+time:\s+\[[\d.]+ \S+ ([\d.]+ \S+) [\d.]+ \S+\]'
    for match in re.finditer(pattern, content):
        test_name = match.group(1)
        median_time = match.group(2)
        results[test_name] = parse_time(median_time)

    return results

def get_allocator_name(filepath):
    """Extract allocator name from filepath using os.path functions."""
    basename = os.path.basename(filepath)
    filename_without_ext = os.path.splitext(basename)[0]
    return filename_without_ext

def sort_allocator_files(files):
    """Sort files: default first, then ALLOCATOR_ORDER, then unknown, then smalloc last."""
    def sort_key(filepath):
        name = get_allocator_name(filepath)

        if name == 'default':
            return (0, 0, name)
        elif name == 'smalloc':
            return (3, 0, name)
        elif name in ALLOCATOR_ORDER:
            return (1, ALLOCATOR_ORDER.index(name), name)
        else:
            # Unknown allocators go between known and smalloc
            return (2, 0, name)

    return sorted(files, key=sort_key)

# Sort files in desired order
sorted_files = sort_allocator_files(args.files)
baseline_file = sorted_files[0]
candidate_files = sorted_files[1:]

baseline_results = parse_file(baseline_file)
candidate_results = [parse_file(f) for f in candidate_files]

# Get all test names (intersection of all files)
all_tests = set(baseline_results.keys())
for cand in candidate_results:
    all_tests &= set(cand.keys())
all_tests = sorted(all_tests)

if not all_tests:
    print("No common tests found across all files.", file=sys.stderr)
    sys.exit(1)

# Create column names from filenames
col_names = [get_allocator_name(baseline_file)] + [get_allocator_name(f) for f in candidate_files]

# Calculate max test name length for formatting
max_test_len = max(len(t) for t in all_tests)
col_width = 22  # "12345.67 µs (+123.4%)"

# Print header
header = f"{'test':<{max_test_len}}"
for name in col_names:
    header += f"  {name:>{col_width}}"
print(header)
print("-" * len(header))

# Track normalized times (time to do 100 seconds worth of baseline work)
normalized_sums = [0.0] * len(col_names)

# Print each row
for test in all_tests:
    baseline_time = baseline_results[test]
    row = f"{test:<{max_test_len}}"

    # Baseline column
    time_str = format_time(baseline_time)
    cell = f"{time_str} (  0.0%)"
    row += f"  {cell:>{col_width}}"
    normalized_sums[0] += 100.0

    # Candidate columns
    for i, cand in enumerate(candidate_results):
        cand_time = cand[test]
        relative = (cand_time - baseline_time) / baseline_time * 100
        time_str = format_time(cand_time)
        cell = f"{time_str} ({relative:>+5.1f}%)"
        row += f"  {cell:>{col_width}}"
        normalized_sums[i + 1] += 100.0 * (cand_time / baseline_time)

    print(row)

# Print normalized sums
print("-" * len(header))
sum_row = f"{'NORMALIZED (100s baseline work)':<{max_test_len}}"
for s in normalized_sums:
    cell = f"{s:>8.1f} s  (      )"
    sum_row += f"  {cell:>{col_width}}"
print(sum_row)

# Print relative to baseline
rel_row = f"{'RELATIVE TO BASELINE':<{max_test_len}}"
baseline_total = normalized_sums[0]
for s in normalized_sums:
    relative = (s - baseline_total) / baseline_total * 100
    cell = f"{'':>8}    ({relative:>+5.1f}%)"
    rel_row += f"  {cell:>{col_width}}"
print(rel_row)
