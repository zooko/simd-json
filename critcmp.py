#!/usr/bin/env python3

# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import re
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='Baseline file followed by candidate files')
parser.add_argument('--commit', help='Git commit hash')
parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
parser.add_argument('--cpu', help='CPU type')
parser.add_argument('--os', help='OS type')
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
            # Unknown allocators go between known and smalloc
            return (2, 0, name)

    return sorted(files, key=sort_key)

def generate_svg_graph(allocators, normalized_sums, metadata, output_file):
    """Generate an SVG bar chart comparing allocator performance."""

    # Graph dimensions
    width = 800
    height = 500
    margin_top = 60
    margin_bottom = 120  # Space for metadata below
    margin_left = 80
    margin_right = 40

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    # Calculate percentages (baseline = 100%, others relative to baseline)
    baseline = normalized_sums[0]
    percentages = [(s / baseline * 100) for s in normalized_sums]

    # Find max for scaling
    max_pct = max(percentages)
    scale_max = max_pct * 1.1  # 10% padding at top

    # Calculate bar properties
    bar_width = chart_width / len(allocators)
    padding = bar_width * 0.2
    actual_bar_width = bar_width - padding

    # Color scheme
    colors = ['#4285f4', '#ea4335', '#fbbc04', '#34a853', '#9333ea', '#ff6b9d', '#00bcd4']

    svg_parts = []
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
  <style>
    .bar {{ stroke: none; }}
    .axis {{ stroke: #333; stroke-width: 1; }}
    .grid {{ stroke: #ddd; stroke-width: 0.5; }}
    .label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 12px; fill: #333; }}
    .value {{ font-family: monospace; font-size: 11px; fill: #999; }}
    .title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 16px; font-weight: 600; fill: #333; }}
    .metadata {{ font-family: monospace; font-size: 10px; fill: #666; }}
  </style>
''')

    # Title
    svg_parts.append(f'  <text x="{width/2}" y="30" class="title" text-anchor="middle">Performance of simd-json with different allocators—time (lower is better)</text>\n')

    # Y-axis
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + chart_height}" class="axis"/>\n')
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>\n')

    # Grid lines and labels (every 20% from 0% to 120%)
    for pct in [0, 20, 40, 60, 80, 100, 120]:
        if pct > scale_max:
            break
        y = margin_top + chart_height * (1 - pct/scale_max)
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" class="grid"/>\n')
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y + 4}" class="label" text-anchor="end">{pct:.0f}%</text>\n')

    # Bars and labels
    for i, (name, pct) in enumerate(zip(allocators, percentages)):
        x = margin_left + i * bar_width + padding/2
        bar_height = (pct / scale_max) * chart_height
        y = margin_top + chart_height - bar_height

        color = colors[i % len(colors)]

        # Bar
        svg_parts.append(f'  <rect x="{x}" y="{y}" width="{actual_bar_width}" height="{bar_height}" class="bar" fill="{color}"/>\n')

        # Value above bar (delta percentage rounded to whole number)
        if i == 0:
            label = "100% (baseline)"
        else:
            delta = round(pct - 100)
            label = f"{pct:.0f}%"

        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{y - 5}" class="value" text-anchor="middle">{label}</text>\n')

        # Allocator name below
        text_y = margin_top + chart_height + 20
        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{text_y}" class="label" text-anchor="middle">{name}</text>\n')

    # Metadata below the graph
    metadata_y = margin_top + chart_height + 50
    metadata_lines = []

    metadata_lines.append("Source: https://github.com/zooko/simd-json")
    if metadata.get('commit'):
        metadata_lines.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        metadata_lines.append(f"Git status: {metadata['git_status']}")
    if metadata.get('cpu'):
        metadata_lines.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        metadata_lines.append(f"OS: {metadata['os']}")

    for i, line in enumerate(metadata_lines):
        y = metadata_y + i * 15
        svg_parts.append(f'  <text x="{width/2}" y="{y}" class="metadata" text-anchor="middle">{line}</text>\n')

    svg_parts.append('</svg>')

    with open(output_file, 'w') as f:
        f.write(''.join(svg_parts))

    print(f"\n📊 Graph saved to: {output_file}")

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

# Print compact summary
print("\n" + "=" * 52)
print("COMPACT SUMMARY")
print("=" * 52)
print()
print(f"{'Allocator':<12}  {'Total Time (1s per test)':>24}  {'vs Baseline':>12}")
print("-" * 52)

num_tests = len(all_tests)
for i, (name, norm_sum) in enumerate(zip(col_names, normalized_sums)):
    per_test = norm_sum / num_tests
    if i == 0:
        vs_baseline = "baseline"
    else:
        pct = (norm_sum - baseline_total) / baseline_total * 100
        vs_baseline = f"{pct:+.1f}%"

    print(f"{name:<12}  {norm_sum:>22.1f} s  {vs_baseline:>12}")

# Generate graph if requested
if args.graph:
    metadata = {
        'commit': args.commit,
        'git_status': args.git_status,
        'cpu': args.cpu,
        'os': args.os
    }
    generate_svg_graph(col_names, normalized_sums, metadata, args.graph)
