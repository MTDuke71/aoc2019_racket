"""Day 17 -- Set and Forget.

The day splits cleanly in two, and the tests follow the split.

*Everything downstream of `camera_view` takes a string*, so the puzzle's own
worked examples -- an ASCII picture for Part 1, a second picture plus the route
it induces for Part 2 -- are reachable from a test with no Intcode program in
sight. That is the same separation [Day 15](../day15.py)'s `MazeDroid` bought,
arrived at from the other direction: there the VM was faked, here it is simply
not needed.

*Where the VM genuinely is the thing under test* -- `camera_view` decoding an
output stream, `run_robot` poking address 0 -- the tests hand it **real Intcode
programs**, hand-assembled and a few cells long, rather than a mock. `[104, c,
104, c, ..., 99]` is a legal program that outputs a chosen string, and
`[1, 9, 10, 11, 4, 11, 99, ...]` is one whose *first instruction changes opcode*
when address 0 is poked -- which is exactly the trick the real puzzle program
plays, so the test exercises the mechanism rather than imitating it.

Three claims are pinned rather than asserted in prose:

  * the greedy "straight through crossings" walk covers **every** scaffold cell
    on the real input (`test_greedy_walk_covers_every_cell`) -- a property of
    the file, not a promise of the statement;
  * `compress` produces a factorisation that **round-trips** to the original
    route and whose every line fits the 20-character limit
    (`test_real_route_factorisation`), so a wrong-but-plausible grammar cannot
    slip through;
  * `run_robot`'s `mem[0] = 2` really reaches the machine and does **not**
    mutate the caller's program (`test_wake_poke_reaches_the_machine`).
"""

from __future__ import annotations

import day17
import day17_disasm
import pytest
from day17 import (
    MEMORY_LIMIT,
    alignment_sum,
    camera_view,
    compress,
    covered,
    expand,
    find_robot,
    intersections,
    parse_input,
    path,
    run_robot,
    scaffold_points,
)
from intcode import VM

LOCKED = (3888, 927809)  # verified on adventofcode.com


def echo_program(text: str) -> list[int]:
    """A real Intcode program that prints `text` and halts.

    `104` is opcode 4 in immediate mode, so `104, c` outputs the literal `c`.
    Assembling one of these means `camera_view` is tested against the actual VM
    -- the decode, the halt condition and the output protocol all included --
    instead of against a stand-in that could drift from it.
    """
    return [code for ch in text for code in (104, ord(ch))] + [99]


# ------------------------------------------------------ part 1: the picture

# The statement's Part One camera feed. Intersections are marked O in the
# puzzle text at (2,2), (2,4), (6,4) and (10,4), summing to 4+8+24+40 = 76.
EXAMPLE1 = (
    "..#..........\n..#..........\n#######...###\n#.#...#...#.#\n#############\n..#...#...#..\n..#####...^.."
)

# The statement's Part Two camera feed, whose greedy route the puzzle spells out.
EXAMPLE2 = (
    "#######...#####\n"
    "#.....#...#...#\n"
    "#.....#...#...#\n"
    "......#...#...#\n"
    "......#...###.#\n"
    "......#.....#.#\n"
    "^########...#.#\n"
    "......#.#...#.#\n"
    "......#########\n"
    "........#...#..\n"
    "....#########..\n"
    "....#...#......\n"
    "....#...#......\n"
    "....#...#......\n"
    "....#####......"
)

EXAMPLE2_ROUTE = "R,8,R,8,R,4,R,4,R,8,L,6,L,2,R,4,R,4,R,8,R,8,R,8,L,6,L,2"


def test_example_intersections():
    assert sorted(intersections(EXAMPLE1)) == [(2, 2), (2, 4), (6, 4), (10, 4)]


def test_example_alignment_sum():
    """4 + 8 + 24 + 40 = 76, the four products the statement works out."""
    assert [x * y for x, y in sorted(intersections(EXAMPLE1))] == [4, 8, 24, 40]
    assert alignment_sum(EXAMPLE1) == 76


def test_robot_cell_counts_as_scaffold():
    """`^v<>` is drawn ON a scaffold, so it takes part in the neighbour test."""
    assert (10, 6) in scaffold_points(EXAMPLE1)  # the `^`
    plus = "..#..\n..#..\n#####\n..#..\n..#.."
    assert intersections(plus) == [(2, 2)]
    assert intersections(plus.replace("#####", "##<##")) == [(2, 2)]


