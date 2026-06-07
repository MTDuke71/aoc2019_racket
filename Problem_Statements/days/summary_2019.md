# AoC 2019 Summary

| Day | Title | Parse | Part 1 | Part 2 | Total | Algorithm | Notes |
|-----|-------|-------|--------|--------|-------|-----------|-------|
| 01 | The Tyranny of the Rocket Equation | 0.0141 ms | 0.0006 ms | 0.0029 ms | 0.0175 ms | Fixed-point iteration (Part 2) | P1 3481005 / P2 5218616; platform set up this day |
| 02 | 1202 Program Alarm | 0.1050 ms | 0.0050 ms | 27.0500 ms | 27.1600 ms | Bytecode interpreter; brute-force grid search (Part 2, affine closed form sidebar) | P1 4945026 / P2 5296; first Intcode VM + first mutable vector |
| 03 | Crossed Wires | 0.5200 ms | 92.2400 ms | 92.2750 ms | 185.0350 ms | Spatial hash (occupancy map) + set intersection; segment-intersection sidebar | P1 2180 / P2 112316; first immutable hash; trace-once variant (day03a) halves solve to ~92 ms (2.0×); mutable-hash measured a dead-end |
| 04 | Secure Container | 0.0000 ms | 38.5000 ms | 38.1000 ms | 76.6000 ms | Run-length encoding + brute-force range scan; stars-and-bars (combinations-with-repetition) closed-form sidebar | P1 1675 / P2 1142; first RLE; non-decreasing via variadic `(apply <= ds)`; parts differ only by `>=` vs `=` |
