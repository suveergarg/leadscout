# Subreddits — reference for revisiting

The full `DEFAULT_SUBREDDITS` list in `src/leadscout/config.py`, with how each entry was
found and its post count in the benchmark corpus so far (`benchmark.db`, still growing as
the deep-history sweep continues — see `scripts/benchmark_classifiers.py`).

## Original list

| Subreddit | Status | Posts in benchmark so far |
|---|---|---|
| CAMPING | live | 25 |
| RECREATIONdotgov | **dead** — confirmed via clean 302 redirect to a search page, not rate-limiting. Left in the config but contributes nothing; harmless since dead names are silently dropped from combined queries. | 0 |
| Yosemite | live | 143 |
| glamping | live | 2 (labeled `Glamping` in RSS) |
| vandwellers | live | 364 |
| GlacierNationalPark | live | 126 |
| nationalparks | live | 145 |
| CampingandHiking | live | 675 |
| RVLiving | live | 192 |
| backpacking | live | 525 |

## Round 1 additions — verified live (real posts confirmed under the name)

| Subreddit | Posts so far |
|---|---|
| hiking | 739 |
| AppalachianTrail | 33 |
| carcamping | 25 |
| JoshuaTree | 22 |
| overlanding | 65 |
| PacificCrestTrail | 18 |
| Ultralight | 49 |
| VanLife | 147 |
| WildernessBackpacking | 116 |
| yellowstone | 93 |
| grandcanyon | 36 |
| JMT | 15 |

## Round 2 additions — verified live

| Subreddit | Posts so far |
|---|---|
| CampingGear | 13 |
| CDT | 0 so far (confirmed real when first tested; hasn't surfaced again yet) |
| DeathValleyNP | 1 |
| GreatSmokyMountains | 0 so far (confirmed real when first tested) |
| hammockcamping | 3 |
| OlympicNationalPark | 6 |
| Sequoia | 0 so far (confirmed real when first tested) |
| Thruhiking | 0 so far (confirmed real when first tested — note lowercase "h", not "ThruHiking") |

## Round 2 additions — NOT yet cleanly verified

A test batch got crowded out by higher-volume subs before the rate limit blocked a clean
retest. Harmless either way (a dead name is silently absent from combined results,
confirmed with RECREATIONdotgov) — whether these are real will show up as their post
count in future sweeps. None had shown up as of this writing:

Zion, RockyMountainNP, Acadia, Arches, BryceCanyon, MountRainier, BackpackingLight,
skoolie, BoondockersWelcome, solocamping, Havasupai, Enchantments.

If revisiting: test these on their own (not mixed with a dominant sub like CampingGear)
to get a clean read, or just watch whether they ever contribute posts in a benchmark run.

## Notes for later

- **How to verify a candidate**: fetch `reddit.com/r/candidate1+candidate2+.../new/.rss?limit=100`
  and check which `<category label="r/...">` values appear in the response. A name that
  never appears across several attempts (and isn't obviously being crowded out by a
  much larger sub in the same query) is likely dead or nonexistent.
- **Rate limit**: the anonymous RSS bucket is shared across all requests from this IP
  (this session's own manual `curl` testing has repeatedly exhausted it) — space out
  verification requests, or just let a real sweep (which already throttles correctly
  based on live headers) settle it.
- **Combining bad names is safe**: a dead/nonexistent subreddit mixed into a combined
  query doesn't break the whole request — confirmed live, it's just silently absent.
