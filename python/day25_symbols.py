r"""Rebase the vendored decompiler's day-25 symbols onto this input.

The vendored Intcode decompiler (intcode-disasm-master/, gitignored) was
written FOR Day 25 and ships its author's annotations in data/25.symbols:
function names, argument names, struct definitions (Location, Item), and
typed globals. The engine CODE is identical across puzzle inputs -- every
function and code-section global in that file matches this input address
for address -- but the world data is not: the author's input stores its
weight threshold as 53 * 57 = 3021 (this input: 84 * 52 = 4368) and lays
out the same twenty room names at different addresses.

This script writes intcode-disasm-master/day25_matt.symbols: the author's
file with the twenty LOCATION_* globals replaced by this input's room
addresses (from day25_disasm's engine recovery) and the threshold names
re-derived from the image. Then:

    cd intcode-disasm-master
    cargo run --release -- hlr ..\inputs\day25.txt --symbols day25_matt.symbols

yields the fully-labelled decompilation (saved locally as day25_hlr.txt,
next to the tool's day17/day19 outputs; all of it gitignored -- the
decoded strings are the puzzle input's own text). The tool colours its
output with ANSI escapes and has no plain theme, so strip them when
redirecting to a file -- in PowerShell:

    ... | % { $_ -replace "$([char]27)\[[0-9;]*[A-Za-z]", '' } | Out-File day25_hlr.txt

Run:  python python/day25_symbols.py
"""

from __future__ import annotations

import re
from pathlib import Path

from day25 import parse_input
from day25_disasm import recover_engine

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "intcode-disasm-master"


def main() -> None:
    source = TOOL / "data" / "25.symbols"
    if not source.is_file():
        raise SystemExit(f"{source} not found -- is the vendored decompiler present?")
    mem = parse_input((ROOT / "inputs" / "day25.txt").read_text())
    engine = recover_engine(mem)

    out: list[str] = []
    replaced = 0
    for line in source.read_text().splitlines():
        if re.match(r"G\s+\d+\s+LOCATION_", line):
            replaced += 1  # the author's-input room addresses
            continue
        line = re.sub(r"MAGIC_THRESHOLD_\d+", f"MAGIC_THRESHOLD_{engine.threshold}", line)
        line = re.sub(r"G 2486 Const_\d+", f"G 2486 Const_{mem[2486]}", line)
        line = re.sub(r"G 1352 Const_\d+", f"G 1352 Const_{mem[1352]}", line)
        line = re.sub(r"> \d+ if item", f"> {engine.threshold} if item", line)
        out.append(line)

    out += [
        "",
        "# Rooms rebased onto this input by python/day25_symbols.py (the",
        f"# author's original carried {replaced} at its own input's addresses;",
        "# same twenty names, different layout and topology).",
    ]
    for addr in sorted(engine.rooms):
        name = "LOCATION_" + re.sub(r"[^A-Za-z0-9]+", "_", engine.rooms[addr].name.upper()).strip("_")
        out.append(f"G {addr}  {name:40} Location")

    dest = TOOL / "day25_matt.symbols"
    dest.write_text("\n".join(out) + "\n")
    print(f"wrote {dest}")
    print(f"  {replaced} room globals rebased; threshold {mem[2486]} * {mem[1352]} = {engine.threshold}")


if __name__ == "__main__":
    main()
