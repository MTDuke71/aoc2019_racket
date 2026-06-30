#lang racket/base

;; Tests for Day 10 — Monitoring Station.
;;
;; Pins:
;;   1. parse-input on the 5×5 spec map (coords of every `#`),
;;   2. Part 1's "best location" on all five spec maps (the 8-detector 5×5
;;      and the four larger 33/35/41/210 examples),
;;   3. Part 2's vaporization order on the 20×20 / 210-detector example —
;;      the spec lists the 1st, 2nd, 3rd, 10th, 20th, 50th, 100th, 199th,
;;      200th, 201st, and 299th asteroids destroyed,
;;   4. the actual answers for inputs/day10.txt.
;;
;; Run with:  raco test test/day10-test.rkt

(require rackunit
         racket/string
         "../src/aoc.rkt"
         "../src/day10.rkt")

(module+ test

  ;; --- parse-input ---

  (define five "
.#..#
.....
#####
....#
...##")
  (check-equal? (parse-input five)
                '((1 . 0) (4 . 0)
                  (0 . 2) (1 . 2) (2 . 2) (3 . 2) (4 . 2)
                  (4 . 3)
                  (3 . 4) (4 . 4))
                "parses asteroid coordinates row-major")

  ;; --- Part 1: best location on every spec map ---

  (check-equal? (best (parse-input five)) '((3 . 4) . 8)
                "5×5 example: best is 3,4 with 8 detected")

  (define (best-of str) (best (parse-input str)))

  (check-equal? (best-of "
......#.#.
#..#.#....
..#######.
.#.#.###..
.#..#.....
..#....#.#
#..#....#.
.##.#..###
##...#..#.
.#....####")
                '((5 . 8) . 33) "best 5,8 with 33")

  (check-equal? (best-of "
#.#...#.#.
.###....#.
.#....#...
##.#.#.#.#
....#.#.#.
.##..###.#
..#...##..
..##....##
......#...
.####.###.")
                '((1 . 2) . 35) "best 1,2 with 35")

  (check-equal? (best-of "
.#..#..###
####.###.#
....###.#.
..###.##.#
##.##.#.#.
....###..#
..#.#..#.#
#..#.#.###
.##...##.#
.....#.#..")
                '((6 . 3) . 41) "best 6,3 with 41")

  ;; --- the big 20×20 map drives both parts of the vaporization test ---

  (define big "
.#..##.###...#######
##.############..##.
.#.######.########.#
.###.#######.####.#.
#####.##.#.##.###.##
..#####..#.#########
####################
#.####....###.#.#.##
##.#################
#####.##.###..####..
..######..##.#######
####.##.####...##..#
.#####..#.######.###
##...#.##########...
#.##########.#######
.####.#.###.###.#.##
....##.##.###..#####
.#.#.###########.###
#.#.#.#####.####.###
###.##.####.##.#..##")

  (define big-asteroids (parse-input big))
  (check-equal? (best big-asteroids) '((11 . 13) . 210)
                "20×20 example: best is 11,13 with 210")

  ;; Part 2: the spec enumerates these positions in the firing order.
  (define order (vaporization-order '(11 . 13) big-asteroids))
  (define (nth n) (list-ref order (sub1 n)))
  (check-equal? (nth 1)   '(11 . 12) "1st vaporized")
  (check-equal? (nth 2)   '(12 . 1)  "2nd vaporized")
  (check-equal? (nth 3)   '(12 . 2)  "3rd vaporized")
  (check-equal? (nth 10)  '(12 . 8)  "10th vaporized")
  (check-equal? (nth 20)  '(16 . 0)  "20th vaporized")
  (check-equal? (nth 50)  '(16 . 9)  "50th vaporized")
  (check-equal? (nth 100) '(10 . 16) "100th vaporized")
  (check-equal? (nth 199) '(9 . 6)   "199th vaporized")
  (check-equal? (nth 200) '(8 . 2)   "200th vaporized")
  (check-equal? (nth 201) '(10 . 9)  "201st vaporized")
  (check-equal? (nth 299) '(11 . 1)  "299th (last) vaporized")
  (check-equal? (length order) 299
                "every asteroid but the station is vaporized exactly once")

  ;; --- actual puzzle input ---
  (define asteroids (parse-input (read-day-input 10)))
  (check-equal? (part1 asteroids) 230 "part 1 (most detectable)")
  (check-equal? (part2 asteroids) 1205 "part 2 (200th vaporized → x*100+y)"))
