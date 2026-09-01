"""Day 25 -- the full session transcript, exactly as played.

Writes Problem_Statements/days/day25_transcript.md: every command part 1
sends and every reply the game prints, in order -- the exploration sweep
(with each of the thirteen item probes shown as the SANDBOXED FORK it is,
indented at the spot where the real droid ran it: the fork is where the
death messages live, since the real droid never takes a trap), then the
walk to the checkpoint and all the pressure-floor trials of the Gray-code
walk, down to the airlock speech.

The transcript is gitignored alongside the full Intcode listings: the room
descriptions are the puzzle input's own text (54.6% of the image -- see
day25_disassembly.md), so committing it would republish the input verbatim.
Regenerate locally:  python python/day25_transcript.py

The recorder is a Droid subclass that taps run/send/fork; the solve itself
is the shipping explore() + crack_floor(), untouched.
"""

from __future__ import annotations

from pathlib import Path

from day25 import PASSWORD, Droid, crack_floor, explore, parse_input

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Problem_Statements" / "days" / "day25_transcript.md"

Event = tuple[str, object]  # ("cmd" | "out" | "halted" | "probe" | "phase", payload)


class RecordingDroid(Droid):
    """The shipping Droid with a flight recorder on its ASCII port."""

    def __init__(self, program: list[int]) -> None:
        super().__init__(program)
        self.events: list[Event] = []

    def run(self, budget: int | None = None) -> str | None:
        text = super().run(budget)
        self.events.append(("out", text))
        if self.halted:
            self.events.append(("halted", None))
        return text

    def send(self, command: str, budget: int | None = None) -> str | None:
        self.events.append(("cmd", command))
        return super().send(command, budget)

    def fork(self) -> RecordingDroid:
        # same copy as Droid.fork, but the clone records too, into a block
        # pinned at this spot in the parent's stream
        clone = RecordingDroid([])
        clone.mem = self.mem.copy()
        clone.ip, clone.rb, clone.halted = self.ip, self.rb, self.halted
        clone.inputs = list(self.inputs)
        self.events.append(("probe", clone.events))
        return clone


def render(events: list[Event], indent: str = "") -> list[str]:
    lines: list[str] = []
    fenced = False
    for kind, payload in events:
        if kind == "cmd":
            lines.append(f"{indent}> {payload}")
        elif kind == "out":
            if payload is None:
                lines.append(f"{indent}[no reply within the step budget -- fork condemned]")
            else:
                assert isinstance(payload, str)
                for line in payload.strip("\n").splitlines():
                    lines.append(f"{indent}{line}" if line else indent.rstrip())
        elif kind == "halted":
            lines.append(f"{indent}[machine halted]")
        elif kind == "probe":
            assert isinstance(payload, list)
            lines.append(f"{indent}    ---- probe fork " + "-" * 44)
            lines.extend(render(payload, indent + "    "))
            lines.append(f"{indent}    ---- fork discarded " + "-" * 40)
        elif kind == "phase":
            if fenced:
                lines.append("```")
                lines.append("")
            lines.append(f"## {payload}")
            lines.append("")
            lines.append("```text")
            fenced = True
    return lines


def main() -> None:
    program = parse_input((ROOT / "inputs" / "day25.txt").read_text())
    droid = RecordingDroid(program)

    droid.events.append(("phase", "PLACEHOLDER-EXPLORE"))
    survey = explore(droid)
    crack_marker = len(droid.events)
    droid.events.append(("phase", "PLACEHOLDER-CRACK"))
    speech = crack_floor(droid, survey)
    match = PASSWORD.search(speech)
    assert match is not None

    commands = sum(1 for k, _ in droid.events if k == "cmd")
    probes = [p for k, p in droid.events if k == "probe"]
    trials = sum(1 for k, c in droid.events[crack_marker:] if k == "cmd" and c == survey.test_door)
    chars = sum(len(t) for k, t in droid.events if k == "out" and isinstance(t, str))
    droid.events[0] = (
        "phase",
        (
            f"Exploration -- {len(survey.rooms)} rooms, {len(probes)} probe forks, "
            f"{len(survey.inventory)} items pocketed"
        ),
    )
    droid.events[crack_marker] = (
        "phase",
        f"Cracking the floor -- the walk to the checkpoint, then {trials} Gray-code trials",
    )

    intro = [
        "# Day 25 — the session transcript",
        "",
        f"> Every command the solver types ({commands} on the real droid) and every",
        f"> reply the game prints ({chars:,} characters), exactly as played by",
        "> [python/day25.py](../../python/day25.py)'s `explore` + `crack_floor`.",
        "> Indented blocks are the item-safety probes: each runs `take` in a",
        "> FORKED copy of the machine, and the fork -- not the real droid -- is",
        "> what melts, hangs, or gets launched into space. Generated by",
        "> [python/day25_transcript.py](../../python/day25_transcript.py); not",
        "> committed -- the room text is the puzzle input's own payload (see",
        "> `.gitignore`).",
        ">",
        f"> The final line's password: **{match.group(1)}**.",
        "",
    ]
    body = render(droid.events)
    body.append("```")
    OUT.write_text("\n".join(intro + body) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({commands} commands, {chars:,} chars of output)")


if __name__ == "__main__":
    main()
