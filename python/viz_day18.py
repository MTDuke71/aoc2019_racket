"""Day 18 visuals: the maze, the Part 2 split, and the condensed weighted graph.

Writes four PNGs into Problem_Statements/days/images/:

  day18_maze_part1.png   the 81x81 vault with keys, doors and the entrance
  day18_maze_part2.png   the split map, each robot's vault tinted
  day18_graph_part1.png  the 53-vertex condensed graph, edges labelled in steps
  day18_graph_part2.png  the same after the split: four components
  day18_plaza.png        the entrance's neighbourhood: the open middle as a weighted core

The graph drawings use Graphviz (`dot`) through networkx/pydot, laid out on the
hop-depth tree from the entrances so depth reads top-down. Keys are circles, doors are squares, the
entrance a diamond; every node carries its letter so colour is never the only
cue. Needs: networkx, matplotlib, pydot, and Graphviz's `dot` on PATH.

Run:  python python/viz_day18.py
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from day18 import Pos, Vault, condense, parse_input, split_entrance
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Problem_Statements" / "days" / "images"

WALL = "#2b2b33"
FLOOR = "#f4f1ea"
KEY = "#1f8a8a"
DOOR = "#d9822b"
ENTRANCE = "#3b3b8f"
VAULT_TINTS = ["#dbe8f7", "#e3f2dc", "#fbe7d9", "#ede1f4"]


def grid_shape(vault: Vault) -> tuple[int, int]:
    xs = [x for x, _ in vault.open_cells]
    ys = [y for _, y in vault.open_cells]
    # open cells never touch the border, so +2 is the full wall-to-wall extent
    return max(xs) + 2, max(ys) + 2


def flood(vault: Vault, start: Pos) -> set[Pos]:
    """Cells reachable from `start` ignoring locks: one robot's whole vault."""
    seen = {start}
    frontier = deque([start])
    while frontier:
        x, y = frontier.popleft()
        for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nbr in vault.open_cells and nbr not in seen:
                seen.add(nbr)
                frontier.append(nbr)
    return seen


def draw_maze(vault: Vault, path: Path, title: str, tint_vaults: bool) -> None:
    w, h = grid_shape(vault)
    regions = [flood(vault, e) for e in vault.entrances] if tint_vaults else [set(vault.open_cells)]
    # Raster the floor: index 0 is wall, region i+1 is that region's tint.
    palette = [WALL] + (
        [VAULT_TINTS[i % len(VAULT_TINTS)] for i in range(len(regions))] if tint_vaults else [FLOOR]
    )
    raster = np.zeros((h, w), dtype=int)
    for i, cells in enumerate(regions):
        for x, y in cells:
            raster[y, x] = i + 1
    fig, ax = plt.subplots(figsize=(11, 11), dpi=150)
    ax.imshow(raster, cmap=ListedColormap(palette), interpolation="nearest", vmin=0, vmax=len(palette) - 1)
    label_style = {
        "ha": "center",
        "va": "center",
        "fontsize": 6.5,
        "color": "white",
        "weight": "bold",
        "zorder": 4,
    }
    for pos, ch in vault.keys.items():
        ax.scatter(*pos, marker="o", s=110, c=KEY, linewidths=0, zorder=3)
        ax.text(*pos, ch, **label_style)
    for pos, ch in vault.doors.items():
        ax.scatter(*pos, marker="s", s=110, c=DOOR, linewidths=0, zorder=3)
        ax.text(*pos, ch.upper(), **label_style)
    for pos in vault.entrances:
        ax.scatter(*pos, marker="D", s=130, c=ENTRANCE, linewidths=0, zorder=3)
        ax.text(*pos, "@", **label_style)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, fontsize=13, loc="left", pad=10)
    handles = [
        Patch(color=KEY, label="key (a-z)"),
        Patch(color=DOOR, label="door (A-Z)"),
        Patch(color=ENTRANCE, label="entrance @"),
    ]
    if tint_vaults:
        for i, cells in enumerate(regions):
            keys = sum(p in cells for p in vault.keys)
            doors = sum(p in cells for p in vault.doors)
            handles.append(
                Patch(
                    color=VAULT_TINTS[i],
                    label=f"vault {i + 1}: {len(cells)} cells, {keys} keys, {doors} doors",
                )
            )
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_graph(vault: Vault) -> nx.Graph:
    """Undirected condensed graph; parallel corridors keep the shortest."""
    g = nx.Graph()
    graph = condense(vault)
    for pos in graph:
        if pos in vault.keys:
            g.add_node(pos, label=vault.keys[pos], kind="key")
        elif pos in vault.doors:
            g.add_node(pos, label=vault.doors[pos].upper(), kind="door")
        else:
            g.add_node(pos, label="@", kind="entrance")
    for src, edges in graph.items():
        for dst, w in edges:
            if g.has_edge(src, dst):
                g[src][dst]["weight"] = min(g[src][dst]["weight"], w)
            else:
                g.add_edge(src, dst, weight=w)
    return g


def tree_layout(h: nx.Graph, roots: list[str]) -> tuple[dict, set]:
    """Graphviz `dot` on the hop-depth spanning forest from the entrances.

    Dijkstra-by-hops from each root gives a tree whose rank is "how many
    points of interest deep"; laying out THAT, then drawing the full edge set
    on top, keeps the four long chains straight and pushes the plaza's
    cross-corridors into arcs. Returns the positions and the tree edge set.
    """
    forest = nx.Graph()
    for root in roots:
        forest = nx.compose(forest, nx.bfs_tree(h, root).to_undirected())
    for n in forest:
        forest.nodes[n].update(h.nodes[n])
    forest.graph["graph"] = {"rankdir": "TB", "nodesep": "0.3", "ranksep": "0.7"}
    layout = nx.nx_pydot.graphviz_layout(forest, prog="dot")
    tree_edges = {frozenset(e) for e in forest.edges}
    return layout, tree_edges


