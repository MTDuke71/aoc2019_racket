# Day 25 — disassembling the adventure engine

> Companion: [python/day25_disasm.py](../../python/day25_disasm.py) — run
> `python python/day25_disasm.py` for the five analysis passes, `--full` for
> the complete annotated listing (`day25_listing.md`, generated locally and
> gitignored because it reproduces the puzzle input cell for cell). Every
> number below is printed by the tool from the image, none is recalled.

The [Day 25](day25.md) input is a **complete compiled application**: a text
adventure with twenty rooms, thirteen items, a seven-verb parser and a
victory condition, in 4,807 cells — the year's largest Intcode image by more
than a factor of two (Day 13's game was 2,640, [Day 23](day23_disassembly.md)'s
network 2,243). And unlike every earlier image, more than half of it is not
code at all: **2,624 cells (54.6%) are text**, invisible to a casual dump
because of the string encoding below. The vendored decompiler's `hlr` pass —
which panicked on Day 23 — handles this image, and its output seeded the
function map that the Python tool then re-derives and verifies from address 0
outward.

## The shape of the image

```
0000..0033   main: enter(start_room); loop { print("Command?"); dispatch() }
0034..1127   string pool (headers, messages, direction names at 66..91)
1128..3093   36 functions with their globals interleaved, plus, at 1894..1983:
             verb-string table, the 33-cell TARGET TABLE, verb-handler table
2959..3009   2^0 .. 2^50 (divmod's bit table)
3094..3123   the 30-cell line buffer
3124..4600   twenty room structs, each followed by its name and description
4601..4652   the item table: 13 rows of [location, name, weight cell, hook]
4653..4806   the thirteen item-name strings
```

