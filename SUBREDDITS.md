# Subreddits — reference for revisiting

The full `DEFAULT_SUBREDDITS` list in `src/leadscout/config.py`, with how each entry was
found and its post count in the benchmark corpus so far (`benchmark.db`, 6,342 posts as
of this writing across 42 subreddits with confirmed activity — see
`scripts/benchmark_classifiers.py`).

**Leads found so far: 5**, all via Ollama (`qwen2.5:14b`) with a 0.4 score threshold:

| Post | Subreddit | Score | Note |
|---|---|---|---|
| "Ticket system is atrocious" | GlacierNationalPark | 0.80 | Repeated failed attempts at a timed-entry ticket system |
| "Fern canyon permit rage" | redwoods | 0.90 | Years of failed permit attempts, textbook lead |
| "Fern Canyon 7/30 or 7/31" | redwoods | 0.70 | Missed a permit, hitchhiking in on someone else's |
| "Reservation.gov site errors" | camping | 0.70 | Got an availability alert, checkout kept erroring |
| "Jedediah Smith Campground" | redwoods | 0.50 | Proactively worried about sites filling fast |

**Key finding**: `r/redwoods` alone produced 3 of the 5 leads (Fern Canyon's permit
system is notoriously hard to get) — specific single-destination/permit-hotspot
subreddits are the highest-value category found so far, better than general
camping/hiking subs by a wide margin per-post.

## Original list

| Subreddit | Status | Posts so far |
|---|---|---|
| CAMPING | live | 25 |
| RECREATIONdotgov | **dead** — confirmed via clean 302 redirect, not rate-limiting | 0 |
| Yosemite | live | 203 |
| glamping | live | 2 (labeled `Glamping`) |
| vandwellers | live | 407 |
| GlacierNationalPark | live | 199 |
| nationalparks | live | 188 |
| CampingandHiking | live | 701 |
| RVLiving | live | 316 |
| backpacking | live | 656 |

## Round 1 — verified live

hiking (932), AppalachianTrail (54), carcamping (49), JoshuaTree (31), overlanding (104),
PacificCrestTrail (39), Ultralight (96), VanLife (249), WildernessBackpacking (158),
yellowstone (161), grandcanyon (50), JMT (28)

## Round 2 — verified live

CampingGear (135), CDT (8), DeathValleyNP (12), GreatSmokyMountains (3),
hammockcamping (62), OlympicNationalPark (72), Sequoia (1), Thruhiking (14),
BryceCanyon (3), havasupai (2)

**Still not confirmed either way** (three sweeps now): Zion, RockyMountainNP, Acadia,
Arches, MountRainier, BackpackingLight, skoolie, BoondockersWelcome, solocamping,
Enchantments. Harmless if wrong (dead names are silently absent from combined
results); worth an isolated retest sometime, or just wait and see if the continuous
overnight loop ever surfaces posts from them.

## Round 3 — verified live

bikepacking (242), coloradotrail (18), Everglades (7), longtrail (6), **redwoods (13,
but 3 of our 5 total leads)**, TahoeRimTrail (7), WinterCamping (4), Canyonlands (1),
shenandoah (1), tentcamping (1)

**Still not confirmed**: Denali, Voyageurs, Congaree, Badlands, CapitolReef, MesaVerde.

## Round 4 — verified live

Specific hard-to-get-permit destinations, added after r/redwoods proved that pattern
valuable: KalalauTrail, mtwhitney, thewave, wonderlandtrail (all low-volume/niche,
~20 posts total across all four in one combined test - narrow but real communities).

## Round 5 — NOT yet live-verified

Rate limit was fully saturated when these were added (tonight's sustained heavy usage
closed the anonymous bucket for extended periods) - same reasoning as round 4, more
specific permit-hotspot destinations: NorthCascades, KingsCanyon, GrandTeton,
MaroonBells, Sawtooth, WindRiverRange, SanJuanMountains, AngelsLanding.

## Notes for later

- **How to verify a candidate**: fetch `reddit.com/r/candidate1+candidate2+.../new/.rss?limit=100`
  and check which `<category label="r/...">` values appear. A name that never appears
  across several attempts (and isn't obviously crowded out by a much larger sub in the
  same query) is likely dead or nonexistent.
- **Rate limit gets *harder* under sustained use, not just per-request.** Early tonight,
  `new` + `top/all` both succeeded per sweep; after ~2 hours of continuous heavy use,
  even `new` started returning almost nothing and `top/all` 429'd immediately. This
  looks like a longer soft-throttle beyond the simple per-response
  `x-ratelimit-reset` window - budget real cooldown time (hours, not minutes) between
  big sweeps.
- **Highest-value subreddit category**: specific single-destination/permit-hotspot subs
  (redwoods/Fern Canyon, GlacierNationalPark's ticket system) rather than general
  camping/hiking subs - worth prioritizing this pattern when adding more candidates.
- **Combining bad names is safe**: a dead/nonexistent subreddit mixed into a combined
  query doesn't break the whole request - confirmed live, it's just silently absent.