def test_tumbling_robot_is_not_scaffold():
    """`X` means it already fell off -- not a cell anything may stand on."""
    assert scaffold_points("X..\n...") == set()
    with pytest.raises(ValueError, match="tumbling"):
        find_robot("X..\n...")


def test_no_robot_is_an_error():
    with pytest.raises(ValueError, match="no robot"):
        find_robot("###\n###")


@pytest.mark.parametrize("view", [EXAMPLE1, EXAMPLE2])
def test_camera_view_decodes_a_real_intcode_program(view):
    """`camera_view` against a hand-assembled program that prints the picture."""
    assert camera_view(echo_program(view)) == view


def test_camera_view_rejects_non_ascii():
    """A value above 127 is the peripheral saying something that is not text.

    Letting it through as `chr()` would corrupt the grid silently -- and Part 2
    proves the concern is real, since the dust report arrives exactly that way.
    """
    with pytest.raises(ValueError, match="non-ASCII"):
        camera_view([104, 999, 99])


# --------------------------------------------------------- part 2: the walk


def test_example_route_matches_the_statement():
    """The greedy walk reproduces the route the puzzle spells out, exactly."""
    assert ",".join(path(EXAMPLE2)) == EXAMPLE2_ROUTE


def test_greedy_walk_covers_every_example_cell():
    assert covered(EXAMPLE2, path(EXAMPLE2)) == scaffold_points(EXAMPLE2)


def test_a_robot_facing_along_the_scaffold_cannot_start():
    """The movement language has no way to say "go forward" before a turn.

    Every move is `turn, distance`, so a route must begin with L or R. Part
    One's picture has the robot facing straight up its own scaffold with
    nothing to either side, so no legal route exists from it -- and `path`
    returns an empty route rather than inventing a leading straight move.
    Part Two's picture faces the robot across the scaffold, which is why its
    route can begin `R,8`.

    `part2` catches this case through its coverage check, which is the point of
    that check being there at all.
    """
    assert path(EXAMPLE1) == []
    assert covered(EXAMPLE1, []) != scaffold_points(EXAMPLE1)


def test_walk_goes_straight_through_crossings():
    """A crossing is never a decision point: the route turns 0 times crossing it.

    A plus with the robot at the bottom of the vertical arm, facing ACROSS it
    so that a legal route exists at all (see the test above). The horizontal
    arm is scaffold too, so a walk that treated the crossing as a junction
    could veer off there; the straight-through rule instead drives the full
    height of the arm as ONE move.
    """
    plus = "..#..\n..#..\n#####\n..#..\n..>.."
    assert ",".join(path(plus)) == "L,4"
    assert (2, 2) in covered(plus, path(plus))  # it really did cross


# -------------------------------------------------- part 2: the compression


def test_example_factorisation_round_trips():
    tokens = path(EXAMPLE2)
    main, functions = compress(tokens)
    assert expand(main, functions) == tokens
    assert len(main) <= MEMORY_LIMIT
    assert all(len(body) <= MEMORY_LIMIT for body in functions)


def test_the_statements_own_factorisation_is_valid():
    """`A,B,C,B,A,C` with the statement's three bodies expands to the route.

    `compress` finds a *different* legal grammar for this example (the puzzle
    says "one approach is", not "the approach is"), so the test checks the
    statement's answer against `expand` rather than demanding `compress`
    reproduce it. What must hold is that both derive the same string.
    """
    main = "A,B,C,B,A,C"
    functions = ["R,8,R,8", "R,4,R,4,R,8", "L,6,L,2"]
    assert ",".join(expand(main, functions)) == EXAMPLE2_ROUTE
    assert len(main) <= MEMORY_LIMIT
    assert all(len(body) <= MEMORY_LIMIT for body in functions)


def test_compress_respects_a_tighter_limit():
    """The limit is a real constraint, not decoration: shrink it and lines shrink."""
    tokens = path(EXAMPLE2)
    main, functions = compress(tokens, limit=12)
    assert expand(main, functions) == tokens
    assert len(main) <= 12
    assert all(len(body) <= 12 for body in functions)


