#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import re
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from collections import defaultdict

# Allocator colors
ALLOCATOR_COLORS = {
    'default': '#78909c',   # blue-grey (distinct from smalloc green)
    'glibc': '#5c6bc0',      # indigo
    'jemalloc': '#66bb6a',    # green
    'snmalloc': '#ab47bc',    # purple
    'mimalloc': '#ffca28',   # amber
    'rpmalloc': '#ff7043',   # deep orange
    'smalloc': '#42a5f5',   # blue
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

    # Match lines like: "test_name  time:   [1.2345 µs 1.2456 µs 1.2567 µs]"
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
    if ns >= 1_000_000:
        return f"{ns/1_000_000:.0f}ms"
    elif ns >= 1_000:
        return f"{ns/1_000:.0f}μs"
    else:
        return f"{ns:.0f}ns"

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

def generate_graph(allocators, normalized_sums, absolute_times, metadata, output_file, title_suffix=''):
    """Generate bar chart comparing allocator performance using matplotlib."""

    # Try to use Arial/Helvetica for a cleaner look
    try:
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        if 'Arial' in available_fonts:
            plt.rcParams['font.family'] = 'Arial'
        elif 'Helvetica' in available_fonts:
            plt.rcParams['font.family'] = 'Helvetica'
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    except:
        plt.rcParams['font.family'] = 'sans-serif'

    # Calculate percentages (baseline = 100%)
    baseline = normalized_sums[0]
    percentages = [(s / baseline) * 100 for s in normalized_sums]

    # Create figure with specific size
    fig, ax = plt.subplots(figsize=(10, 5))
    plt.subplots_adjust(bottom=0.22, top=0.88, left=0.08, right=0.97)

    # Bar properties - wider bars
    n_allocators = len(allocators)
    bar_width = 0.75
    x_positions = range(n_allocators)

    # Create bars
    bars = []
    for i, (allocator, pct) in enumerate(zip(allocators, percentages)):
        color = get_color(allocator)
        bar = ax.bar(i, pct, bar_width, color=color, edgecolor='none')
        bars.append(bar[0])

    # Set y-axis
    max_pct = max(percentages)
    ax.set_ylim(0, max(max_pct * 1.15, 115))
    ax.set_ylabel('Time vs Baseline (%)', fontsize=11, color='#999999')

    # Style y-axis
    ax.yaxis.set_tick_params(colors='#999999')
    for label in ax.get_yticklabels():
        label.set_color('#999999')
    ax.spines['left'].set_color('#999999')

    # X-axis labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(allocators, fontsize=11)

    # Grid - subtle horizontal lines
    ax.yaxis.grid(True, linestyle='--', alpha=0.3, linewidth=0.5)
    ax.set_axisbelow(True)

    # Fixed offset for labels (in points)
    LABEL_OFFSET_ABOVE = 3  # Distance from bar top to bottom of absolute time label
    LABEL_OFFSET_INSIDE = 6  # Distance from bar top to top of percentage label

    # Add labels above and inside bars
    for i, (bar, allocator, pct) in enumerate(zip(bars, allocators, percentages)):
        bar_height = bar.get_height()
        x_pos = bar.get_x() + bar.get_width() / 2

        # Absolute time above bar
        if allocator in absolute_times and absolute_times[allocator] > 0:
            time_label = format_time(absolute_times[allocator])
            ax.annotate(time_label,
                       xy=(x_pos, bar_height),
                       xytext=(0, LABEL_OFFSET_ABOVE),
                       textcoords='offset points',
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold',
                       color='#333333')

        # Percentage label inside bar at top (fixed offset from top)
        if allocator == allocators[0]:  # baseline
            pct_label = "baseline"
        else:
            ratio = pct / 100.0
            pct_label = format_pct_diff(ratio)

        ax.annotate(pct_label,
                   xy=(x_pos, bar_height),
                   xytext=(0, -LABEL_OFFSET_INSIDE),
                   textcoords='offset points',
                   ha='center', va='top',
                   fontsize=9, fontweight='bold',
                   color='white')

    # Title
    base_title = "Performance of simd-json with different allocators"
    if title_suffix:
        title = f"{base_title}{title_suffix}"
    else:
        title = f"{base_title}—time (lower is better)"
    ax.set_title(title, fontsize=16, fontweight='bold', pad=15, color='#333333')

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#000000')

    # Metadata - single line format
    meta_parts = []
    if metadata.get('source'):
        meta_parts.append(f"Source: {metadata['source']}")
    elif metadata.get('commit'):
        meta_parts.append("Source: https://github.com/zooko/simd-json")

    if metadata.get('commit'):
        meta_parts.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        meta_parts.append(f'Git status: "{metadata["git_status"]}"')

    line2_parts = []
    if metadata.get('cpu'):
        line2_parts.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        line2_parts.append(f"OS: {metadata['os']}")

    if meta_parts:
        fig.text(0.5, 0.08, " · ".join(meta_parts), ha='center', fontsize=10, 
                color='#666666', family='monospace')
    if line2_parts:
        fig.text(0.5, 0.03, " · ".join(line2_parts), ha='center', fontsize=10, 
                color='#666666', family='monospace')

    plt.savefig(output_file, format='svg', bbox_inches='tight', dpi=150)
    plt.close()
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
