"""Day 25 -- disassembling the adventure engine.

Companion to Problem_Statements/days/day25_disassembly.md. Five passes:

  1. RECURSIVE-DESCENT DISASSEMBLY. Day 17's call idiom again (return
     address into rb[+0], jump, return via `jnz/jz .. rb[+0]`), plus three
     flavours of indirect control flow: calls through a value in a frame
     slot (the room and item HOOKS), a call through the global the bit
     decomposer holds its callback in, and -- Day 23's trick, now in the
     inner loop -- a `jz #0 [0]` whose jump operand is PATCHED with the
     verb handler's address just before it executes. Five short gaps in
     the descent turn out to be dead code: the compiler's function
     epilogue, emitted after hooks that halt or loop and never return.

  2. THE WORLD. main() hands the room printer one pointer, and the whole
     ship unrolls from it: rooms are seven-cell structs (name, description,
     an on-enter hook, four door slots in north/east/south/west order --
     the order of the direction-name table), doors are just pointers at
     other rooms, and exactly one room carries a hook: the pressure floor,
     whose hook is the weigher. Strings never appear in the image as
     ASCII: a string is length-prefixed with each cell holding
     `char - (index + length)`, so the SAME character encodes differently
     at every position -- which is why no strings dump ever showed text.

  3. THE ITEMS. One 13-row table: location (a room pointer, or -1 for
     "carried"), name, an obfuscated weight cell, and an ON-TAKE HOOK.
     Weight = cell - salt - row (the same affine-by-position idea as the
     strings); the five trap items weigh exactly 0 -- their cell IS the
     salt-plus-row zero point -- and their hooks, called in vitro here,
     are three printing halts, one flag-setter (the electromagnet), and
     one honest infinite loop.

  4. THE WEIGHER, STATICALLY. The floor hook sums the carried weights,
     splits the total into 33 bits, and compares them MSB-first against a
     33-cell table whose bits are stored as "greater or less than
     84 * 52". Decoding that table yields the target weight -- and the
     success message prints the droid's own weight as the password, so
     TARGET IS ANSWER: part 1 off the disk, no game played. The eight
     safe weights are eight distinct powers of two, so the subset that
     opens the door is literally the binary representation of the target.

  5. CROSS-CHECK. The static password against the live game, and the
     static subset walked to the checkpoint carrying exactly those four
     items: the door opens on the first try.

Every number printed is read out of the image via anchored parses (main's
first argument, the one hooked room, the weigher's call arguments, the
comparator's patched table base...), never recalled; any shape the parses
do not recognise is refused loudly. The function ADDRESSES differ between
puzzle inputs, but the chain re-derives them from address 0 outward.

Run:  python python/day25_disasm.py [path-to-program] [--full]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from day25 import Droid, explore, parse_input
from intcode import VM

OPS = {
    1: ("add", 3),
    2: ("mul", 3),
    3: ("in", 1),
    4: ("out", 1),
    5: ("jnz", 2),
    6: ("jz", 2),
    7: ("lt", 3),
    8: ("eq", 3),
    9: ("arb", 1),
    99: ("hlt", 0),
}

DIRECTIONS = ("north", "east", "south", "west")  # door-slot order, see pass 2


# ------------------------------------------------------------------ instructions


def mode(mem: list[int], addr: int, index: int) -> int:
    return (mem[addr] // 10 ** (index + 1)) % 10


def operand(mem: list[int], addr: int, index: int) -> str:
    raw = mem[addr + index]
    m = mode(mem, addr, index)
    if m == 1:
        return f"#{raw}"
    if m == 2:
        return f"rb[{raw:+d}]"
    return f"[{raw}]"


def render_instruction(mem: list[int], addr: int) -> tuple[str, int] | tuple[None, int]:
    op = mem[addr] % 100
    if op not in OPS:
        return None, 0
    name, count = OPS[op]
    if addr + count >= len(mem):
        return None, 0
    args = " ".join(operand(mem, addr, i) for i in range(1, count + 1))
    return f"{name:4}{' ' + args if args else ''}", count + 1


@dataclass(frozen=True)
class Instr:
    addr: int
    op: int
    modes: tuple[int, int, int]
    params: tuple[int, ...]
    size: int


def decode_at(mem: list[int], addr: int) -> Instr | None:
    op = mem[addr] % 100
    if op not in OPS:
        return None
    count = OPS[op][1]
    if addr + count >= len(mem):
        return None
    return Instr(
        addr=addr,
        op=op,
        modes=tuple(mode(mem, addr, i) for i in (1, 2, 3)),
        params=tuple(mem[addr + 1 : addr + 1 + count]),
        size=count + 1,
    )


def call_sites(mem: list[int]) -> dict[int, tuple[int | None, int]]:
    """Every `rb[+0] = ret; jmp ...` pair -> {call address: (target, ret)}.

    Day 17's convention. A non-immediate jump is a call through whatever
    the operand holds -- target None here; the tables say what it can be.
    """
    found = {}
    for addr in range(len(mem) - 7):
        if mem[addr] not in (21101, 21102) or mem[addr + 3] != 0:
            continue
        if mem[addr + 4] % 100 not in (5, 6) or (mem[addr + 4] // 100) % 10 != 1:
            continue
        a, b = mem[addr + 1], mem[addr + 2]
        ret = a + b if mem[addr] == 21101 else a * b
        jump_immediate = (mem[addr + 4] // 1000) % 10 == 1
        target = mem[addr + 6] if jump_immediate else None
        found[addr] = (target, ret)
    return found


def descend(mem: list[int], entries: list[int]) -> dict[int, tuple[str, int]]:
    """Disassemble forward from every entry point, following static jumps."""
    seen: dict[int, tuple[str, int]] = {}
    stack = list(entries)
    while stack:
        addr = stack.pop()
        while 0 <= addr < len(mem) and addr not in seen:
            text, size = render_instruction(mem, addr)
            if text is None:
                break
            seen[addr] = (text, size)
            op = mem[addr] % 100
            if op == 99:
                break
            if op in (5, 6):
                if (mem[addr] // 1000) % 10 == 1:
                    stack.append(mem[addr + 2])
                immediate = (mem[addr] // 100) % 10 == 1
                if immediate and (mem[addr + 1] != 0) == (op == 5):
                    break  # unconditional: nothing follows
            addr += size
    return seen


def body(mem: list[int], entry: int) -> list[Instr]:
    """One function's instructions only, in address order.

    A call-aware walk: at an rb[+0]-idiom call site the callee is NOT
    followed -- the walk resumes at the return address the store names,
    which plain descent can never reach (returns are dynamic). Other
    static jumps are followed as usual; an indirect jump (a return, or a
    call through a hook value) ends its path.
    """
    sites = call_sites(mem)
    seen: dict[int, Instr] = {}
    stack = [entry]
    while stack:
        addr = stack.pop()
        while addr not in seen:
            ins = decode_at(mem, addr)
            if ins is None:
                break
            seen[addr] = ins
            if ins.op == 99:
                break
            if addr in sites:
                jump = decode_at(mem, addr + ins.size)
                assert jump is not None
                seen[jump.addr] = jump
                stack.append(sites[addr][1])
                break
            if ins.op in (5, 6):
                if ins.modes[1] == 1:
                    stack.append(ins.params[1])
                if ins.modes[0] == 1 and (ins.params[0] != 0) == (ins.op == 5):
                    break  # unconditional: nothing follows
            addr += ins.size
    return [seen[a] for a in sorted(seen)]


# ------------------------------------------------------- reading the image


def decode_string(mem: list[int], addr: int) -> str:
    """Length prefix, then cell i holds `char - (i + length)`."""
    n = mem[addr]
    return "".join(chr(mem[addr + 1 + i] + i + n) for i in range(n))


def string_ok(mem: list[int], addr: int, limit: int) -> bool:
    n = mem[addr]
    if not 0 < n <= limit - addr:
        return False
    try:
        return all(c == "\n" or 32 <= ord(c) < 127 for c in decode_string(mem, addr))
    except ValueError:
        return False


def imm_stores_before(mem: list[int], instrs: list[Instr], call_addr: int) -> dict[int, int]:
    """rb-slot -> immediate, from the straight-line stores preceding a call.

    Walks backwards over `add/mul #a #b rb[+k]` instructions; anything else
    ends the scan. This is how a call site's immediate arguments -- table
    bases, counts, callback addresses -- are read out of the code.
    """
    slots: dict[int, int] = {}
    index = next(i for i, ins in enumerate(instrs) if ins.addr == call_addr)
    for ins in reversed(instrs[:index]):
        if ins.op not in (1, 2) or ins.modes != (1, 1, 2):
            break
        a, b, dest = ins.params
        slots.setdefault(dest, a + b if ins.op == 1 else a * b)
    return slots


def calls_in(mem: list[int], instrs: list[Instr]) -> list[tuple[int, int, dict[int, int]]]:
    """(call address, static target, {rb slot: immediate arg}) per idiom call."""
    sites = call_sites(mem)
    out = []
    for ins in instrs:
        if ins.addr in sites and sites[ins.addr][0] is not None:
            target = sites[ins.addr][0]
            assert target is not None
            out.append((ins.addr, target, imm_stores_before(mem, instrs, ins.addr)))
    return out


# --------------------------------------------------------- engine recovery


@dataclass(frozen=True)
class RoomRec:
    addr: int
    name: str
    desc_ptr: int
    hook: int
    doors: tuple[int, int, int, int]  # north, east, south, west; 0 = wall


@dataclass(frozen=True)
class ItemRec:
    row: int
    addr: int
    location: int  # room address, or -1 once carried
    name_ptr: int
    name: str
    weight_cell: int
    weight: int  # weight_cell - salt - row
    hook: int  # 0 = safe; else the on-take trap


@dataclass
class Engine:
    """Everything the anchored parses recover from the image."""

    start_room: int = 0
    prompt: int = 0  # the "Command?" string
    rooms: dict[int, RoomRec] = field(default_factory=dict)
    weigher: int = 0  # the one room hook: the pressure floor's
    floor: int = 0  # the room carrying it
    item_table: tuple[int, int, int] = (0, 0, 0)  # base, rows, stride
    salt: int = 0  # weight = cell - salt - row
    items: list[ItemRec] = field(default_factory=list)
    threshold_cells: tuple[int, int] = (0, 0)  # the two factor globals
    threshold: int = 0
    bit_base: int = 0
    bit_count: int = 0
    weight_global: int = 0
    verdict_global: int = 0
    verb_strings: int = 0
    verb_handlers: int = 0
    verb_count: int = 0
    verbs: list[tuple[str, int]] = field(default_factory=list)
    buffer: int = 0
    buffer_len: int = 0
    dir_table: int = 0
    powers: tuple[int, int] = (0, 0)  # base, count
    success_strings: tuple[int, int] = (0, 0)
    names: dict[int, str] = field(default_factory=dict)  # function entry -> role
    globals_: dict[int, str] = field(default_factory=dict)  # cell -> role


def _sole(values: list[int], what: str) -> int:
    if len(set(values)) != 1:
        raise ValueError(f"expected one {what}, found {sorted(set(values))}")
    return values[0]


def recover_engine(mem: list[int]) -> Engine:
    """The derivation chain, address 0 outward. Loud on any unknown shape."""
    e = Engine()

    # main: enter(start_room), then loop { print(prompt); dispatch() }
    main = body(mem, 0)
    main_calls = calls_in(mem, main)
    if len(main_calls) != 3:
        raise ValueError(f"main makes {len(main_calls)} static calls, expected 3")
    (_, enter_room, args0), (_, print_str, args1), (_, dispatcher, _) = main_calls
    e.start_room = args0[1]
    e.prompt = args1[1]
    e.names |= {0: "main", enter_room: "enter_room", print_str: "print_str", dispatcher: "dispatch"}

    # enter_room: header strings, the doors loop (-> for_each + door callback,
    # count 4), the item lister, then the indirect hook call.
    enter = body(mem, enter_room)
    enter_calls = calls_in(mem, enter)
    room_global = next(ins.params[2] for ins in enter if ins.op in (1, 2) and ins.modes[2] == 0)
    e.globals_[room_global] = "here (current room)"
    doors_call = next(c for c in enter_calls if 2 in c[2] and c[2].get(2) == 4)
    for_each, door_cb = doors_call[1], doors_call[2][4]
    e.names |= {for_each: "for_each", door_cb: "print_door"}
    lister = enter_calls[-1][1]
    e.names[lister] = "list_items"

    # print_door: `- ` + direction name -- the add that patches in the table.
    e.dir_table = _sole(
        [i.params[1] for i in body(mem, door_cb) if i.op == 1 and i.modes == (2, 1, 0)],
        "direction table base",
    )

    # print_str delegates to for_each_str with the decoder as callback.
    ps_calls = calls_in(mem, body(mem, print_str))
    for_each_str, putchar = ps_calls[0][1], ps_calls[0][2][2]
    e.names |= {for_each_str: "for_each_str", putchar: "put_decoded"}

    # list_items: for_each over the item table (first sighting of it).
    li_calls = calls_in(mem, body(mem, lister))
    table_args = next(c[2] for c in li_calls if c[1] == for_each)
    e.item_table = (table_args[1], table_args[2], table_args[3])
    e.names[table_args[4]] = "print_item"

    # dispatch: reader first, then the verb loop: strings table, matcher,
    # handlers table (feeding the patched `jz #0 [0]`), bound from the lt.
    # (its other calls are print_str -- the stuck / unrecognized messages)
    disp = body(mem, dispatcher)
    disp_calls = calls_in(mem, disp)
    reader = disp_calls[0][1]
    matcher = next(t for _, t, _a in disp_calls[1:] if t != print_str)
    e.names |= {reader: "read_line", matcher: "match_str"}
    match_cb = _sole(
        [c[2][2] for c in calls_in(mem, body(mem, matcher)) if c[1] == for_each_str],
        "match callback",
    )
    e.names[match_cb] = "match_char"
    patch_adds = [i for i in disp if i.op == 1 and i.modes == (2, 1, 0)]
    if len(patch_adds) != 2:
        raise ValueError(f"dispatch has {len(patch_adds)} patching adds, expected 2")
    e.verb_strings, e.verb_handlers = (i.params[1] for i in patch_adds)
    e.verb_count = _sole([i.params[1] for i in disp if i.op == 7 and i.modes[1] == 1], "verb-loop bound")
    stuck = next(i.params[0] for i in disp if i.op == 6 and i.modes[0] == 0)
    e.globals_[stuck] = "stuck (electromagnet flag)"
    # a movement verb ends in \n (whole-line match); take/drop end in a
    # space (prefix match, the item name starts at offset 5)
    e.verbs = [
        (decode_string(mem, mem[e.verb_strings + i]).strip(), mem[e.verb_handlers + i])
        for i in range(e.verb_count)
    ]
    for verb, handler in e.verbs:
        e.names[handler] = f"do_{verb}"

    # read_line: for_each clears the buffer (base, length), then `in` loop.
    rd_calls = calls_in(mem, body(mem, reader))
    clear_args = next(c[2] for c in rd_calls if c[1] == for_each)
    e.buffer, e.buffer_len = clear_args[1], clear_args[2]
    e.names[clear_args[4]] = "clear_cell"

    # the world: rooms are 7-cell structs; exactly one has an on-enter hook.
    stack, seen = [e.start_room], set()
    while stack:
        r = stack.pop()
        if r in seen:
            continue
        seen.add(r)
        if not string_ok(mem, mem[r], len(mem)):
            raise ValueError(f"room struct at {r}: name pointer decodes to junk")
        doors = tuple(mem[r + 3 : r + 7])
        e.rooms[r] = RoomRec(r, decode_string(mem, mem[r]), mem[r + 1], mem[r + 2], doors)
        stack.extend(d for d in doors if d)
    hooked = [r for r in e.rooms.values() if r.hook]
    if len(hooked) != 1:
        raise ValueError(f"rooms with on-enter hooks: {[r.name for r in hooked]}")
    e.floor, e.weigher = hooked[0].addr, hooked[0].hook
    e.names[e.weigher] = "weigh (pressure-floor hook)"

    # the weigher: zeroes the weight global, folds the item table through
    # the accumulator, multiplies the two threshold factors, then streams
    # the total's bits through the comparator.
    weigher = body(mem, e.weigher)
    w_calls = calls_in(mem, weigher)
    acc_args = next(c[2] for c in w_calls if c[1] == for_each)
    if (acc_args[1], acc_args[2], acc_args[3]) != e.item_table:
        raise ValueError("the weigher and the item lister disagree about the item table")
    accumulator = acc_args[4]
    threshold_mul = _sole([i.addr for i in weigher if i.op == 2 and i.modes == (0, 0, 0)], "threshold mul")
    e.threshold_cells = (mem[threshold_mul + 1], mem[threshold_mul + 2])
    e.threshold = mem[e.threshold_cells[0]] * mem[e.threshold_cells[1]]
    bits_call = next(c for c in w_calls if c[1] not in (for_each, print_str))
    bit_split, e.bit_count, comparator = bits_call[1], bits_call[2][2], bits_call[2][3]
    e.names |= {
        accumulator: "add_item_weight",
        bit_split: "split_bits",
        comparator: "check_bit",
    }
    e.weight_global = _sole(
        [i.params[2] for i in weigher if i.op == 2 and i.modes == (1, 1, 0)], "weight global"
    )
    # the weigher's other callees: enter_room (the eject re-entry) and success
    success_call = [
        c
        for c in w_calls
        if c[1] not in (for_each, print_str, bit_split) and e.names.get(c[1]) != "enter_room"
    ]
    e.globals_ |= {
        e.weight_global: "weight (the future password)",
        mem[threshold_mul + 3]: "threshold (84 * 52)",
        e.threshold_cells[0]: "threshold factor",
        e.threshold_cells[1]: "threshold factor",
    }
    # the verdict global: what the comparator writes and the weigher tests.
    comp = body(mem, comparator)
    e.verdict_global = _sole(
        [i.params[2] for i in comp if i.op in (1, 2) and i.modes == (1, 1, 0)],
        "verdict global",
    )
    e.globals_[e.verdict_global] = "verdict (-1 light, 0 open, +1 heavy)"
    e.bit_base = _sole([i.params[1] for i in comp if i.op == 1 and i.modes == (2, 1, 0)], "bit-table base")

    # the accumulator: weight = cell - salt - row; the salt is the literal
    # in its one immediate-plus-position add.
    acc = body(mem, accumulator)
    e.salt = -_sole([i.params[0] for i in acc if i.op == 1 and i.modes == (1, 0, 2)], "salt literal")

    # success: print(speech); print_number(weight); print(coda); halt.
    success = _sole([c[1] for c in success_call], "success function")
    e.names[success] = "open_and_reveal"
    sc = calls_in(mem, body(mem, success))
    speeches = [args[1] for _, t, args in sc if t == print_str]
    printer = _sole([t for _, t, _args in sc if t != print_str], "number printer")
    e.names[printer] = "print_number"
    e.success_strings = (speeches[0], speeches[-1])
    digits = calls_in(mem, body(mem, printer))[0][1]
    e.names[digits] = "print_digits"
    divmod_fn = _sole(  # print_digits recurses; its other callee is divmod
        [t for _, t, _a in calls_in(mem, body(mem, digits)) if t != digits], "divmod"
    )
    e.names[divmod_fn] = "divmod"
    dm = body(mem, divmod_fn)
    e.powers = (
        _sole([i.params[1] for i in dm if i.op == 1 and i.modes == (2, 1, 0)], "powers base"),
        _sole(  # the one nonzero immediate init: the loop counter (q/r init to 0)
            [i.params[1] for i in dm if i.op == 2 and i.modes == (1, 1, 2) and i.params[1]],
            "powers count",
        ),
    )

    # the items, at last: weight = cell - salt - row.
    base, rows, stride = e.item_table
    for row in range(rows):
        a = base + row * stride
        loc, name_ptr, cell, hook = mem[a : a + 4]
        if not string_ok(mem, name_ptr, len(mem)):
            raise ValueError(f"item row {row}: name pointer {name_ptr} decodes to junk")
        if loc not in e.rooms:
            raise ValueError(f"item row {row}: location {loc} is not a room")
        e.items.append(
            ItemRec(row, a, loc, name_ptr, decode_string(mem, name_ptr), cell, cell - e.salt - row, hook)
        )
    for item in e.items:
        if item.hook:
            e.names.setdefault(item.hook, f"trap_{item.name.replace(' ', '_')}")

    # bookkeeping globals discovered along the way, for the listing.
    for fn, roles in (
        (lister, ("printed header", "wanted location")),
        (matcher, ("match offset", "match ok")),
        (bit_split, ("bit callback",)),
    ):
        cells = sorted(
            {
                i.params[2]
                for i in body(mem, fn)
                if i.op in (1, 2)
                and i.modes[2] == 0
                and not (i.modes[0] == i.modes[1] == 1 and i.params[2] in e.globals_)
            }
            - set(e.globals_)
        )
        for cell, role in zip(cells, roles):
            e.globals_.setdefault(cell, role)
    move = _sole(
        [c[1] for d in DIRECTIONS for c in calls_in(mem, body(mem, dict(e.verbs)[d]))],
        "move helper",
    )
    e.names[move] = "move"
    for verb, cb_role in (("take", "find_and_take"), ("drop", "find_and_drop")):
        handler_body = body(mem, dict(e.verbs)[verb])
        cb = _sole(
            [c[2][4] for c in calls_in(mem, handler_body) if c[1] == for_each],
            f"{verb} callback",
        )
        e.names[cb] = cb_role
        for i in handler_body:
            if i.op in (1, 2) and i.modes == (1, 1, 0):
                e.globals_.setdefault(i.params[2], f"found it ({verb})")
    return e


# ------------------------------------------------------ static solution


def decode_target(mem: list[int], engine: Engine | None = None) -> int:
    """The weight the floor wants: the bit table read against the threshold.

    Bit i of the table (MSB first) is stored as a value above or below
    84 * 52 -- nothing else about the cell matters. This number is also
    the password (see open_and_reveal): TARGET IS ANSWER.
    """
    e = engine or recover_engine(mem)
    target = 0
    for i in range(e.bit_count):
        cell = mem[e.bit_base + i]
        if cell == e.threshold:
            raise ValueError(f"bit cell {i} equals the threshold: undecodable")
        target = target * 2 + (1 if cell > e.threshold else 0)
    return target


def static_subset(mem: list[int], engine: Engine | None = None) -> list[str]:
    """The unique safe-item subset weighing exactly the target.

    General subset-sum over the safe weights (meet in the middle would be
    overkill for eight items); uniqueness is asserted, and on this input
    it holds for a stronger reason pinned in pass 4: the eight weights
    are eight distinct powers of two, so every subset has a distinct sum
    and the winning subset is the target's binary representation.
    """
    e = engine or recover_engine(mem)
    target = decode_target(mem, e)
    safe = [i for i in e.items if not i.hook]
    matches = [
        combo
        for k in range(len(safe) + 1)
        for combo in combinations(safe, k)
        if sum(i.weight for i in combo) == target
    ]
    if len(matches) != 1:
        raise ValueError(f"{len(matches)} subsets weigh {target}")
    return [i.name for i in matches[0]]


def static_password(mem: list[int]) -> int:
    """Part 1 with the VM never started."""
    return decode_target(mem)


# ------------------------------------------------- the in-vitro hook harness


def call_hook(program: list[int], addr: int, limit: int = 300_000) -> tuple[str, str, dict[int, int]]:
    """Call one hook on the live machine, alone, and report what it did.

    The recovered convention replayed by hand: return address in rb[+0]
    pointing at a hand-planted `hlt` outside the image, rb parked past the
    heap. Returns (outcome, printed text, {image cell: new value}) where
    outcome is 'returned', 'halted' (the hook's own hlt -- a death), or
    'hung' (the step budget expired -- the infinite loop).
    """
    vm = VM(list(program))
    ret, base = 90_000, 90_010
    vm.mem[ret] = 99
    vm.rb = base
    vm.mem[base] = ret
    vm.ip = addr
    out: list[int] = []
    outcome = "hung"
    for _ in range(limit):
        result = vm.step()
        if isinstance(result, tuple):
            out.append(result[1])
        elif result == "halted":
            outcome = "returned" if vm.ip == ret else "halted"
            break
        elif result == "blocked":
            outcome = "blocked"
            break
    text = "".join(map(chr, out))
    changed = {a: vm.mem[a] for a in range(len(program)) if vm.mem[a] != program[a]}
    return outcome, text, changed


# ------------------------------------------------------------------ the passes


def operand_patches(mem: list[int], listing: dict[int, tuple[str, int]]) -> list[tuple[int, int, int]]:
    """Stores whose destination lands inside another decoded instruction."""
    inside = {a + i: a for a, (_, size) in listing.items() for i in range(1, size)}
    found = []
    for addr in sorted(listing):
        if mem[addr] % 100 not in (1, 2, 7, 8):
            continue
        if (mem[addr] // 10000) % 10 != 0:
            continue
        dest = mem[addr + 3]
        if dest in inside:
            found.append((addr, dest, inside[dest]))
    return found


def entry_points(mem: list[int], engine: Engine) -> list[int]:
    return sorted(
        {0, *engine.names}
        | {t for t, _ in call_sites(mem).values() if t is not None}
        | {r for _, r in call_sites(mem).values()}
    )


def full_descent(mem: list[int], engine: Engine) -> dict[int, tuple[str, int]]:
    return descend(mem, entry_points(mem, engine))


def engine_data_cells(e: Engine) -> set[int]:
    """Every cell the recovery knows to be data near the code: the globals
    and the fixed tables. (Rooms, items and the string pool live in their
    own regions and never masquerade as code.)"""
    cells = set(e.globals_)
    cells |= set(range(e.dir_table, e.dir_table + 4))
    cells |= set(range(e.verb_strings, e.verb_strings + e.verb_count))
    cells |= set(range(e.verb_handlers, e.verb_handlers + e.verb_count))
    cells |= set(range(e.bit_base, e.bit_base + e.bit_count))
    cells |= set(range(e.powers[0], e.powers[0] + e.powers[1]))
    cells |= set(range(e.buffer, e.buffer + e.buffer_len))
    return cells


def gaps_in(covered: set[int], size: int) -> list[tuple[int, int]]:
    """Maximal uncovered [lo, hi] runs, address order."""
    gaps = []
    a = 0
    while a < size:
        if a in covered:
            a += 1
            continue
        lo = a
        while a < size and a not in covered:
            a += 1
        gaps.append((lo, a - 1))
    return gaps


def dead_epilogues(
    mem: list[int], listing: dict[int, tuple[str, int]], engine: Engine
) -> dict[int, tuple[str, int]]:
    """The unreachable instructions between functions.

    The compiler emits `arb; ret` (and, after a hlt, a jump to it) at the
    end of every function; a hook that halts or loops leaves its epilogue
    unreachable. A gap counts only if it decodes as instructions exactly
    tiling it AND is not a string -- the message pool, and even three
    globals whose load-time junk spells `arb; hlt`, would otherwise
    masquerade as code.
    """
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    covered |= engine_data_cells(engine)
    dead: dict[int, tuple[str, int]] = {}
    for lo, hi in gaps_in(covered, len(mem)):
        if string_ok(mem, lo, hi + 1):
            continue
        trial = decode_gap(mem, lo, hi)
        if trial is not None:
            dead |= trial
    return dead


def decode_gap(mem: list[int], lo: int, hi: int) -> dict[int, tuple[str, int]] | None:
    """The gap as instructions exactly tiling [lo, hi], or None.

    Seeded at every still-undecoded cell, not just lo: an epilogue is TWO
    unreachable snippets (`jnz` to the live hlt, then an `arb; ret` nothing
    jumps to), and only the first is reachable from the gap's start.
    """
    tiled: dict[int, tuple[str, int]] = {}
    cells: set[int] = set()
    addr = lo
    while addr <= hi:
        if addr in cells:
            addr += 1
            continue
        for a, entry in descend(mem, [addr]).items():
            if lo <= a <= hi:
                tiled[a] = entry
                cells.update(range(a, a + entry[1]))
        if addr not in cells:
            return None
    return tiled if cells == set(range(lo, hi + 1)) else None


def pass1(mem: list[int], engine: Engine) -> dict[int, tuple[str, int]]:
    listing = full_descent(mem, engine)
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    calls = call_sites(mem)
    patches = operand_patches(mem, listing)
    jump_patches = [p for p in patches if mem[p[2]] % 100 in (5, 6) and p[1] == p[2] + 2]
    dead = dead_epilogues(mem, listing, engine)

    print("== pass 1: recursive descent ==")
    print(f"  {len(listing)} live instructions covering {len(covered)} of {len(mem)} cells,")
    print(f"  plus {len(dead)} unreachable ones: the compiler's function epilogues")
    print("  stranded behind hooks that halt or loop and never return")
    print(f"  {len(calls)} rb[+0]-idiom call sites; indirect control flow three ways:")
    print("    - hooks called through a frame slot (rooms' on-enter, items' on-take)")
    print("    - the bit decomposer's callback, called through a global")
    print(f"    - the verb dispatch: {len(jump_patches)} patched jump TARGET(s) -- Day 23's")
    print("      one-off boot trick is this engine's regular calling convention")
    print(f"  {len(patches)} self-modifying stores, all operand patches (indexed addressing)")
    return listing


def pass2(mem: list[int], engine: Engine) -> None:
    e = engine
    print("\n== pass 2: the world ==")
    print("  strings: length-prefixed, cell = char - (index + length) -- position-salted")
    print(
        f"  {len(e.rooms)} rooms from the start pointer {e.start_room} "
        f"({e.rooms[e.start_room].name}), 7 cells each:"
    )
    print("  [name, description, on-enter hook, north, east, south, west]")
    for r in sorted(e.rooms.values(), key=lambda r: r.addr):
        doors = " ".join(f"{d[0].upper()}->{e.rooms[p].name}" for d, p in zip(DIRECTIONS, r.doors) if p)
        tag = "  <-- the hook: the weigher" if r.hook else ""
        print(f"    {r.addr:4} {r.name:26} {doors}{tag}")
    floor = e.rooms[e.floor]
    for r in e.rooms.values():
        for d, p in zip(DIRECTIONS, r.doors):
            if p:
                back = e.rooms[p].doors[(DIRECTIONS.index(d) + 2) % 4]
                assert back == r.addr, f"{r.name} {d} not reciprocated by {e.rooms[p].name}"
    print("  every door reciprocated by its opposite door -- the graph is undirected")
    print(f"  the one hooked room is {floor.name}: enter it and the weigher runs")
    print(f"  verbs: {[v for v, _ in e.verbs]} (line buffer at {e.buffer}, {e.buffer_len} cells)")


def pass3(mem: list[int], engine: Engine) -> None:
    e = engine
    print("\n== pass 3: the items ==")
    print(
        f"  table at {e.item_table[0]}: {e.item_table[1]} rows of [location, name, weight cell, on-take hook]"
    )
    print(f"  weight = cell - {e.salt} - row (position-salted, like the strings)")
    for item in e.items:
        room = e.rooms[item.location].name
        w = (
            f"2^{item.weight.bit_length() - 1}"
            if item.weight and (item.weight & (item.weight - 1)) == 0
            else str(item.weight)
        )
        hook = f"hook {item.hook}" if item.hook else "no hook"
        print(f"    {item.row:2} {item.name:20} {room:24} weight {item.weight:>10} ({w:>5}) {hook}")
    print("  the five hooked items all weigh EXACTLY 0 -- their cell is the salt-")
    print("  plus-row zero point -- and their hooks, called in vitro:")
    for item in e.items:
        if not item.hook:
            continue
        outcome, text, changed = call_hook(mem, item.hook)
        line = text.strip().splitlines()[0] if text.strip() else "(silent)"
        extra = ""
        if outcome == "returned" and changed:
            names = ", ".join(f"[{a}]={v} ({e.globals_.get(a, '?')})" for a, v in changed.items())
            extra = f" -- sets {names}"
        if outcome == "hung":
            extra = f" -- printed {text.count(chr(10))}+ copies before the budget expired"
        print(f"    {item.name:20} {outcome:8} {line!r}{extra}")


def pass4(mem: list[int], engine: Engine) -> None:
    e = engine
    target = decode_target(mem, e)
    subset = static_subset(mem, e)
    safe = [i for i in e.items if not i.hook]
    print("\n== pass 4: the weigher, statically ==")
    print(
        f"  droid weight = sum over carried rows of (cell - {e.salt} - row), "
        f"split into {e.bit_count} bits (MSB first)"
    )
    print(
        f"  each bit checked against the table at {e.bit_base}: bit = cell > "
        f"[{e.threshold_cells[0]}]*[{e.threshold_cells[1]}] = {e.threshold}"
    )
    print(f"  decoded target = {target:#035b} = {target}")
    speech = decode_string(mem, e.success_strings[0])
    print(f"  on equality, open_and_reveal prints {speech.strip().splitlines()[-1][:45]!r}...")
    print("  ...then PRINT_NUMBER(weight): the password IS the droid's weight,")
    print("  so the target above is part 1 -- off the disk, no game played")
    powers = sorted(i.weight.bit_length() - 1 for i in safe)
    assert all(i.weight and (i.weight & (i.weight - 1)) == 0 for i in safe)
    print(f"  the {len(safe)} safe weights are distinct powers of two: 2^{powers}")
    print(f"  so subsets reach {2 ** len(safe)} distinct sums and the answer's binary")
    print(f"  digits pick the load-out: {sorted(subset)}")
    print(f"  STATIC PART 1 = {target}")


def pass5(mem: list[int], engine: Engine) -> None:
    print("\n== pass 5: cross-check against the live game ==")
    target = decode_target(mem, engine)
    subset = set(static_subset(mem, engine))
    droid = Droid(list(mem))
    survey = explore(droid)
    assert set(survey.inventory) >= subset
    for item in survey.inventory:
        if item not in subset:
            droid.send(f"drop {item}")
    for door in survey.checkpoint_path:
        droid.send(door)
    reply = droid.send(survey.test_door)
    assert reply is not None
    ok = "Alert!" not in reply and str(target) in reply
    print(f"  carried the static subset {sorted(subset)} to the checkpoint:")
    print(f"  door opened on the FIRST try with the static password in the speech: {ok}")
    rejected = {i.name for i in engine.items if i.hook}
    print(f"  probe-rejected items == statically hooked items: {set(survey.rejected) == rejected}")


# ------------------------------------------------------------ the full listing

NOTE_ROLES = {
    "main": "boot: enter the start room, then loop { prompt; dispatch }",
    "enter_room": "print header, name, description, doors, items; run the hook",
    "print_str": "decode-and-print via for_each_str + put_decoded",
    "put_decoded": "out(cell + index + length) -- the string decoder",
    "for_each": "for i in 0..n-1: fn(base + i*stride, i)",
    "for_each_str": "for i in 0..len-1: fn(cell[i], i, len)",
    "print_door": "`- <direction>` for each non-wall door slot",
    "list_items": "scan the item table for a location (a room, or -1 = carried)",
    "print_item": "header on first hit, then `- <name>`",
    "dispatch": "read a line; if stuck, complain; else match the 7 verbs",
    "read_line": "-1-fill the buffer, then read chars to newline",
    "clear_cell": "the buffer's -1 fill",
    "match_str": "compare a decoded string against the buffer at an offset",
    "match_char": "one char: decode, newline -> -1, compare to the buffer cell",
    "find_and_take": "item here + name match at offset 5: take it, run its hook",
    "find_and_drop": "carried item + name match at offset 5: put it here",
    "do_north": "move via door slot 0",
    "do_east": "move via door slot 1",
    "do_south": "move via door slot 2",
    "do_west": "move via door slot 3",
    "do_take": "find a here-item matching at offset 5; run its hook",
    "do_drop": "find a carried item matching at offset 5",
    "do_inv": "list_items(-1)",
    "move": "enter the room in door slot k, or `You can't go that way.`",
    "weigh (pressure-floor hook)": "sum carried weights; compare bits; open or eject",
    "add_item_weight": "weight += cell - salt - row, carried rows only",
    "check_bit": "one bit vs the table: sets the verdict at the first difference",
    "split_bits": "recursive MSB-first binary decomposition of the weight",
    "open_and_reveal": "the airlock speech, with the WEIGHT printed as the password",
    "print_number": "sign and zero handling around print_digits",
    "print_digits": "recursive divmod-10 digit printer",
    "divmod": "restoring binary long division over the powers table",
    "trap_escape_pod": "on-take: print and halt",
    "trap_molten_lava": "on-take: print and halt",
    "trap_photons": "on-take: print and halt",
    "trap_infinite_loop": "on-take: print the take message forever",
    "trap_giant_electromagnet": "on-take: set the stuck flag; dispatch does the rest",
}


def full_listing(mem: list[int]) -> str:
    """The whole image, cell by cell, every cell exactly once -- asserted."""
    e = recover_engine(mem)
    listing = full_descent(mem, e)
    calls = call_sites(mem)
    all_code = dict(listing)

    # --- classify every data cell -------------------------------------
    covered: set[int] = set()
    segments: list[tuple[int, str, object]] = []  # (start, kind, payload)

    def claim(lo: int, hi: int, kind: str, payload: object) -> None:
        span = set(range(lo, hi + 1))
        if span & covered:
            raise ValueError(f"segment {kind} {lo}..{hi} overlaps another")
        covered.update(span)
        segments.append((lo, kind, payload))

    for addr in sorted(listing):
        size = listing[addr][1]
        claim(addr, addr + size - 1, "code", addr)

    def claim_string(addr: int, note: str) -> None:
        if addr in covered:
            return
        if not string_ok(mem, addr, len(mem)):
            raise ValueError(f"expected a string at {addr}")
        claim(addr, addr + mem[addr], "str", note)

    # everything the engine recovery names, BEFORE any gap sweeping: the
    # weigher's three globals hold 109, 0, 99 at load -- junk that happens
    # to decode as `arb; hlt` -- so data must outrank dead-code detection.
    claim(e.dir_table, e.dir_table + 3, "dirtab", None)
    for i in range(4):
        claim_string(mem[e.dir_table + i], "direction name")
    claim(e.verb_strings, e.verb_strings + e.verb_count - 1, "verbtab", None)
    claim(e.verb_handlers, e.verb_handlers + e.verb_count - 1, "handlertab", None)
    for i in range(e.verb_count):
        claim_string(mem[e.verb_strings + i], "verb")
    claim(e.bit_base, e.bit_base + e.bit_count - 1, "bittab", None)
    claim(e.powers[0], e.powers[0] + e.powers[1] - 1, "powers", None)
    claim(e.buffer, e.buffer + e.buffer_len - 1, "buffer", None)
    for cell, role in e.globals_.items():
        claim(cell, cell, "global", role)
    for r in e.rooms.values():
        claim(r.addr, r.addr + 6, "room", r)
        claim_string(mem[r.addr], f"name of {r.name}")
        claim_string(r.desc_ptr, f"description of {r.name}")
    _base, _rows, stride = e.item_table
    for item in e.items:
        claim(item.addr, item.addr + stride - 1, "item", item)
        claim_string(item.name_ptr, f"item name, row {item.row}")

    # remaining gaps: message-pool strings, or the dead epilogues.
    dead: dict[int, tuple[str, int]] = {}
    for lo, hi in gaps_in(covered, len(mem)):
        a = lo
        while a <= hi and string_ok(mem, a, hi + 1):
            a += mem[a] + 1
        if a == hi + 1:
            a = lo
            while a <= hi:
                claim_string(a, "message")
                a += mem[a] + 1
            continue
        trial = decode_gap(mem, lo, hi)
        if trial is None:
            raise ValueError(f"gap {lo}..{hi} is neither strings nor code")
        for t, (_text, size) in trial.items():
            claim(t, t + size - 1, "code", t)
        dead |= trial
        all_code |= trial

    missing = set(range(len(mem))) - covered
    if missing:
        raise ValueError(f"{len(missing)} cells unclassified, first {sorted(missing)[:5]}")

    # --- emit ---------------------------------------------------------
    lines: list[str] = []
    in_block = False

    def block(on: bool) -> None:
        nonlocal in_block
        if on and not in_block:
            lines.append("```")
            in_block = True
        if not on and in_block:
            lines.append("```")
            lines.append("")
            in_block = False

    def emit(addr: int, raw: list[int], asm: str, note: str = "") -> None:
        cells = " ".join(str(v) for v in raw)
        text = f"{addr:04d}  {cells:<26} {asm}"
        lines.append(f"{text:<64}; {note}" if note else text.rstrip())

    def header(title: str) -> None:
        block(False)
        lines.append(f"## {title}")
        lines.append("")
        block(True)

    dead_cells = {a + i for a, (_, size) in dead.items() for i in range(size)}

    all_instrs = [ins for ins in (decode_at(mem, a) for a in sorted(all_code)) if ins]
    print_str_addr = next(k for k, v in e.names.items() if v == "print_str")

    def call_note(addr: int) -> str:
        target, ret = calls[addr]
        name = e.names.get(target, str(target)) if target is not None else "(indirect)"
        note = f"call {name} -> ret {ret}"
        arg = imm_stores_before(mem, all_instrs, addr).get(1)
        if target == print_str_addr and arg is not None and string_ok(mem, arg, len(mem)):
            snippet = decode_string(mem, arg).strip().replace("\n", " ")
            note += f'  "{snippet[:38]}{"..." if len(snippet) > 38 else ""}"'
        return note

    for start, kind, payload in sorted(segments):
        if kind == "code":
            addr = start
            if addr in e.names:
                role = e.names[addr]
                header(f"{addr:04d} — {role}" + (f": {NOTE_ROLES[role]}" if role in NOTE_ROLES else ""))
            elif addr in dead and addr - 1 not in dead_cells:
                header(f"{addr:04d} — dead code: the unreachable epilogue")
            block(True)
            text, size = all_code[addr]
            note = call_note(addr) if addr in calls else ""
            emit(addr, mem[addr : addr + size], text, note)
        elif kind == "str":
            block(True)
            n = mem[start]
            decoded = decode_string(mem, start)
            emit(start, [n], ".len", f'{payload}: "{decoded.replace(chr(10), chr(92) + "n")[:52]}"')
            for row in range(start + 1, start + 1 + n, 12):
                cells = mem[row : min(row + 12, start + 1 + n)]
                emit(row, cells, "")
        elif kind == "global":
            block(True)
            emit(start, [mem[start]], f".int {mem[start]}", str(payload))
        elif kind == "room":
            r = payload
            header(f"{r.addr:04d} — room: {r.name}")
            doors = ", ".join(
                f"{d} {e.rooms[p].name}" if p else f"{d} —" for d, p in zip(DIRECTIONS, r.doors)
            )
            emit(
                r.addr,
                mem[r.addr : r.addr + 7],
                ".room",
                f"hook {e.names.get(r.hook, r.hook)}; {doors}" if r.hook else doors,
            )
        elif kind == "item":
            item = payload
            if item.row == 0:
                header(f"{item.addr:04d} — the item table: [location, name, weight cell, hook]")
            hook = e.names.get(item.hook, str(item.hook)) if item.hook else "none"
            emit(
                item.addr,
                mem[item.addr : item.addr + 4],
                ".item",
                f"{item.name}: in {e.rooms[item.location].name}, weight {item.weight}, hook {hook}",
            )
        elif kind == "dirtab":
            header(f"{start:04d} — the direction-name table (door-slot order)")
            emit(start, mem[start : start + 4], ".ptr", "north, east, south, west")
        elif kind == "verbtab":
            header(
                f"{start:04d} — verb strings (searched in this order; a trailing "
                "space means prefix match, \\n whole-line)"
            )
            emit(
                start,
                mem[start : start + e.verb_count],
                ".ptr",
                ", ".join(repr(decode_string(mem, mem[start + i])) for i in range(e.verb_count)),
            )
        elif kind == "handlertab":
            block(True)
            emit(
                start,
                mem[start : start + e.verb_count],
                ".ptr",
                "handlers: " + ", ".join(e.names[h] for _, h in e.verbs),
            )
        elif kind == "bittab":
            header(f"{start:04d} — the target's {e.bit_count} bits, MSB first: bit = cell > {e.threshold}")
            for row in range(start, start + e.bit_count, 6):
                cells = mem[row : min(row + 6, start + e.bit_count)]
                bits = "".join("1" if c > e.threshold else "0" for c in cells)
                emit(row, cells, "", f"bits {bits}")
        elif kind == "powers":
            header(f"{start:04d} — 2^0 .. 2^{e.powers[1] - 1}: divmod's bit table")
            for row in range(start, start + e.powers[1], 4):
                emit(row, mem[row : min(row + 4, start + e.powers[1])], "")
        elif kind == "buffer":
            header(f"{start:04d} — the {e.buffer_len}-cell line buffer (-1-filled per read)")
            for row in range(start, start + e.buffer_len, 10):
                emit(row, mem[row : min(row + 10, start + e.buffer_len)], "")
    block(False)

    target = decode_target(mem, e)
    intro = "\n".join(
        [
            "# Day 25 — the complete listing (`day25.txt`)",
            "",
            f"> All {len(mem)} integers of `inputs/day25.txt`, every one accounted for:",
            f"> {len(listing)} live instructions plus {len(dead)} unreachable epilogue ones,",
            "> the position-salted string pool, the direction/verb/handler tables, the",
            f"> {e.bit_count}-bit target table, the powers-of-two table, the line buffer, and",
            f"> the {len(e.rooms)}-room, {len(e.items)}-item world. Generated by",
            "> [python/day25_disasm.py](../../python/day25_disasm.py) —",
            "> `python python/day25_disasm.py --full`. Not committed: the raw cells",
            "> republish the puzzle input (see `.gitignore`).",
            ">",
            "> The analysis behind the annotations is in",
            "> [day25_disassembly.md](day25_disassembly.md); this file is the evidence,",
            "> in address order. Notation: `[a]` position, `#n` immediate, `rb[+n]`",
            "> relative.",
            "",
            f"The bit table decodes to {target}: the target weight, and the password.",
            "",
            "",
        ]
    )
    return intro + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    full = "--full" in argv
    argv = [a for a in argv if a != "--full"]
    default = Path(__file__).resolve().parent.parent / "inputs" / "day25.txt"
    mem = parse_input(Path(argv[0] if argv else default).read_text())

    if full:
        sys.stdout.reconfigure(encoding="utf-8")
        print(full_listing(mem), end="")
        return

    engine = recover_engine(mem)
    pass1(mem, engine)
    pass2(mem, engine)
    pass3(mem, engine)
    pass4(mem, engine)
    pass5(mem, engine)


if __name__ == "__main__":
    main()