def test_compress_reports_failure_instead_of_guessing():
    """A route with no repetition cannot be covered by three functions.

    `R,100,R,101,...,R,140`: every distance is distinct, so no body can ever be
    reused, and three bodies of at most 20 characters cover at most ~60
    characters of a 245-character route.

    The first draft of this test used `R,1,...,R,12` and FAILED -- that route
    is short enough that three 20-character functions really do cover it. The
    bound that matters is total *characters*, not "no repetition".
    """
    tokens = [token for n in range(100, 141) for token in ("R", str(n))]
    assert len(",".join(tokens)) > 3 * MEMORY_LIMIT
    assert compress(tokens) is None


def test_two_function_budget_is_honoured():
    """`names` bounds the number of non-terminals, and the bound bites."""
    tokens = ["R", "8", "L", "4", "R", "8", "L", "4"]
    assert compress(tokens, names="A") is not None  # one repeated body suffices

    # 24 characters and not a repetition of any shorter body, so a single
    # 20-character function cannot express it.
    aperiodic = ["R", "10", "L", "12", "R", "14", "L", "16", "R", "18"]
    assert len(",".join(aperiodic)) > MEMORY_LIMIT
    assert compress(aperiodic, names="A") is None


# ------------------------------------------------------- part 2: the poke


def poke_probe() -> list[int]:
    """A program whose FIRST instruction changes opcode when address 0 is poked.

    Layout: `mem[0]` is the opcode with operands at 9, 10 and destination 11,
    then `4, 11` outputs the result and `99` halts. Unpoked (`mem[0] == 1`) it
    adds: 200 + 3 = 203. Poked to 2 it multiplies: 200 * 3 = 600. Both are
    above 127, so `run_robot` reads either as a dust report and the two cases
    are distinguishable.

    This is the real puzzle program's own trick -- its first cell is `1` and
    the wake-up poke turns that add into a multiply.
    """
    return [1, 9, 10, 11, 4, 11, 99, 0, 0, 200, 3, 0]


def test_wake_poke_reaches_the_machine():
    assert run_robot(poke_probe(), "A", ["R,8"]) == 600  # 200*3, not 200+3


def test_wake_poke_does_not_mutate_the_caller_s_program():
    """The poke goes into the VM's memory, so the parsed input stays reusable.

    `solve` runs the camera and then the robot off the same list; if `run_robot`
    wrote through, the second run would start from a woken program.
    """
    program = poke_probe()
    before = list(program)
    run_robot(program, "A", ["R,8"])
    assert program == before


def test_dust_is_identified_structurally_not_positionally():
    """Prompt characters are ignored; the >127 value is the answer.

    The robot narrates in ASCII before reporting, so "the last output" and "the
    only large output" are different rules. Only the second one survives the
    video feed being switched on.
    """
    program = [104, ord("A"), 104, ord(":"), 104, 10, 104, 927809, 99]
    assert run_robot(program, "A", ["R,8"]) == 927809


def test_no_dust_report_is_an_error():
    with pytest.raises(RuntimeError, match="without reporting any dust"):
        run_robot(echo_program("Function:\n"), "A", ["R,8"])


# ------------------------------------------------------------- the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it."""
    assert parse_input("1,2,3\r\n") == [1, 2, 3]
    assert parse_input("1,2,3\n") == parse_input("1,2,3\r\n")


def test_crlf_real_input(real_input):
    text = real_input(17)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_view_shape(real_input):
    view = camera_view(parse_input(real_input(17)))
    rows = view.strip("\n").splitlines()
    assert len(rows) == 35
    assert {len(row) for row in rows} == {55}, "the feed is rectangular"
    assert len(scaffold_points(view)) == 319
    assert len(intersections(view)) == 14


def test_greedy_walk_covers_every_cell(real_input):
    """The straight-through walk visits all 319 scaffold cells on this input.

    Nothing in the statement promises a greedy route is complete -- a scaffold
    shaped as a tree rather than a self-crossing path would defeat it -- so
    `part2` checks this at run time and this test pins the input's own answer.
    """
    view = camera_view(parse_input(real_input(17)))
    assert covered(view, path(view)) == scaffold_points(view)


