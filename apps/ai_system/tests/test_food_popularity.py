"""Stage 5: popularity counts training interactions only, so evaluation cannot leak."""

from datetime import date
from pathlib import Path

import pytest

from savora_ai.core.food_data.popularity import count_interactions, load_popularity

CUTOFF = date(2012, 1, 1)


def test_only_interactions_before_the_cutoff_count() -> None:
    table = count_interactions(
        [("10", "2005-03-01"), ("10", "2011-12-31"), ("10", "2015-06-01"), ("20", "2016-01-01")],
        CUTOFF,
    )
    assert table.count("FC_10") == 2  # the 2015 interaction is held out
    assert table.training_interactions == 2 and table.held_out_interactions == 2


def test_recipe_seen_only_after_the_cutoff_counts_zero() -> None:
    table = count_interactions([("20", "2016-01-01")], CUTOFF)
    assert table.count("FC_20") == 0
    assert "FC_20" not in table.counts


def test_cutoff_day_itself_is_held_out() -> None:
    assert count_interactions([("1", "2012-01-01")], CUTOFF).count("FC_1") == 0


@pytest.mark.parametrize("row", [("abc", "2005-01-01"), ("1", "not a date")])
def test_bad_rows_fail_loudly(row: tuple[str, str]) -> None:
    with pytest.raises(ValueError):
        count_interactions([row], CUTOFF)


def test_counts_are_order_independent() -> None:
    rows = [("2", "2001-01-01"), ("1", "2001-01-01"), ("2", "2002-01-01")]
    assert count_interactions(rows, CUTOFF) == count_interactions(list(reversed(rows)), CUTOFF)


def test_loader_reads_multiline_reviews_and_reports(tmp_path: Path) -> None:
    path = tmp_path / "RAW_interactions.csv"
    path.write_text(
        "user_id,recipe_id,date,rating,review\n"
        '1,5,2003-02-17,4,"Great.\nCooked on top of stove."\n'
        "2,5,2018-12-20,5,late\n",
        encoding="utf-8",
    )
    table = load_popularity(path, CUTOFF)
    assert table.count("FC_5") == 1
    report = table.report()
    assert report["cutoff"] == "2012-01-01" and report["heldOutInteractionsIgnored"] == 1
    assert isinstance(report["sourceSha256"], str)


def test_loader_needs_the_columns(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_popularity(path, CUTOFF)
