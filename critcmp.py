#!/usr/bin/env python3
"""
Compare criterion benchmark results across multiple allocators.
"""

# Thanks to Claude (Opus 4.5) for writing and updating this to my specifications.

import argparse
import re
from collections import defaultdict

# Configurable weights for different test categories
# Higher weight = more importance in the final weighted sum
WEIGHTS = {
    "log/": 10000,
    "event_stacktrace": 1000,
    "github_events/": 100,
    "apache_builds/": 100,
    "twitter/": 10,
    "citm_catalog/": 10,
    "canada/": 1,
}

DEFAULT_WEIGHT = 100

# Allocator colors for SVG graph
ALLOCATOR_COLORS = {
    'default': '#78909c',
    'glibc': '#5c6bc0',
    'jemalloc': '#66bb6a',
    'snmalloc': '#ab47bc',
    'mimalloc': '#ffca28',
    'rpmalloc': '#ff7043',
    'smalloc': '#42a5f5',
}
UNKNOWN_ALLOCATOR_COLOR = '#9e9e9e'

def get_weight(test_name: str) -> int:
    """Get the weight for a test based on its name prefix."""
    for prefix, weight in WEIGHTS.items():
        if test_name.startswith(prefix):
            return weight
    return DEFAULT_WEIGHT

def parse_file(filename: str) -> dict[str, float]:
    """Parse a Criterion benchmark output file and return {test_name: time_in_seconds}."""
    results = {}
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match lines like: "test_name time: [1.2345 µs 1.2456 µs 1.2567 µs]"
    # The middle value is the median/point estimate
    pattern = r'^(\S+)\s+time:\s+\[[\d.]+ [µnms]+\s+([\d.]+)\s+([µnms]+)'

    for match in re.finditer(pattern, content, re.MULTILINE):
        test_name = match.group(1)
        median_value = float(match.group(2))
        unit = match.group(3)

        # Convert to seconds
        multipliers = {'ns': 1e-9, 'µs': 1e-6, 'ms': 1e-3, 's': 1}
        time_seconds = median_value * multipliers.get(unit, 1)
        results[test_name] = time_seconds

    return results

def format_time(seconds: float) -> str:
    """Format time in appropriate units."""
    if seconds >= 1:
        return f"{seconds:.2f}s"
    elif seconds >= 0.001:
        return f"{seconds * 1000:.2f}ms"
    elif seconds >= 0.000001:
        return f"{seconds * 1_000_000:.2f}µs"
    else:
        return f"{seconds * 1_000_000_000:.1f}ns"

def format_time_fixed_width(seconds: float, width: int = 8) -> str:
    """Format time in milliseconds with 1 decimal place, fixed width."""
    ms = seconds * 1000
    return f"{ms:.1f}".rjust(width)

def format_diff(baseline: float, current: float) -> str:
    """Format the percentage difference from baseline."""
    if baseline == 0:
        return "(  N/A )"
    diff_pct = ((current - baseline) / baseline) * 100
    rounded_pct = round(diff_pct)
    if rounded_pct > 0:
        return f"({rounded_pct:+4d}%)"
    elif rounded_pct < 0:
        return f"({rounded_pct:+4d}%)"
    else:
        return "(   0%)"

def format_pct_diff(ratio: float) -> str:
    """Format percentage difference from baseline for graph labels."""
    pct_diff = (ratio - 1.0) * 100
    if abs(pct_diff) < 0.5:
        return "0%"
    elif pct_diff > 0:
        return f"+{int(round(pct_diff))}%"
    else:
        return f"{int(round(pct_diff))}%"

def get_color(name: str) -> str:
    """Get color for an allocator."""
    return ALLOCATOR_COLORS.get(name, UNKNOWN_ALLOCATOR_COLOR)

def escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def rounded_rect_path(x: float, y: float, width: float, height: float, radius: float) -> str:
    """Generate SVG path for rectangle with only top corners rounded."""
    r = min(radius, width / 2, height / 2)
    return (
        f"M {x} {y + height}"
        f" L {x + width} {y + height}"
        f" L {x + width} {y + r}"
        f" A {r} {r} 0 0 0 {x + width - r} {y}"
        f" L {x + r} {y}"
        f" A {r} {r} 0 0 0 {x} {y + r}"
        f" Z"
    )

def print_results(allocators: list[str], all_results: dict[str, dict[str, float]], 
                  sorted_tests: list[str]) -> dict[str, float]:
    """Print the results table and return weighted sums."""

    if not allocators or not sorted_tests:
        print("No data to display.")
        return {}

    baseline_alloc = allocators[0]

    # Find the longest test name for formatting
    max_test_len = max(len(t) for t in sorted_tests)
    max_test_len = max(max_test_len, 4)  # At least "test"

    # Column widths
    weight_width = 6
    time_width = 8
    diff_width = 7
    col_width = time_width + 1 + diff_width

    # Print header
    print()

    # Allocator names row
    header1 = " " * (max_test_len + 2) + " " * (weight_width + 2)
    for alloc in allocators:
        header1 += f"{alloc:^{col_width}}  "
    print(header1)

    # Separator row
    header2 = " " * (max_test_len + 2) + " " * (weight_width + 2)
    for _ in allocators:
        header2 += "-" * col_width + "  "
    print(header2)

    # Column labels row
    header3 = f"{'test':<{max_test_len}}  {'weight':>{weight_width}}"
    for _ in allocators:
         header3 += f"  {'time ms':>{time_width}} {'(diff%)':>{diff_width}}"
    print(header3)

    # Underline row
    header4 = f"{'-' * 4:<{max_test_len}}  {'-' * weight_width:>{weight_width}}"
    for _ in allocators:
        header4 += f"  {'-' * time_width} {'-' * diff_width}"
    print(header4)

    total_width = max_test_len + 2 + weight_width + len(allocators) * (2 + col_width)

    # Track weighted sums
    weighted_sums: dict[str, float] = defaultdict(float)
    test_count = 0

    # Print each test row
    for test in sorted_tests:
        weight = get_weight(test)

        # Check if baseline has this test
        if test not in all_results.get(baseline_alloc, {}):
            continue

        baseline_time = all_results[baseline_alloc][test]
        baseline_weighted = baseline_time * weight

        row = f"{test:<{max_test_len}}  {weight:>{weight_width}}"

        for alloc in allocators:
            if test in all_results.get(alloc, {}):
                raw_time = all_results[alloc][test]
                weighted_time = raw_time * weight
                weighted_sums[alloc] += weighted_time

                time_str = format_time_fixed_width(weighted_time, time_width)

                if alloc == baseline_alloc:
                    diff_str = "( base)"
                else:
                    diff_str = format_diff(baseline_weighted, weighted_time)

                row += f"  {time_str} {diff_str}"
            else:
                row += f"  {'N/A':>{time_width}} {'':>{diff_width}}"

        test_count += 1
        print(row)

    # Print summary
    print("-" * total_width)

    # SUM row
    sum_row = f"{'SUM':<{max_test_len}}  {'':{weight_width}}"
    baseline_sum = weighted_sums.get(baseline_alloc, 0)
    for alloc in allocators:
        alloc_sum = weighted_sums[alloc]
        time_str = format_time_fixed_width(alloc_sum, time_width)
        if alloc == baseline_alloc:
            diff_str = "( base)"
        else:
            diff_str = format_diff(baseline_sum, alloc_sum)
        sum_row += f"  {time_str} {diff_str}"
    print(sum_row)

    print("-" * total_width)
    print()
    print(f"Tests compared: {test_count}")
    print()

    # Final summary table
    print(f"{'Allocator':<15} {'Weighted Sum':>12} vs Baseline")
    print("-" * 15 + " " + "-" * 12 + " " + "-" * 11)
    for alloc in allocators:
        alloc_sum = weighted_sums[alloc]
        time_str = format_time_fixed_width(alloc_sum, time_width)
        if alloc == baseline_alloc:
            diff_str = "   baseline"
        else:
            diff_str = "    " + format_diff(baseline_sum, alloc_sum)
        print(f"{alloc:<15} {time_str:>12} {diff_str}")

    return dict(weighted_sums)