def test_real_route_factorisation(real_input):
    """The shipped grammar round-trips and fits in the robot's memory."""
    view = camera_view(parse_input(real_input(17)))
    tokens = path(view)
    assert len(tokens) == 68  # 34 turn/distance pairs

    main, functions = compress(tokens)
    assert expand(main, functions) == tokens
    assert len(functions) == 3
    assert len(main) <= MEMORY_LIMIT
    assert all(len(body) <= MEMORY_LIMIT for body in functions)
    assert set(main.split(",")) == {"A", "B", "C"}


def test_uncompressed_route_would_not_fit(real_input):
    """The memory limit is why Part 2 is a puzzle and not a transcription."""
    view = camera_view(parse_input(real_input(17)))
    assert len(",".join(path(view))) == 162
    assert 162 > MEMORY_LIMIT


def test_solve_agrees_with_the_parts(real_input):
    program = parse_input(real_input(17))
    assert day17.solve(program) == (day17.part1(program), day17.part2(program))


def test_real_input(check_locked):
    check_locked(17, LOCKED)


def test_every_intersection_is_crossed_exactly_twice(real_input):
    """The route's revisit count equals the intersection count, exactly.

    A self-crossing path visits a crossing once on each of the two strands
    through it. So `1 + sum(distances)` -- cells stepped on, with multiplicity
    -- should exceed the number of distinct cells by exactly the number of
    crossings, and it does: 333 - 319 = 14. Nothing else on the route is
    driven over twice, which is what makes the greedy walk both complete and
    non-wasteful.
    """
    view = camera_view(parse_input(real_input(17)))
    tokens = path(view)
    stepped = 1 + sum(int(d) for d in tokens[1::2])
    assert stepped == 333
    assert stepped - len(scaffold_points(view)) == len(intersections(view)) == 14


def test_route_alphabet_is_tiny(real_input):
    """Only three distinct distances appear in the whole 34-move route.

    6, 10 and 12 -- which is *why* three 20-character functions suffice. A
    route drawn from a wide alphabet of distances would not factor at all
    (`test_compress_reports_failure_instead_of_guessing` builds exactly that).
    """
    view = camera_view(parse_input(real_input(17)))
    tokens = path(view)
    assert sorted({int(d) for d in tokens[1::2]}) == [6, 10, 12]
    assert set(tokens[::2]) == {"L", "R"}


def test_the_factorisation_is_unique(real_input):
    """This route has EXACTLY ONE legal (main, A, B, C) factorisation.

    Counted by exhaustive search below -- the same recursion `compress` runs,
    but continuing instead of returning at the first hit. So the backtracker's
    search order cannot matter on this input, and the grammar in the guide is
    *the* grammar rather than *a* grammar. That is a property of the puzzle
    input, not of the algorithm.
    """
    view = camera_view(parse_input(real_input(17)))
    tokens = path(view)

    found = []

    def count(i, functions, main):
        if i == len(tokens):
            if len(",".join(main)) <= MEMORY_LIMIT:
                found.append((",".join(main), [",".join(b) for b in functions]))
            return
        if len(",".join([*main, "A"])) > MEMORY_LIMIT:
            return
        for name, body in zip("ABC", functions):
            if tokens[i : i + len(body)] == body:
                count(i + len(body), functions, [*main, name])
        if len(functions) < 3:
            for length in range(1, len(tokens) - i + 1):
                body = tokens[i : i + length]
                if len(",".join(body)) > MEMORY_LIMIT:
                    break
                count(i + length, [*functions, body], [*main, "ABC"[len(functions)]])

    count(0, [], [])
    assert len(found) == 1
    assert found[0] == compress(tokens)


# ------------------------------------------------- the disassembly (day17_disasm)


def test_static_descent_is_complete(real_input):
    """Every code cell is reached, and what is left over is exactly the data.

    933 code cells + 548 data cells = 1481. The data is the string table
    (330..578, 249 cells) and the run-length table (1182..1480, 299 cells);
    nothing else in the file is unaccounted for. Descent is only complete
    because it is seeded with RETURN addresses as well as call targets -- the
    return is an indirect jump through the frame, and address 58 (everything
    after the first call) is reachable no other way.
    """
    mem = parse_input(real_input(17))
    listing = day17_disasm.descend(
        mem,
        [
            0,
            *(t for t, _ in day17_disasm.call_sites(mem).values()),
            *(r for _, r in day17_disasm.call_sites(mem).values()),
        ],
    )
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    assert len(covered) == 933
    data = set(range(330, 579)) | set(range(1182, 1481))
    assert covered | data == set(range(len(mem)))
    assert not (covered & data)


