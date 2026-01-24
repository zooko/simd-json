#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import re
import argparse
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='Baseline file followed by candidate files')
parser.add_argument('--commit', help='Git commit hash')
parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
parser.add_argument('--cpu', help='CPU type')
parser.add_argument('--os', help='OS type')
parser.add_argument('--source', help='Source URL')
parser.add_argument('--graph', help='Output SVG graph to this file')
args = parser.parse_args()

# Allocator colors (matching smalloc benchmark colors)
ALLOCATOR_COLORS = {
    'default': '#ab47bc',    # purple
    'glibc': '#5c6bc0',      # indigo
    'jemalloc': '#42a5f5',   # blue
    'snmalloc': '#26a69a',   # teal
    'mimalloc': '#ffca28',   # amber
    'rpmalloc': '#ff7043',   # deep orange
    'smalloc': '#66bb6a',    # green
}
UNKNOWN_ALLOCATOR_COLOR = '#9e9e9e'  # gray

# Allocator ordering
ALLOCATOR_ORDER = ['default', 'jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc', 'smalloc']

def get_color(name):
    return ALLOCATOR_COLORS.get(name, UNKNOWN_ALLOCATOR_COLOR)

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

def sort_allocators(allocators):
    """Sort allocators in canonical order."""
    def sort_key(name):
        if name in ALLOCATOR_ORDER:
            return (0, ALLOCATOR_ORDER.index(name))
        return (1, name)
    return sorted(allocators, key=sort_key)

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
            return (2, 0, name)
    return sorted(files, key=sort_key)

def format_pct_diff(ratio):
    """Format percentage difference from baseline."""
    pct_diff = (ratio - 1.0) * 100
    if abs(pct_diff) < 0.5:
        return "0%"
    elif pct_diff > 0:
        return f"+{int(round(pct_diff))}%"
    else:
        return f"{int(round(pct_diff))}%"

def generate_graph(allocators, normalized_sums, metadata, output_file):
    """Generate a bar chart comparing allocator performance."""

    # Calculate ratios (relative to baseline)
    baseline = normalized_sums[0]
    ratios = [s / baseline for s in normalized_sums]

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    plt.subplots_adjust(bottom=0.22, top=0.88)

    # Bar positioning
    x = np.arange(len(allocators))
    bar_width = 0.6

    # Convert ratios to percentages for display
    percentages = [r * 100 for r in ratios]

    # Create bars
    bars = ax.bar(x, percentages, bar_width,
                  color=[get_color(a) for a in allocators],
                  edgecolor='none')

    # Add value labels above bars
    for i, (bar, ratio) in enumerate(zip(bars, ratios)):
        height = bar.get_height()
        if i == 0:
            label = "100% (baseline)"
        else:
            label = format_pct_diff(ratio)
        ax.annotate(label,
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords='offset points',
                    ha='center', va='bottom',
                    fontsize=9, fontweight='bold',
                    color='#333333')

    # Add horizontal line at 100% for reference
    ax.axhline(y=100, color='#333333', linewidth=1.5, linestyle='--', alpha=0.7)

    # Styling
    ax.set_xticks(x)
    ax.set_xticklabels(allocators, fontsize=10)
    ax.set_ylabel('Time vs Baseline (%)', fontsize=11)
    ax.set_ylim(0, max(percentages) * 1.15)

    # Grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    # Title
    ax.set_title('Performance of simd-json with different allocators\n(Time vs baseline, lower is better)',
                 fontsize=14, fontweight='bold', pad=15)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Metadata
    meta_lines = []
    if metadata.get('source'):
        meta_lines.append(f"Source: {metadata['source']}")

    line1_parts = []
    if metadata.get('commit'):
        line1_parts.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        line1_parts.append(f"Git status: {metadata['git_status']}")
    if line1_parts:
        meta_lines.append(" · ".join(line1_parts))

    line2_parts = []
    if metadata.get('cpu'):
        line2_parts.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        line2_parts.append(f"OS: {metadata['os']}")
    if line2_parts:
        meta_lines.append(" · ".join(line2_parts))

    y_pos = 0.08
    for line in meta_lines:
        fig.text(0.5, y_pos, line, ha='center', fontsize=9, color='#666666', family='monospace')
        y_pos -= 0.03

    plt.savefig(output_file, format='svg', bbox_inches='tight', dpi=150)
    plt.close()

    print(f"📊 Graph saved to: {output_file}")

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

# Track normalized times (time to do 1 seconds worth of baseline work per test)
normalized_sums = [0.0] * len(col_names)

# Print each row
for test in all_tests:
    baseline_time = baseline_results[test]
    row = f"{test:<{max_test_len}}"

    # Baseline column
    time_str = format_time(baseline_time)
    cell = f"{time_str} (  0.0%)"
    row += f"  {cell:>{col_width}}"
    normalized_sums[0] += 1.0

    # Candidate columns
    for i, cand in enumerate(candidate_results):
        cand_time = cand[test]
        relative = (cand_time - baseline_time) / baseline_time * 100
        time_str = format_time(cand_time)
        cell = f"{time_str} ({relative:>+5.1f}%)"
        row += f"  {cell:>{col_width}}"
        normalized_sums[i + 1] += 1.0 * (cand_time / baseline_time)

    print(row)

# Print normalized sums
print("-" * len(header))
sum_row = f"{'NORMALIZED (1s of baseline work per test)':<{max_test_len}}"
for s in normalized_sums:
    cell = f"{s:>8.1f} s  (     )"
    sum_row += f"  {cell:>{col_width}}"
print(sum_row)

# Print relative to baseline
rel_row = f"{'RELATIVE TO BASELINE':<{max_test_len}}"
baseline_total = normalized_sums[0]
for s in normalized_sums:
    relative = (s - baseline_total) / baseline_total * 100
    cell = f"{'':>8}   ({relative:>+5.1f}%)"
    rel_row += f"  {cell:>{col_width}}"
print(rel_row)

# Print compact summary
print("\n" + "=" * 60)
print("BENCHMARK SUMMARY")
print("=" * 60)
print()
print(f"{'Allocator':<12} {'Total Time (1s per test)':>24} {'vs Baseline':>12}")
print("-" * 52)

for i, (name, norm_sum) in enumerate(zip(col_names, normalized_sums)):
    if i == 0:
        vs_baseline = "baseline"
    else:
        pct = (norm_sum - baseline_total) / baseline_total * 100
        vs_baseline = f"{pct:+.1f}%"
    print(f"{name:<12} {norm_sum:>22.1f} s {vs_baseline:>12}")

# Generate graph if requested
if args.graph:
    metadata = {
        'commit': args.commit,
        'git_status': args.git_status,
        'cpu': args.cpu,
        'os': args.os,
        'source': args.source or 'Unknown',
    }
    generate_graph(col_names, normalized_sums, metadata, args.graph)