def generate_graph(allocators: list[str], weighted_sums: dict[str, float], 
                   metadata: dict, output_file: str, title_suffix: str = ''):
    """Generate SVG bar chart comparing allocator performance."""

    baseline = weighted_sums.get(allocators[0], 0)

    if baseline == 0:
        print("Warning: Baseline has no data, skipping graph generation.")
        return

    percentages = [(weighted_sums.get(a, 0) / baseline) * 100 for a in allocators]
    baseline_time_str = format_time(baseline)

    # SVG dimensions
    svg_width = 800
    svg_height = 450
    margin_left = 80
    margin_right = 40
    margin_top = 60
    margin_bottom = 100

    chart_width = svg_width - margin_left - margin_right
    chart_height = svg_height - margin_top - margin_bottom

    n_allocators = len(allocators)
    bar_spacing = chart_width / n_allocators
    bar_width = bar_spacing * 0.7
    corner_radius = 8

    max_pct = max(percentages)
    y_max = max(max_pct * 1.15, 115)

    svg_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}">')
    svg_parts.append(f'  <rect width="{svg_width}" height="{svg_height}" fill="white"/>')

    svg_parts.append('''  <style>
    .title { font-family: Arial, Helvetica, sans-serif; font-size: 18px; font-weight: bold; fill: #333333; }
    .axis-label { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #666666; }
    .tick-label { font-family: Arial, Helvetica, sans-serif; font-size: 11px; fill: #666666; }
    .bar-label-name { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #333333; }
    .bar-label-value { font-family: monospace; font-size: 11px; fill: #555555; }
    .bar-label-pct { font-family: Arial, Helvetica, sans-serif; font-size: 12px; font-weight: bold; fill: white; }
    .metadata { font-family: monospace; font-size: 10px; fill: #666666; }
    .grid-line { stroke: #cccccc; stroke-width: 0.5; }
  </style>''')

    # Title
    base_title = "Performance of simd-json with different allocators"
    title = f"{base_title}{title_suffix}" if title_suffix else f"{base_title}—time (lower is better)"
    svg_parts.append(f'  <text x="{svg_width / 2}" y="35" class="title" text-anchor="middle">{escape_xml(title)}</text>')

    # Y-axis label
    y_label = f"Time vs Baseline (%, baseline = {baseline_time_str})"
    y_label_y = margin_top + chart_height / 2
    svg_parts.append(f'  <text x="20" y="{y_label_y}" class="axis-label" text-anchor="middle" transform="rotate(-90 20 {y_label_y})">{escape_xml(y_label)}</text>')

    # Grid lines and ticks
    y_ticks = [0, 20, 40, 60, 80, 100]
    if y_max > 100:
        # Add ticks up to y_max in increments of 20
        tick = 120
        while tick <= y_max:
            y_ticks.append(tick)
            tick += 20

    for tick in y_ticks:
        if tick > y_max:
            continue
        y_pos = margin_top + chart_height - (tick / y_max * chart_height)
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y_pos}" x2="{margin_left + chart_width}" y2="{y_pos}" class="grid-line"/>')
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y_pos + 4}" class="tick-label" text-anchor="end">{tick}%</text>')

    # Bars
    for i, (allocator, pct) in enumerate(zip(allocators, percentages)):
        color = get_color(allocator)
        bar_x = margin_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_height = (pct / y_max) * chart_height
        bar_y = margin_top + chart_height - bar_height

        path = rounded_rect_path(bar_x, bar_y, bar_width, bar_height, corner_radius)
        svg_parts.append(f'  <path d="{path}" fill="{color}"/>')

        name_x = bar_x + bar_width / 2
        svg_parts.append(f'  <text x="{name_x}" y="{margin_top + chart_height + 20}" class="bar-label-name" text-anchor="middle">{escape_xml(allocator)}</text>')

        time_label = format_time(weighted_sums.get(allocator, 0))
        svg_parts.append(f'  <text x="{name_x}" y="{bar_y - 8}" class="bar-label-value" text-anchor="middle">{escape_xml(time_label)}</text>')

        pct_label = "baseline" if allocator == allocators[0] else format_pct_diff(pct / 100.0)
        if bar_height > 35:
            svg_parts.append(f'  <text x="{name_x}" y="{bar_y + 18}" class="bar-label-pct" text-anchor="middle">{escape_xml(pct_label)}</text>')

    # Metadata
    meta_parts = []
    if metadata.get('source'):
        meta_parts.append(f"Source: {metadata['source']}")
    elif metadata.get('commit'):
        meta_parts.append("Source: https://github.com/zooko/simd-json")
    if metadata.get('commit'):
        meta_parts.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        meta_parts.append(f"Git status: {metadata['git_status']}")

    line2_parts = []
    if metadata.get('cpu'):
        line2_parts.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        line2_parts.append(f"OS: {metadata['os']}")
    if metadata.get('cpucount'):
        line2_parts.append(f"CPU Count: {metadata['cpucount']}")

    meta_y = svg_height - 35
    if meta_parts:
        svg_parts.append(f'  <text x="{svg_width / 2}" y="{meta_y}" class="metadata" text-anchor="middle">{escape_xml(" · ".join(meta_parts))}</text>')
    if line2_parts:
        svg_parts.append(f'  <text x="{svg_width / 2}" y="{meta_y + 15}" class="metadata" text-anchor="middle">{escape_xml(" · ".join(line2_parts))}</text>')

    svg_parts.append('</svg>')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_parts))

    print(f"\nGraph saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Compare Criterion benchmark results across allocators')
    parser.add_argument('files', nargs='+', help='Criterion output files to compare')
    parser.add_argument('--title-suffix', default='', help='Suffix to add to graph title')
    parser.add_argument('--commit', help='Git commit hash')
    parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
    parser.add_argument('--cpu', help='CPU type')
    parser.add_argument('--os', help='OS type')
    parser.add_argument('--cpucount', help='Number of CPUs')
    parser.add_argument('--graph', help='Output SVG graph to this file')
    parser.add_argument('--source', help='Source URL')

    args = parser.parse_args()

    # Parse all results - extract allocator name from filename
    all_results: dict[str, dict[str, float]] = {}
    allocators: list[str] = []

    for filepath in args.files:
        # Extract allocator name from filename (e.g., "tmp/default" -> "default")
        allocator_name = filepath.rsplit('/', 1)[-1].replace('.txt', '').replace('.bench', '')
        allocators.append(allocator_name)
        all_results[allocator_name] = parse_file(filepath)

    # Get all unique test names
    all_tests: set[str] = set()
    for results in all_results.values():
        all_tests.update(results.keys())

    # Sort tests by weight (descending) then name
    sorted_tests = sorted(all_tests, key=lambda t: (-get_weight(t), t))

    # Print results and get weighted sums
    weighted_sums = print_results(allocators, all_results, sorted_tests)

    # Generate graph if requested
    if args.graph:
        metadata = {
            'commit': args.commit,
            'git_status': args.git_status,
            'cpu': args.cpu,
            'os': args.os,
            'cpucount': args.cpucount,
            'source': args.source
        }
        generate_graph(allocators, weighted_sums, metadata, args.graph, args.title_suffix)

if __name__ == "__main__":
    main()
