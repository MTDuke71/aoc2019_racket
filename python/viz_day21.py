"""Day 21 visuals: the hull and the droid's flight across it.

Writes two PNGs into maps/ (gitignored, like the Day 15 maps: the hull IS the
puzzle input's payload -- all 160 nine-bit chunk values can be read straight
off the picture, so committing it would republish the input):

  day21_walk_path.png  Part 1 -- the WALK course (7 chunks), one band
  day21_run_path.png   Part 2 -- the full run (WALK's 7 chunks + 153 more),
                       wrapped 10 chunks per band

The hull is recovered statically from the program image (day21_disasm's
pass 3), and the trajectory is the faithful `cross_chunk` stepper re-run with
a flight recorder: one (column, altitude) sample per tick. A surviving droid
advances exactly one column per tick, so the whole flight is an altitude
profile over the stitched ribbon -- windows overlap at their shared ground
(each chunk's exit column 21 is the next chunk's entry column 5), which is
what makes the concatenation seamless.

Every chunk is cross-checked: the recorder's survival verdict must match the
un-instrumented `cross_chunk`, and the one-column-per-tick claim is asserted
on every chunk's sample count.

Run:  python python/viz_day21.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from day21 import PART1_SCRIPT, PART2_SCRIPT, parse_input, run_script
from day21_disasm import GROUND_LEFT, chunk_window, cross_chunk, recover_courses
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "maps"

GROUND = "#2b2b33"  # neutral tile fill (day18's wall)
HOLE = "#c2410c"  # hole outline -- the gap itself is the primary cue
PATH = "#0d9488"  # the altitude profile
JUMP = "#4f46e5"  # take-off markers

START, END = 5, 21  # run_chunk's own entry and exit columns
SPAN = END - START  # 16 columns of each window are actually traversed


def fly_chunk(window: str, script: tuple[str, ...]) -> tuple[bool, list[int], list[int]]:
    """`cross_chunk` with a flight recorder.

    Returns (survived, altitudes, take_offs): the altitude at each column
    START..END inclusive, and the columns where the script fired a jump. The
    physics is copied line for line from day21_disasm.cross_chunk; the only
    additions are the two recordings.
    """
    col, alt, thrust = START, 1, 0
    altitudes, take_offs = [alt], []
    while True:
        if alt < 1:
            return False, altitudes, take_offs
        if col == END:
            return True, altitudes, take_offs
        tile = window[col] == "#"
        jump = False
        if tile and alt == 1:
            sensors = {chr(ord("A") + k): window[col + 1 + k] == "#" for k in range(9)}
            jump = run_script(script, sensors)
        if jump:
            thrust = 2
            take_offs.append(col)
        if alt > 1 or (tile and alt == 1):
            col += 1
        if thrust:
            thrust -= 1
            alt += 1
        else:
            alt -= 1
        if alt == 0 and window[col] == "#":
            alt = 1
        altitudes.append(alt)


def fly_course(course: list[tuple[int, int]], script: tuple[str, ...]) -> tuple[str, list[int], list[int]]:
    """Stitch the chunks into one ribbon and fly it.

    Returns (hull, altitudes, take_offs) in global tile coordinates: chunk i's
    columns START..END-1 land at 16*i .. 16*i+15, and the final chunk's exit
    column is the ribbon's last tile. A surviving droid moves one column per
    tick, so `altitudes[x]` IS the altitude over tile x -- asserted below, and
    each chunk's verdict is cross-checked against the un-instrumented stepper.
    """
    hull, altitudes, take_offs = [], [], []
    for i, (addr, value) in enumerate(course):
        window = chunk_window(value)
        survived, alts, offs = fly_chunk(window, script)
        assert survived == cross_chunk(window, script), f"recorder disagrees at cell {addr}"
        assert survived, f"the script dies in the chunk at cell {addr} ({value})"
        assert len(alts) == SPAN + 1, f"non-ballistic tick count at cell {addr}"
        hull.append(window[START:END])
        altitudes.extend(alts[:-1])  # the exit sample is the next chunk's entry
        take_offs.extend(i * SPAN + c - START for c in offs)
    hull.append("#")  # the last chunk's exit tile
    altitudes.append(1)
    return "".join(hull), altitudes, take_offs


def path_y(alt: int) -> float:
    return (alt - 1) * 0.85 + 0.18


def draw_course(
    course: list[tuple[int, int]],
    script: tuple[str, ...],
    per_band: int,
    path: Path,
    title: str,
) -> None:
    hull, altitudes, take_offs = fly_course(course, script)
    holes = [x for x, ch in enumerate(hull) if ch == "."]
    width = per_band * SPAN
    bands = (len(course) + per_band - 1) // per_band
    pitch = 3.6

    fig, ax = plt.subplots(figsize=(max(10.0, width * 0.095), 1.4 + bands * 0.62), dpi=150)
    for b in range(bands):
        lo, hi = b * width, min((b + 1) * width, len(hull) - 1)
        y0 = -b * pitch
        # chunk separators, then the tiles: ground filled, holes outlined gaps
        for x in range(lo, hi + 1, SPAN):
            ax.plot([x - lo] * 2, [y0 - 1.15, y0 + 2.15], color="#e2e2e2", lw=0.7, zorder=0)
        for x in range(lo, hi + (b == bands - 1)):
            if hull[x] == "#":
                ax.add_patch(
                    Rectangle((x - lo + 0.05, y0 - 1), 0.9, 0.95, facecolor=GROUND, edgecolor="none")
                )
            else:
                ax.add_patch(
                    Rectangle(
                        (x - lo + 0.1, y0 - 0.95),
                        0.8,
                        0.85,
                        facecolor="none",
                        edgecolor=HOLE,
                        lw=0.9,
                    )
                )
        xs = range(hi - lo + 1)
        ax.plot(
            [x + 0.5 for x in xs],
            [y0 + path_y(a) for a in altitudes[lo : hi + 1]],
            color=PATH,
            lw=1.6,
            solid_capstyle="round",
            zorder=3,
        )
        offs = [x - lo for x in take_offs if lo <= x <= hi]
        ax.plot(
            [x + 0.5 for x in offs],
            [y0 + path_y(1)] * len(offs),
            "^",
            color=JUMP,
            ms=4.5,
            lw=0,
            zorder=4,
        )
        ax.text(
            -1.5,
            y0 + 0.4,
            f"[{course[b * per_band][0]}]",
            ha="right",
            va="center",
            fontsize=7,
            color="#666666",
            family="monospace",
        )

    ax.set_xlim(-6, width + 1.5)
    ax.set_ylim(-(bands - 1) * pitch - 1.6, 2.6)
    ax.set_axis_off()
    ax.set_title(title, fontsize=11, loc="left", pad=8)
    ax.legend(
        handles=[
            Patch(facecolor=GROUND, label="hull"),
            Patch(facecolor="none", edgecolor=HOLE, label="hole"),
            Line2D([], [], color=PATH, lw=1.6, label="droid altitude"),
            Line2D([], [], color=JUMP, marker="^", lw=0, ms=5, label="take-off"),
        ],
        loc="upper right",
        bbox_to_anchor=(1, -0.01),
        ncol=4,
        frameon=False,
        fontsize=8,
    )
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(
        f"  wrote {path.relative_to(ROOT)}: {len(course)} chunks, "
        f"{len(holes)} holes, {len(take_offs)} jumps over {len(hull)} tiles"
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    mem = parse_input((ROOT / "inputs" / "day21.txt").read_text())
    walk, run = recover_courses(mem)
    hazard = 9  # window columns GROUND_LEFT..GROUND_LEFT+8 carry the chunk's payload
    assert all(chunk_window(v).count("#") >= 32 - hazard for _, v in walk + run)
    assert GROUND_LEFT - START == 5  # five guaranteed tiles of approach in every window

    draw_course(
        walk,
        PART1_SCRIPT,
        per_band=len(walk),
        path=OUT / "day21_walk_path.png",
        title="Day 21, Part 1 -- the WALK course: J = not(A and B and C) and D",
    )
    draw_course(
        walk + run,
        PART2_SCRIPT,
        per_band=10,
        path=OUT / "day21_run_path.png",
        title="Day 21, Part 2 -- the full course: J = not(A and B and C) and D and (E or H)",
    )


if __name__ == "__main__":
    main()
