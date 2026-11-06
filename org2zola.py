# SPDX-FileCopyrightText: 2026 karmar <karmar@posteo.de>
# SPDX-License-Identifier: GPL-3.0-or-later

#!/usr/bin/env python3
# ============================================================================
# org2zola.py — convert org-roam notes into a Zola site skeleton.
#
# Usage:  python3 org2zola.py SRC_DIR SITE_DIR BASE_URL
#
# Sections:
#   * Notes tagged  #+filetags: :blog:  (or "blog" among several tags)
#     become blog posts under content/blog/.
#   * All other notes become wiki pages under content/wiki/.
#   * The overview note (org-roam naming: *-wiki.org, e.g.
#     20260531142502-wiki.org) is promoted to the wiki section index
#     (content/wiki/_index.md), so its content heads /wiki/.
#     If several match, the oldest (lowest timestamp) wins; the others
#     remain ordinary wiki pages.
#
# Languages / translations:
#   * The note language is taken from #+language: (default: "en").
#   * A roam link between two blog notes of DIFFERENT languages declares
#     them as translations of each other — e.g. the English article
#     links to [[id:<german-note>][Deutsche Version]] as usual in
#     org-roam, and the site pairs them automatically.
#   * Translations are emitted using Zola's multilingual convention:
#     the English page becomes content/blog/<en-stem>.md and its German
#     counterpart content/blog/<en-stem>.de.md (the EN note's stem
#     carries the pair). Templates get page.translations to build the
#     language-switch button. German pages are excluded from the
#     English section listings; they are reachable via the switch
#     button (and the language-specific section index).
#
# Roam links [[id:...]] are resolved via :ID: drawers across BOTH
# sections. IMPORTANT: Zola only rewrites links to page permalinks when
# they use its @/ internal-link scheme — but pandoc mangles org links
# whose target starts with "@" (they never reach the output as links).
# Therefore:
#   1. roam links are rewritten to RELATIVE targets (../wiki/foo.md)
#      before pandoc, which pandoc converts to normal markdown links;
#   2. AFTER pandoc, a plain-text substitution converts
#      ](../wiki/foo.md)  ->  ](@/wiki/foo.md)
#      so Zola sees valid internal links and rewrites them to the real
#      page URLs. Zola validates @/ targets at build time, so dangling
#      targets fail loudly instead of serving 404s.
#
# Site chrome (nav + banner links) is configured in the constants below
# and written to config.toml [extra].
# ============================================================================
import re
import sys
import pathlib
import subprocess

src_dir = pathlib.Path(sys.argv[1])
site_dir = pathlib.Path(sys.argv[2])
base_url = sys.argv[3]

# ---------------------------------------------------------------------------
# Site identity — adjust freely. These land in config.toml [extra] and are
# consumed by the templates for the banner/menu.
# ---------------------------------------------------------------------------
SITE_TITLE = "KARMAR"
GITLAB_PROFILE = "https://gitlab.com/karmarian"
GITHUB_PROFILE = "https://github.com/karmarian"
SOURCE_REPO = "https://gitlab.com/karmarian/wiki"

DEFAULT_LANG = "en"