def draw_nodes(h: nx.Graph, layout: dict, ax, size: int) -> None:
    for kind, shape, colour, scale in (
        ("key", "o", KEY, 1.0),
        ("door", "s", DOOR, 0.9),
        ("entrance", "D", ENTRANCE, 1.1),
    ):
        nodes = [n for n, d in h.nodes(data=True) if d["kind"] == kind]
        nx.draw_networkx_nodes(
            h, layout, nodelist=nodes, node_shape=shape, node_color=colour, node_size=size * scale, ax=ax
        )
    nx.draw_networkx_labels(
        h,
        layout,
        labels=nx.get_node_attributes(h, "label"),
        font_size=9,
        font_color="white",
        font_weight="bold",
        ax=ax,
    )


LEGEND = [
    Patch(color=KEY, label="key (circle)"),
    Patch(color=DOOR, label="door (square)"),
    Patch(color=ENTRANCE, label="entrance (diamond)"),
]
LABEL_BOX = {"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85}


def draw_graph(vault: Vault, path: Path, title: str) -> None:
    g = build_graph(vault)
    relabel = {(x, y): f"n{x}_{y}" for x, y in g.nodes}  # Graphviz wants string ids
    h = nx.relabel_nodes(g, relabel)
    layout, tree_edges = tree_layout(h, [relabel[e] for e in vault.entrances])
    weights = nx.get_edge_attributes(h, "weight")
    straight = [e for e in h.edges if frozenset(e) in tree_edges]
    arcs = [e for e in h.edges if frozenset(e) not in tree_edges]

    n_comp = nx.number_connected_components(h)
    fig, ax = plt.subplots(figsize=(20, 12), dpi=150)
    nx.draw_networkx_edges(h, layout, ax=ax, edgelist=straight, edge_color="#8c8c8c", width=1.6)
    nx.draw_networkx_edge_labels(
        h,
        layout,
        ax=ax,
        edge_labels={e: weights[e] for e in straight},
        font_size=7,
        font_color="#333333",
        bbox=LABEL_BOX,
        rotate=False,
    )
    # Cross edges (the plaza and the four cycles) fan out as arcs of varying bend so they stay distinct.
    for i, e in enumerate(arcs):
        rad = (0.12 + 0.06 * (i % 5)) * (1 if i % 2 else -1)
        style = f"arc3,rad={rad}"
        nx.draw_networkx_edges(
            h,
            layout,
            ax=ax,
            edgelist=[e],
            edge_color="#b8b8b8",
            width=0.9,
            arrows=True,
            arrowstyle="-",
            connectionstyle=style,
        )
        nx.draw_networkx_edge_labels(
            h,
            layout,
            ax=ax,
            edge_labels={e: weights[e]},
            font_size=6,
            font_color="#666666",
            bbox=LABEL_BOX,
            rotate=False,
            connectionstyle=style,
        )
    draw_nodes(h, layout, ax, 420)
    ax.set_axis_off()
    plural = "s" if n_comp > 1 else ""
    ax.set_title(
        f"{title} -- {h.number_of_nodes()} vertices, {h.number_of_edges()} edges, {n_comp} component{plural}. "
        f"Straight edges: hop-depth tree from the entrance{plural}; arcs: the {len(arcs)} cross-corridors. "
        f"Labels are steps.",
        fontsize=11,
        loc="left",
    )
    ax.legend(handles=LEGEND, loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def draw_plaza(vault: Vault, path: Path) -> None:
    """The entrance and its condensed-graph neighbours: the open middle of the map as a weighted clique-ish core."""
    g = build_graph(vault)
    (entrance,) = vault.entrances
    core = [entrance, *sorted(g.neighbors(entrance), key=lambda p: g.nodes[p]["label"])]
    sub = g.subgraph(core)
    layout = nx.circular_layout(sub)
    weights = nx.get_edge_attributes(sub, "weight")
    fig, ax = plt.subplots(figsize=(11, 11), dpi=150)
    longest = max(weights.values())
    widths = [max(0.5, 3.0 - 2.5 * (w / longest)) for w in weights.values()]
    nx.draw_networkx_edges(sub, layout, ax=ax, edge_color="#9a9a9a", width=widths)
    nx.draw_networkx_edge_labels(
        sub,
        layout,
        ax=ax,
        edge_labels=weights,
        font_size=7,
        font_color="#333333",
        bbox=LABEL_BOX,
        rotate=False,
    )
    draw_nodes(sub, layout, ax, 700)
    ax.set_axis_off()
    ax.set_title(
        f"The plaza: `@` and its {len(core) - 1} condensed-graph neighbours, {sub.number_of_edges()} corridors among them "
        f"(thicker = shorter; labels are steps)",
        fontsize=11,
        loc="left",
    )
    ax.legend(handles=LEGEND, loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    vault = parse_input((ROOT / "inputs" / "day18.txt").read_text())
    split = split_entrance(vault)
    draw_maze(
        vault, OUT / "day18_maze_part1.png", "Day 18, Part 1 -- the vault (81x81, 26 keys, 26 doors)", False
    )
    draw_maze(
        split,
        OUT / "day18_maze_part2.png",
        "Day 18, Part 2 -- the split: four sealed vaults, one robot each",
        True,
    )
    draw_graph(vault, OUT / "day18_graph_part1.png", "Part 1 condensed graph")
    draw_graph(split, OUT / "day18_graph_part2.png", "Part 2 condensed graph")
    draw_plaza(vault, OUT / "day18_plaza.png")
    for p in sorted(OUT.glob("day18_*.png")):
        print(f"  wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
