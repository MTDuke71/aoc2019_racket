r"""Day 23 -- Category Six.

The statement ships no worked example at all -- there is nothing to run
except fifty copies of the real NIC. So, as on Days 17, 19 and 21, the suite
tests the LOGIC without the puzzle input: the scheduler is exercised with
tiny hand-assembled Intcode NICs (each listed opcode by opcode below), which
lets every scheduling rule -- delivery, framing, boot, idle, the NAT --
be provoked on purpose instead of observed by accident.

What is pinned, per the repo rule that identities live as tests, not prose:

  * Round-robin order and packet framing: the first event on the broadcast
    network is address 0's packet, and a relayed packet crosses the network
    intact (dest, X, Y all preserved).
  * The boot round is NOT an idle round: a NIC that polls once before its
    first send (BOOTSLOW) still gets its packet out. A scheduler that
    tested idleness in round 1 would declare this network dead -- the real
    input's round 1 is exactly such a spurious quiet round.
  * "Twice in a row" means CONSECUTIVE: CONVERGE's wake Ys climb
    25, 26, ..., 30 and part 2 fires only on the second 30, not on the
    first wake.
  * A network that idles with an empty NAT -- or halts outright -- raises
    instead of spinning forever.
  * On the real input, the wake Ys are STRICTLY DECREASING until the final
    repeated pair -- the network relaxes monotonically to a fixed point --
    so "first Y delivered twice in a row" and "first Y ever repeated"
    happen to agree here, and the first wake replays the very first packet
    that reached 255 (part 1's answer). Every one of the 151 packets that
    reach 255 carries the same X.

And from the disassembly (day23_disasm; see day23_disassembly.md): the
image is a 50-node DATAFLOW GRAPH -- operator census, exact slot-routing
arithmetic, the seven decoy nodes and the six-node y-cone; the whole
network collapsing to y' = ((y - a)^3 + 10^8(7y + 3a)) // 10^9 with a =
part 2's answer (the input is generated from its own solution, and
F'(a) = 0.7 is why the live deltas shrink by ~0.7); the floor-division
fixed-point ladder 11085..11088 with the seed descending onto the top
rung; the divide subroutine pinned by calling it in vitro on the live
machine (floor for x >= 0, -1 for x < 0); the boot dispatch as the year's
first self-modified jump target; and both answers recovered off the disk
with the VM never started, the static iterates matching the live NAT's
deliveries element for element.
"""

from __future__ import annotations

from itertools import pairwise
from math import isqrt

import day23_disasm
import pytest
from day23 import parse_input, part1, part2, run_network, solve

LOCKED = (18982, 11088)  # verified on adventofcode.com

# --------------------------------------------------------------- the fixtures
#
# Each fixture is a real Intcode program, hand-assembled; addresses in the
# comments. All of them keep polling forever after their work is done --
# a NIC that halts stops absorbing -1s and the network can never idle
# normally again.

# Read the address, send (255, address, 77), then poll forever.
#   0: in [20]          4: out [20]         8: in [21]
#   2: out #255         6: out #77         10: jnz #1 #8
BROADCAST = [3, 20, 104, 255, 4, 20, 104, 77, 3, 21, 1105, 1, 8]

# Address 0 seeds one packet (1, 10, 20); every NIC then relays whatever it
# receives to 255 unchanged. Pins that a packet crosses the network intact.
#   0: in [50]              11: in [51]              20: in [53]
#   2: jnz [50] #11         13: eq #-1 [51] [52]     22: out #255
#   5: out #1               17: jnz [52] #11         24: out [51]
#   7: out #10                                       26: out [53]
#   9: out #20                                       28: jnz #1 #11
RELAY = [3, 50, 1005, 50, 11, 104, 1, 104, 10, 104, 20, 3, 51, 108, -1, 51, 52, 1005, 52, 11, 3, 53, 104, 255, 4, 51, 4, 53, 1105, 1, 11]  # fmt: skip

