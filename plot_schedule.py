import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def plot_schedule(entries, students, days, periods, output_path="schedule_gantt.png"):
    """
    Draw a cleaner Gantt-like chart for a school schedule.

    entries: list of tuples (student, day_index, period_index, subject, room)
    students: list like ["S1", "S2", "S3"]
    days: list like ["Mon", "Tue", ...]
    periods: iterable like range(5)
    output_path: where to save the PNG
    """
    if not entries:
        print("No entries to plot.")
        return

    periods = list(periods)
    period_count = len(periods)
    total_slots = len(days) * period_count

    # --- Room colors ---
    unique_rooms = sorted({room for _, _, _, _, room in entries})
    cmap = plt.get_cmap("tab10")
    room_colors = {
        room: cmap(i % 10)
        for i, room in enumerate(unique_rooms)
    }

    fig, ax = plt.subplots(figsize=(16, 5))

    # --- Y positions for student groups ---
    row_height = 8
    row_gap = 7
    y_map = {}
    y_ticks = []
    y_labels = []

    # S1 at top, then S2, then S3
    reversed_students = list(reversed(students))

    for idx, student in enumerate(reversed_students):
        y = 10 + idx * (row_height + row_gap)
        y_map[student] = y
        y_ticks.append(y + row_height / 2)
        y_labels.append(student)

    # --- Draw lesson blocks ---
    for student, day_idx, period_idx, subject, room in entries:
        start = day_idx * period_count + period_idx
        color = room_colors[room]

        ax.broken_barh(
            [(start, 1)],
            (y_map[student], row_height),
            facecolors=color,
            edgecolors="black",
            linewidth=1.0,
        )

        # If you want less clutter, keep only subject here
        ax.text(
            start + 0.5,
            y_map[student] + row_height / 2,
            f"{subject}",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    # --- Grid / slot boundaries ---
    # Major ticks = slot boundaries (0,1,2,3...), used for grid lines
    boundaries = list(range(total_slots + 1))
    ax.set_xticks(boundaries)
    ax.set_xticklabels([])

    # Minor ticks = centers of slots, used for labels
    centers = [i + 0.5 for i in range(total_slots)]
    center_labels = []
    for day_name in days:
        for period_idx in periods:
            center_labels.append(f"{day_name}\nP{period_idx + 1}")

    ax.set_xticks(centers, minor=True)
    ax.set_xticklabels(center_labels, minor=True, rotation=90)

    # Grid on slot boundaries
    ax.grid(axis="x", which="major", linestyle="-", linewidth=0.8, alpha=0.35)
    ax.grid(axis="y", which="major", linestyle="-", linewidth=0.8, alpha=0.35)

    # --- Thicker lines between days ---
    for day_idx in range(len(days) + 1):
        x = day_idx * period_count
        ax.axvline(x=x, color="black", linewidth=2.0, alpha=0.7)

    # --- Optional: day labels above chart ---
    top_y = max(y_map.values()) + row_height + 4
    for day_idx, day_name in enumerate(days):
        center_x = day_idx * period_count + period_count / 2
        ax.text(
            center_x,
            top_y,
            day_name,
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    # --- Y axis ---
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)

    # --- Limits / labels ---
    ax.set_xlim(0, total_slots)
    ax.set_ylim(8, top_y + 3)
    ax.set_xlabel("Week timeline")
    ax.set_title("School schedule Gantt view")

    # --- Legend for rooms ---
    legend_handles = [
        Patch(facecolor=room_colors[room], edgecolor="black", label=room)
        for room in unique_rooms
    ]
    ax.legend(
        handles=legend_handles,
        title="Rooms",
        bbox_to_anchor=(1.02, 1),
        loc="upper left"
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"Chart saved to: {output_path}")
    plt.show()