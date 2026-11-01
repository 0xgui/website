import json
import unittest
from pathlib import Path

from scripts.feeds import (
    ChallengeError,
    EmptyFeed,
    MalformedFeed,
    looks_like_challenge,
    posts_from_api,
    posts_from_rss,
)

FIX = Path(__file__).parent / "fixtures"


class FeedTests(unittest.TestCase):
    def test_normal_rss(self):
        posts = posts_from_rss((FIX / "normal.xml").read_text(encoding="utf-8"))
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.slug, "hello-world")
        self.assertEqual(post.title, "Hello world")
        self.assertEqual(post.kind, "full")
        self.assertIn("The full essay.", post.body_html)
        self.assertIn("pic.jpg", post.body_html)
        self.assertEqual(post.cover_url, "https://cdn.example/cover.jpg")
        self.assertEqual(post.date_key(), "2026-03-05")

    def test_cdata(self):
        post = posts_from_rss((FIX / "cdata.xml").read_text(encoding="utf-8"))[0]
        self.assertEqual(post.title, "Hello & welcome")
        self.assertNotIn("CDATA", post.title)
        self.assertIn("Body with CDATA", post.body_html)

    def test_entities_decoded_once(self):
        post = posts_from_rss((FIX / "entities.xml").read_text(encoding="utf-8"))[0]
        self.assertEqual(post.title, "AT&T <robots>")
        self.assertNotIn("&amp;", post.title)
        self.assertEqual(post.description, "Fish & chips")

    def test_empty(self):
        with self.assertRaises(EmptyFeed):
            posts_from_rss((FIX / "empty.xml").read_text(encoding="utf-8"))

    def test_malformed(self):
        with self.assertRaises(MalformedFeed):
            posts_from_rss((FIX / "malformed.xml").read_text(encoding="utf-8"))

    def test_paywalled_rss_is_a_stub(self):
        post = posts_from_rss((FIX / "paywalled.xml").read_text(encoding="utf-8"))[0]
        self.assertEqual(post.kind, "stub")
        self.assertNotIn("secret", post.body_html)
        self.assertIn("excerpt", post.body_html.lower() + post.description.lower())

    def test_challenge_html_is_not_a_feed(self):
        body = (FIX / "challenge.html").read_text(encoding="utf-8")
        self.assertTrue(looks_like_challenge(403, body, "text/html"))
        with self.assertRaises(ChallengeError):
            posts_from_rss(body)

    def test_api_and_paid(self):
        posts = posts_from_api(json.loads((FIX / "api.json").read_text(encoding="utf-8")))
        self.assertEqual(posts[0].kind, "full")
        self.assertIn("<p>The full essay.</p>", posts[0].body_html)
        paid = posts_from_api(json.loads((FIX / "api-paid.json").read_text(encoding="utf-8")))
        self.assertEqual(paid[0].kind, "stub")
        self.assertNotIn("secret", paid[0].body_html)
        self.assertIn("public excerpt", paid[0].body_html.lower())


if __name__ == "__main__":
    unittest.main()
