# playorangecat.com — deploy notes

Everything needed to host the site is in this folder. It is a fully static
site: one self-contained `index.html` (all CSS, JS and images inlined, ~1.8 MB),
plus a redirect and the domain config. No build step, no dependencies.

## Files

| File | What it does |
| --- | --- |
| `index.html` | The whole site. Pages are hash routes: `/#home`, `/#games`, `/#sudoku`, `/#2048`, `/#about`, `/#support`, `/#faq`, `/#contact`, `/#privacy` |
| `privacy.html` | Redirects to `/#privacy` — keeps the URL the apps already link to alive |
| `CNAME` | Tells GitHub Pages to serve the site at `playorangecat.com` |
| `.nojekyll` | Stops GitHub from running Jekyll over the files |

**Do not hand-edit `index.html`.** It is compiled from the design file. Ask for a
rebuild and replace it wholesale.

## 1. Push to GitHub

Either reuse the existing `orangecatstudios-web` repo or make a new public one
(a repo named `playorangecat` is fine — the custom domain makes the repo name
invisible).

```bash
cd site
git init
git add -A
git commit -m "Launch playorangecat.com"
git branch -M main
git remote add origin https://github.com/benjaminpassmore/playorangecat.git
git push -u origin main
```

If you reuse `orangecatstudios-web`, copy these four files into the repo root,
delete the old `privacy.html` (this one replaces it), commit and push.

## 2. Turn on Pages

Repo → **Settings → Pages**

- Source: **Deploy from a branch**
- Branch: **main**, folder: **/ (root)**
- Custom domain: **playorangecat.com** → Save
- Tick **Enforce HTTPS** once the certificate is issued (can take up to an hour)

## 3. DNS at GoDaddy

GoDaddy → My Products → playorangecat.com → **DNS → Manage Zones**.

Delete GoDaddy's default parked `A` record for `@` and the `CNAME` for `www`
(the ones pointing at their parking page), then add:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | @ | 185.199.108.153 | 600 |
| A | @ | 185.199.109.153 | 600 |
| A | @ | 185.199.110.153 | 600 |
| A | @ | 185.199.111.153 | 600 |
| CNAME | www | benjaminpassmore.github.io | 600 |

Those four A records are GitHub Pages' apex-domain addresses; all four go in so
the site stays up if one is down. Verify the values against GitHub's current
docs ("Managing a custom domain for your GitHub Pages site") before relying on
them long-term — GitHub has changed them in the past.

Propagation is usually minutes, occasionally a few hours. GitHub's Pages
settings page shows a green check when the domain resolves.

## 4. After it is live

- Point the apps' `PRIVACY_POLICY_URL` at `https://playorangecat.com/privacy.html`
  (currently `https://benjaminpassmore.github.io/orangecatstudios-web/privacy.html`).
  It lives in `screens/SettingsScreen.tsx` and `screens/PaywallScreen.tsx` in the
  Warmboard Sudoku repo.
- Add the domain as the Support URL and Marketing URL in App Store Connect and
  the Google Play listing.
- The contact form opens the visitor's own email app with a pre-filled draft to
  orangecatstudios@proton.me (subject tagged with the topic chip; name, email,
  topic and message in the body). Nothing is sent until they press send there,
  and nothing is silently dropped. If you later want submissions to arrive
  without the visitor's mail client involved, point the form at Formspree's
  free tier — it works on static GitHub Pages with no backend.