def test_four_subroutines(real_input):
    """The program has a calling convention, which Day 15's did not."""
    mem = parse_input(real_input(17))
    calls = day17_disasm.call_sites(mem)
    assert {t for t, _ in calls.values()} == {579, 622, 786, 979}
    assert len(calls) == 20
    # `interpret` is called twice: once for the main routine, once (from inside
    # itself, at 767) for a movement function. Two levels, exactly as the
    # statement's "functions may not call other functions" describes.
    assert sorted(a for a, (t, _) in calls.items() if t == 622) == [306, 767]


def test_the_scaffold_is_run_length_encoded_data(real_input):
    """299 runs expand to exactly 55*35 bits -- the map is stored, not drawn."""
    mem = parse_input(real_input(17))
    width, height = mem[day17_disasm.WIDTH_CMP], mem[day17_disasm.HEIGHT_CMP]
    assert (width, height) == (55, 35)
    runs = mem[mem[day17_disasm.RLE_FIRST] :]
    assert len(runs) == 299
    assert sum(runs) == width * height == 1925
    assert len(day17_disasm.decode_rle(mem)) == 1925


def test_view_recovered_without_running_the_vm(real_input):
    """The camera picture comes out of the file byte for byte.

    Same result as [Day 15](day15_disassembly.md), by the same route: the world
    is compiled into the program rather than computed by it.
    """
    mem = parse_input(real_input(17))
    assert day17_disasm.recover_view(mem) == camera_view(mem)


def test_robot_start_is_a_literal(real_input):
    """(26, 16) facing '^' -- three variables the renderer compares against."""
    mem = parse_input(real_input(17))
    assert (mem[576], mem[577], mem[578]) == (26, 16, 0)
    assert "".join(chr(mem[558 + d]) for d in range(4)) == "^>v<"
    assert mem[562:566] == [0, 1, 0, -1]  # dx
    assert mem[566:570] == [-1, 0, 1, 0]  # dy
    assert find_robot(camera_view(mem)) == ((26, 16), "^")


def test_both_answers_come_off_the_disk(real_input):
    """Part 1 AND Part 2 without ever starting the machine.

    Part 1 from the recovered map; Part 2 by replaying the vacuum accumulator
    over our own route. Day 15 managed this for both answers too, but there
    both were literals; here Part 2 is a computation the disassembly has to
    reproduce exactly, down to the bitmap ADDRESS being one of the addends.
    """
    mem = parse_input(real_input(17))
    view = day17_disasm.recover_view(mem)
    assert alignment_sum(view) == 3888
    assert day17_disasm.recover_dust(mem, view, path(view)) == 927809


def test_the_poke_flips_one_cell(real_input):
    """`mem[0] = 2` turns an add into a multiply, and that is its whole effect.

    Instruction 0 is `add [330] [331] [332]` with mem[330..332] = [0, 1, 1]:
    unpoked it stores 0 + 1 = 1, poked it stores 0 * 1 = 0. The test at 58 is
    `jz [332] #62`, so 1 falls through to the `hlt` at 61 (print the map and
    stop) and 0 jumps into the robot. One cell, one bit of meaning.
    """
    mem = parse_input(real_input(17))
    assert mem[0:4] == [1, 330, 331, 332]
    assert mem[330:333] == [0, 1, 1]
    assert mem[330] + mem[331] == 1  # cameras only
    assert mem[330] * mem[331] == 0  # wake the robot
    assert mem[58:62] == [1006, 332, 62, 99]


def test_the_stack_starts_just_past_the_bitmap(real_input):
    """`arb #3406` at address 4, and 1481 + 55*35 == 3406 exactly."""
    mem = parse_input(real_input(17))
    assert mem[4] == 109
    bitmap_base = mem[day17_disasm.BITMAP_BASE]
    assert bitmap_base == len(mem) == 1481
    assert mem[5] == bitmap_base + 55 * 35 == 3406


