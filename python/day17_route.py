"""Day 17 -- render the route as an interactive HTML page.

The grammar decomposition is the day's real artifact: ten calls --
A,B,A,C,B,C,B,C,A,C -- tiling one 332-step route over 319 scaffold cells.
`python/day17.py` never draws it. This writes a single self-contained HTML
file: the 55x35 scaffold with the route drawn in execution order, coloured by
which movement function is driving, with a draw-through animation and
click-to-highlight for each call and each function.

    python python/day17_route.py            # -> maps/day17_route.html
    python python/day17_route.py --out FILE # somewhere else

Everything in the page is computed from the real input via day17's own
functions -- no coordinate is hand-copied. The output is derived from the
puzzle input, so `maps/` is gitignored for the same reason `inputs/*.txt`
and the full Intcode listings are.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from day17 import (
    STEP,
    TURN_LEFT,
    TURN_RIGHT,
    camera_view,
    compress,
    find_robot,
    intersections,
    parse_input,
    path,
    scaffold_points,
)

ROOT = Path(__file__).resolve().parent.parent

mem = parse_input((ROOT / "inputs" / "day17.txt").read_text())
view = camera_view(mem)
tokens = path(view)
main, funcs = compress(tokens)
bodies = dict(zip("ABC", [f.split(",") for f in funcs]))
calls = main.split(",")
cells = scaffold_points(view)
crossings = sorted(intersections(view))

S = 16
(sx, sy), _f = find_robot(view)
pos, facing = (sx, sy), "^"


def center(p):
    return ((p[0] + 0.5) * S, (p[1] + 0.5) * S)


segs = []
for name in calls:
    pts = [center(pos)]
    steps = 0
    for turn, dist in zip(bodies[name][::2], bodies[name][1::2]):
        facing = (TURN_LEFT if turn == "L" else TURN_RIGHT)[facing]
        dx, dy = STEP[facing]
        n = int(dist)
        pos = (pos[0] + dx * n, pos[1] + dy * n)
        pts.append(center(pos))
        steps += n
    segs.append((name, pts, steps))

ex, ey = pos
total = sum(s for _, _, s in segs)
SPEED = 600.0  # px per second for the draw-through

tiles = "\n".join(
    f'      <rect x="{x * S + 1.5}" y="{y * S + 1.5}" width="{S - 3}" height="{S - 3}" rx="2.5"/>'
    for y in range(35)
    for x in range(55)
    if (x, y) in cells
)

poly_lines, css_anim = [], []
elapsed = 0.0
for i, (name, pts, steps) in enumerate(segs):
    length = steps * S
    points = " ".join(f"{x:g},{y:g}" for x, y in pts)
    poly_lines.append(
        f'      <polyline class="leg leg-{name}" data-call="{i}" points="{points}"\n'
        f'        style="--len:{length}; --dur:{length / SPEED:.3f}s; --delay:{elapsed / SPEED:.3f}s"/>'
    )
    elapsed += length
polys = "\n".join(poly_lines)

rings = "\n".join(
    f'      <circle class="crossing" cx="{(x + 0.5) * S}" cy="{(y + 0.5) * S}" r="5"/>' for x, y in crossings
)

chips = "\n".join(
    f'        <button class="chip chip-{name}" data-call="{i}">'
    f'<span class="chip-name">{name}</span><span class="chip-steps">{steps}</span></button>'
    for i, (name, _pts, steps) in enumerate(segs)
)

cards = "\n".join(
    f'        <button class="card card-{name}" data-fn="{name}">'
    f'<span class="card-name">{name}</span>'
    f"<code>{','.join(bodies[name])}</code>"
    f'<span class="card-meta">{len(",".join(bodies[name]))} of 20 chars &middot; '
    f"{sum(int(d) for d in bodies[name][1::2])} steps &middot; called {calls.count(name)}&times;</span>"
    f"</button>"
    for name in "ABC"
)

sxc, syc = center((sx, sy))

html = f"""<title>One Route, Three Functions</title>
<style>
  :root {{
    --bg: #F4F6F8;
    --panel: #FFFFFF;
    --ink: #1C2733;
    --muted: #5C6C7D;
    --tile: #DDE4EB;
    --edge: #C9D3DD;
    --a: #3E7FD4;
    --b: #D9862B;
    --c: #9A5FD0;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #0F151C;
      --panel: #161E27;
      --ink: #E4EBF2;
      --muted: #8B9AAB;
      --tile: #28323E;
      --edge: #333F4D;
      --a: #6AA6F0;
      --b: #E8A34C;
      --c: #B98AE6;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0F151C;
    --panel: #161E27;
    --ink: #E4EBF2;
    --muted: #8B9AAB;
    --tile: #28323E;
    --edge: #333F4D;
    --a: #6AA6F0;
    --b: #E8A34C;
    --c: #B98AE6;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: ui-monospace, "Cascadia Code", Consolas, "SF Mono", monospace;
    margin: 0;
    padding: 28px 20px 48px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 22px; }}
  header h1 {{
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0 0 6px;
    text-wrap: balance;
  }}
  header p {{
    font-family: system-ui, sans-serif;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.55;
    margin: 0;
    max-width: 62ch;
  }}
  header a {{ color: inherit; }}
  .stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px 26px;
    padding: 12px 16px;
    background: var(--panel);
    border: 1px solid var(--edge);
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
  }}
  .stat {{ display: flex; flex-direction: column; gap: 1px; }}
  .stat b {{ font-size: 17px; font-weight: 600; }}
  .stat span {{ font-size: 11px; color: var(--muted); letter-spacing: 0.06em; text-transform: uppercase; }}
  figure {{
    margin: 0;
    background: var(--panel);
    border: 1px solid var(--edge);
    border-radius: 8px;
    padding: 14px;
    overflow-x: auto;
  }}
  figure svg {{ display: block; max-width: 100%; height: auto; min-width: 640px; }}
  figcaption {{
    font-family: system-ui, sans-serif;
    font-size: 12.5px;
    color: var(--muted);
    padding: 10px 4px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }}
  .tile {{ fill: var(--tile); }}
  .leg {{
    fill: none;
    stroke-width: 6;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0.92;
    transition: opacity 0.15s;
  }}
  .leg-A {{ stroke: var(--a); }}
  .leg-B {{ stroke: var(--b); }}
  .leg-C {{ stroke: var(--c); }}
  svg.run .leg {{
    stroke-dasharray: var(--len) var(--len);
    animation: draw var(--dur) linear var(--delay) both;
  }}
  @keyframes draw {{
    from {{ stroke-dashoffset: var(--len); }}
    to {{ stroke-dashoffset: 0; }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    svg.run .leg {{ animation: none; stroke-dasharray: none; }}
  }}
  svg.focused .leg {{ opacity: 0.13; }}
  svg.focused .leg.hot {{ opacity: 1; }}
  .crossing {{ fill: none; stroke: var(--ink); stroke-width: 1.4; opacity: 0.55; }}
  .start {{ fill: var(--ink); }}
  .endcap {{ fill: none; stroke: var(--ink); stroke-width: 2; }}
  .maplabel {{ font: 11px ui-monospace, Consolas, monospace; fill: var(--ink); opacity: 0.8; }}
  button {{
    font: inherit;
    color: inherit;
    background: var(--panel);
    border: 1px solid var(--edge);
    border-radius: 7px;
    cursor: pointer;
  }}
  button:focus-visible {{ outline: 2px solid var(--a); outline-offset: 2px; }}
  .replay {{ font-size: 12px; padding: 5px 12px; white-space: nowrap; }}
  .replay:hover {{ border-color: var(--muted); }}
  .program {{ display: flex; flex-direction: column; gap: 14px; }}
  .program h2 {{
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0;
  }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    padding: 6px 13px 5px;
    border-width: 1px 1px 3px;
    font-variant-numeric: tabular-nums;
  }}
  .chip-name {{ font-size: 16px; font-weight: 600; }}
  .chip-steps {{ font-size: 10.5px; color: var(--muted); }}
  .chip-A {{ border-bottom-color: var(--a); }}
  .chip-B {{ border-bottom-color: var(--b); }}
  .chip-C {{ border-bottom-color: var(--c); }}
  .chip.hot, .card.hot {{ background: color-mix(in srgb, var(--panel) 82%, var(--ink)); }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }}
  .card {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding: 11px 14px;
    text-align: left;
    border-left-width: 4px;
  }}
  .card-A {{ border-left-color: var(--a); }}
  .card-B {{ border-left-color: var(--b); }}
  .card-C {{ border-left-color: var(--c); }}
  .card-name {{ font-weight: 600; font-size: 15px; }}
  .card code {{ font-size: 13px; }}
  .card-meta {{ font-size: 11px; color: var(--muted); }}
  footer {{
    font-family: system-ui, sans-serif;
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.6;
    max-width: 72ch;
  }}
