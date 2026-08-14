"""Tests for the test platform itself.

conftest.py's two fixtures encode a policy -- a missing input skips, an
unverified answer can never report green -- and a policy that nothing checks is
a policy that quietly stops holding. These tests point `inputs_dir` at a
tmp_path and drive the fixtures against stub "day modules", so they prove the
machinery on a fresh clone with no puzzle inputs present at all.
"""

from __future__ import annotations

import pytest

CRLF_TEXT = "1,2,3\r\n4,5,6\r\n"


@pytest.fixture
def inputs_dir(tmp_path):
    """Override conftest's fixture: a fake inputs/ holding one day-07 file."""
    (tmp_path / "day07.txt").write_text(CRLF_TEXT, encoding="utf-8", newline="")
    return tmp_path


def stub(parsed, one, two, *, on_part1=lambda data: None):
    """A fake day module as three callables, for passing to check_locked."""

    def parse_input(text):
        return list(parsed)

    def part1(data):
        on_part1(data)
        return one

    def part2(data):
        return two(data) if callable(two) else two

    return {"parse_input": parse_input, "part1": part1, "part2": part2}


# ------------------------------------------------------------- real_input


def test_returns_the_file_verbatim_including_crlf(real_input):
    """Windows inputs are CRLF and the fixture must not launder that away.

    Tolerating the trailing \r is each day's parse_input's job; cleaning it
    here would hide precisely the bug this repo hits on a Windows checkout.
    """
    assert real_input(7) == CRLF_TEXT


def test_skips_rather_than_fails_when_the_input_is_absent(real_input):
    with pytest.raises(pytest.skip.Exception) as excinfo:
        real_input(9)
    assert "absent" in str(excinfo.value)


def test_accepts_a_variant_input_name(real_input, inputs_dir):
    (inputs_dir / "day13_alt.txt").write_text("alt", encoding="utf-8")
    assert real_input("13_alt") == "alt"


# ----------------------------------------------------------- check_locked


@pytest.mark.parametrize(
    "locked",
    [
        pytest.param((11, 22), id="tuple"),
        pytest.param([11, 22], id="list"),
        pytest.param({"part1": 11, "part2": 22}, id="dict"),
    ],
)
def test_passes_when_both_answers_match(check_locked, locked):
    got = check_locked(7, locked, **stub([1, 2, 3], 11, 22))
    assert got == {"part 1": 11, "part 2": 22}


def test_fails_loudly_when_an_answer_regresses(check_locked):
    with pytest.raises(AssertionError) as excinfo:
        check_locked(7, (11, 22), **stub([1, 2, 3], 999, 22))
    message = str(excinfo.value)
    assert "day07 part 1" in message and "999" in message and "11" in message


def test_unlocked_day_reports_its_answers_and_skips(check_locked):
    """LOCKED = None must never look like a pass."""
    with pytest.raises(pytest.skip.Exception) as excinfo:
        check_locked(7, None, **stub([1, 2, 3], 11, 22))
    message = str(excinfo.value)
    assert "UNVERIFIED" in message
    assert "part 1 = 11" in message and "part 2 = 22" in message


def test_a_locked_part_is_still_checked_when_the_other_is_unlocked(check_locked):
    """The assert runs before the skip, so half-verified days still catch regressions."""
    with pytest.raises(AssertionError):
        check_locked(7, {"part1": 11, "part2": None}, **stub([1, 2, 3], 999, 22))

    with pytest.raises(pytest.skip.Exception) as excinfo:
        check_locked(7, {"part1": 11, "part2": None}, **stub([1, 2, 3], 11, 22))
    assert "part 2 = 22" in str(excinfo.value)


def test_each_part_gets_a_freshly_parsed_copy(check_locked):
    """Every Intcode day mutates its program list; part 2 must not inherit that."""
    fns = stub(
        [1, 2, 3],
        11,
        lambda data: 22 if data == [1, 2, 3] else -1,
        on_part1=lambda data: data.append(99),
    )
    assert check_locked(7, (11, 22), **fns) == {"part 1": 11, "part 2": 22}


def test_missing_input_skips_before_any_answer_is_checked(check_locked):
    with pytest.raises(pytest.skip.Exception) as excinfo:
        check_locked(9, (11, 22), **stub([1], 0, 0))
    assert "absent" in str(excinfo.value)
