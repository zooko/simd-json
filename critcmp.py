#!/usr/bin/env python3

# Thanks to Claude (Opus 4.5) for writing this to my specifications.

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

def generate_svg_graph(col_names, normalized_sums, metadata, output_file):
    """Generate an SVG bar chart of normalized performance."""

    # SVG dimensions
    width = 800
    height = 500
    margin_top = 120  # Extra space for metadata
    margin_right = 50
    margin_bottom = 80
    margin_left = 80

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    # Data
    n = len(col_names)
    baseline_total = normalized_sums[0]
    percentages = [(s / baseline_total * 100) for s in normalized_sums]

    # Find max for scaling
    max_val = max(percentages)
    scale = chart_height / (max_val * 1.1)  # 10% headroom

    # Bar width
    bar_width = (chart_width / n) * 0.7
    bar_spacing = chart_width / n

    # Colors
    colors = {
        'default': '#95a5a6',
        'jemalloc': '#3498db',
        'snmalloc': '#2ecc71',
        'mimalloc': '#e74c3c',
        'rpmalloc': '#f39c12',
        'smalloc': '#9b59b6'
    }

    svg = []
    svg.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg.append(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">')

    # Style
    svg.append('<defs><style>')
    svg.append('text { font-family: monospace, sans-serif; }')
    svg.append('.title { font-size: 16px; font-weight: bold; }')
    svg.append('.metadata { font-size: 11px; fill: #666; }')
    svg.append('.label { font-size: 12px; text-anchor: middle; }')
    svg.append('.value { font-size: 11px; text-anchor: middle; font-weight: bold; }')
    svg.append('.axis-label { font-size: 12px; }')
    svg.append('</style></defs>')

    # Background
    svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

    # Title
    svg.append(f'<text x="{width/2}" y="20" class="title" text-anchor="middle">Time (lower is better)</text>')

    # Metadata
    y_meta = 40
    if metadata.get('commit'):
        commit_short = metadata['commit'][:12] if len(metadata['commit']) > 12 else metadata['commit']
        svg.append(f'<text x="10" y="{y_meta}" class="metadata">Commit: {commit_short}</text>')
        y_meta += 14
    if metadata.get('git_status'):
        svg.append(f'<text x="10" y="{y_meta}" class="metadata">Status: {metadata["git_status"]}</text>')
        y_meta += 14
    if metadata.get('cpu'):
        svg.append(f'<text x="10" y="{y_meta}" class="metadata">CPU: {metadata["cpu"]}</text>')
        y_meta += 14
    if metadata.get('os'):
        svg.append(f'<text x="10" y="{y_meta}" class="metadata">OS: {metadata["os"]}</text>')

    # Chart area
    chart_y = margin_top

    # Draw horizontal grid lines
    for i in range(0, 6):
        grid_val = (max_val * 1.1) * i / 5
        y = chart_y + chart_height - (grid_val * scale)
        svg.append(f'<line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" stroke="#ddd" stroke-width="1"/>')
        svg.append(f'<text x="{margin_left - 5}" y="{y + 4}" class="axis-label" text-anchor="end">{grid_val:.0f}%</text>')

    # Draw bars
    for i, (name, pct, norm_time) in enumerate(zip(col_names, percentages, normalized_sums)):
        x = margin_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_height = pct * scale
        y = chart_y + chart_height - bar_height

        color = colors.get(name, '#34495e')

        # Bar
        svg.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" opacity="0.8"/>')

        # Value on top of bar
        svg.append(f'<text x="{x + bar_width/2}" y="{y - 5}" class="value" fill="{color}">{pct:.1f}%</text>')

        # Time below
        time_str = f"{norm_time:.1f}s"
        svg.append(f'<text x="{x + bar_width/2}" y="{y - 20}" class="value" fill="#666" font-size="10">{time_str}</text>')

        # Label (rotated if needed)
        label_y = chart_y + chart_height + 15
        if len(name) > 8:
            # Rotate long names
            svg.append(f'<text x="{x + bar_width/2}" y="{label_y}" class="label" transform="rotate(45 {x + bar_width/2} {label_y})">{name}</text>')
        else:
            svg.append(f'<text x="{x + bar_width/2}" y="{label_y}" class="label">{name}</text>')

    # Y-axis label
    svg.append(f'<text x="15" y="{chart_y + chart_height/2}" class="title" transform="rotate(-90 15 {chart_y + chart_height/2})" text-anchor="middle" font-size="14">% of Baseline Time</text>')

    svg.append('</svg>')

    with open(output_file, 'w') as f:
        f.write('\n'.join(svg))

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

# Print compact summary
print("\n" + "=" * 60)
print("COMPACT SUMMARY")
print("=" * 60)
print()
print(f"{'Allocator':<12}  {'Normalized':>12}  {'Per Test':>12}  {'vs Baseline':>12}")
print("-" * 60)

num_tests = len(all_tests)
for i, (name, norm_sum) in enumerate(zip(col_names, normalized_sums)):
    per_test = norm_sum / num_tests
    if i == 0:
        vs_baseline = "baseline"
    else:
        pct = (norm_sum - baseline_total) / baseline_total * 100
        vs_baseline = f"{pct:+.1f}%"

    print(f"{name:<12}  {norm_sum:>10.1f} s  {per_test:>10.1f} s  {vs_baseline:>12}")

# Generate graph if requested
if args.graph:
    metadata = {
        'commit': args.commit,
        'git_status': args.git_status,
        'cpu': args.cpu,
        'os': args.os
    }
    generate_svg_graph(col_names, normalized_sums, metadata, args.graph)
