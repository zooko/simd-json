#!/usr/bin/env python3

# Thanks to Claude (Opus 4.5) for writing this to my specifications.

import sys
import re
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='Baseline file followed by candidate files')
parser.add_argument('--graph', help='Output SVG graph to this file')
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

# ==============================================================================
# COMPACT SUMMARY SECTION
# ==============================================================================

print("\n" + "=" * 60)
print("COMPACT SUMMARY")
print("=" * 60)

# Vertical format - each allocator on its own row
print(f"\n{'Allocator':<12} {'Normalized Time':<18} {'vs Baseline':<12}")
print("-" * 42)
for i, name in enumerate(col_names):
    norm_time = normalized_sums[i]
    if i == 0:
        rel_str = "baseline"
    else:
        rel_pct = (norm_time - baseline_total) / baseline_total * 100
        rel_str = f"{rel_pct:+6.1f}%"
    print(f"{name:<12} {norm_time:>8.1f} s ({norm_time/len(all_tests):>5.1f}s/test) {rel_str:>12}")

# Ranking table (sorted by performance)
print(f"\n{'Rank':<6} {'Allocator':<12} {'Speedup vs Best':<18}")
print("-" * 36)
sorted_results = sorted(enumerate(normalized_sums), key=lambda x: x[1])
best_time = sorted_results[0][1]

for rank, (idx, time) in enumerate(sorted_results, 1):
    speedup = time / best_time
    marker = "🏆" if rank == 1 else f"{rank}."
    print(f"{marker:<6} {col_names[idx]:<12} {speedup:>5.2f}x")

# ==============================================================================
# SVG GRAPH GENERATION
# ==============================================================================

if args.graph:
    # Graph dimensions
    width = 800
    height = 400
    margin_left = 120
    margin_right = 40
    margin_top = 40
    margin_bottom = 80
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    # Bar width and spacing
    bar_spacing = 10
    total_bar_width = plot_width - (len(col_names) - 1) * bar_spacing
    bar_width = total_bar_width / len(col_names)

    # Find max normalized time for scaling
    max_norm_time = max(normalized_sums)

    # Colors for each allocator
    colors = ['#4A90E2', '#7ED321', '#F5A623', '#D0021B', '#BD10E0', '#50E3C2', '#B8E986']

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '  <style>',
        '    .bar { stroke: #333; stroke-width: 1; }',
        '    .axis { stroke: #333; stroke-width: 2; }',
        '    .grid { stroke: #ddd; stroke-width: 1; }',
        '    .label { font-family: monospace; font-size: 12px; }',
        '    .title { font-family: monospace; font-size: 16px; font-weight: bold; }',
        '    .value-label { font-family: monospace; font-size: 10px; }',
        '  </style>',
        '',
        f'  <text x="{width/2}" y="25" text-anchor="middle" class="title">Allocator Performance Comparison (Normalized)</text>',
        '',
        '  <!-- Y-axis -->',
        f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" class="axis"/>',
        '  <!-- X-axis -->',
        f'  <line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" class="axis"/>',
        '',
    ]

    # Y-axis grid lines and labels
    num_gridlines = 5
    for i in range(num_gridlines + 1):
        y_val = max_norm_time * i / num_gridlines
        y_pos = margin_top + plot_height - (y_val / max_norm_time * plot_height)

        # Grid line
        svg_lines.append(f'  <line x1="{margin_left}" y1="{y_pos}" x2="{margin_left + plot_width}" y2="{y_pos}" class="grid"/>')
        # Label
        svg_lines.append(f'  <text x="{margin_left - 10}" y="{y_pos + 4}" text-anchor="end" class="label">{y_val:.0f}s</text>')

    # Bars
    for i, (name, norm_time) in enumerate(zip(col_names, normalized_sums)):
        x = margin_left + i * (bar_width + bar_spacing)
        bar_height = (norm_time / max_norm_time) * plot_height
        y = margin_top + plot_height - bar_height

        color = colors[i % len(colors)]
        svg_lines.append(f'  <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" class="bar"/>')

        # Value label on top of bar
        svg_lines.append(f'  <text x="{x + bar_width/2}" y="{y - 5}" text-anchor="middle" class="value-label">{norm_time:.1f}s</text>')

        # X-axis label (allocator name)
        label_x = x + bar_width / 2
        label_y = margin_top + plot_height + 20
        # Rotate if names are long
        if len(name) > 8:
            svg_lines.append(f'  <text x="{label_x}" y="{label_y}" text-anchor="end" transform="rotate(-45 {label_x} {label_y})" class="label">{name}</text>')
        else:
            svg_lines.append(f'  <text x="{label_x}" y="{label_y}" text-anchor="middle" class="label">{name}</text>')

    svg_lines.append('</svg>')

    with open(args.graph, 'w') as f:
        f.write('\n'.join(svg_lines))

    print(f"\nGraph saved to: {args.graph}")
