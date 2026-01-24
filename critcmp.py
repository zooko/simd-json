#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import re
import argparse
from collections import defaultdict

# Allocator colors
ALLOCATOR_COLORS = {
    'default': '#78909c',   # blue-grey (distinct from smalloc green)
    'glibc': '#5c6bc0',     # indigo
    'jemalloc': '#66bb6a',  # green
    'snmalloc': '#ab47bc',  # purple
    'mimalloc': '#ffca28',  # amber
    'rpmalloc': '#ff7043',  # deep orange
    'smalloc': '#42a5f5',   # blue
    'smalloc + ffi': '#93c2f9', # light blue
}
UNKNOWN_ALLOCATOR_COLOR = '#9e9e9e'  # gray

# Canonical allocator ordering: default first, then these in order, then unknown, then smalloc last
ALLOCATOR_ORDER = ['default', 'jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc', 'smalloc']

def get_color(name):
    return ALLOCATOR_COLORS.get(name, UNKNOWN_ALLOCATOR_COLOR)

def sort_allocators(names):
    """Sort allocator names in canonical order: default, known allocators, unknown, smalloc last."""
    def sort_key(name):
        if name in ALLOCATOR_ORDER:
            return (0, ALLOCATOR_ORDER.index(name))
        else:
            # Unknown allocators go between rpmalloc and smalloc
            return (0, ALLOCATOR_ORDER.index('smalloc') - 0.5)
    return sorted(names, key=sort_key)

def parse_file(filename):
    """Parse a Criterion benchmark output file and return {test_name: median_ns}."""
    results = {}
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match lines like: "test_name                  time:   [1.2345 µs 1.2456 µs 1.2567 µs]"
    pattern = r'^(\S+)\s+time:\s+\[[\d.]+ [µnms]+\s+([\d.]+)\s+([µnms]+)'

    for match in re.finditer(pattern, content, re.MULTILINE):
        test_name = match.group(1)
        median_value = float(match.group(2))
        unit = match.group(3)

        # Convert to nanoseconds
        multipliers = {'ns': 1, 'µs': 1000, 'ms': 1_000_000, 's': 1_000_000_000}
        median_ns = median_value * multipliers.get(unit, 1)
        results[test_name] = median_ns

    return results

def format_time(ns):
    """Format nanoseconds as human-readable string."""
    if ns >= 1_000_000_000:
        val = ns / 1_000_000_000
        if val >= 100:
            return f"{val:.0f}s"
        elif val >= 10:
            return f"{val:.1f}s"
        else:
            return f"{val:.2f}s"
    elif ns >= 1_000_000:
        val = ns / 1_000_000
        if val >= 100:
            return f"{val:.0f}ms"
        elif val >= 10:
            return f"{val:.1f}ms"
        else:
            return f"{val:.2f}ms"
    elif ns >= 1_000:
        val = ns / 1_000
        if val >= 100:
            return f"{val:.0f}μs"
        elif val >= 10:
            return f"{val:.1f}μs"
        else:
            return f"{val:.2f}μs"
    else:
        if ns >= 100:
            return f"{ns:.0f}ns"
        elif ns >= 10:
            return f"{ns:.1f}ns"
        else:
            return f"{ns:.2f}ns"

def get_allocator_name(filename):
    """Extract allocator name from filename."""
    basename = filename.rsplit('/', 1)[-1]  # Get just the filename
    name = basename.replace('.txt', '').replace('.bench', '').replace('criterion-', '')
    return name

def format_pct_diff(ratio):
    """Format percentage difference from baseline."""
    pct_diff = (ratio - 1.0) * 100
    if abs(pct_diff) < 0.5:
        return "0%"
    elif pct_diff > 0:
        return f"+{int(round(pct_diff))}%"
    else:
        return f"{int(round(pct_diff))}%"