def test_the_parsed_program_reuses_the_rle_cells(real_input):
    """The run-length table's own memory becomes the movement-program store.

    Consumed once at boot, then recycled: the main routine's length lands at
    1182 and the three function buffers at 1193, 1204 and 1215 -- an 11-cell
    stride (one length plus ten slots, ten being the most tokens a
    20-character line can hold).

    The internal encoding is a bytecode: call A/B/C is -1/-2/-3, turn right is
    -4, turn left is -5, and a positive value is a distance. The negative
    numbering is not cosmetic -- dispatch is `1182 + 11 * -opcode`, so the
    opcode IS the index arithmetic.
    """
    mem = parse_input(real_input(17))
    view = camera_view(mem)
    main, functions = compress(path(view))

    vm = VM(mem)
    vm.mem[0] = 2
    vm.inputs.extend(ord(ch) for ch in "\n".join([main, *functions, "n"]) + "\n")
    while vm.step() != "halted":
        pass

    encode = {"A": -1, "B": -2, "C": -3, "R": -4, "L": -5}
    assert vm.mem[1182] == len(main.split(","))
    assert [vm.mem[1183 + i] for i in range(10)][: len(main.split(","))] == [
        encode[name] for name in main.split(",")
    ]
    for offset, body in zip((1193, 1204, 1215), functions):
        tokens = body.split(",")
        assert vm.mem[offset] == len(tokens)
        want = [encode.get(t, 0) or int(t) for t in tokens]
        assert [vm.mem[offset + 1 + i] for i in range(len(tokens))] == want
        assert 1182 + 11 * -encode[chr(ord("A") + (offset - 1193) // 11)] == offset


def test_every_self_modification_is_an_operand_patch(real_input):
    """20 patched stores, and not one of them touches an opcode or a jump target.

    Intcode has no indexed addressing, so an array access must rewrite the
    operand it is about to execute -- the bootstrap's two moving pointers, the
    renderer's bitmap fetches, the interpreter's instruction fetch, the
    parser's stores. All of them address DATA. Control flow is entirely static,
    which is precisely why `test_static_descent_is_complete` can hold.
    """
    mem = parse_input(real_input(17))
    calls = day17_disasm.call_sites(mem)
    listing = day17_disasm.descend(
        mem,
        [0, *(t for t, _ in calls.values()), *(r for _, r in calls.values())],
    )
    patches = day17_disasm.operand_patches(mem, listing)
    assert len(patches) == 20

    starts = set(listing)
    for _store, dest, owner in patches:
        assert dest not in starts, "a patch landed on an opcode cell"
        assert owner < dest < owner + listing[owner][1]


def test_the_parser_not_the_interpreter_forbids_nesting(real_input):
    """ "Functions may not call other functions" is a front-end rule.

    The interpreter's dispatch is uniform -- any negative opcode that is not
    -4 or -5 is treated as a call, at any depth, with no depth counter. Feed
    the machine a function body containing `A` and it is the PARSER that
    objects, by name.
    """
    mem = parse_input(real_input(17))
    vm = VM(mem)
    vm.mem[0] = 2
    vm.inputs.extend(ord(ch) for ch in "A\nA\nR,8\nR,8\nn\n")
    out = []
    while True:
        result = vm.step()
        if result == "halted":
            break
        if isinstance(result, tuple):
            out.append(result[1])
    text = "".join(chr(v) for v in out if v < 128)
    assert "Expected R, L, or distance but got: A" in text


def test_full_listing_accounts_for_every_cell(real_input):
    """The --full listing is continuous: all 1481 cells, each exactly once.

    `full_listing` raises if any cell goes unlisted (or if the string-table
    walk derails), so calling it IS the coverage assertion; the spot checks
    below pin the rendering of one line from each kind of region.
    """
    text = day17_disasm.full_listing(parse_input(real_input(17)))
    assert "0000  1 330 331 332          add  [330]=mode.a [331]=mode.b [332]=mode" in text
    assert "interpret:" in text
    assert '.str 6 "Main:' in text  # a length-prefixed string
    assert "; vacuumed" in text and "; dust" in text  # the embedded counters
    assert "; return" in text
    assert text.count("call draw") == 6