Recursive descent (Day 17's `rb[+0]` call idiom, 62 call sites) covers 536
live instructions; five short gaps between functions turn out to be **dead
code** — the compiler emits an `arb; ret` epilogue (behind a `jnz` to the
`hlt` where there is one) for *every* function, and the five hooks that halt
or loop forever strand theirs unreachable: 14 dead instructions, the
stranded-epilogue phenomenon [Day 21](day21_disassembly.md)'s `die` showed
once, here five times over. Three of the weigher's globals load as
`109, 0, 99` — junk that happens to decode as `arb #0; hlt` — which is why
the tool classifies data before it hunts for epilogues.

Indirect control flow comes in three flavours, all of which defeat plain
descent and one of which is an old friend:

- **hooks called through a frame slot** — `jnz #1 rb[-1]` where the slot
  holds a room's on-enter or an item's on-take function pointer;
- **a call through a global** — the bit decomposer parks its callback in a
  variable and jumps `jz #0 [2721]`;
- **a patched jump target** — the verb dispatch stores `handlers[i]` into
  the operand of the `jz #0 [0]` two instructions ahead and then executes
  it. Day 23's one-off boot trick is this engine's *regular calling
  convention*, exercised up to eight times per typed command.

30 self-modifying stores in total, every one an operand patch (Intcode still
has no indexed addressing; this is how every table in this guide is read).

## Strings that are never ASCII

`put_decoded`, the three-instruction leaf under `print_str`, is the whole
cipher:

```
1256  arb #5
1258  add rb[-4] rb[-3] rb[-1]     ; cell + index
1262  add rb[-2] rb[-1] rb[-1]     ; + length
1266  out rb[-1]
```

A string is a length prefix followed by cells holding `char − (index +
length)`. The same letter encodes differently at every position and in every
string — `"north"` is `105 105 107 108 95` — so grepping the image for
ASCII, which works on Days 17 and 21, finds nothing. 87 strings decode this
way: 22 fixed messages, 20 room names, 20 room descriptions, 13 item names,
7 verbs, 4 directions, ~2,500 characters in all.

The verb table is the parser: `match_char` decodes one character, maps a
newline to −1 (the buffer's empty-cell fill), and compares. So a verb ending
in `\n` (`north`, `inv`) must match the **whole line**, while `take ` and
`drop ` (trailing space) are **prefixes** and the item name is matched
separately at offset 5 with an exact-end check. Command parsing, string
compare, and buffer sentinel in one 12-instruction callback.

## The world as data

`main` passes one pointer to `enter_room` and the whole ship unrolls from
it. A room is seven cells — `[name, description, on-enter hook, north,
east, south, west]`, the door slots in the order of the direction-name
table at 66, which is also why `do_north..do_west` are four one-line
handlers calling `move(3)..move(6)`. Doors are pointers at other rooms; the
tool checks that **every door is reciprocated by its opposite door** (the
graph is undirected), and the walk from the start pointer reaches all 20
rooms — the 19 the live droid enters, plus the Pressure-Sensitive Floor,
which it only ever bounces off.

Exactly one room has a non-zero hook. It is the floor, and its hook is the
weigher. Everything else on the ship — every death, every joke — lives in
the item table.

## The item table

Thirteen rows of `[location, name pointer, weight cell, on-take hook]`,
location −1 meaning "carried" (the same sentinel `do_inv` scans for). The
weight cell is obfuscated with the same affine-by-position idea as the
strings: **weight = cell − 27 − row**. Eight items carry real weights; five
carry a hook, and all five weigh **exactly 0** — their cell is precisely
the salt-plus-row zero point, so even the engine considers a trap
weightless.

The hooks, called *in vitro* on the live machine (return address planted on
a `hlt` outside the image, exactly the harness Day 23 used on its divide):

| item | hook does | outcome |
|---|---|---|
| escape pod | prints `You're launched into space! Bye!` | `hlt` |
| molten lava | prints `...You melt!` | `hlt` |
| photons | prints `...You are eaten by a Grue!` | `hlt` |
| infinite loop | prints `You take the infinite loop.` **forever** | never returns |
| giant electromagnet | sets `[1129] = 1` and returns politely | session poisoned |

The infinite loop's joke is structural: its "you take it" message *is* the
loop body. The electromagnet is the subtle one — nothing halts, but
`dispatch` checks `[1129]` before matching any verb and answers every later
command, even `inv`, with the stuck message. Three deaths kill the machine,
one kills time, one kills the session; `take_is_survivable`'s three checks
(halted / budget expired / no room header) are these five hooks sorted into
their equivalence classes, and the suite pins that the probe's five
rejections are exactly the five hooked rows.

## The weigher

The floor's hook, in full:

1. zero `[1550]`, then fold the item table through `add_item_weight`:
   every row with location −1 contributes `cell − 27 − row`;
2. compute the threshold: `mul [2486] [1352] [1551]` — **84 × 52 = 4368**,
   a constant shipped as a product of two globals for no reason but
   obfuscation;
3. `split_bits(weight, 33, check_bit)`: a recursive divide-by-doubling
   that emits the weight's 33 bits **MSB first** (the recursion doubles a
   power up to 2³³, then unwinds — compare `divmod`, which does the same
   job iteratively over the 2⁰..2⁵⁰ table at 2959);
4. `check_bit` compares bit *i* against the table at 1901: the expected
   bit is stored as a cell **greater or less than 4368** — the actual bit
   values never appear in the image — and the first difference sets the
   verdict: droid bit 1 where the table says 0 → heavier; 0 where it says
   1 → lighter. First-difference-MSB-first is lexicographic order, which
   on equal-length bit strings *is* numeric order — the engine performs
   `cmp(weight, target)` without ever materialising the target;
5. verdict −1 or +1: print the alert and re-enter the checkpoint (the
   ejection). Verdict 0: `open_and_reveal`.

## Target is answer

`open_and_reveal` prints the airlock speech in three pieces: the
`Analysis complete!` text, then — `print_number([1550])` — **the droid's
own weight**, then ` on the keypad...`. The password is not stored
anywhere; it is *recomputed from your inventory* every time someone opens
the door. Which means the 33-cell table at 1901 does not merely gate part 1
— it **is** part 1:

```
cells > 4368 →  000000000001010000000010000001000₂  =  2622472
```

`static_password` reads the answer off the disk in ~9 ms, VM never started
— against ~2.9 s for the played game. Day 23's rhyme continues: that input
was generated from its own part-2 answer; this one *stores* its answer, one
bit per cell, behind a comparison with 84×52.

And the search the shipping solution runs is revealed as a designed
non-search: the eight safe weights are **eight distinct powers of two** —
2³, 2⁷, 2¹⁰, 2¹³, 2¹⁹, 2²¹, 2²², 2³⁰ — so all 256 subsets weigh
differently, the winning load-out is unique, and its members are literally
the 1-bits of the target: 2622472 = 2²¹ + 2¹⁹ + 2¹⁰ + 2³ = fixed point +
prime number + antenna + whirled peas. The puzzle is SUBSET-SUM with a
planted unique solution, and the planting *is* binary notation.

Pass 5 closes the loop live: carry exactly the static four to the
checkpoint and the door opens on the **first** try, password in the speech.

## The two divides

The engine ships two integer-division routines, neither shared with the
other and both cousins of Day 23's divide at 436:

- `split_bits` (2722/2763): recursive, table-free — doubles the divisor on
  the way down, subtracts on the way up, and hands each quotient bit to a
  callback instead of assembling a number. Division as a *stream of bits*,
  which is exactly what the comparator wants.
- `divmod` (3010): iterative restoring division over the 2⁰..2⁵⁰ table,
  returning quotient and remainder — the loop under `print_digits`'
  recursion. Its 51-entry table exists to print **one number, once**: the
  password is the only numeric output in the entire game.

## Tests pinned by this analysis

From `test_day25.py` (all real-input tests skip gracefully on a clean
clone): the live sweep agrees with the static engine on the map, the item
placement, and — item for item — the five traps; the static password
equals the live game's; the safe weights are distinct powers of two, traps
weigh 0, and the unique subset sums to the target; the five hooks behave in
vitro as the table above says (the electromagnet's flag then locks the live
dispatcher, pinned by taking it in a fork and asking for `inv`); and
`full_listing` accounts for all 4,807 cells or raises.