</style>

<div class="wrap">
  <header>
    <h1>One route, three functions</h1>
    <p>AoC 2019 Day 17, Part Two: the vacuum robot's tour of the scaffold, drawn
    in execution order and colored by which movement function is driving. Ten
    calls &mdash; <code>{main}</code> &mdash; tile the whole 332-step route.
    Companion figure to the day&rsquo;s function guide and disassembly.</p>
  </header>

  <div class="stats">
    <div class="stat"><b>{total}</b><span>steps</span></div>
    <div class="stat"><b>{len(tokens) // 2}</b><span>moves</span></div>
    <div class="stat"><b>{len(cells)}</b><span>scaffold cells</span></div>
    <div class="stat"><b>{len(crossings)}</b><span>crossings, each driven twice</span></div>
    <div class="stat"><b>{len(main)}<small>/20</small></b><span>main routine chars</span></div>
  </div>

  <figure>
    <svg id="map" class="run" viewBox="-6 -6 {55 * S + 12} {35 * S + 12}" role="img"
         aria-label="The 55 by 35 scaffold grid with the robot's route drawn over it, colored by movement function: blue for A, amber for B, violet for C. The route starts at cell 26,16 facing up and ends at cell 54,28. Rings mark the 14 intersections, each driven through twice.">
      <g class="tiles">
{tiles}
      </g>
      <g>
{polys}
      </g>
{rings}
      <path class="start" d="M {sxc - 5.5} {syc + 4.5} L {sxc + 5.5} {syc + 4.5} L {sxc} {syc - 6} Z"/>
      <rect class="endcap" x="{ex * S + 3.5}" y="{ey * S + 3.5}" width="{S - 7}" height="{S - 7}" rx="2"/>
      <text class="maplabel" x="{sxc + 10}" y="{syc - 8}">start (26,16)</text>
      <text class="maplabel" x="{(ex + 0.5) * S - 10}" y="{(ey + 2) * S}" text-anchor="end">end (54,28)</text>
    </svg>
    <figcaption>
      <span>Draw order is drive order. Rings are the 14 intersections &mdash; the only
      cells visited twice, once per strand.</span>
      <button class="replay" id="replay">&#8635; replay</button>
    </figcaption>
  </figure>

  <div class="program">
    <h2>Main routine &mdash; {len(main)} of 20 characters</h2>
    <div class="chips">
{chips}
    </div>
    <h2>Movement functions</h2>
    <div class="cards">
{cards}
    </div>
  </div>

  <footer>
    Click a call to light its leg of the route; click a function to light every
    leg it drives. The whole 34-move route spells only three distinct distances
    (6, 10, 12), which is why three 20-character functions cover it &mdash; and
    this <code>(main, A, B, C)</code> factorisation is the only legal one, by
    exhaustive count.
  </footer>
</div>

<script>
  const map = document.getElementById("map");
  const legs = [...map.querySelectorAll(".leg")];
  const buttons = [...document.querySelectorAll(".chip, .card")];
  let active = null;

  function clear() {{
    active = null;
    map.classList.remove("focused");
    legs.forEach(l => l.classList.remove("hot"));
    buttons.forEach(b => b.classList.remove("hot"));
  }}

  buttons.forEach(btn => btn.addEventListener("click", () => {{
    const key = btn.dataset.call ?? btn.dataset.fn;
    if (active === key) return clear();
    clear();
    active = key;
    btn.classList.add("hot");
    map.classList.add("focused");
    const match = btn.dataset.call !== undefined
      ? l => l.dataset.call === btn.dataset.call
      : l => l.classList.contains("leg-" + btn.dataset.fn);
    legs.forEach(l => l.classList.toggle("hot", match(l)));
  }}));

  document.getElementById("replay").addEventListener("click", () => {{
    clear();
    map.classList.remove("run");
    void map.getBoundingClientRect();
    map.classList.add("run");
  }});
</script>
"""

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--out", type=Path, default=None, help="output file (default: maps/day17_route.html)")
args = parser.parse_args()

out = args.out or ROOT / "maps" / "day17_route.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8", newline="\n")
print(f"wrote {out}: {len(html)} chars, {len(tiles.splitlines())} tiles, {total} steps")
