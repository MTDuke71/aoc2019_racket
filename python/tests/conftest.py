"""Fixtures shared by every day's test module.

Two hazards this file exists to remove.

1. **Puzzle inputs are not in the repo.** `.gitignore` carries `inputs/*.txt`,
   because AoC asks that inputs not be republished. A fresh clone therefore has
   none of them, and a test that needs one must SKIP rather than fail -- a red
   suite on a clean checkout trains you to ignore red. That is `real_input`.

2. **An answer nobody has submitted is not a verified answer.** `check_locked`
   compares against the day's `LOCKED` constant when there is one, and when
   `LOCKED` is `None` it reports what the code currently produces and skips.
   The one thing it will never do is report a green pass for a number nothing
   has confirmed. Copy the value into `LOCKED` only after the site accepts it.

Both signal through skips, which is why `addopts = "-rs"` is set in
pyproject.toml: skip reasons are printed on every run, never swallowed.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUTS = REPO_ROOT / "inputs"

PARTS = ("part 1", "part 2")


def _stem(day: int | str) -> str:
    """1 -> 'day01'; '13_alt' -> 'day13_alt'. Days with variant inputs use the latter."""
    return f"day{day:02d}" if isinstance(day, int) else f"day{day}"


def _normalise(locked) -> dict[str, object]:
    """Accept `None`, a 2-sequence, or a dict; return {'part 1': ..., 'part 2': ...}.

    `None` in any slot means "not verified yet".
    """
    if locked is None:
        return {p: None for p in PARTS}
    if isinstance(locked, dict):
        out = {}
        for part, key in zip(PARTS, ("part1", "part2")):
            out[part] = locked.get(key, locked.get(part))
        return out
    first, second = locked
    return {"part 1": first, "part 2": second}


@pytest.fixture
def inputs_dir() -> Path:
    """The directory puzzle inputs live in.

    A separate fixture purely so a test module can override it -- see
    test_platform.py, which points it at a tmp_path in order to exercise
    `real_input` and `check_locked` without depending on any real input file.
    """
    return INPUTS


@pytest.fixture
def real_input(inputs_dir):
    """`real_input(3)` -> the text of inputs/day03.txt, or a skip if it is absent.

    Returns the text with any CRLF intact: tolerating `\r` is the day module's
    job, and handing it pre-cleaned text here would hide the bug this repo
    actually hits on Windows.

    Note the `newline=""`. `Path.read_text()` opens in universal-newline mode
    and rewrites every `\r\n` to `\n`, so reading an input the obvious way
    would launder the CRLF away before any parser ever saw it -- and a CRLF
    test run through it would be asserting nothing. (`read_text` grew a
    `newline` parameter in 3.13; this repo runs 3.12, hence `open`.)
    """

    def _load(day: int | str) -> str:
        path = inputs_dir / f"{_stem(day)}.txt"
        if not path.is_file():
            shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
            pytest.skip(f"{shown} is absent (inputs are gitignored)")
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()

    return _load


@pytest.fixture
def check_locked(real_input):
    """Run a day against its real input and check it against known-good answers.

        LOCKED = (3481005, 5218616)          # verified on adventofcode.com

        def test_real_input(check_locked):
            check_locked(1, LOCKED)

    A day whose `part1`/`part2` do not yet take the parsed data alone can pass
    callables instead of relying on the module's::

        check_locked(8, LOCKED, part1=lambda d: day08.part1(d, 25, 6))

    Each part is handed a FRESHLY PARSED copy: several days (every Intcode one)
    mutate the program list in place, so sharing one parse between the parts
    would make part 2 depend on part 1 having run.
    """

    def _check(day: int | str, locked, *, module=None, parse_input=None, part1=None, part2=None):
        if module is None and None in (parse_input, part1, part2):
            module = importlib.import_module(_stem(day))
        parse = parse_input or module.parse_input
        fns = {"part 1": part1 or module.part1, "part 2": part2 or module.part2}

        text = real_input(day)
        got = {part: fn(parse(text)) for part, fn in fns.items()}
        want = _normalise(locked)

        for part in PARTS:
            if want[part] is not None:
                assert got[part] == want[part], (
                    f"{_stem(day)} {part}: produced {got[part]!r}, locked answer is {want[part]!r}"
                )

        unlocked = [p for p in PARTS if want[p] is None]
        if unlocked:
            # Asserted first, skipped second: a regression in an already-locked
            # part still fails loudly even though the day as a whole is unverified.
            produced = "; ".join(f"{p} = {got[p]!r}" for p in unlocked)
            pytest.skip(
                f"{_stem(day)}: UNVERIFIED -- {produced}. "
                f"Submit it, then put it in LOCKED to turn this into a real check."
            )
        return got

    return _check
