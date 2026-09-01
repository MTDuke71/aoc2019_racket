"""Day 25 visuals: the ship as the tree it is, and the answer as binary.

Writes two PNGs into Problem_Statements/days/images/:

  day25_ship_map.png  the twenty rooms as a tree rooted at the start room --
                      which is what the ship actually IS: twenty rooms, only
                      nineteen door pairs, no cycles. Edges carry their
                      compass direction, because the directions cannot be
                      drawn literally: laying rooms out by their own doors
                      (north = up one cell, etc.) lands five PAIRS of rooms
                      on the same spot -- the ship is a spatially impossible
                      text-adventure classic, pinned by
                      test_ship_is_a_tree_with_impossible_geometry.
  day25_weights.png   TARGET IS ANSWER, drawn: the 33-bit target weight the
                      pressure floor demands, with each safe item sitting at
                      its own power of two -- the winning load-out is
                      literally the target's 1-bits.

Everything is recovered statically from the image via day25_disasm's engine
recovery -- the game is never run. Needs: networkx, matplotlib, pydot, and
Graphviz's `dot` on PATH (the tree layout).

Run:  python python/viz_day25.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from day25 import parse_input
from day25_disasm import DIRECTIONS, decode_target, recover_engine
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Problem_Statements" / "days" / "images"

FLOOR_FACE = "#f4f1ea"
WIN_FACE = "#f7e8b0"
SAFE_INK = "#1f8a8a"
TRAP_INK = "#b3312f"
START_EDGE = "#3b3b8f"
CHECK_EDGE = "#d9822b"
ROUTE = "#d9822b"
EDGE_GRAY = "#8a8a8a"


def ship_figure(engine, target: int) -> None:
    rooms = engine.rooms
    items_by_room: dict[int, list] = {}
    for item in engine.items:
        items_by_room.setdefault(item.location, []).append(item)
    winners = {
        item.location
        for item in engine.items
        if not item.hook and target >> (item.weight.bit_length() - 1) & 1
    }

    # the tree, rooted at the start: parent -> child edges with a direction
    tree = nx.DiGraph()
    parent_door: dict[int, str] = {}
    parent_of: dict[int, int] = {}
    queue, seen = [engine.start_room], {engine.start_room}
    while queue:
        addr = queue.pop(0)
        label_w = max(len(rooms[addr].name), 14) * 0.11
        tree.add_node(addr, width=f"{label_w:.2f}", height="0.55", shape="box")
        for slot, dest in enumerate(rooms[addr].doors):
            if dest and dest not in seen:
                seen.add(dest)
                tree.add_edge(addr, dest)
                parent_door[dest] = DIRECTIONS[slot]
                parent_of[dest] = addr
                queue.append(dest)

    # the checkpoint route, walked backwards up the tree
    checkpoint = next(a for a in rooms if any(d == engine.floor for d in rooms[a].doors))
    route_edges = set()
    node = checkpoint
    while node != engine.start_room:
        route_edges.add((parent_of[node], node))
        node = parent_of[node]

    pos = nx.nx_pydot.graphviz_layout(tree, prog="dot", root=str(engine.start_room))

    fig, ax = plt.subplots(figsize=(17, 10))
    for a, b in tree.edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        on_route = (a, b) in route_edges
        ax.plot(
            [x1, x2],
            [y1, y2],
            color=ROUTE if on_route else EDGE_GRAY,
            linewidth=3.0 if on_route else 1.2,
            zorder=1,
        )
        ax.text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            parent_door[b][0].upper(),
            fontsize=8,
            color="#555",
            ha="center",
            va="center",
            bbox={"boxstyle": "circle,pad=0.15", "fc": "white", "ec": "none"},
            zorder=2,
        )

    for addr, (x, y) in pos.items():
        room = rooms[addr]
        face = WIN_FACE if addr in winners else FLOOR_FACE
        edge, lw, ls = "#666666", 1.0, "-"
        if addr == engine.start_room:
            edge, lw = START_EDGE, 2.5
        elif addr == checkpoint:
            edge, lw = CHECK_EDGE, 2.5
        elif addr == engine.floor:
            edge, lw, ls = TRAP_INK, 2.5, "--"
        ax.text(
            x,
            y + 4,
            room.name,
            fontsize=9,
            fontweight="bold",
            ha="center",
            va="bottom",
            zorder=3,
            bbox={"boxstyle": "round,pad=0.45", "fc": face, "ec": edge, "lw": lw, "linestyle": ls},
        )
        for item in items_by_room.get(addr, []):
            tag = f"â˜  {item.name}" if item.hook else f"{item.name} (2^{item.weight.bit_length() - 1})"
            ax.text(
                x,
                y - 7,
                tag,
                fontsize=8,
                ha="center",
                va="top",
                color=TRAP_INK if item.hook else SAFE_INK,
                zorder=3,
                bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.85},
            )

    ax.legend(
        handles=[
            Patch(fc=FLOOR_FACE, ec=START_EDGE, lw=2, label="Hull Breach (start)"),
            Patch(fc=FLOOR_FACE, ec=CHECK_EDGE, lw=2, label="Security Checkpoint"),
            Patch(fc=FLOOR_FACE, ec=TRAP_INK, lw=2, linestyle="--", label="Pressure-Sensitive Floor"),
            Patch(fc=WIN_FACE, ec="#666", label="holds a winning item"),
            Line2D([], [], color=ROUTE, lw=3, label="route to the checkpoint"),
            Line2D([], [], color=SAFE_INK, marker="$a$", lw=0, label="safe item (weight 2^k)"),
            Line2D([], [], color=TRAP_INK, marker="$â˜ $", lw=0, label="trap item (weighs 0)"),
        ],
        loc="upper right",
        fontsize=9,
        framealpha=0.95,
    )
    ax.set_title(
        "The ship is a tree: 20 rooms, 19 door pairs, no cycles â€” and its compass directions "
        "(edge letters) describe a spatially impossible layout",
        fontsize=12,
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "day25_ship_map.png", dpi=150)
    plt.close(fig)


def weights_figure(engine, target: int) -> None:
    safe = sorted((i for i in engine.items if not i.hook), key=lambda i: -i.weight)
    traps = [i.name for i in engine.items if i.hook]

    fig, ax = plt.subplots(figsize=(14, 4.6))
    for p in range(33):
        bit = target >> p & 1
        ax.add_patch(plt.Rectangle((p - 0.45, 1.0), 0.9, 0.8, fc=WIN_FACE if bit else "white", ec="#999"))
        if bit:
            ax.text(p, 1.4, "1", ha="center", va="center", fontsize=11, fontweight="bold")
        if p % 4 == 0 or bit:
            ax.text(p, 1.95, str(p), ha="center", va="bottom", fontsize=7, color="#777")

    # adjacent powers (2^19, 2^21, 2^22) would collide: stagger label depths
    for rank, item in enumerate(safe):
        p = item.weight.bit_length() - 1
        chosen = bool(target >> p & 1)
        depth = 0.42 if rank % 2 == 0 else -0.02
        ax.plot([p], [0.55], "o", markersize=9, color=CHECK_EDGE if chosen else "#bbbbbb", zorder=3)
        ax.plot([p, p], [0.62, 0.98], color=CHECK_EDGE if chosen else "#cccccc", lw=2 if chosen else 1)
        if rank % 2:
            ax.plot([p, p], [0.12, 0.48], color="#dddddd", lw=0.8, zorder=1)
        ax.text(
            p,
            depth,
            f"{item.name}\n$2^{{{p}}}$",
            ha="center",
            va="top",
            fontsize=8,
            color="#333" if chosen else "#999",
            fontweight="bold" if chosen else "normal",
        )
    ax.text(
        0.01,
        0.02,
        "weightless traps: " + ", ".join(traps),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color=TRAP_INK,
        style="italic",
    )

    ax.set_title(
        f"TARGET IS ANSWER: the floor's 33-bit table decodes to {target} = "
        f"{target:#b},\nand the winning load-out is exactly its 1-bits",
        fontsize=11,
    )
    ax.set_xlim(-1, 34)
    ax.set_ylim(-0.55, 2.35)
    ax.invert_xaxis()
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "day25_weights.png", dpi=150)
    plt.close(fig)


def main() -> None:
    program = parse_input((ROOT / "inputs" / "day25.txt").read_text())
    engine = recover_engine(program)
    target = decode_target(program, engine)
    OUT.mkdir(exist_ok=True)
    ship_figure(engine, target)
    weights_figure(engine, target)
    print(f"wrote {OUT / 'day25_ship_map.png'}")
    print(f"wrote {OUT / 'day25_weights.png'}")


if __name__ == "__main__":
    main()
