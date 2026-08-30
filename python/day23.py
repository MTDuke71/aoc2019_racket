"""AoC 2019 Day 23 -- Category Six.

The Intcode machine is unchanged (frozen at Day 9; see python/intcode.py).
The peripheral this time is a NETWORK: fifty copies of the same NIC program,
each booted with its address (0..49), exchanging (dest, X, Y) packet triples
over opcodes 3 and 4. The puzzle is not the VM and not the packets -- it is
the SCHEDULER. Both I/O directions are declared non-blocking (an input with
an empty queue reads -1), so the day is writing a cooperative round-robin
event loop over fifty coroutines, and part 2's NAT turns it into the classic
DISTRIBUTED TERMINATION DETECTION problem: decide, from outside, that fifty
communicating processes have collectively gone quiet.

The scheduling quantum here is "run until starved": each VM's slice steps
until it asks for input the queue cannot answer, at which point it is fed one
-1 and the next VM runs. That makes every slice boundary a starved read --
after any full round, all fifty VMs are parked at an input instruction with
exactly one pending -1. Which yields the idle test run_network leans on:

  A round in which no packet was sent and every queue is empty proves the
  network is at a FIXED POINT -- every VM absorbed one -1 and emitted
  nothing -- PROVIDED the token each VM absorbed really was a -1. That is
  guaranteed from round 2 onward (round n consumes the -1 that round n-1's
  starvation queued) and guaranteed false in round 1, where each VM absorbs
  its ADDRESS. Round 1 of the real input is exactly such a spurious quiet
  round: every NIC reads its address, polls once before saying anything,
  and starves -- a boot round that looks idle and isn't. Hence the
  `rounds >= 2` guard, and test_boot_quiet_round_is_not_idle pins a NIC
  that a round-1 idle test would misjudge.

The NAT (address 255) is a one-packet register, not a queue: it keeps only
the last packet sent to it, and when the network idles it forwards that
packet to address 0 to wake everything up. run_network reports both sides of
the NAT's life as a stream of events -- ("nat", x, y) when a packet reaches
255, ("wake", x, y) when idleness triggers the forward -- and the two parts
are two different questions about that one stream: part 1 is the first "nat"
Y, part 2 the first Y two consecutive "wake" events share. `solve` answers
both from a single run of the network.

Run:  python python/day23.py
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from pathlib import Path

from intcode import VM

NAT = 255  # the one address that is a register, not a computer
SIZE = 50  # NICs on the network, addressed 0..SIZE-1


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def run_network(program: list[int], size: int = SIZE) -> Iterator[tuple[str, int, int]]:
    """Boot `size` NICs and run the network; yield the NAT's view of it.

    An endless stream of events -- callers stop consuming when their answer
    appears:

        ("nat", x, y)   a packet arrived at address 255
        ("wake", x, y)  the network idled, so the NAT forwarded its held
                        packet to address 0

    Scheduling is cooperative round-robin. One slice runs a VM until it
    starves (asks for input nobody has sent), delivering queued packets and
    dispatching completed output triples along the way; a starved VM is fed
    one -1 and set aside until the next round. Idleness -- no packet moved
    all round, every queue empty, and (rounds >= 2, see the module
    docstring) every VM demonstrably running on -1s alone -- is a fixed
    point the network cannot leave by itself, which is precisely when the
    statement's NAT intervenes. A network that reaches that fixed point
    before the NAT holds anything is dead for good, and raising beats
    spinning on it forever.
    """
    vms = [VM(list(program)) for _ in range(size)]
    for address, vm in enumerate(vms):
        vm.inputs.append(address)
    queues: list[deque[tuple[int, int]]] = [deque() for _ in range(size)]
    triples: list[list[int]] = [[] for _ in range(size)]
    nat: tuple[int, int] | None = None
    rounds = 0

    while True:
        rounds += 1
        busy = False
        for vm, queue, triple in zip(vms, queues, triples):
            while True:
                result = vm.step()
                if result == "blocked":
                    if not queue:
                        vm.inputs.append(-1)
                        break
                    vm.inputs.extend(queue.popleft())
                    busy = True
                elif result == "halted":
                    break
                elif isinstance(result, tuple):
                    triple.append(result[1])
                    if len(triple) == 3:
                        dest, x, y = triple
                        triple.clear()
                        busy = True
                        if dest == NAT:
                            nat = (x, y)
                            yield ("nat", x, y)
                        else:
                            queues[dest].append((x, y))

        if rounds >= 2 and not busy and all(not q for q in queues):
            if nat is None:
                raise RuntimeError("network idle but the NAT holds no packet -- deadlock")
            queues[0].append(nat)
            yield ("wake", *nat)


def part1(program: list[int], size: int = SIZE) -> int:
    """Y of the first packet sent to address 255."""
    for kind, _x, y in run_network(program, size):
        if kind == "nat":
            return y
    raise AssertionError("run_network never returns")


def part2(program: list[int], size: int = SIZE) -> int:
    """First Y the NAT delivers to address 0 twice in a row."""
    last = None
    for kind, _x, y in run_network(program, size):
        if kind == "wake":
            if y == last:
                return y
            last = y
    raise AssertionError("run_network never returns")


def solve(program: list[int]) -> tuple[int, int]:
    """Both answers from one run of the network.

    The first packet to 255 arrives before the first idle (it has to: an
    idle network can only replay the NAT's packet, so 255-traffic precedes
    wake-traffic), so one event stream serves both questions.
    """
    first = last = None
    for kind, _x, y in run_network(program):
        if kind == "nat" and first is None:
            first = y
        elif kind == "wake":
            if y == last:
                assert first is not None
                return first, y
            last = y
    raise AssertionError("run_network never returns")


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day23.txt").read_text()
    first, repeated = solve(parse_input(text))
    print(f"part 1: {first}")
    print(f"part 2: {repeated}")


if __name__ == "__main__":
    main()