# Address 0 seeds (255, 0, 25); on every wake-up it sends the Y back to 255
# incremented -- but only while Y < 30. The wake Ys climb 25, 26, ..., 30
# and then repeat: a miniature of the real input's relaxation to a fixed
# point (except climbing, where the real network descends).
#   0: in [60]              11: in [61]              26: add [63] [64] [63]
#   2: jnz [60] #39         13: eq #-1 [61] [62]     30: out #255
#   5: out #255             17: jnz [62] #11         32: out #0
#   7: out #0               20: in [63]              34: out [63]
#   9: out #25              22: lt [63] #30 [64]     36: jnz #1 #11
#  39: in [61]   (non-zero addresses only listen)
#  41: jnz #1 #39
CONVERGE = [3, 60, 1005, 60, 39, 104, 255, 104, 0, 104, 25, 3, 61, 108, -1, 61, 62, 1005, 62, 11, 3, 63, 1007, 63, 30, 64, 1, 63, 64, 63, 104, 255, 104, 0, 4, 63, 1105, 1, 11, 3, 61, 1105, 1, 39]  # fmt: skip

# Reads the address, polls ONCE (absorbing a -1), and only then sends
# (255, address, 42). Round 1 of this network is quiet -- every NIC parked
# at a starved read having produced nothing -- yet the network is not idle:
# the sends are still coming. The `rounds >= 2` guard exists for this NIC.
#   0: in [50]          4: out #255         8: out #42
#   2: in [51]          6: out [50]        10: in [51]
#                                          12: jnz #1 #10
BOOTSLOW = [3, 50, 3, 51, 104, 255, 4, 50, 104, 42, 3, 51, 1105, 1, 10]

# Polls forever, never sends: the network idles with an empty NAT.
#   0: in [10]          2: jnz #1 #0
DEADLOCK = [3, 10, 1105, 1, 0]


def events(program, size, n):
    """The first n events of a network -- run_network is endless by design."""
    out = []
    for event in run_network(program, size):
        out.append(event)
        if len(out) == n:
            return out


# ------------------------------------------------- scheduling and framing


def test_round_robin_order():
    """Address 0's slice runs first, so its packet reaches the NAT first."""
    assert events(BROADCAST, 5, 1) == [("nat", 0, 77)]


def test_broadcast_answers():
    """All five NICs shout at 255; the NAT keeps only the LAST packet, so
    every wake replays address 4's -- and the second wake repeats it."""
    assert part1(BROADCAST, size=5) == 77
    assert events(BROADCAST, 5, 7)[4:] == [("nat", 4, 77), ("wake", 4, 77), ("wake", 4, 77)]
    assert part2(BROADCAST, size=5) == 77


def test_relayed_packet_arrives_intact():
    """(1, 10, 20) sent by NIC 0 is received by NIC 1 and forwarded to 255
    with X and Y untouched -- delivery, queueing and triple framing all in
    one packet. The idle network then cycles wake -> relay -> wake."""
    assert events(RELAY, 2, 4) == [("nat", 10, 20), ("wake", 10, 20), ("nat", 10, 20), ("wake", 10, 20)]
    assert part1(RELAY, size=2) == 20
    assert part2(RELAY, size=2) == 20


# --------------------------------------------------------------- boot vs idle


def test_boot_quiet_round_is_not_idle():
    """Round 1 of this network moves no packet and fills no queue, yet
    declaring it idle would be wrong: every NIC is one -1 away from its
    first send. The scheduler must wait out the boot round."""
    assert part1(BOOTSLOW, size=3) == 42
    assert events(BOOTSLOW, 3, 3) == [("nat", 0, 42), ("nat", 1, 42), ("nat", 2, 42)]


def test_idle_with_empty_nat_raises():
    with pytest.raises(RuntimeError, match="NAT"):
        part1(DEADLOCK, size=3)


def test_halted_network_raises():
    """A NIC that halts stops absorbing -1s; a network of them can only
    deadlock, and the scheduler says so rather than spinning."""
    with pytest.raises(RuntimeError, match="deadlock"):
        part1([99], size=3)


# ------------------------------------------------------------------- the NAT


def test_twice_in_a_row_means_consecutive():
    """CONVERGE's wake Ys are 25, 26, 27, 28, 29, 30, 30 -- six DIFFERENT
    values before the repeat. Part 2 must not fire until the plateau."""
    wakes = [y for kind, _x, y in events(CONVERGE, 3, 15) if kind == "wake"]
    assert wakes[:7] == [25, 26, 27, 28, 29, 30, 30]
    assert part1(CONVERGE, size=3) == 25
    assert part2(CONVERGE, size=3) == 30


