#!/usr/bin/env python3
"""Finish a Claude Design export of the site before it is committed.

    python3 tools/post_export.py index.html            # rewrite in place
    python3 tools/post_export.py index.html --dry-run  # report only

Safe to run more than once. It does three things the Design export can't:

1. Outer <head> tags. The export puts its description, Open Graph and icon
   tags inside the bundle, so they only exist after JavaScript runs. Link
   previews (iMessage, WhatsApp, Slack, Discord, X) and search snippets read
   the raw HTML, so they are copied out here, plus a preview image, icons,
   a viewport tag and lang="en".
2. Loading splash. Replaces the export's placeholder with the header logo
   centred on white, and hides the "Unpacking..." pill.
3. Image weight. Re-encodes bundled images that are far larger than they are
   ever shown. Images that don't come out meaningfully smaller are left alone.

Needs Pillow (pip install pillow).
"""
import argparse
import base64
import io
import json
import re
import sys

from PIL import Image
from PIL.PngImagePlugin import PngInfo

SITE = "https://playorangecat.com"
MARK = b"ocs-post-export"   # written into images this script re-encodes
# Cloudflare Web Analytics site token (dash.cloudflare.com > Web Analytics >
# playorangecat.com > Manage site). Empty = no analytics beacon.
CF_WEB_ANALYTICS_TOKEN = "8a6bfc77337d43c0b1b5c580ae95d5cc"   # public site token, not a secret
HEAD_START = "<!-- ocs:head (tools/post_export.py) -->"
HEAD_END = "<!-- /ocs:head -->"
SPLASH_LOGO_PX = 128   # shown size; stored at 2x


# ---------------------------------------------------------------- bundle I/O

def find_script(html, kind):
    m = re.search(r'(<script type="__bundler/%s">)(.*?)(</script>)' % kind, html, re.S)
    if not m:
        sys.exit("Not a Design export: no __bundler/%s script found." % kind)
    return m


def template_text(html):
    return json.loads(find_script(html, "template").group(2))


def load_manifest(html):
    return json.loads(find_script(html, "manifest").group(2))


def store_manifest(html, manifest):
    m = find_script(html, "manifest")
    body = m.group(2)
    lead = body[: len(body) - len(body.lstrip())]
    tail = body[len(body.rstrip()):]
    text = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False)
    return html[: m.start(2)] + lead + text + tail + html[m.end(2):]


# ---------------------------------------------------------------- 1. head

def template_meta(tpl, attr, key):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % (attr, re.escape(key)), tpl)
    return m.group(1) if m else None


