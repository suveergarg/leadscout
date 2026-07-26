from __future__ import annotations

# Cheap first-pass filter narrowing the LLM-classify candidate set to posts that plausibly
# signal "wants availability help" — not general camping chatter.
PHRASES = [
    "sold out",
    "no availability",
    "no sites available",
    "fully booked",
    "everything is booked",
    "any tips getting a permit",
    "how do you get a permit",
    "how do you snag",
    "keep checking",
    "keep refreshing",
    "refresh the site",
    "any alerts for",
    "is there an app",
    "is there a tool",
    "notify me when",
    "cancellation watch",
    "campnab",
    "waitlist",
    "sniper",
    "booked up",
    "impossible to book",
    "recreation.gov is a nightmare",
]


def matched_phrase(title: str, body: str) -> str | None:
    """Returns the first matching phrase, or None. Case-insensitive substring match."""
    haystack = f"{title}\n{body}".lower()
    for phrase in PHRASES:
        if phrase in haystack:
            return phrase
    return None