def test_solve_answers_both_from_one_run():
    assert solve(CONVERGE) == (25, 30)


# ------------------------------------------------------------------ the input


def test_real_traffic_shape(real_input):
    """One full run to part 2's stopping point, with the whole event stream
    kept: the wake sequence descends STRICTLY until the final repeated
    pair (a monotone relaxation -- so consecutive-repeat and ever-repeated
    coincide on this input), the first wake replays the first packet that
    reached 255, all 151 packets to 255 share one X value, and `solve`
    agrees with the stream it is summarizing."""
    program = parse_input(real_input(23))
    nat_events, wake_ys = [], []
    for kind, x, y in run_network(program):
        if kind == "nat":
            nat_events.append((x, y))
        else:
            wake_ys.append(y)
            if len(wake_ys) >= 2 and wake_ys[-1] == wake_ys[-2]:
                break

    assert all(a > b for a, b in pairwise(wake_ys[:-1]))  # strict descent...
    assert wake_ys[-1] == wake_ys[-2]  # ...until the fixed point
    assert wake_ys[0] == nat_events[0][1]  # first wake replays part 1's packet
    assert len(wake_ys) == 26
    assert len(nat_events) == 151
    assert len({x for x, _y in nat_events}) == 1  # one NIC owns the 255 traffic
    assert solve(parse_input(real_input(23))) == (nat_events[0][1], wake_ys[-1])
    # The disassembly's static model reproduces the NAT's whole life, element
    # for element: the wake sequence IS the iteration of the recovered map.
    assert day23_disasm.wake_sequence(program) == wake_ys
    assert day23_disasm.static_answers(program) == (nat_events[0][1], wake_ys[-1])


# ---------------------------------------- the disassembly (day23_disasm)


def test_node_table_shape(real_input):
    """Fifty stubs, all parsed, none refused: 32 constants/identities, 15
    products, 2 sums, ONE quotient -- and that quotient node is the only
    NIC that ever addresses 255, its X pre-set to node 0's salt so the
    NAT's relay lands in the seed slot. Seven nodes compute into the void."""
    nodes = day23_disasm.recover_nodes(parse_input(real_input(23)))
    assert len(nodes) == 50
    census: dict[str, int] = {}
    for node in nodes.values():
        census[node.op] = census.get(node.op, 0) + 1
    assert census == {"id": 32, "mul": 15, "sum": 2, "div": 1}
    assert sorted(a for a, n in nodes.items() if not n.consumers) == [5, 9, 17, 31, 44, 45, 48]
    assert day23_disasm.y_cone(nodes) == {0, 10, 19, 25, 34, 43}
    nat_talkers = [n for n in nodes.values() if any(d == 255 for d, _ in n.consumers)]
    assert [n.address for n in nat_talkers] == [10]
    assert nat_talkers[0].op == "div"
    (x,) = [x for d, x in nat_talkers[0].consumers if d == 255]
    assert x == nodes[0].salt


def test_routing_is_exact(real_input):
    """The slot-addressing arithmetic is airtight -- every X a multiple of
    its receiver's salt, slot in range, every empty slot fed exactly once,
    every constant slot fed never -- and the 65 consumer entries collapse
    to the 59 distinct (src, dest) edges the live run exhibits."""
    nodes = day23_disasm.recover_nodes(parse_input(real_input(23)))
    day23_disasm.validate(nodes)  # raises on any routing or accounting flaw
    entries = [(n.address, d) for n in nodes.values() for d, _ in n.consumers]
    assert len(entries) == 65
    assert len(set(entries)) == 59


def test_recovered_map_is_built_from_the_answer(real_input):
    """The network collapses to y' = P(y) // 10^9 where P is EXACTLY
    (y - a)^3 + 10^8*(7y + 3a) with a = part 2's answer: the puzzle input
    is generated from its own solution, F(a) = a lands with zero remainder,
    and F'(a) = 7*10^8 / 10^9 = 0.7 -- the measured convergence ratio of
    the live wake sequence is a design parameter."""
    coeffs, divisor, seed = day23_disasm.recover_map(parse_input(real_input(23)))
    a = LOCKED[1]
    assert divisor == 10**9
    assert coeffs == [3 * a * 10**8 - a**3, 3 * a * a + 7 * 10**8, -3 * a, 1]
    assert day23_disasm.closed_form(coeffs, divisor) == a
    assert seed == 20982
    assert day23_disasm.map_value(coeffs, divisor, a) == a
    assert day23_disasm.map_value(coeffs, divisor, seed) == LOCKED[0]


