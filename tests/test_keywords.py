from __future__ import annotations

from leadscout.keywords import matched_phrase


def test_matches_known_phrase() -> None:
    assert matched_phrase("Site was sold out in 2 minutes", "") == "sold out"


def test_matches_in_body_case_insensitive() -> None:
    phrase = matched_phrase("trip report", "Anyone know if there's an APP to Notify Me When a site opens?")
    assert phrase == "notify me when"


def test_no_match_on_unrelated_post() -> None:
    assert matched_phrase("Best tent for winter camping?", "Looking for recommendations under $200") is None
