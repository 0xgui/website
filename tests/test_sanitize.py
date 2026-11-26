import unittest

from scripts.htmltext import html_to_markdown, sanitize


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

    def test_uri_scheme_allowlist_for_links_and_images(self):
        html = (
            '<p>'
            '<a href="  javascript:alert(1)">padded</a> '
            '<a href="java\tscript:alert(1)">tabbed</a> '
            '<a href="\x00javascript:alert(1)">nul</a> '
            '<a href="vbscript:msgbox(1)">vbs</a> '
            '<a href="data:text/html,<script>alert(1)</script>">data</a> '
            '<a href="https://example.com/ok">https</a> '
            '<a href="http://example.com/ok">http</a> '
            '<a href="mailto:guilherme@silvags.com">mail</a> '
            '<a href="/about/">rel</a> '
            '<a href="#top">frag</a>'
            '</p>'
            '<img src="data:image/svg+xml,<svg onload=alert(1)>" alt="svg">'
            '<img src="javascript:alert(1)" alt="js">'
            '<img src="vbscript:msgbox(1)" alt="vbs">'
            '<img src="http://cdn.example/insecure.webp" alt="http">'
            '<img src="https://cdn.example/safe.webp" alt="safe">'
            '<img src="images/01.webp" alt="local">'
        )
        out = sanitize(html)
        for bad in ("javascript:", "vbscript:", "data:", "insecure.webp"):
            self.assertNotIn(bad, out.lower())
        self.assertIn('href="https://example.com/ok"', out)
        self.assertIn('href="http://example.com/ok"', out)
        self.assertIn('href="mailto:guilherme@silvags.com"', out)
        self.assertIn('href="/about/"', out)
        self.assertIn('href="#top"', out)
        self.assertIn('src="https://cdn.example/safe.webp"', out)
        self.assertIn('src="images/01.webp"', out)

    def test_youtube_iframe_host_validation(self):
        html = (
            '<iframe src="https://evil.example/embed/abcdef123"></iframe>'
            '<iframe src="https://youtube.com.evil.example/embed/abcdef123"></iframe>'
            '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
            '<iframe src="https://www.youtube-nocookie.com/embed/abc123456"></iframe>'
            '<iframe src="https://youtu.be/xyz987654"></iframe>'
        )
        out = sanitize(html)
        self.assertNotIn("abcdef123", out)
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ", out)
        self.assertIn("https://www.youtube.com/watch?v=abc123456", out)
        self.assertIn("https://www.youtube.com/watch?v=xyz987654", out)

    def test_unclosed_tags_inside_skipped_widget_preserve_following_content(self):
        html = (
            '<div class="subscription-widget"><span>unclosed</div>'
            '<p>KEEP</p>'
            '<div class="subscribe-widget"><div>nested</div></p>still skipped</div>'
            '<p>ALSO KEEP</p>'
        )
        out = sanitize(html)
        self.assertNotIn("unclosed", out)
        self.assertNotIn("nested", out)
        self.assertNotIn("still skipped", out)
        self.assertIn("<p>KEEP</p>", out)
        self.assertIn("<p>ALSO KEEP</p>", out)

    def test_pre_scrubs_banned_terms_while_preserving_whitespace(self):
        html = (
            '<pre>  city = "Leiria"\n'
            '    link = https://x.com/someone\n'
            '      keep =   42</pre>'
        )
        out = sanitize(html)
        self.assertNotIn("Leiria", out)
        self.assertNotIn("x.com", out)
        self.assertIn('<pre>  city = ""\n    link = \n      keep =   42</pre>', out)

    def test_leiria_is_removed_and_portugal_kept(self):
        html = "<p>The first event in Portugal.</p><p>Leiria stays out.</p>"
        out = sanitize(html)
        self.assertIn("in Portugal", out)
        self.assertNotIn("Leiria", out)

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


class MarkdownTests(unittest.TestCase):
    def test_inline_formatting_inside_links_and_dt(self):
        doc = (
            '<main>'
            '<p><a href="/about/"><strong>About</strong> me</a> and '
            '<a href="/work/"><em>my</em> <code>work</code></a>.</p>'
            '<dl><dt><code>MCU</code> &amp; <em>board</em></dt><dd>ATOM Matrix</dd></dl>'
            '</main>'
        )
        md = html_to_markdown(doc, "https://silvags.com/")
        self.assertIn("[**About** me](https://silvags.com/about/)", md)
        self.assertIn("[*my* `work`](https://silvags.com/work/)", md)
        self.assertIn("**`MCU` & *board*:** ATOM Matrix", md)

    def test_whitespace_only_emphasis_does_not_corrupt_markdown(self):
        doc = "<main><p>It <em><strong>does something</strong></em><strong> </strong>in physical space.</p></main>"
        md = html_to_markdown(doc, "https://silvags.com/")
        self.assertEqual(md, "It ***does something*** in physical space.\n")

    def test_unclosed_tag_inside_aria_hidden_preserves_document(self):
        doc = '<main><span aria-hidden="true"><b>x</span><p>KEEP</p></main>'
        md = html_to_markdown(doc, "https://silvags.com/")
        self.assertNotIn("x", md)
        self.assertEqual(md, "KEEP\n")

    def test_sub_span_spacing_inside_headings(self):
        doc = (
            '<main>'
            '<h2>Hitachi Digital <span class="sub">formerly synvert xgeeks</span></h2>'
            '<h3>Deichmann <span class="sub">client</span></h3>'
            '</main>'
        )
        md = html_to_markdown(doc, "https://silvags.com/")
        self.assertIn("## Hitachi Digital · formerly synvert xgeeks", md)
        self.assertIn("### Deichmann · client", md)
        self.assertNotIn("—", md)

    def test_html_table_renders_as_markdown_pipe_table(self):
        doc = (
            "<main>"
            "<table>"
            "<thead><tr><th>A</th><th>B</th></tr></thead>"
            "<tbody><tr><td>1</td><td>2</td></tr><tr><td>a | b</td><td><a href='/x/'><strong>link</strong></a></td></tr></tbody>"
            "</table>"
            "</main>"
        )
        md = html_to_markdown(doc, "https://silvags.com/")
        expected = (
            "| A | B |\n"
            "| --- | --- |\n"
            "| 1 | 2 |\n"
            "| a \\| b | [**link**](https://silvags.com/x/) |\n"
        )
        self.assertEqual(md, expected)

        headerless = "<main><table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table></main>"
        self.assertEqual(
            html_to_markdown(headerless, "https://silvags.com/"),
            "| A | B |\n| --- | --- |\n| 1 | 2 |\n",
        )


if __name__ == "__main__":
    unittest.main()