def esc_toml(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def slugify(h):
    # Approximation of the Zola heading anchor algorithm.
    s = h.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


org_files = sorted(src_dir.glob("*.org"))
if not org_files:
    raise SystemExit("ERROR: no .org files found in " + str(src_dir))


def is_overview(stem):
    return stem == "wiki" or stem.endswith("-wiki")


# ---- pass 1: classification + roam ID map (across all notes) ---------------
id_re = re.compile(r":ID:\s*([0-9a-zA-Z-]+)")
tags_re = re.compile(r"^\s*#\+filetags:\s*(.+?)\s*$", re.M)
title_re = re.compile(r"^\s*#\+title:\s*(.+?)\s*$", re.M)
lang_re = re.compile(r"^\s*#\+language:\s*(\S+)\s*$", re.M)

id_map = {}
note_meta = {}
for org in org_files:
    text = org.read_text(encoding="utf-8")
    tm = title_re.search(text)
    gm = tags_re.search(text)
    lm = lang_re.search(text)
    tags = ([t for t in gm.group(1).strip().strip(":").split(":") if t]
            if gm else [])
    note_meta[org.stem] = {
        "title": tm.group(1) if tm else org.stem,
        "blog": "blog" in tags,
        "overview": is_overview(org.stem),
        "lang": lm.group(1).lower() if lm else DEFAULT_LANG,
    }
    im = id_re.search(text)
    if im:
        if im.group(1) in id_map:
            print("WARN: duplicate roam ID " + im.group(1), file=sys.stderr)
        id_map[im.group(1)] = org.stem

blog_set = {s for s, m in note_meta.items() if m["blog"]}
# Oldest (lowest timestamp prefix) *-wiki note becomes the section index.
overview_candidates = sorted(s for s, m in note_meta.items() if m["overview"])
overview_stem = overview_candidates[0] if overview_candidates else None
if len(overview_candidates) > 1:
    print(
        "WARN: multiple overview candidates ({}) — using {}".format(
            ", ".join(overview_candidates), overview_stem
        ),
        file=sys.stderr,
    )

# ---- pass 1.5: translation pairing -----------------------------------------
# A roam link between two blog notes of different languages declares a
# translation pair. Run over all notes first so pairing is independent
# of processing order.
raw_id_re = re.compile(r"\[\[id:([0-9a-zA-Z-]+)")
translation_of = {}
for org in org_files:
    s = org.stem
    ms = note_meta[s]
    if not ms["blog"]:
        continue
    for ident in raw_id_re.findall(org.read_text(encoding="utf-8")):
        t = id_map.get(ident)
        if t is None or not note_meta[t]["blog"]:
            continue
        if note_meta[t]["lang"] != ms["lang"]:
            translation_of[s] = t
            translation_of[t] = s

# Languages that actually occur among blog posts (besides the default).
blog_langs = sorted({note_meta[s]["lang"]
                     for s in blog_set if note_meta[s]["lang"] != DEFAULT_LANG})


# ---- pass 2: link rewriting (pre-pandoc) ------------------------------------
# Targets stay RELATIVE at this stage (../wiki/foo.md): pandoc turns them
# into ordinary markdown links. The @/ swap happens post-pandoc (pass 3).
link_re = re.compile(r"\[\[([^\[\]]+)\](?:\[([^\[\]]*)\])?\]")


def expand(m):
    target, desc = m.group(1), m.group(2)
    if target.startswith("id:"):
        rest = target[3:]
        ident, heading = rest, None
        if "#" in rest:
            ident, heading = rest.split("#", 1)
        stem = id_map.get(ident)
        if stem is None:
            print("WARN: unresolved roam ID " + ident, file=sys.stderr)
            return desc if desc else ident
        if stem == overview_stem:
            t = "../wiki/_index.md"
        else:
            section = "blog" if stem in blog_set else "wiki"
            t = "../" + section + "/" + stem + ".md"
        if heading:
            t = t + "#" + slugify(heading)
        return "[[" + t + "][" + (desc if desc else stem) + "]]"
    if target.startswith("*"):
        heading = target[1:]
        return "[[#" + slugify(heading) + "][" + (desc if desc else heading) + "]]"
    # file:/https/mailto and anything else: leave untouched for pandoc
    return m.group(0)


def rewrite(text):
    return link_re.sub(expand, text)


# ---- pass 3: convert -------------------------------------------------------
content = site_dir / "content"
(content / "blog").mkdir(parents=True, exist_ok=True)
(content / "wiki").mkdir(parents=True, exist_ok=True)

# Post-pandoc substitution: markdown links written by pandoc as
# [desc](../wiki/foo.md) or [desc](../wiki/foo.md#anchor) become Zola
# internal links [desc](@/wiki/foo.md). Plain text surgery — pandoc never
# touches these.
internal_re = re.compile(r"\]\(\.\./((?:wiki|blog)/[^\s)#]*?\.md)(#[^\s)#]*)?\)")


def fix_internal(m):
    target, anchor = m.group(1), m.group(2)
    return "](@/" + target + (anchor or "") + ")"


def blog_filename(stem, lang):
    # Translations share the DEFAULT-language note's stem so Zola pairs
    # them (<stem>.md + <stem>.de.md). An unpaired translation keeps its
    # own stem.
    if lang == DEFAULT_LANG:
        return stem + ".md"
    return translation_of.get(stem, stem) + "." + lang + ".md"


n_blog = n_wiki = n_overview = 0
for org in org_files:
    stem = org.stem
    meta = note_meta[stem]
    text = org.read_text(encoding="utf-8")
    dm = re.match(r"(\d{4})(\d{2})(\d{2})\d{6}", stem)
    date = "{}-{}-{}".format(dm.group(1), dm.group(2), dm.group(3)) if dm else None

    tmp = site_dir / (stem + ".pre.org")
    tmp.write_text(rewrite(text), encoding="utf-8")
    md = subprocess.run(
        ["pandoc", "-f", "org", "-t", "gfm", "--wrap=none", str(tmp)],
        check=True, capture_output=True, text=True,
    ).stdout
    tmp.unlink()

    # Two plain-text fixups, applied OUTSIDE fenced code blocks only
    # (chunks at even indices are outside the ``` fences):
    #   1. pandoc maps org verbatim =x= to gfm highlight ==x==, which Zola
    #      does not render; turn it back into inline code.
    #   2. relative ../(wiki|blog)/foo.md links -> Zola @/ internal links.
    chunks = md.split("```")
    for i in range(0, len(chunks), 2):
        chunks[i] = re.sub(r"==([^\n=]+)==", r"`\1`", chunks[i])
        chunks[i] = internal_re.sub(fix_internal, chunks[i])
    md = "```".join(chunks)

    fm = '+++\ntitle = "' + esc_toml(meta["title"]) + '"\n'
    if date:
        fm = fm + "date = " + date + "\n"
    fm = fm + 'template = "page.html"\ndraft = false\n+++\n\n'

    if stem == overview_stem:
        # The overview note heads the wiki section.
        fm = ('+++\ntitle = "Wiki"\nsort_by = "title"'
              + '\ntemplate = "section.html"\n+++\n\n')
        (content / "wiki" / "_index.md").write_text(fm + md, encoding="utf-8")
        n_overview += 1
    elif meta["blog"]:
        (content / "blog" / blog_filename(stem, meta["lang"])).write_text(
            fm + md, encoding="utf-8"
        )
        n_blog += 1
    else:
        (content / "wiki" / (stem + ".md")).write_text(fm + md, encoding="utf-8")
        n_wiki += 1

# Section indexes
(content / "blog" / "_index.md").write_text(
    '+++\ntitle = "Blog"\nsort_by = "date"\n'
    'template = "section.html"\n+++\n',
    encoding="utf-8",
)
# Per-language section indexes, so translated pages have a proper parent
# section (they stay out of the EN listings via the lang filter).
for lg in blog_langs:
    (content / "blog" / ("_index." + lg + ".md")).write_text(
        '+++\ntitle = "Blog (' + lg.upper() + ')"\nsort_by = "date"\n'
        'template = "section.html"\n+++\n',
        encoding="utf-8",
    )
(content / "_index.md").write_text(
    '+++\ntitle = "Home"\ntemplate = "index.html"\n+++\n',
    encoding="utf-8",
)

# ---- templates -------------------------------------------------------------
tpl = site_dir / "templates"
tpl.mkdir(exist_ok=True)

# Accent color: forest green, LaTeX-style
#   \definecolor{accent}{HTML}{2E5C55}  ->  #2E5C55
# Used for the banner background and page headings; links take a slightly
# lighter tint so body copy stays legible against the paper-white body.
base_css = """
    :root {
      --ink: #24292f;
      --muted: #57606a;
      --line: #d0d7de;
      --paper: #fdfdfc;
      --accent: #2E5C55;
      --accent-light: #4a7d74;
      --on-accent: #f5f8f7;
      --on-accent-muted: rgba(245, 248, 247, 0.75);
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: var(--paper);
           font: 16px/1.6 system-ui, -apple-system, sans-serif; }
    a { color: var(--accent-light); }
    a:hover { color: var(--accent); }
    /* headings carry the accent color */
    h1, h2, h3 { color: var(--accent); font-weight: 650; }
    h1 { border-bottom: 1px solid var(--line); padding-bottom: .3rem; }
    /* banner: forest-green band */
    .banner { display: flex; flex-wrap: wrap; gap: 1rem;
              align-items: baseline; justify-content: space-between;
              padding: 1rem 1.5rem;
              background: var(--accent);
              border-bottom: 2px solid #234740; }
    .banner .brand { font-weight: 700; font-size: 1.1rem;
                     letter-spacing: .04em;
                     text-decoration: none; color: var(--on-accent); }
    .banner nav a { margin-right: 1rem; text-decoration: none;
                    color: var(--on-accent-muted); }
    .banner nav a:hover { color: var(--on-accent); }
    .banner .social { font-size: 0.9rem; }
    .banner .social a { margin-left: 1rem; text-decoration: none;
                        color: var(--on-accent-muted); }
    .banner .social a:hover { color: var(--on-accent); }
    main { max-width: 46rem; margin: 0 auto; padding: 1.5rem; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    code, pre { background: #f2f5f4; border-radius: 4px; }
    code { padding: .15em .35em; }
    pre { padding: 1rem; overflow-x: auto;
          border-left: 3px solid var(--accent); }
    pre code { padding: 0; background: none; }
    table { border-collapse: collapse; }
    th { background: #eef2f1; }
    th, td { border: 1px solid var(--line); padding: .4rem .6rem; }
    blockquote { border-left: 3px solid var(--accent);
                 margin-left: 0; padding: 0 1rem; color: var(--muted); }
    footer { border-top: 1px solid var(--line); color: var(--muted);
             text-align: center; padding: 1rem; font-size: 0.85rem;
             margin-top: 2rem; }
    /* language-switch pills on translated articles */
    .langs { margin: .2rem 0 1rem; }
    .lang-btn { display: inline-block; padding: .15rem .7rem;
                border: 1px solid var(--accent); border-radius: 999px;
                color: var(--accent); text-decoration: none;
                font-size: .8rem; letter-spacing: .08em; }
    .lang-btn:hover { background: var(--accent); color: var(--on-accent); }
"""

(tpl / "base.html").write_text(
    '<!DOCTYPE html>\n<html lang="en">\n  <head>\n'
    '    <meta charset="utf-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '    <meta name="theme-color" content="#2E5C55">\n'
    '    <title>{% block title %}'
    + SITE_TITLE
    + '{% endblock title %}</title>\n'
    "    <style>"
    + base_css
    + "</style>\n"
    "  </head>\n  <body>\n"
    '    <header class="banner">\n'
    '      <a class="brand" href="{{ get_url(path="/" ) }}">'
    + SITE_TITLE
    + "</a>\n"
    "      <nav>\n"
    '        <a href="{{ get_url(path="wiki/") }}">Wiki</a>\n'
    '        <a href="{{ get_url(path="blog/") }}">Blog</a>\n'
    "      </nav>\n"
    '      <div class="social">\n'
    '        <a href="{{ config.extra.gitlab_profile }}" rel="me">GitLab</a>\n'
    '        <a href="{{ config.extra.github_profile }}" rel="me">GitHub</a>\n'
    '        <a href="{{ config.extra.source_repo }}">Source</a>\n'
    "      </div>\n"
    "    </header>\n"
    "    <main>\n"
    "{% block content %}{% endblock content %}\n"
    "    </main>\n"
    "    <footer>\n"
    "      Built with <a href=\"https://www.getzola.org/\">Zola</a> — "
    '      <a href="{{ config.extra.source_repo }}">view source</a>\n'
    "    </footer>\n"
    "  </body>\n"
    "</html>\n",
    encoding="utf-8",
)

listing = (
    '{% extends "base.html" %}\n'
    "{% block title %}{{ section.title }} — "
    + SITE_TITLE
    + " {% endblock title %}\n"
    "{% block content %}\n"
    "<h1>{{ section.title }}</h1>\n"
    "{{ section.content | safe }}\n"
    "<ul>\n"
    "{% for page in section.pages %}\n"
    # keep translations out of the default-language listings
    "  {%- if page.lang == '" + DEFAULT_LANG + "' %}\n"
    "  <li>\n"
    '    {%- if page.date %}<time class="muted">'
    '{{ page.date | date(format="%Y-%m-%d") }}</time> — {% endif -%}\n'
    '    <a href="{{ page.permalink }}">{{ page.title }}</a>\n'
    "  </li>\n"
    "  {% endif %}\n"
    "{% endfor %}\n"
    "</ul>\n"
    "{% endblock content %}\n"
)
(tpl / "section.html").write_text(listing, encoding="utf-8")

(tpl / "page.html").write_text(
    '{% extends "base.html" %}\n'
    "{% block title %}{{ page.title }} — "
    + SITE_TITLE
    + " {% endblock title %}\n"
    "{% block content %}\n"
    "<article>\n"
    "  <h1>{{ page.title }}</h1>\n"
    # language-switch pills: link to every translated version
    "  {%- if page.translations %}\n"
    '  <nav class="langs">\n'
    "    {% for tr in page.translations %}\n"
    '    <a class="lang-btn" href="{{ tr.permalink }}">'
    "{{ tr.lang | upper }}</a>\n"
    "    {% endfor %}\n"
    "  </nav>\n"
    "  {%- endif %}\n"
    '  {%- if page.date %}<p class="muted"><time>'
    '{{ page.date | date(format="%Y-%m-%d") }}</time></p>{% endif -%}\n'
    "  {{ page.content | safe }}\n"
    "</article>\n"
    "{% endblock content %}\n",
    encoding="utf-8",
)

# Front page: intro + newest blog posts (ready for later expansion).
# NOTE: Tera/Zola has no `slice` filter; cap the loop with loop.index.
# Translated posts are skipped; only default-language posts are listed.
(tpl / "index.html").write_text(
    '{% extends "base.html" %}\n'
    "{% block content %}\n"
    "<h1>Welcome</h1>\n"
    "{{ section.content | safe }}\n"
    '{% set blog = get_section(path="blog/_index.md") %}\n'
    "<h2>Recent blog posts</h2>\n"
    "{% if blog.pages %}\n"
    "<ul>\n"
    "{% for page in blog.pages %}\n"
    "  {% if loop.index <= 5 %}\n"
    "  {%- if page.lang == '" + DEFAULT_LANG + "' %}\n"
    "  <li>\n"
    '    <time class="muted">{{ page.date | date(format="%Y-%m-%d") }}</time>\n'
    '    — <a href="{{ page.permalink }}">{{ page.title }}</a>\n'
    "  </li>\n"
    "  {% endif %}\n"
    "  {% endif %}\n"
    "{% endfor %}\n"
    "</ul>\n"
    '{% else %}\n<p class="muted">No blog posts yet.</p>\n{% endif %}\n'
    '<p><a href="{{ get_url(path="wiki/") }}"><strong>Browse the Wiki</strong></a></p>\n'
    "{% endblock content %}\n",
    encoding="utf-8",
)

# ---- config ----------------------------------------------------------------
config = (
    'base_url = "' + base_url + '"\n'
    + 'title = "' + esc_toml(SITE_TITLE) + '"\n'
    + 'default_language = "' + DEFAULT_LANG + '"\n'
    + "compile_sass = false\n"
    + "build_search_index = false\n"
    + "generate_feeds = true\n"
    + 'feed_filenames = ["atom.xml"]\n'
)
# Register every language that actually occurs so Zola pairs the
# *.md / *.<lang>.md files as translations.
for lg in blog_langs:
    config += (
        "\n[languages." + lg + "]\n"
        "generate_feeds = false\n"
    )
config += (
    "\n[extra]\n"
    + 'gitlab_profile = "' + GITLAB_PROFILE + '"\n'
    + 'github_profile = "' + GITHUB_PROFILE + '"\n'
    + 'source_repo = "' + SOURCE_REPO + '"\n'
)
(site_dir / "config.toml").write_text(config, encoding="utf-8")

print(
    "converted {} notes -> {} wiki, {} blog ({} translations), "
    "{} overview ({} roam IDs mapped)".format(
        len(org_files), n_wiki, n_blog, len(translation_of) // 2,
        n_overview, len(id_map)
    )
)
