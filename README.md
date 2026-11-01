# silvags.com

Personal website and robot build log. Static HTML/CSS/JS — no build step.

Essays from Binary Paths are mirrored into `writing/<slug>/` by `python3 scripts/mirror_substack.py`. Agent indexes (`llms.txt`, Markdown twins, `robots.txt`, `sitemap.xml`, `feed.xml`) are regenerated from the HTML by `python3 scripts/build_agent.py`. Tests: `python3 -m unittest discover -s tests -v` and `node --test tests/negotiate.test.mjs`.
