from __future__ import annotations

import respx
from httpx import Response

from leadscout import reddit_client
from leadscout.reddit_client import RssRedditClient

_SELFPOST_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><author><name>/u/camper1</name></author>
<content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;Sold out the second it went live, so frustrating. Anyone know a tool that&amp;#39;ll alert me?&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt; &amp;#32; submitted by &amp;#32; &lt;a href="https://www.reddit.com/user/camper1"&gt; /u/camper1 &lt;/a&gt; &lt;br/&gt; &lt;span&gt;&lt;a href="https://www.reddit.com/r/CAMPING/comments/abc123/title/"&gt;[link]&lt;/a&gt;&lt;/span&gt; &amp;#32; &lt;span&gt;&lt;a href="https://www.reddit.com/r/CAMPING/comments/abc123/title/"&gt;[comments]&lt;/a&gt;&lt;/span&gt;</content>
<id>t3_abc123</id>
<link href="https://www.reddit.com/r/CAMPING/comments/abc123/title/" />
<updated>2026-07-26T19:26:48+00:00</updated>
<published>2026-07-26T19:26:48+00:00</published>
<title>Sold out in seconds, any alert tool?</title>
</entry>
</feed>"""

_LINK_ONLY_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><author><name>/u/latawxuce</name></author>
<content type="html">&lt;table&gt;&lt;tr&gt;&lt;td&gt;&lt;a href="https://example.com/thumb"&gt;&lt;img src="https://example.com/thumb.jpg" /&gt;&lt;/a&gt;&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</content>
<id>t3_def456</id>
<link href="https://www.reddit.com/r/CAMPING/comments/def456/title/" />
<updated>2026-07-26T18:25:27+00:00</updated>
<published>2026-07-26T18:25:27+00:00</published>
<title>Cool gallery photo</title>
</entry>
</feed>"""

_DELETED_AUTHOR_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;post body&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt;</content>
<id>t3_ghi789</id>
<link href="https://www.reddit.com/r/CAMPING/comments/ghi789/title/" />
<updated>2026-07-26T18:00:00+00:00</updated>
<title>No published tag, no author</title>
</entry>
</feed>"""

_MULTIREDDIT_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<category term="camping" label="r/camping"/>
<content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;post in r/camping&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt;</content>
<id>t3_multi1</id>
<link href="https://www.reddit.com/r/camping/comments/multi1/title/" />
<updated>2026-07-26T19:00:00+00:00</updated>
<title>From r/camping</title>
</entry>
<entry>
<category term="Yosemite" label="r/Yosemite"/>
<content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;post in r/Yosemite&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt;</content>
<id>t3_multi2</id>
<link href="https://www.reddit.com/r/Yosemite/comments/multi2/title/" />
<updated>2026-07-26T19:01:00+00:00</updated>
<title>From r/Yosemite</title>
</entry>
</feed>"""


@respx.mock
def test_new_posts_parses_selftext_entry() -> None:
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(
        return_value=Response(200, text=_SELFPOST_FEED)
    )
    client = RssRedditClient(user_agent="test-agent")
    posts = client.new_posts("CAMPING", limit=25)

    assert len(posts) == 1
    post = posts[0]
    assert post.post_id == "abc123"
    assert post.subreddit == "CAMPING"
    assert post.title == "Sold out in seconds, any alert tool?"
    assert post.permalink == "https://www.reddit.com/r/CAMPING/comments/abc123/title/"
    assert post.author == "camper1"
    assert "Sold out" in post.body_snippet
    assert "'ll alert me" in post.body_snippet  # entity-decoded, not left as &#39;
    assert "submitted by" not in post.body_snippet
    assert "[link]" not in post.body_snippet
    assert post.created_utc == 1785094008.0


@respx.mock
def test_new_posts_link_only_post_has_empty_snippet() -> None:
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(
        return_value=Response(200, text=_LINK_ONLY_FEED)
    )
    client = RssRedditClient(user_agent="test-agent")
    posts = client.new_posts("CAMPING")
    assert posts[0].body_snippet == ""


@respx.mock
def test_new_posts_handles_missing_author_and_published() -> None:
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(
        return_value=Response(200, text=_DELETED_AUTHOR_FEED)
    )
    client = RssRedditClient(user_agent="test-agent")
    posts = client.new_posts("CAMPING")
    assert posts[0].author == "[deleted]"
    assert posts[0].created_utc == 1785088800.0  # falls back to <updated>


@respx.mock
def test_new_posts_respects_limit() -> None:
    two_entries = _SELFPOST_FEED.replace("</feed>", "") + _LINK_ONLY_FEED.split("<feed", 1)[1]
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(
        return_value=Response(200, text=two_entries)
    )
    client = RssRedditClient(user_agent="test-agent")
    posts = client.new_posts("CAMPING", limit=1)
    assert len(posts) == 1


@respx.mock
def test_new_posts_builds_sort_time_filter_and_after_into_url() -> None:
    route = respx.get(
        "https://www.reddit.com/r/CAMPING/top/.rss",
        params={"limit": "100", "t": "all", "after": "t3_abc123"},
    ).mock(return_value=Response(200, text=_SELFPOST_FEED))
    client = RssRedditClient(user_agent="test-agent")
    client.new_posts("CAMPING", limit=100, sort="top", time_filter="all", after="t3_abc123")
    assert route.called


@respx.mock
def test_new_posts_waits_out_rate_limit_before_next_request(monkeypatch) -> None:
    exhausted = Response(
        200,
        text=_SELFPOST_FEED,
        headers={"x-ratelimit-remaining": "0.0", "x-ratelimit-reset": "38"},
    )
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(return_value=exhausted)

    sleep_calls: list[float] = []
    monkeypatch.setattr(reddit_client.time, "sleep", sleep_calls.append)

    client = RssRedditClient(user_agent="test-agent")
    client.new_posts("CAMPING")  # first call: nothing to wait for yet
    assert sleep_calls == []

    client.new_posts("CAMPING")  # bucket was exhausted by the previous response
    assert len(sleep_calls) == 1
    assert 0 < sleep_calls[0] <= 38


@respx.mock
def test_new_posts_multireddit_attributes_each_post_to_its_real_subreddit() -> None:
    respx.get("https://www.reddit.com/r/camping+Yosemite/new/.rss").mock(
        return_value=Response(200, text=_MULTIREDDIT_FEED)
    )
    client = RssRedditClient(user_agent="test-agent")
    posts = client.new_posts("camping+Yosemite", limit=25)

    assert len(posts) == 2
    by_id = {p.post_id: p for p in posts}
    assert by_id["multi1"].subreddit == "camping"
    assert by_id["multi2"].subreddit == "Yosemite"


@respx.mock
def test_new_posts_no_wait_when_rate_limit_headers_absent() -> None:
    respx.get("https://www.reddit.com/r/CAMPING/new/.rss").mock(
        return_value=Response(200, text=_SELFPOST_FEED)
    )
    client = RssRedditClient(user_agent="test-agent")
    client.new_posts("CAMPING")
    assert client._sleep_until is None