def head_block(tpl):
    title = re.search(r"<title>(.*?)</title>", tpl, re.S)
    title = title.group(1).strip() if title else "Orange Cat Studios"
    desc = template_meta(tpl, "name", "description") or ""
    og_title = template_meta(tpl, "property", "og:title") or title
    og_desc = template_meta(tpl, "property", "og:description") or desc
    og_url = template_meta(tpl, "property", "og:url") or SITE + "/"
    theme = template_meta(tpl, "name", "theme-color") or "#ffffff"
    lines = [
        HEAD_START,
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="description" content="%s">' % desc,
        '<meta name="theme-color" content="%s">' % theme,
        '<link rel="canonical" href="%s">' % og_url,
        '<link rel="icon" href="/favicon.ico" sizes="any">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        '<meta property="og:site_name" content="Orange Cat Studios">',
        '<meta property="og:type" content="website">',
        '<meta property="og:url" content="%s">' % og_url,
        '<meta property="og:title" content="%s">' % og_title,
        '<meta property="og:description" content="%s">' % og_desc,
        '<meta property="og:image" content="%s/assets/og-image.png">' % SITE,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="Orange Cat Studios: small games, built with obsession.">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if CF_WEB_ANALYTICS_TOKEN:
        # Cookieless page-view counts. Lives on window, so it survives the bundle's page swap.
        lines.append(
            "<script type=\"module\" src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            "data-cf-beacon='{\"token\": \"%s\"}'></script>" % CF_WEB_ANALYTICS_TOKEN)
    lines.append(HEAD_END)
    return "\n  ".join(lines)


def apply_head(html, tpl):
    head_end = html.index("</head>")
    head = html[:head_end]
    block = head_block(tpl)
    if HEAD_START in head:
        a = head.index(HEAD_START)
        b = head.index(HEAD_END) + len(HEAD_END)
        head = head[:a] + block + head[b:]
    else:
        m = re.search(r'<meta charset="[^"]*">', head, re.I)
        if not m:
            sys.exit("No <meta charset> in the outer head; not touching it.")
        head = head[: m.end()] + "\n  " + block + head[m.end():]
    head = re.sub(r"^(<!DOCTYPE html>\s*)<html>", r'\1<html lang="en">', head, count=1, flags=re.I)
    return head + html[head_end:]


# ---------------------------------------------------------------- 2. splash

SPLASH_CSS = """<style id="ocs-splash">
    /* Loading splash (tools/post_export.py) */
    body, #__bundler_thumbnail { background: #ffffff; }
    #__bundler_thumbnail svg { display: block; }
    #__bundler_thumbnail image { animation: ocs-breathe 1.8s ease-in-out infinite; }
    #__bundler_loading { display: none; }
    @keyframes ocs-breathe { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) { #__bundler_thumbnail image { animation: none; } }
  </style>"""


def header_logo_png(manifest, tpl):
    m = re.search(r'<img src="([0-9a-f-]{36})" alt="Orange Cat Studios"', tpl)
    if not m or m.group(1) not in manifest:
        sys.exit("Couldn't find the header logo (img alt=\"Orange Cat Studios\") in the bundle.")
    im = Image.open(io.BytesIO(base64.b64decode(manifest[m.group(1)]["data"]))).convert("RGBA")
    px = SPLASH_LOGO_PX * 2
    if max(im.size) > px:
        im.thumbnail((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def splash_svg(png):
    uri = "data:image/png;base64," + base64.b64encode(png).decode()
    h = SPLASH_LOGO_PX // 2
    # No viewBox or other camelCase attributes: the Design export mangles them.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" role="img" '
        'aria-label="Orange Cat Studios">'
        '<rect width="100%" height="100%" fill="#ffffff"></rect>'
        '<image x="50%" y="50%" width="{s}" height="{s}" transform="translate(-{h} -{h})" href="{u}"></image>'
        "</svg>"
    ).format(s=SPLASH_LOGO_PX, h=h, u=uri)


def apply_splash(html, manifest, tpl):
    m = re.search(r'(<div id="__bundler_thumbnail">)(.*?)(</div>)', html, re.S)
    if not m:
        sys.exit("No loading placeholder (#__bundler_thumbnail) found.")
    current = m.group(2)
    # The Design source's own placeholder is already this splash; keep it if so.
    if not ('aria-label="Orange Cat Studios"' in current and "data:image/png;base64," in current):
        svg = splash_svg(header_logo_png(manifest, tpl))
        html = html[: m.start(2)] + svg + html[m.end(2):]
    if '<style id="ocs-splash">' in html:
        html = re.sub(r'<style id="ocs-splash">.*?</style>', lambda m: SPLASH_CSS, html, count=1, flags=re.S)
    else:
        i = html.index("</head>")
        html = html[:i] + "  " + SPLASH_CSS + "\n" + html[i:]
    return html


# ---------------------------------------------------------------- 3. images

def shown_px(tpl, uid):
    """Largest explicit px width/max-width an <img> using this asset is given, or None."""
    best = 0
    for m in re.finditer(r'<img src="%s"[^>]*?style="([^"]*)"' % re.escape(uid), tpl):
        for w in re.findall(r"(?:^|;)\s*(?:max-)?width:\s*(\d+)px", m.group(1)):
            best = max(best, int(w))
    return best or None


def target_width(im, tpl, uid):
    w, h = im.size
    px = shown_px(tpl, uid)
    if px:
        return min(w, px * (3 if px <= 120 else 2))   # small marks get 3x for iPhones
    if h > w * 1.5:          # phone screenshot: never shown wider than ~320px here
        return min(w, 640)
    return w if max(w, h) <= 1600 else int(w * 1600 / max(w, h))


def optimize_images(manifest, tpl, log):
    before = after = 0
    for uid, ent in manifest.items():
        mime = ent.get("mime")
        if mime not in ("image/jpeg", "image/png") or ent.get("compressed"):
            continue
        raw = base64.b64decode(ent["data"])
        im = Image.open(io.BytesIO(raw))
        im.load()
        before += len(raw)
        if MARK in (im.info.get("comment") or b"") or im.info.get("Software") == MARK.decode():
            after += len(raw)       # already done on an earlier run; don't re-compress
            continue
        alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        tw = target_width(im, tpl, uid)
        if tw < im.size[0]:
            im = im.convert("RGBA" if alpha else "RGB").resize(
                (tw, round(im.size[1] * tw / im.size[0])), Image.LANCZOS)
        buf = io.BytesIO()
        if alpha:
            info = PngInfo()
            info.add_text("Software", MARK.decode())
            im.save(buf, "PNG", optimize=True, pnginfo=info)
            new_mime = "image/png"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True, progressive=True,
                                   comment=MARK)
            new_mime = "image/jpeg"
        new = buf.getvalue()
        if len(new) < len(raw) * 0.9:
            ent["data"] = base64.b64encode(new).decode()
            ent["mime"] = new_mime
            after += len(new)
            log.append("  %s %-10s %5d KB -> %4d KB  (%dx%d)" % (
                uid[:8], mime.split("/")[1], len(raw) // 1024, len(new) // 1024, *im.size))
        else:
            after += len(raw)
    log.append("  images total: %d KB -> %d KB" % (before // 1024, after // 1024))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    html = open(args.path, encoding="utf-8").read()
    size0 = len(html.encode())
    tpl = template_text(html)
    manifest = load_manifest(html)

    log = []
    html = apply_splash(html, manifest, tpl)      # before resizing: uses the full-size logo
    optimize_images(manifest, tpl, log)
    html = store_manifest(html, manifest)
    html = apply_head(html, tpl)

    print("Images:")
    print("\n".join(log))
    print("Head tags, splash: applied")
    print("File: %d KB -> %d KB" % (size0 // 1024, len(html.encode()) // 1024))
    if not args.dry_run:
        with open(args.path, "w", encoding="utf-8", newline="") as f:
            f.write(html)


if __name__ == "__main__":
    main()