def escape_xml(text):
    """Escape special XML characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def rounded_rect_path(x, y, width, height, radius):
    """Generate SVG path for rectangle with only top corners rounded."""
    # Ensure radius doesn't exceed half the width or height
    r = min(radius, width / 2, height / 2)

    # Start at bottom-left, go clockwise
    # Bottom-left corner (sharp)
    path = f"M {x} {y + height}"

    # Bottom edge to bottom-right (sharp corner)
    path += f" L {x + width} {y + height}"

    # Right edge up to where top-right curve starts
    path += f" L {x + width} {y + r}"

    # Top-right rounded corner (arc)
    path += f" A {r} {r} 0 0 0 {x + width - r} {y}"

    # Top edge to where top-left curve starts
    path += f" L {x + r} {y}"

    # Top-left rounded corner (arc)
    path += f" A {r} {r} 0 0 0 {x} {y + r}"

    # Left edge back to start
    path += f" Z"

    return path

def generate_graph(allocators, normalized_sums, absolute_times, metadata, output_file, title_suffix=''):
    """Generate SVG bar chart comparing allocator performance."""

    # Calculate percentages (baseline = 100%)
    baseline = normalized_sums[0]
    percentages = [(s / baseline) * 100 for s in normalized_sums]

    # Get baseline absolute time for y-axis label
    baseline_allocator = allocators[0]
    baseline_time_ns = absolute_times.get(baseline_allocator, 0)
    baseline_time_str = format_time(baseline_time_ns)

    # SVG dimensions and layout
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

    # Y-axis scale
    max_pct = max(percentages)
    y_max = max(max_pct * 1.15, 115)

    # Build SVG
    svg_parts = []

    # SVG header
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}">')

    # Background
    svg_parts.append(f'  <rect width="{svg_width}" height="{svg_height}" fill="white"/>')

    # Styles
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
    if title_suffix:
        title = f"{base_title}{title_suffix}"
    else:
        title = f"{base_title}—time (lower is better)"
    title_x = svg_width / 2
    title_y = 35
    svg_parts.append(f'  <text x="{title_x}" y="{title_y}" class="title" text-anchor="middle">{escape_xml(title)}</text>')

    # Y-axis label (rotated)
    y_label = f"Time vs Baseline (%, baseline = {baseline_time_str})"
    y_label_x = 20
    y_label_y = margin_top + chart_height / 2
    svg_parts.append(f'  <text x="{y_label_x}" y="{y_label_y}" class="axis-label" text-anchor="middle" transform="rotate(-90 {y_label_x} {y_label_y})">{escape_xml(y_label)}</text>')

    # Grid lines and Y-axis ticks
    y_ticks = [0, 20, 40, 60, 80, 100]
    if y_max > 100:
        y_ticks.append(int(y_max // 20 * 20))

    for tick in y_ticks:
        if tick > y_max:
            continue
        y_pos = margin_top + chart_height - (tick / y_max * chart_height)

        # Grid line
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y_pos}" x2="{margin_left + chart_width}" y2="{y_pos}" class="grid-line"/>')

        # Tick label
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y_pos + 4}" class="tick-label" text-anchor="end">{tick}</text>')

    # Bars
    for i, (allocator, pct) in enumerate(zip(allocators, percentages)):
        color = get_color(allocator)

        # Bar position
        bar_x = margin_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_height = (pct / y_max) * chart_height
        bar_y = margin_top + chart_height - bar_height

        # Draw bar with rounded top corners
        path = rounded_rect_path(bar_x, bar_y, bar_width, bar_height, corner_radius)
        svg_parts.append(f'  <path d="{path}" fill="{color}"/>')

        # Allocator name below bar
        name_x = bar_x + bar_width / 2
        name_y = margin_top + chart_height + 20
        svg_parts.append(f'  <text x="{name_x}" y="{name_y}" class="bar-label-name" text-anchor="middle">{escape_xml(allocator)}</text>')

        # Time value above bar
        time_label = format_time(absolute_times[allocator])
        value_y = bar_y - 8
        svg_parts.append(f'  <text x="{name_x}" y="{value_y}" class="bar-label-value" text-anchor="middle">{escape_xml(time_label)}</text>')

        # Percentage inside bar (near top)
        if allocator == allocators[0]:  # baseline
            pct_label = "baseline"
        else:
            ratio = pct / 100.0
            pct_label = format_pct_diff(ratio)
        pct_y = bar_y + 18

        # Only show if bar is tall enough
        if bar_height > 35:
            svg_parts.append(f'  <text x="{name_x}" y="{pct_y}" class="bar-label-pct" text-anchor="middle">{escape_xml(pct_label)}</text>')

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

    meta_y = svg_height - 35
    if meta_parts:
        meta_text = " · ".join(meta_parts)
        svg_parts.append(f'  <text x="{svg_width / 2}" y="{meta_y}" class="metadata" text-anchor="middle">{escape_xml(meta_text)}</text>')

    if line2_parts:
        line2_text = " · ".join(line2_parts)
        svg_parts.append(f'  <text x="{svg_width / 2}" y="{meta_y + 15}" class="metadata" text-anchor="middle">{escape_xml(line2_text)}</text>')

    # Close SVG
    svg_parts.append('</svg>')

    # Write to file
    svg_content = '\n'.join(svg_parts)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    print(f"\n📊 Graph saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Compare Criterion benchmark results across allocators')
    parser.add_argument('files', nargs='+', help='Criterion output files to compare')
    parser.add_argument('--title-suffix', default='',
                        help='Suffix to add to graph title')
    parser.add_argument('--commit', help='Git commit hash')
    parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
    parser.add_argument('--cpu', help='CPU type')
    parser.add_argument('--os', help='OS type')
    parser.add_argument('--graph', help='Output SVG graph to this file')
    parser.add_argument('--source', help='Source URL')

    args = parser.parse_args()

    # Parse all files and get allocator names
    file_data = {}
    for f in args.files:
        name = get_allocator_name(f)
        file_data[name] = parse_file(f)

    # Sort allocator names using the single canonical ordering
    sorted_names = sort_allocators(list(file_data.keys()))

    # Get all test names (intersection of all files)
    all_tests = None
    for results in file_data.values():
        if all_tests is None:
            all_tests = set(results.keys())
        else:
            all_tests &= set(results.keys())
    all_tests = sorted(all_tests) if all_tests else []

    if not all_tests:
        print("No common tests found across all files.", file=sys.stderr)
        sys.exit(1)

    # Baseline is first allocator in sorted order
    baseline_name = sorted_names[0]
    baseline_results = file_data[baseline_name]

    # Track normalized times and absolute times
    normalized_sums = []
    absolute_time_sums = []

    for name in sorted_names:
        results = file_data[name]
        norm_sum = 0.0
        abs_sum = 0.0
        for test in all_tests:
            baseline_time = baseline_results[test]
            test_time = results[test]
            norm_sum += test_time / baseline_time
            abs_sum += test_time
        normalized_sums.append(norm_sum)
        absolute_time_sums.append(abs_sum)

    # Calculate average absolute times
    num_tests = len(all_tests)
    absolute_times = {name: total / num_tests for name, total in zip(sorted_names, absolute_time_sums)}

    # Print summary
    print(f"\nTests compared: {len(all_tests)}")
    print(f"\n{'Allocator':<12} {'Normalized Sum':>16} {'vs Baseline':>12}")
    print("-" * 44)

    baseline_total = normalized_sums[0]
    for name, norm_sum in zip(sorted_names, normalized_sums):
        pct = (norm_sum - baseline_total) / baseline_total * 100
        vs_baseline = "baseline" if name == sorted_names[0] else f"{pct:+.1f}%"
        print(f"{name:<12} {norm_sum:>16.1f} {vs_baseline:>12}")

    # Generate graph if requested
    if args.graph:
        metadata = {
            'commit': args.commit,
            'git_status': args.git_status,
            'cpu': args.cpu,
            'os': args.os,
            'source': args.source
        }
        generate_graph(sorted_names, normalized_sums, absolute_times, metadata, args.graph, args.title_suffix)

if __name__ == '__main__':
    main()
