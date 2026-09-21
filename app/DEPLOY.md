# Publishing this page

The site is one self-contained file. All the data is inlined into
`app/index.html` as `window.__AFL__`, so there is no build step, no server,
and no API to stand up. Three files go up:

    index.html               the page
    og-draw-cost.png         the social card image (outputs/figures/og-draw-cost.png)
    afl-draw-methodology.pdf the method note the footer links to (docs/)

## Step 1 — set the URL

`index.html` ships with `__SITE_URL__` wherever an absolute URL is needed.
Those are the canonical tag and the OG/Twitter card tags, and they have to be
absolute or LinkedIn will not render a preview card. Once you know the
address, run this from the project root:

    python -c "p='app/index.html';s=open(p,encoding='utf-8').read();open(p,'w',encoding='utf-8').write(s.replace('__SITE_URL__','https://YOUR-URL-HERE/'))"

Keep the trailing slash. Check it worked:

    grep -c __SITE_URL__ app/index.html    # should print 0

## Step 2 — pick a host

**Netlify Drop — fastest, no account needed to try.**
Go to https://app.netlify.com/drop and drag a folder containing the three
files. You get a URL in about ten seconds. Claim the site with a free account
if you want to keep it and rename it to something readable. Redeploying means
dragging the folder again.

**GitHub Pages — free and permanent, best if you want it to last.**
Create a new public repo, upload the three files to the root, then
Settings → Pages → Source: Deploy from a branch → main → / (root). Live at
`https://<user>.github.io/<repo>/` within a minute or two. Add an empty
`.nojekyll` file at the root so Jekyll does not touch it.

**Cloudflare Pages — free, custom domain is easiest here.**
Connect the repo or upload the folder directly. Same result, better if you
ever put a real domain on it.

## Step 3 — check the social card

Paste the URL into https://www.linkedin.com/post-inspector/. It shows exactly
what the card will look like and forces LinkedIn to re-scrape if you change
the tags later. LinkedIn caches aggressively, so do this before posting, not
after.