def test_fixed_point_ladder(real_input):
    """Exact arithmetic has ONE integer fixed point (the other two roots of
    (y-a)^3 = 3*10^8 (y-a) sit at a +/- 10^4*sqrt(3), irrational since
    3*10^8 is not a perfect square). Floor division widens it to a ladder
    -- 11085..11088 attracting, two stray rungs out by the repelling roots
    -- and the descent from the seed steps down ONTO THE TOP RUNG: part 2
    from above is 11088, but the same network seeded below would stick at
    11085. The answer is which side the seed is on."""
    coeffs, divisor, _seed = day23_disasm.recover_map(parse_input(real_input(23)))
    a = LOCKED[1]
    assert isqrt(3 * 10**8) ** 2 != 3 * 10**8
    ladder = day23_disasm.floored_fixed_points(coeffs, divisor, a)
    assert ladder == [-6232, -6231, 11085, 11086, 11087, 11088, 28409, 28410]
    assert day23_disasm.map_value(coeffs, divisor, a + 1) == a  # from above: onto the top rung
    assert day23_disasm.map_value(coeffs, divisor, 11084) == 11085  # from below: the bottom


def test_static_answers_locked(real_input):
    """Both answers off the disk, the VM never started."""
    assert day23_disasm.static_answers(parse_input(real_input(23))) == LOCKED


@pytest.mark.parametrize(
    "x, d, want",
    [
        (100, 7, 14),
        (0, 5, 0),
        (9, 10, 0),  # below the divisor: the subtract-off fast path
        (29569, 29569, 1),  # the NAT packet decoding to node 0's slot 1
        (54759, 18253, 3),  # a boot packet decoding to node 25's slot 3
        (2**45 + 12345, 91297, (2**45 + 12345) // 91297),  # 51 rounds of long division
        (-5, 2, -1),  # NOT floor (-3): negatives fall through the fast path...
        (-1000000, 7, -1),  # ...untouched, and the receive loop drops slot -1
    ],
)
def test_divide_in_vitro(real_input, x, d, want):
    """The divide at 436, called ON THE LIVE MACHINE with a hand-planted
    return address and nothing else running: exact floor division for
    x >= 0, and a constant -1 for x < 0 -- which the receive loop's
    `v - 1 < 0 -> drop` check turns into 'negative X is discarded'."""
    program = parse_input(real_input(23))
    assert day23_disasm.call_subroutine(program, day23_disasm.DIVIDE, x, d) == want


def test_self_modifying_stores_all_patch_operands(real_input):
    """22 self-modifying stores, every one an operand patch -- and exactly
    ONE patches a jump TARGET (the boot dispatch at 2 -> [10], the 50-way
    goto), the first patched jump of the year's disassemblies. The other
    21 are array addressing and one jump CONDITION, both data."""
    mem = parse_input(real_input(23))
    listing = day23_disasm.full_descent(mem)
    patches = day23_disasm.operand_patches(mem, listing)
    assert len(patches) == 22
    kinds = [(store, day23_disasm.patch_kind(mem, dest, owner)) for store, dest, owner in patches]
    assert [store for store, kind in kinds if kind == "jump target"] == [2]
    assert sum(1 for _, kind in kinds if kind == "jump condition") == 2  # 185/189 -> the barrier's [194]


def test_full_listing_accounts_for_every_cell(real_input):
    """2,243 cells, every one listed exactly once (full_listing asserts the
    coverage internally); 11 runtime sections plus one section per NIC."""
    mem = parse_input(real_input(23))
    assert len(mem) == 2243
    text = day23_disasm.full_listing(mem)
    assert sum(1 for line in text.splitlines() if line.startswith("## ")) == 11 + 50
    assert sum(1 for line in text.splitlines() if line.startswith("## ") and "NIC " in line) == 50


# ------------------------------------------------------------------- CRLF


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it."""
    assert parse_input("104,255,99\r\n") == [104, 255, 99]


def test_crlf_real_input(real_input):
    text = real_input(23)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_input(check_locked):
    check_locked(23, LOCKED)
