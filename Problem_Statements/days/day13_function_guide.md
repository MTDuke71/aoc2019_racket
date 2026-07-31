# Day 13 — Care Package (function guide)

> The Intcode VM ([Day 9](day09_function_guide.md), stepped with
> [Day 7](day07_function_guide.md)'s block/resume protocol) becomes an
> **arcade cabinet** — a Breakout clone with walls, bricks, a paddle and a
> ball. Nothing about the machine changes; this is the first day where the
> VM is *imported as a library* rather than re-derived, because the
> instruction set froze at Day 9 and everything interesting has moved to the
> peripheral. Three ideas carry the day, and none of them are opcodes.
> **(1) Output is a display protocol**: a flat integer stream that is really
> a stream of `(x, y, tile)` triples, and framing it is the whole of Part 1.
> **(2) One triple is out of band**: `(x, y) = (-1, 0)` carries the *score*
> instead of a tile — a sentinel-tagged union smuggled down an untyped wire,
> which is a real protocol-design pattern with a real name. **(3) Input is a
> control loop**: Part 2 patches memory address 0 to `2` for free play, and
> the program starts asking for the joystick. The answer is one line,
> `(sgn (- ball paddle))`, and that line is a *bang-bang controller* whose
> correctness has an actual proof rather than a shrug.
> [day13_disassembly.md](day13_disassembly.md) takes the cabinet apart and
> finds the first Intcode program that reads like **compiler output** — a real
> calling convention, a 15-cell stack, a heap of two 1,000-cell arrays — and
> therefore the first one static recursive descent recovers *completely*. It
> also finds that the free-play poke is not a flag but an **opcode rewrite**
> (`add` → `mul` at address 0), and that both of this day's answers are
> arithmetic on the disk image: the starting screen is a literal 40×25 tile
> array, and the score is an order-independent sum over a point-value table
> hidden behind an affine permutation. The game never had to be played.

## The puzzle in one paragraph

The Intcode program is an arcade game. It draws by emitting output in groups
of three: `x` (distance from the left), `y` (distance from the top), and a
tile id — `0` empty, `1` wall, `2` block, `3` horizontal paddle, `4` ball.
**Part 1:** run the game as shipped and count the *block* tiles on the screen
when it exits. **Part 2:** set memory address `0` to `2` (the cabinet's
"quarters inserted" cell) to play for free. The game now reads a joystick
(`-1` left, `0` neutral, `1` right) and reports the score through a fourth
kind of draw command: a triple whose `(x, y)` is `(-1, 0)` sets the score
display rather than painting a tile. Break every block; report the final
score. On the real input the board is **40 × 25** with **348 blocks**, and
the winning score is **16999**.

---

## The algorithm in Python

Day 13 is *interpreter-flavored* like Days 5/7/9/11, so the Python companion
([python/day13.py](../../python/day13.py)) mirrors the Racket almost
statement-for-statement. The VM class is byte-for-byte
[python/day11.py](../../python/day11.py)'s; only the driver is new:

```python
EMPTY, WALL, BLOCK, PADDLE, BALL = range(5)

def commands(vm, joystick):
    """Yield the cabinet's (x, y, tile) draw commands until it halts."""
    outs = []
    while True:
        result = vm.step()
        if result == "blocked":
            vm.inputs.append(joystick())      # called NOW, not earlier
        elif result == "halted":
            return
        elif isinstance(result, tuple):
            outs.append(result[1])
            if len(outs) == 3:
                yield (outs[0], outs[1], outs[2])
                outs = []

def screen(program):
    tiles = {}
    for x, y, tile in commands(VM(program), unreachable):
        tiles[(x, y)] = tile             # last write wins: this is a frame
    return tiles

def part1(program):
    return sum(1 for tile in screen(program).values() if tile == BLOCK)

def play(program, quarters=2):
    vm = VM(program)
    if quarters is not None:
        vm.mem[0] = quarters                       # insert two quarters
    score = 0
    ball = paddle = 0
    for x, y, tile in commands(vm, lambda: (ball > paddle) - (ball < paddle)):
        if (x, y) == (-1, 0):
            score = tile                           # sentinel: a score, not a tile
        elif tile == BALL:
            ball = x
        elif tile == PADDLE:
            paddle = x
    return score
```

Two things the Python version says more loudly than the Racket:

- **`commands` is a generator, and that is exactly the right shape.** The
  consumer's loop body runs *between* yields, so `ball` and `paddle` are
  already updated by the time the generator resumes and calls `joystick()`.
  Python's coroutines hand you for free the interleaving that
  [src/day13.rkt](../../src/day13.rkt) spells out as an explicit recursive
  loop — and it is the same interleaving the VM itself needs, one level down.
  Two nested coroutines: the Intcode machine yielding to its driver, the
  driver yielding to the player.
- **`(ball > paddle) - (ball < paddle)`** is Python's idiom for `sign`, since
  `bool` is an `int`. Racket just has `sgn`.

Running `python python/day13.py` against the real input independently
confirms **348** and **16999**, and prints the identical starting board.

---

## The VM stops being the lesson: `src/intcode.rkt`

Days 2 → 5 → 7 → 9 each *changed* the machine, so each of those days owns its
own copy of it: the diff between consecutive copies **is** the lesson, and the
function guides annotate them line by line.

That era ended at [Day 9](day09_function_guide.md). Relative mode plus opcode
9 completed the instruction set — the puzzle text even said so ("the BOOST
program will output a *complete* Intcode computer"). Day 11 still pasted the
machine into `src/day11.rkt` because its guide walks that code as content.
From Day 13 on, every Intcode day is a **driver** problem: the puzzle is the
world you wire around an unchanging CPU. So the machine moves once, into
[src/intcode.rkt](../../src/intcode.rkt), which Day 13 requires and Days
15/17/19/21/23/25 can require as they land:

```racket
(provide
 step-result/c
 (contract-out
  [vm?         (-> any/c boolean?)]
  [make-vm     (-> (vectorof exact-integer?) vm?)]
  [vm-halted?  (-> vm? boolean?)]
  [vm-enqueue! (-> vm? exact-integer? void?)]
  [vm-poke!    (-> vm? exact-integer? exact-integer? void?)]
  [vm-step!    (-> vm? step-result/c)]))
```

The body is Day 11's `vm-step!` unchanged. Two deliberate choices:

- **Day 11's copy stays put.** Rewriting it to a `require` would strand its
  guide's annotation on code that no longer exists. Duplication across a
  teaching artifact and a library is a *fine* trade when the artifact's whole
  job is to be read a year later.
- **`vm-poke!` is new**, and it earns its place: some puzzles state a
  precondition as a *memory edit* rather than as input.
  [Day 2](day02_function_guide.md)'s `(noun, verb)` was one; Day 13's "set
  address 0 to 2" is another. That is a different channel from opcode 3, and
  the API should say so.

`step-result/c` is worth a second look — it is a contract for a *return
value*, which is where Racket's contract system does the work a sum type
would do in a typed language:

```racket
(define step-result/c
  (or/c 'ran 'blocked 'halted (list/c 'output exact-integer?)))
```

`or/c` is a union; `list/c` describes a fixed-length list element by element.
Together they say "one of three symbols, or a two-element tagged list whose
second element is an integer" — Rust's
`enum Step { Ran, Blocked, Halted, Output(i64) }` written as a runtime
predicate instead of a compile-time type. The cost is that it is checked on
every single one of the ~610 000 `vm-step!` calls a Part 2 run makes; the
benchmark section below has the bill.

---

## The Day 13 code, form by form

### `next-command!` — framing a flat stream into triples

```racket
(define (next-command! machine joystick)
  (let loop ([outs '()])
    (match (vm-step! machine)
      ['blocked (vm-enqueue! machine (joystick)) (loop outs)]
      ['ran     (loop outs)]
      [`(output ,n)
       (define outs* (cons n outs))
       (if (= 3 (length outs*)) (reverse outs*) (loop outs*))]
      ['halted  #f])))
```

Structurally this is [Day 11](day11_function_guide.md)'s `run-to-outputs!`
with `2` changed to `3` — but the change of number changes what the function
*means*. Day 11's pair was a *command with two fields* (paint, turn). Day
13's triple is a **frame in a stream**: the program will emit thousands of
them, and the caller consumes them one at a time in a loop rather than once
per world-cycle. In protocol terms this is **framing** — recovering message
boundaries from a byte (here, integer) stream that has none. Intcode's output
channel is unframed: nothing in `4 <val>` says "this is the last field of a
command". The framing is a convention the two ends agree on out of band, in
the puzzle prose. That is the same problem a UART, a TCP-based protocol, or a
chess engine's UCI parser has, and the same solution: fix the record length
(or a delimiter) by agreement, then count.

Three Racket details worth restating for a cold reader:

- **`match` on `vm-step!`'s return value.** `` `(output ,n)`` is a quasiquote
  pattern: it matches the two-element list `(output <something>)` and binds
  `n` to that something, in one line. The symbols `'blocked` / `'ran` /
  `'halted` are literal patterns. This is the consumer half of the sum type
  `step-result/c` describes.
- **The accumulator is built backwards and reversed.** `(cons n outs)` is
  O(1) and produces reverse order; `reverse` at the end costs one pass over
  three elements. The alternative — `(append outs (list n))` — is O(n) per
  element and is the classic quadratic-accumulator mistake.
- **`#f` for "halted".** Day 11 returned a short list and let the caller
  check its length; here `#f` is a cleaner end-of-stream marker because the
  caller `match`es it as its own clause. A trailing partial triple (one or
  two outputs, then halt) can't happen with a well-formed cabinet, and
  treating halt as end-of-stream regardless keeps the driver total rather
  than erroring on a malformed program.

### The joystick is a *thunk*, and that is the whole trick

Look at the type of the second parameter. Day 11 passed the camera reading as
a **value**:

```racket
(run-to-outputs! machine camera)          ; Day 11 — a number
(next-command!   machine joystick)        ; Day 13 — a procedure of no args
```

Day 11 could get away with a value because it re-entered the driver once per
robot cycle, and the camera reading for that cycle was known at the moment of
the call. Day 13's driver is re-entered once per *draw command*, and the
program emits many draw commands between joystick reads — including the draw
commands that tell you where the ball now is. If the joystick were a value,
it would be a snapshot taken before the frame was drawn, and the paddle would
always be reacting to the previous frame.

Making it a thunk moves the evaluation to the instant `vm-step!` reports
`'blocked`:

```racket
['blocked (vm-enqueue! machine (joystick)) (loop outs)]
```

This is **call-by-need at the call site**, hand-rolled: the caller passes a
*computation*, not a result, and the callee decides when (and whether) to run
it. Racket has `delay`/`force` promises and `lambda ()` thunks for this;
Haskell would get it for free from laziness; Rust would take an
`impl FnMut() -> i64`. The general name for the pattern is a **callback**,
but the specific reason it is needed here is worth naming precisely: the
value's *freshness* matters, not just its existence.

### `screen`, `count-tiles`, `part1` — the board as a last-write-wins frame

```racket
(define (screen program)
  (define machine (make-vm program))
  (let loop ([tiles (hash)])
    (match (next-command! machine no-joystick)
      [#f tiles]
      [(list x y id) (loop (hash-set tiles (cons x y) id))])))

(define (count-tiles tiles id)
  (for/sum ([t (in-hash-values tiles)]) (if (= t id) 1 0)))

(define (part1 program) (count-tiles (screen program) BLOCK))
```

`hash-set` on an immutable hash returns a *new* hash sharing structure with
the old one (a HAMT — the same persistent-map machinery
[Day 3](day03_function_guide.md) leaned on), so this fold is cheap despite
looking like it copies a 1000-cell board a thousand times.

The important semantic is **last write wins**. The puzzle asks for the blocks
on screen *"when the game exits"*, not for the number of block-drawing
commands. Those differ the moment a coordinate is redrawn — which is exactly
what happens on every ball movement in Part 2 (the old cell is repainted
empty). Modelling the screen as a map from coordinate to tile makes "the
final frame" the default and "the draw log" the thing you'd have to work for.
Day 11's hull made the opposite choice for the opposite reason: there,
`hash-count` had to mean "painted at least once", so absence of a key was
load-bearing. Same data structure, two different questions, and in both cases
the question decided the encoding.

`no-joystick` is a procedure that raises:

```racket
(define (no-joystick)
  (error 'screen "the cabinet asked for joystick input before free play"))
```

Part 1 runs the cabinet with its single shipped quarter, so it draws the
board and halts without ever reading input. If it *did* read, guessing a
value would silently produce a wrong answer; failing loudly is the right
call. This is the same instinct as `unreachable!()` in Rust — encode "this
branch is impossible" as a crash, not as a default.

### `render` and the glyph table

```racket
(define glyphs (hash EMPTY #\space WALL #\█ BLOCK #\# PADDLE #\= BALL #\o))
```

A hash from tile id to character, and `render` is
[Day 11](day11_function_guide.md)'s bounding-box-over-a-sparse-hash with one
difference: every cell is drawn here (walls included), so the bounding box is
the whole cabinet screen rather than the ink. `#\█` is a literal character —
Racket source is UTF-8 and `#\<char>` takes any of them, so the box-drawing
glyph needs no escape.

`render` is not part of any answer. It earns its place twice: it is how you
*notice* a framing bug (an off-by-one in the triple chunking scrambles the
board into visible noise rather than producing a plausibly-wrong integer),
and it turns "348" into something a human can look at.

### `play` — three integers, and one poke

```racket
(define (play program #:quarters [quarters 2])
  (define machine (make-vm program))
  (when quarters (vm-poke! machine 0 quarters))
  (let loop ([score 0] [ball 0] [paddle 0])
    (match (next-command! machine (lambda () (sgn (- ball paddle))))
      [#f score]
      [(list -1 0 v) (loop v ball paddle)]
      [(list x _ id)
       (loop score
             (if (= id BALL)   x ball)
             (if (= id PADDLE) x paddle))])))
```

**The state is three integers.** Not a board — a score and two x
coordinates. This is the single most interesting line-level fact about the
day, and it is easy to miss because the natural first draft carries the
screen hash along out of sheer momentum (Part 1 needed it, so Part 2 must,
right?). It doesn't:

- the **y** of everything is irrelevant, because the paddle only moves
  horizontally, so tracking is a one-dimensional problem;
- the **blocks** are irrelevant, because they break on contact whether or not
  the player knows where they are;
- the **walls** are irrelevant, because the ball bounces off them without the
  player's participation.

A 1000-cell screen collapses to three numbers. The benchmark section measures
what carrying the hash anyway would have cost.

**The match clause order is load-bearing.** `[(list -1 0 v) ...]` must come
before `[(list x _ id) ...]`, because `-1` and `0` are literal patterns and
the general clause would happily bind `x` to `-1`. Racket's `match` tries
clauses top to bottom, first match wins — the same discipline as a Haskell
function's equations, or a Rust `match` (except Rust warns on an arm the
earlier ones already cover, and Racket will not). The `_` in the general
clause is the wildcard: y is matched and discarded, documenting that the
value exists and is deliberately unused.

**`#:quarters` is a keyword argument with a default.** Racket keyword
arguments are part of the function's contract:

```racket
[play (->* ((vectorof exact-integer?))
           (#:quarters (or/c #f exact-integer?))
           exact-integer?)]
```

`->*` takes a list of mandatory argument contracts, a list of optional ones,
and a result contract. Passing `#f` skips the poke entirely, which is how the
tests drive scripted cabinets whose address 0 is a real instruction they need
back. The Rust analogue is `Option<i64>` plus a builder or a
`play_with(program, Some(2))`; Racket's keyword-with-default is closer to
Python's `def play(program, quarters=2)`.

### `solve`

Prints Part 1, then the starting board, then Part 2. The board isn't an
answer; it's between the two parts because that's where it explains the
first one and previews the second.

---

## The problem within the problem, #1: in-band signaling

The score arrives through the *same* channel as the tiles, distinguished only
by an impossible coordinate:

```
 1  2  3      →  paddle at (1,2)
-1  0  16999  →  the score is 16999
```

This is **in-band signaling**: control information multiplexed onto a data
channel, with a reserved value marking the switch. The name comes from
telephony — the [blue box](https://en.wikipedia.org/wiki/Blue_box) worked
because AT&T's 2600 Hz supervisory tone travelled on the same wire as the
voice, so a whistle in the right pitch was indistinguishable from the
network's own control signal. Once you have the name, the pattern is
everywhere:

| System | Data | Sentinel |
|---|---|---|
| C `getchar` | a byte, `0..255` | `EOF` = `-1`, which is why it returns `int` |
| POSIX `read` | a byte count | `-1` = error, real code in `errno` |
| SQL | a column value | `NULL` |
| Floating point | a real number | `NaN`, and its payload bits |
| Sentinel-terminated strings | characters | `'\0'` |
| Day 13 | a tile at `(x, y)` | a tile at `(-1, 0)` |

The pattern's failure mode is always the same: the sentinel must be a value
the data channel can never legitimately produce. C's `getchar` needs a return
type *wider* than a byte so `-1` is not a valid character; assigning it to a
`char` is a classic bug. Day 13's screen coordinates are non-negative, so
`(-1, 0)` is safely outside the domain — but note the puzzle takes care to
specify *both* coordinates. `x = -1` alone would be enough on this board; the
program pins `y = 0` too, which is belt-and-braces against a future screen
that scrolls.

**What a typed language does instead.** Rust would make the framing produce a
sum type and let the compiler enforce the split:

```rust
enum Command { Draw { x: i64, y: i64, tile: Tile }, Score(i64) }

fn frame(a: i64, b: i64, c: i64) -> Command {
    if (a, b) == (-1, 0) { Command::Score(c) }
    else { Command::Draw { x: a, y: b, tile: Tile::from(c) } }
}
```

The decoding still happens — someone has to compare against `(-1, 0)` — but
it happens *once*, at the boundary, and every downstream `match` is
exhaustiveness-checked. Racket's `match` clause order does the same job with
no type declaration and no compiler check, which is the trade this repo keeps
making: contracts at the module boundary, patterns inside.

Worth noticing: the Racket code above never actually *builds* a `Command`
value. The `match` in `play` is the decoder and the consumer at once, fused.
That is idiomatic in a dynamically-typed functional language and would be
considered sloppy in Rust — not because it's wrong, but because naming the
intermediate type is where a compiler can start helping you.

---

## The problem within the problem, #2: the player is a bang-bang controller

```racket
(lambda () (sgn (- ball paddle)))
```

One line, and it wins a game of Breakout. It deserves better than "obviously
you follow the ball."

### It has a name

This is a **bang-bang controller** (also *on-off controller*, or in control
theory a *relay controller*): the actuator has finitely many settings —
here `{-1, 0, +1}` — and the control law is the *sign* of the error signal
`e = ball − paddle`. There is no proportional term, no integral, no
derivative; there is no notion of "a little bit left". A household
thermostat is the canonical example, and so is a chess engine's null-move
pruning switch: the input is continuous, the output is a decision.

Bang-bang control is not a poor man's PID. When the actuator is genuinely
discrete — as here, where the paddle moves 0 or 1 cells per tick and nothing
in between — a proportional controller *cannot be implemented*, and
bang-bang is the optimal policy for the class of minimum-time problems this
belongs to (the relevant result is Pontryagin's maximum principle: for
time-optimal control of a system with bounded input, the optimal control is
bang-bang). The joystick's three positions are the bounded input, and
"get the paddle under the ball as fast as possible" is the time-optimal
problem.

### Why it cannot lose here

Let `g = ball_x − paddle_x` be the error. Each tick the ball moves diagonally
(`Δball_x = ±1`, always, because that is the puzzle's stated movement rule)
and the paddle moves by our joystick reading, `sgn(g)`. So:

```
g' = g + Δball_x − sgn(g)
```

- If `g > 0`: `sgn(g) = 1`, so `g' = g + Δball_x − 1 ∈ {g − 2, g}`.
- If `g < 0`: symmetric — `g' ∈ {g, g + 2}`.
- If `g = 0`: `g' = Δball_x = ±1`.

**`|g|` never increases while `|g| ≥ 1`**, and it strictly decreases (by 2)
on every tick where the ball moves *toward* the paddle's chase direction. The
paddle's top speed equals the ball's horizontal speed, so once the gap is
closed it can be held: the system reaches `|g| ≤ 1` and stays inside it
forever. That is the invariant. There is no oscillation to worry about — the
classic bang-bang pathology, *chattering* around the setpoint, is harmless
when the setpoint is a moving target you only need to shadow.

The one-tick lag is real and does not matter: the joystick is answered from
the ball position drawn on the *previous* frame, so the paddle is chasing
where the ball was. Since the ball's horizontal speed is exactly 1, chasing
its last known position keeps `|g| ≤ 1` rather than `g = 0` — which is
sufficient, because the ball's descent to the paddle row takes many ticks and
the gap closes long before it matters.

### The precondition: a chasing paddle can only *hold* the gap

The invariant cuts both ways, and the second edge is easy to miss. `|g|` never
grows — but by the same arithmetic it never shrinks either, unless the ball is
moving *toward* the paddle. If the paddle is behind a receding ball, `Δball_x`
and `sgn(g)` have the same sign and `g' = g + 1 − 1 = g` **exactly**. Traced
from a patched starting position:

```
LOSS   ball x=24, paddle x=20 (paddle behind, ball moving right)
  tick 1: ball=(24,20) vel=(1,1) paddle=20  gap=-4
  tick 2: ball=(25,21) vel=(1,1) paddle=21  gap=-4
  tick 3: ball=(26,22) vel=(1,1) paddle=22  gap=-4
  tick 4: ball=(27,23) vel=(1,1) paddle=23  gap=-4   -> y=24, game over
```

Four ticks, four cells of chase, zero cells gained. It would make no difference
if there were three hundred ticks: a tracking paddle behind a receding ball
gains nothing, ever. The gap closes only at a *reversal*, when the ball turns
around and comes back at `2` cells per tick.

So the controller is safe once it is under the ball, and powerless to get there
against a receding one. The shipped starting state hands it a solved
precondition — the paddle is already ahead of the ball, on the side the ball is
travelling toward:

```
WIN    ball x=18, paddle x=20 (paddle ahead)
  tick 1: ball=(18,20) paddle=20  gap=+2
  tick 2: ball=(19,21) paddle=19  gap=+0     <- closed at 2/tick
  tick 3: ball=(20,22) paddle=19  gap=-1     <- intercept
  tick 4: ball=(21,21) vel=(1,-1) …          <- bounced; |g| = 1 for the next 4,774 ticks
```

Tick 3 is worth a second look: the pre-move gap is `−1`, and it still
intercepts. The joystick is read at address 75 and the paddle moves *before*
the physics runs in the same tick, so the paddle steps to 20 and only then does
the `y` probe check `tile(20,23)` and find it. That is the payoff for
`next-command!` taking a **thunk**: a joystick value computed one instruction
earlier would leave the paddle a cell behind and this interception would fail.

### Is 4,778 the fastest possible?

The score is start-independent, so "better" can only mean *fewer ticks*.
Sweeping every legal paddle column (1..38) against ball starts near it
(offsets −2..+2 on the shipped row, all four initial velocities) — 736
configurations, 624 of them wins:

| | ticks | score |
|---|---:|---:|
| best (ball 26, vel (1,−1)) | **4,025** | 16999 |
| shipped (ball 18, vel (1,1)) | 4,778 | 16999 |
| median of 624 wins | 6,392 | 16999 |
| worst (ball 27, vel (1,1)) | 10,531 | 16999 |

So no: the shipped start ranks 23rd of 624, top 4% but beaten by 15.8%. Every
one of the 624 scores 16999, which is order-independence confirmed at a scale
the argument alone can't reach.

The structural result is better than the numbers, though. Of the **152**
distinct ball start states with at least one win, the number whose tick count
depends on where the paddle started is **zero**. Paddle 25, 26, 27 and 28 all
clear in exactly 4,025 given the ball at 26. The paddle's column decides only
*whether* you win, never *how long* — because under tracking the paddle is a
**pure mirror**: it arrives directly beneath the ball, and a straight paddle hit
flips `dy` exactly like a wall hit. Its starting offset washes out in the first
few ticks, before the first interception.

**But the paddle is only a mirror because *this* controller makes it one.**
Probe 3 (address 264) fires when probes 1 and 2 both miss, and it flips **both**
`dx` and `dy`. A paddle at `(ball_x + dx, 23)` rather than `(ball_x, 23)` takes
a *corner hit* and sends the ball back the way it came, where a straight hit
lets it continue. One cell of positioning is one bit of steering per bounce. A
controller that deliberately chose corner hits is not covered by this sweep and
could plausibly beat 4,025 — which is precisely the boundary named below: it
would be search, not control.

### The ball is a bouncing DVD logo, and that is a theorem

Watch the animation for a minute and it starts to look like the DVD screensaver.
That is not a loose resemblance — it is the same dynamical system, and the
identification pays.

`dx` and `dy` are only ever *negated*, never zeroed, so the ball moves
diagonally on **every** tick: a 45° billiard in a rectangle, which is what the
logo is. The immediate consequence is a conserved quantity:

> **`(x + y) mod 2` is invariant.** Each tick changes `x` by ±1 and `y` by ±1,
> so their sum changes by 0 or ±2. The ball lives on one colour of a
> checkerboard, forever.

Measured over the real run: **400** distinct cells occupied out of 874 interior
cells, and **zero** odd-parity cells in 4,778 ticks.

**The corner question, answered.** The logo's folk-question — will it ever land
exactly in a corner? — is decidable here. The ball starts at `(18,20)`, so its
class is even. The interior corners are `(1,1)` and `(38,22)` (even) and
`(38,1)` and `(1,22)` (odd). The ball can **never** touch the odd two, no
matter how long you watch. And on this input it lands on `(1,1)` *twice*.

**Half the blocks are on cells the ball cannot occupy** — 177 even, 171 odd —
and it clears them anyway, because a block is broken by *probing* a neighbour,
not by entering it. Probes 1 and 2 read `(x+dx, y)` and `(x, y+dy)`, both
parity-flipped. So the reachable set for *breaking* is the whole board while
the reachable set for *being* is half of it. The collision design quietly
depends on that; a version that broke blocks by occupying them would be
unsolvable on this board.

**And the late-game feeling has a number.** Unfold the reflections (the mirror
trick from the [predictive-controller sidebar](#why-it-cannot-lose-here)) and
the trajectory on an emptied board is a straight line on a torus: horizontal
period `2 × 37`, vertical `2 × 21`, so the orbit closes every
`lcm(74, 42) = 1554` ticks. The whole game is 4,778 ticks — 3.07 orbits. It
never completes a clean one: the longest drought between block breaks is 140
ticks against a median of 3. The stretches that look like the screensaver are
the ball transiting the cleared lower half on a long diagonal before finding
something at the top.

That periodicity is also a **third non-termination mode**, distinct from the
[collision livelock](day13_disassembly.md#the-fixed-point-has-no-bound--the-cabinet-can-livelock)
and from losing: the orbit is closed, so if the last surviving blocks sat off
the current orbit, the ball would circle forever and the game would never halt.
Breaking a block perturbs the orbit, which is why it never happens — all 624
wins in the sweep halted — but "the ball provably cannot reach what is left" is
a legitimate failure state for this program, not a hypothetical.

**What would break it.** Every hypothesis in that proof is load-bearing, and
naming them is how the technique transfers:

- *If the paddle were slower than the ball* (say it moved 1 cell every 2
  ticks), `|g|` could grow and the invariant collapses. You would need to
  predict the ball's landing column and start moving early — a *feedforward*
  controller instead of feedback.
- *If the ball accelerated* (many real Breakout clones speed the ball up as
  bricks clear), same collapse, same fix.
- *If the paddle had to be positioned to aim the bounce* — to clear a
  specific brick — tracking would be adequate but not optimal, and you would
  be doing search, not control.

The predictive alternative is the standard next step: simulate the ball
ballistically (it travels in straight diagonal lines, reflecting off walls,
so its landing column is computable in closed form by unfolding the
reflections — the same *mirror trick* as the classic light-in-a-box problem)
and drive the paddle straight there. On this input it buys nothing, because
tracking already never misses. It is worth knowing as the thing you reach
for the moment the paddle loses its speed parity with the ball.

### Did we actually win?

The program halts either when the last block breaks *or* when the ball gets
past the paddle — and in both cases `play` returns "the last score it saw".
So a returned number is not by itself proof of a win. Instrumenting the run
settles it:

```
score events   : 349
first three    : (command #1000 -> 0) (#1022 -> 14) (#1048 -> 87)
last two       : (#20262 -> 16934) (#20804 -> 16999)
final score    : 16999
blocks left    : 0        balls left: 1     paddles left: 1
game ticks     : 4778     (joystick reads)
draw commands  : 20805
vm-step! calls : 609973
```

**349 score events = 1 + 348.** The first lands at draw command #1000 — that
is, immediately after the 1000-cell opening board is painted — and its value
is `0`: the segment display being initialised. The remaining **348 are
exactly the 348 blocks** from Part 1, one score update per brick destroyed
(the first brick is worth 14, the last is worth 65). And the final board,
re-rendered at halt, is empty: no blocks, one ball, one paddle. The game was
won, not lost, and the two parts cross-check each other — Part 1's answer is
derivable from Part 2's event count.

That is a much stronger check than "the number looks plausible", and it is
the kind of thing worth instrumenting even after the star is collected.

---

## Watching it run: two peripherals, one driver

It's a *game*. Nothing in this repo so far has had a picture worth animating,
and this one has walls, blocks, a paddle and a ball. So
[scripts/day13_arcade.rkt](../../scripts/day13_arcade.rkt) puts it on a screen:

```
racket scripts/day13_arcade.rkt              # a window, the AI plays
racket scripts/day13_arcade.rkt --human      # a window, YOU play (arrow keys)
racket scripts/day13_arcade.rkt --terminal   # ANSI animation in the console
racket scripts/day13_arcade.rkt --heat       # colour blocks by their point value
racket scripts/day13_arcade.rkt path/to.txt  # one specific board
```

With no path it offers every `inputs/day13*.txt` it finds, so a second user's
program sits alongside this one: number keys pick the board on the window's
start screen, or type a number at the terminal's prompt. That is not a cosmetic
feature — the two boards are **different sizes** (40×25 and 45×24), which broke
two things worth naming. The window had `W`/`H` and the paddle row hardcoded;
they now come from `screen-geometry`, which measures the board off the *opening
frame* rather than the code, since the repaint `prime!` absorbs draws every cell
exactly once and therefore already knows how big the board is and where the
paddle sits. And `--heat` read the hash constants from fixed operand cells,
which silently yields the wrong table on any other input — see
[the disassembly](day13_disassembly.md#what-changes-between-users-inputs) for
why, and `imm-operand` for the fix.

Both peripherals open on the **starting board and wait** — any key in the
window, Enter in the terminal — and both hold the **final frame** until they're
dismissed, so neither the opening (which is Part 1's answer, 348 blocks) nor
the ending flashes past. That needs one addition to the driver, `prime!`: step
the machine to its *first* joystick read, absorbing the 1,000-command opening
repaint without playing a tick. `--speed N` sets game ticks per rendered frame
(default 2, or 1 with `--human`) and `--fps N` the frame rate.

The interesting part is how little code that took, and *why* — the answer is a
decision made back in `next-command!` for reasons that had nothing to do with
graphics.

### The joystick thunk was a UI hook all along

[`next-command!`](../../src/day13.rkt) takes the joystick as a **thunk**, called
at the instant the machine blocks on opcode 3, rather than as a value computed
in advance. That was done so the controller could see the frame it is
responding to (the [bang-bang section](#the-problem-within-the-problem-2-the-player-is-a-bang-bang-controller)
above). But "the joystick is a function called at block time" is *exactly* the
interface a UI needs, because a human's answer also doesn't exist until the
moment it's asked for:

```racket
(lambda () (sgn (- ball paddle)))    ; the solve:  tracking controller
(lambda () (unbox stick))            ; the viewer: whatever key is held down
```

Swapping those is the entire difference between solving Day 13 and playing it.
The VM, `src/intcode.rkt`, the block/resume protocol and the stream framing are
all untouched — **the cabinet cannot tell** whether a program or a person is at
the joystick. Had `play` computed the joystick value *before* calling the
driver (the obvious first draft), a UI would have needed a different driver.

The other thing a UI needs is a **frame boundary**, and that also already
exists: the draw commands between two joystick reads are exactly one game tick.
The [disassembly](day13_disassembly.md) says why this is guaranteed rather than
lucky — the program's `draw(x, y, tile)` subroutine emits its three outputs
*inside* the routine that stores to the screen array, so the output stream is a
write-through log of a memory-mapped display, and no partial triple can be
in flight when the machine stops to ask for input.

### The shared driver

The viewer's `cab` struct is `play`'s loop with three additions, each of which
is a thing a *renderer* needs and a *solver* doesn't:

| `play` carries | the viewer also carries | why |
|---|---|---|
| `score`, `ball` x, `paddle` x | the ball's **y** | a solver never needs it (the paddle moves horizontally); a renderer must draw the ball somewhere |
| — | the `screen` hash | `play` proves you can throw the board away; a picture is the board |
| — | an `on-draw` callback | fires per cell update, so a renderer can patch instead of rebuild |

That callback is the viewer's own version of the cabinet's write-through
display: the program tells us which cell changed, so we don't have to diff.

### Peripheral 1 — the terminal (35 lines)

`\e[H` to home the cursor, redraw the 40×25 glyph grid using the same glyph
table as [`render`](#render-and-the-glyph-table), `sleep` for the frame budget. No dependencies, and it
works over SSH. Watch-only: reading arrow keys from a terminal needs raw-mode
support that isn't in the standard distribution.

```
AoC 2019 Day 13 — the AI plays  (tick     0)

████████████████████████████████████████
█                                      █
█    # ###   #  # ###  #  # #### ###   █
...
█                 o                    █
█                                      █
█                                      █
█                   =                  █
█                                      █

  score 0         blocks left 348

  Press Enter to start…
```

The one wrinkle in a redraw-from-home animation: a prompt printed under one
frame outlives the next, shorter one. `\e[J` (erase from cursor down) at the
end of each repaint fixes it.

### Peripheral 2 — a window, via `big-bang` (95 lines)

`2htdp/universe`'s `big-bang` is HtDP's world loop — a value, a clock, and
handlers (`on-tick`, `on-key`, `to-draw`, `stop-when`). It ships with Racket,
so this needs no packages. Four things about it are worth a cold reader's
time.

**The impedance mismatch.** `big-bang` wants a *functional* world that each
handler replaces; `cab` is a mutable struct wrapped around a mutable VM.
Racket lets the handlers return the same mutated struct, so it works, but the
shape is a lie about where the state lives. The honest reading is that
`big-bang` is being used as an **event loop**, not as a world machine — which
is what an emulator front-end is. `racket/gui` with a canvas and a timer would
say the same thing without the pretence, at about twice the code. Rust
analogue: this is `minifb`/`macroquad`'s `while window.is_open()` loop, with
`&mut World` where big-bang insists on `World -> World`.

**Frame cost, and the fix.** `place-image` is lazy — building a 440-image
composite costs ~3 ms — but *rasterising* one costs about **25 ms more per
frame** than blitting a pre-`freeze`d bitmap, and 25 ms will not hold 30 fps.
So walls and blocks are composed once and
`freeze`d into a single bitmap, and the `on-draw` callback patches *that
bitmap* when a block breaks: one composite per break, **348 per game** instead
of 440 per frame. Ball and paddle are drawn on top as sprites. That's the
classic background/sprite split, and the cabinet's write-through protocol is
what makes it available — the program hands us the invalidation rectangle for
free.

**A watchdog, because faithful emulation can hang you.** The cabinet's
collision resolution is a fixed-point loop with no iteration bound, and it
livelocks when the ball is wedged between a side wall and the paddle on the
paddle's own row — the probe flips `dx` forever and the machine never reaches
its next `INPUT`. It is [a real defect in the puzzle program](day13_disassembly.md#the-fixed-point-has-no-bound--the-cabinet-can-livelock),
reachable by a human holding a direction while the ball comes down a wall
column, and emulating it faithfully means freezing the window. So `tick!` caps
one tick at 200 000 instructions — calibrated against a measured median of
**112** per tick and a p99 of **321** — and flags the cabinet `wedged?`
instead of spinning. Both peripherals then report `CABINET WEDGED` rather than
appearing to crash. It is the one place the viewer deliberately stops being a
faithful emulator, which is exactly the sort of thing an emulator front-end
exists to decide.

**`stop-when` means "exit", not "pause".** The obvious way to end the game is
`[stop-when cab-halted? draw]` — and it makes the window vanish the instant the
last block breaks. Stopping causes `big-bang` to *return*; the module then
finishes, `racket` exits, and the process takes its window with it. (`[close-on-stop #f]`
does not help — that flag only controls whether big-bang itself hides the
frame.) This is a trap you will not hit in DrRacket, where the REPL process
outlives the animation and the window sticks around. So game-over is **not** a
stop condition here: `advance` no-ops once the machine halts, the final frame
keeps being redrawn, and `stop-when` fires only on an explicit `q`. The GUI
equivalent of the terminal's `Press Enter to exit…`.

### `--heat`: the disassembly, playable

Each block is coloured by its hidden point value (cold blue = 1, hot red = 98),
recovered from the affine-permuted table the
[disassembly](day13_disassembly.md#the-hidden-score-map) found at cell 1639:

```
slot(x, y) = 1639 + ((25x + y) * 503 + 366) mod 1000
```

Playing with it on is a good way to *see* the argument that the final score is
order-independent: there is no gradient, no "top rows are worth more", nothing
a player could aim at. Every colour is broken exactly once no matter what you
do — the only decision that changes the score is whether you finish.

Per the [optimisation policy](../../CLAUDE.md), none of this touches
[src/day13.rkt](../../src/day13.rkt): the shipping solution stays a
dependency-free `play` returning an integer, and the viewer is a separate
script that imports nothing but the VM.

---

## Possible optimization

Per this repo's [standing policy](../../CLAUDE.md), the shipping source stays
idiomatic and the faster variants live here.

**1. Don't carry the screen through `play`.** This one *is* in the shipping
source, because dropping dead state isn't an optimization, it's just not
writing it. But it is worth measuring what the natural first draft costs:
threading a `(hash-set tiles (cons x y) id)` through all 20 805 draw commands
adds allocation of 20 805 cons cells and 20 805 HAMT nodes for data that is
never read. Measured on the real input:

```
play (three integers) : 132.05 ms
play (+ screen hash)  : 135.15 ms     (~2.3% slower, mean of 20)
```

Smaller than you'd guess — Racket's immutable-hash `hash-set` is genuinely
cheap and the VM stepping dominates — but it is pure waste, and the version
without it is also *shorter*.

**2. Part 1 is free if you fold it into Part 2.** The free-play patch is a
single memory cell; it doesn't change the board the program paints. So the
first 1000 draw commands of a Part 2 run *are* Part 1's answer, and a
`both-parts` entry point could count blocks on the opening frame and return
both numbers from one run — saving the entire Part 1 pass (~4 ms of the
day's ~134 ms). This is the same solve-granularity restructure
[Day 3](day03_function_guide.md)'s `day03a.rkt` made, and it would be worth
building out the same way if the win were bigger. Sketch:

```racket
;; UNTESTED sketch.
(define (both-parts program)
  (define machine (make-vm program))
  (vm-poke! machine 0 2)
  (let loop ([blocks (hash)] [opening? #t] [score 0] [ball 0] [paddle 0])
    ...
    ;; while `opening?`, also accumulate block coordinates; flip `opening?`
    ;; to #f on the first score event, and stop tracking the board there.
    ))
```

The catch is that "the opening frame is finished" has to be detected, and the
cleanest signal is the first `(-1, 0, 0)` score event — which is a *protocol*
observation, not a structural one. That fragility is why it stays a sidebar.

**3. Use a mutable vector for the Part 1 board.** The screen is 40 × 25 and
dense; a `(make-vector 1000 0)` indexed by `y*40 + x` would replace the
immutable hash with flat writes, the same reshape
[Day 8](day08_function_guide.md) used for its layered image. It needs the
screen dimensions known up front (they aren't, until you've seen the whole
stream) or a grow-on-demand vector, which is how you end up back at a hash.
Cheap in a language with bounds-checked arrays and a known board size; not
obviously worth it here.

**4. Skip the contract on `vm-step!`.** `step-result/c` is checked on all
~610 000 steps of a Part 2 run. Racket's `contract-out` boundary checks are
not free, and a `(module+ fast ...)` submodule exporting the raw function
would show the difference. Not taken: the whole point of the contracts in
this repo is that they're on by default and document the interface, and the
day is fast enough that the bill isn't worth arguing with.

---

## Tests (what's pinned and why)

[test/day13-test.rkt](../../test/day13-test.rkt) does **not** re-test the
VM's opcode semantics — `src/intcode.rkt` is Day 11's `vm-step!` moved
verbatim, and its behavior is already pinned by
[Day 9](day09_function_guide.md)'s quine and
[Day 7](day07_function_guide.md)'s feedback loop. What's new on Day 13 is the
peripheral, so that's what's tested. Every fixture is a **scripted cabinet**
built from `104` (output-immediate) instructions, so the test programs read
as literal display commands rather than as Intcode puzzles of their own.

1. **Framing**, against the prose's own example: `104,1,104,2,104,3,
   104,6,104,5,104,4,99` must produce exactly `{(1,2): paddle, (6,5): ball}`.
   An off-by-one in the chunking cannot survive this.
2. **Last write wins.** Two blocks drawn, then one of them redrawn as empty:
   two distinct coordinates, one block, one empty cell. If draws accumulated
   instead of overwriting, the block count would still read 2.
3. **`render`'s glyph mapping**, on a 2×2 synthetic board, plus the empty
   board rendering as `""` rather than erroring.
4. **The sentinel routes to the score**, not to a tile: `-1,0,12345` returns
   `12345` (the prose's own number), and a second score event supersedes the
   first — pinning "the answer is the score at halt".
5. **The joystick's sign convention**, with a cabinet that draws a ball and a
   paddle at given columns, reads the joystick into scratch cell 100 (past
   the end of the program — grow-on-write memory handles it), and echoes it
   back *as the score*. So `play`'s return value literally is the joystick
   reading: `+1` for ball-right-of-paddle, `-1` for ball-left, `0` for
   aligned. A sign flip here would still solve nothing and fail loudly.
6. **The free-play poke lands on address 0.** The fixture is
   `99,0,0,0,104,-1,104,0,104,42,99`: as written, address 0 is `HALT` and the
   game never starts (score 0). Poked with `2`, address 0 becomes a multiply
   instruction, control falls through into the display commands, and the
   score is 42. Same bytes, two behaviors — which is the puzzle's own trick,
   in miniature.
7. **The real input**: `part1 = 348`, `part2 = 16999`, plus the starting
   board's geometry and histogram — 1000 cells drawn, 40 × 25, 88 walls,
   exactly one ball at `(18, 20)`, exactly one paddle at `(20, 23)`, and the
   five tile counts summing to 1000. A framing bug that shifted every triple
   by one would still yield a plausible-looking block count; it cannot
   survive an exact geometry check. The rendered board is spot-checked at two
   cells (the wall corner, and the ball's own position) rather than pinned
   whole — unlike [Day 11](day11_function_guide.md), the picture here isn't
   the answer, so a full-picture pin would just be brittle.

The ball starting at `(18, 20)` and the paddle at `(20, 23)` is itself worth
pinning: the ball starts **left of** the paddle, so the very first joystick
reading of the real game is `-1`, not `0`. A controller that only reacted
after seeing the ball move would already be a frame behind on tick one.

`raco test test/day13-test.rkt` → **27 tests passed**.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 13  | 2.1500    | 4.2000      | 128.0500    | 134.4000   |
```

Mean over **20** iterations.

**Parse (2.2 ms)** is the largest of any day so far — not because the code
changed (it's Day 5's `parse-input`, verbatim) but because the program is the
biggest yet at **2640 cells**, roughly 2.7× Day 9's BOOST. The cost is linear
in program length and it shows: Day 9's parse was 0.82 ms.

**Part 1 (4.2 ms)** is one run of the cabinet to the halt after the opening
frame: **17 107 `vm-step!` calls** and 1000 `hash-set`s. Comparable to
[Day 9](day09_function_guide.md)'s Part 1 (0.10 ms) times the extra work, and
well under [Day 11](day11_function_guide.md)'s 24 ms — the game's opening
frame is a *short* program run; the drawing is nearly all of it.

**Part 2 (128 ms) is 30× Part 1**, and the ratio is the whole story of the
day: 4778 game ticks × ~128 instructions per tick = **609 973 `vm-step!`
calls**, versus Part 1's 17 107. At ~4.8 million steps/second this is the
same per-step cost as Part 1; there is simply 36× more program to run,
because Part 1 stops after drawing one frame and Part 2 plays a whole game of
Breakout. Nothing in the *driver* is hot — 20 805 draw commands, 4778
`sgn` calls, and three integers of state are noise next to half a million
interpreted instructions.

For calibration against the year so far: Day 13's **total** is second only to
[Day 3](day03_function_guide.md)'s 185 ms, and its **Part 2 alone** is the
single most expensive part of any day this year — ahead of Day 3's 92 ms and
[Day 12](day12_function_guide.md)'s 82 ms. It is also comfortably the most
expensive *Intcode* day, a title [Day 9](day09_function_guide.md) held with
54 ms.

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

// The VM from Day 11's sketch, unchanged — mem/ip/rb/inputs/halted,
// `fn step(&mut self) -> Step`, `enum Step { Ran, Blocked, Output(i64), Halted }`.

#[derive(Clone, Copy, PartialEq)]
enum Tile { Empty, Wall, Block, Paddle, Ball }

impl From<i64> for Tile {
    fn from(n: i64) -> Self {
        match n {
            0 => Tile::Empty, 1 => Tile::Wall, 2 => Tile::Block,
            3 => Tile::Paddle, 4 => Tile::Ball,
            _ => panic!("bad tile id {n}"),
        }
    }
}

enum Command { Draw { x: i64, y: i64, tile: Tile }, Score(i64) }

/// Step the machine until it emits a full command, or halts.
/// `joystick` is `FnMut` so the caller can close over mutable world state.
fn next_command(vm: &mut Vm, joystick: &mut impl FnMut() -> i64) -> Option<Command> {
    let mut outs = [0i64; 3];
    let mut n = 0;
    loop {
        match vm.step() {
            Step::Blocked => vm.inputs.push_back(joystick()),
            Step::Ran => {}
            Step::Output(v) => {
                outs[n] = v;
                n += 1;
                if n == 3 {
                    return Some(match (outs[0], outs[1]) {
                        (-1, 0) => Command::Score(outs[2]),
                        (x, y)  => Command::Draw { x, y, tile: outs[2].into() },
                    });
                }
            }
            Step::Halted => return None,
        }
    }
}

fn part1(program: &[i64]) -> usize {
    let mut vm = Vm::new(program);
    let mut tiles: HashMap<(i64, i64), Tile> = HashMap::new();
    let mut never = || unreachable!("cabinet asked for input before free play");
    while let Some(cmd) = next_command(&mut vm, &mut never) {
        if let Command::Draw { x, y, tile } = cmd {
            tiles.insert((x, y), tile);
        }
    }
    tiles.values().filter(|&&t| t == Tile::Block).count()
}

fn part2(program: &[i64]) -> i64 {
    let mut vm = Vm::new(program);
    vm.mem.insert(0, 2);                       // insert two quarters
    let (mut score, mut ball, mut paddle) = (0i64, 0i64, 0i64);
    loop {
        // The borrow checker's one demand: `joystick` closes over `ball` and
        // `paddle`, which the loop body also mutates — so the closure is
        // rebuilt each iteration from copies rather than held across it.
        let (b, p) = (ball, paddle);
        let mut joystick = move || (b - p).signum();
        match next_command(&mut vm, &mut joystick) {
            None => return score,
            Some(Command::Score(v)) => score = v,
            Some(Command::Draw { x, tile, .. }) => match tile {
                Tile::Ball => ball = x,
                Tile::Paddle => paddle = x,
                _ => {}
            },
        }
    }
}
```

The correspondences worth seeing:

- **`enum Command` ↔ the clause order in `match`.** Rust names the sum type
  and decodes the `(-1, 0)` sentinel exactly once, in `next_command`; every
  consumer then gets exhaustiveness checking for free. Racket fuses decode
  and consume into one `match` and relies on you putting the sentinel clause
  first. Both are ~5 lines. The difference shows up the *third* time you
  consume the stream, when Rust has already told you about the case you
  forgot.
- **`enum Tile` ↔ the five `define`d integers.** `EMPTY`/`WALL`/`BLOCK`/…
  in Racket are just names for `0..4`, and `count-tiles` takes an
  `(integer-in 0 4)` contract to catch garbage at the boundary. Rust's
  `From<i64>` puts the same check at the same boundary; the win is that
  downstream code can never compare a tile to a coordinate by accident.
- **`FnMut` ↔ the thunk.** The lazy-joystick trick translates directly, but
  Rust charges rent for it: the closure captures `ball` and `paddle`, and the
  loop body wants to mutate them. The sketch above copies them per iteration
  (they're `i64`, so it's free) — a real implementation would more likely
  make the world a struct and pass `&World` in. This is the same friction
  Day 11's sketch hit with `val`/`addr` borrowing `self`: single-threaded
  mutable-closure code is where Racket reads more directly than Rust.
- **`[i64; 3]` + index ↔ the cons-and-reverse accumulator.** Rust's fixed
  array says "exactly three, on the stack" and needs no reversal. Racket's
  list accumulator is idiomatic and heap-allocates three cells per command —
  62 415 cells across a Part 2 run, all immediately garbage. A generational
  collector eats that for breakfast, and the benchmark above says so, but the
  Rust version is genuinely doing less work.
- **`while let Some(cmd) = …` ↔ `#f` as end-of-stream.** `Option<Command>`
  is the typed version of returning `#f`, and `while let` is the loop form
  built for it. Racket's `match` clause `[#f tiles]` is the same idea with
  the type erased.

---

## What's next

Day 13 is the first Intcode day where the *machine* contributed nothing new —
it was a dependency, not a topic. Expect that to be the shape of the rest of
the year's odd-numbered days: **Day 15** (Oxygen System) wires the same VM to
a repair droid that has to *map* an unknown maze, which turns the driver into
a graph search — BFS or DFS over a world you can only observe by walking it,
with backtracking done by issuing the reverse move. That is the natural
sequel to this day's control loop: Day 13's player needed three integers of
state, Day 15's needs a whole discovered map plus a frontier.

Between them, **Day 14** (Space Stoichiometry) leaves Intcode for a
topological sort over a reaction graph, with a Part 2 that almost certainly
wants binary search over a monotone function. See the
[summary table](summary_2019.md) for the running scoreboard.
