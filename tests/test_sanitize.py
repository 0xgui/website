import unittest

from scripts.htmltext import sanitize


class SanitizeTests(unittest.TestCase):
    def test_strips_script_and_handlers(self):
        html = '<p onclick="alert(1)">Hi</p><script>alert(1)</script><p>There</p>'
        out = sanitize(html)
        self.assertNotIn("script", out.lower())
        self.assertNotIn("onclick", out)
        self.assertIn("Hi", out)
        self.assertIn("There", out)

    def test_keeps_links_images_and_structure(self):
        html = (
            '<p>See <a href="https://example.com/a">docs</a> and <strong>this</strong>.</p>'
            '<ul><li>One</li></ul>'
            '<img src="https://cdn.example/a.webp" alt="Arm">'
        )
        out = sanitize(html)
        self.assertIn('href="https://example.com/a"', out)
        self.assertIn('target="_blank"', out)
        self.assertIn("<strong>this</strong>", out)
        self.assertIn("<li>One</li>", out)
        self.assertIn('src="https://cdn.example/a.webp"', out)
        self.assertIn('alt="Arm"', out)

    def test_drops_javascript_and_banned_links(self):
        html = (
            '<a href="javascript:alert(1)">x</a>'
            '<a href="https://x.com/someone">profile</a>'
            '<a href="https://twitter.com/someone">bird</a>'
            '<p>See https://x.com/someone today.</p>'
        )
        out = sanitize(html)
        self.assertNotIn("javascript:", out)
        self.assertNotIn("x.com", out)
        self.assertNotIn("twitter.com", out)
        self.assertIn("profile", out)
        self.assertIn("today", out)

    def test_place_names_are_removed(self):
        html = "<p>The first event in Portugal, and the highest point of Portugal.</p><p>Leiria stays out.</p>"
        out = sanitize(html)
        self.assertNotIn("Portugal", out)
        self.assertNotIn("Leiria", out)
        self.assertIn("there", out)
        self.assertIn("of the trip", out)

    def test_entities_are_not_double_encoded(self):
        out = sanitize("<p>AT&amp;T</p>")
        self.assertIn("AT&amp;T", out)
        self.assertNotIn("&amp;amp;", out)

    def test_subscription_widget_and_image_chrome(self):
        html = (
            '<div class="subscription-widget-wrap-editor"><form><p>Subscribe now</p></form></div>'
            '<figure><a class="image-link" href="https://cdn.example/full.jpg">'
            '<div><picture><source srcset="https://cdn.example/a.webp">'
            '<img src="https://cdn.example/a.jpg" alt="Pico"></picture>'
            '<button>save</button></div></a><figcaption>On the desk</figcaption></figure>'
        )
        out = sanitize(html)
        self.assertNotIn("Subscribe", out)
        self.assertNotIn("<button", out)
        self.assertNotIn("<form", out)
        self.assertIn('src="https://cdn.example/a.jpg"', out)
        self.assertIn("On the desk", out)
        self.assertIn("<figcaption>", out)


if __name__ == "__main__":
    unittest.main()
