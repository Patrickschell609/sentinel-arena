"""
Charts - The money shot grouped bar chart.

Generates the grouped bar chart that tells the whole story:
Every attack category on the Y-axis, three bars per category
(Raw, Guardrailed, SENTINEL), with SENTINEL always at 0%.
"""

from pathlib import Path
from typing import Dict
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# SENTINEL color scheme
COLOR_RAW = '#d94040'       # Red
COLOR_GUARDRAIL = '#d4a24e' # Amber
COLOR_SENTINEL = '#2d8c4e'  # Green


def _category_display_name(cat: str) -> str:
    """Human-readable category names."""
    names = {
        "jailbreakbench": "JailbreakBench",
        "cot_hijack": "CoT Hijacking",
        "autodan": "AutoDAN",
        "encoding": "Encoding Evasion",
        "role_play": "Role-Play / DAN",
        "multi_turn": "Multi-Turn",
        "custom": "GCG / Custom",
    }
    return names.get(cat, cat)


def generate_asr_chart(
    summary: Dict[str, Dict[str, Dict]],
    output_path: Path,
    title: str = "Attack Success Rate by Defense Strategy",
) -> Path:
    """
    Generate the grouped bar chart.

    Args:
        summary: {category: {config: {total, jailbroken, asr}}}
        output_path: Where to save the PNG.
        title: Chart title.

    Returns:
        Path to the saved chart.
    """
    categories = sorted(summary.keys())
    cat_labels = [_category_display_name(c) for c in categories]

    raw_asrs = []
    guard_asrs = []
    sent_asrs = []

    for cat in categories:
        configs = summary[cat]
        raw_asrs.append(configs.get("raw", {}).get("asr", 0))
        guard_asrs.append(configs.get("guardrailed", {}).get("asr", 0))
        sent_asrs.append(configs.get("sentinel", {}).get("asr", 0))

    y = np.arange(len(categories))
    bar_height = 0.25

    fig, ax = plt.subplots(figsize=(12, max(6, len(categories) * 1.2)))

    # Horizontal bars
    bars_raw = ax.barh(y + bar_height, raw_asrs, bar_height,
                       label='Raw Model', color=COLOR_RAW, edgecolor='white')
    bars_guard = ax.barh(y, guard_asrs, bar_height,
                         label='Guardrailed', color=COLOR_GUARDRAIL, edgecolor='white')
    bars_sent = ax.barh(y - bar_height, sent_asrs, bar_height,
                        label='SENTINEL', color=COLOR_SENTINEL, edgecolor='white')

    # Labels on bars
    for bars in [bars_raw, bars_guard, bars_sent]:
        for bar in bars:
            width = bar.get_width()
            label = f'{width:.0f}%'
            x_pos = max(width + 1.5, 4)
            ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                    label, va='center', fontsize=9, fontweight='bold')

    ax.set_xlabel('Attack Success Rate (%)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_yticks(y)
    ax.set_yticklabels(cat_labels, fontsize=11)
    ax.set_xlim(0, 105)
    ax.legend(loc='lower right', fontsize=11)

    # Grid
    ax.xaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    # Add annotation for SENTINEL
    ax.annotate(
        'ALWAYS 0%\nBY CONSTRUCTION',
        xy=(2, y[-1] - bar_height),
        fontsize=10, fontweight='bold', color=COLOR_SENTINEL,
        ha='left', va='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                  edgecolor=COLOR_SENTINEL, alpha=0.9),
    )

    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return output_path
