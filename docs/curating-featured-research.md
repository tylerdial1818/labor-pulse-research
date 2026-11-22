# Curating featured AI research

The AI Impact page on laborpulse.org shows a rotating list of recent research on how AI is affecting jobs and wages. The list lives in [`ai_impact/featured.json`](../ai_impact/featured.json). The site reads it from `main` with an hourly cache, so **merging a PR that edits it is the publishing step**. Nothing in this process calls a paid API.

## How it works

1. **Collect (automatic, weekly).** The [Research feeds](../.github/workflows/feeds.yml) Action runs `lpresearch feeds collect` every Monday. It reads the open feeds in [`ai_impact/feed_sources.json`](../ai_impact/feed_sources.json) (arXiv, OpenAlex, NBER and think-tank RSS), keeps items that mention both AI and a labor-market topic, skips anything already featured or already collected, and commits `ai_impact/candidates/<date>.json`. Each file also records which sources worked, so a dead feed shows up as `"ok": false`.
2. **Curate (monthly, in a LaborPulse project thread).** Ask Claude to "curate this month's featured AI research". The steps are below. The result is a PR, never a direct push.
3. **Review.** Tyler reads the PR and merges it. CI runs `lpresearch check-featured` first.

## Curation steps (for whoever curates, human or Claude)

1. Read the candidates files added since the last curation PR. Open each promising item's page and read at least the abstract and main findings. Favor work that measures AI's effect on jobs, hiring, wages or productivity with real data, updated trackers from credible institutions, and landmark-paper revisions. Skip opinion pieces, vendor marketing and work with no data.
2. Pick about five to eight items. Keep a balance of findings: include studies that find no effect as well as ones that find an effect.
3. For each pick, add an entry to `featured.json`:
   - `summary`: two sentences in plain language, written for someone with no economics background. Say what was measured and what was found.
   - `evidence`: any number in the summary must also appear in a short quote copied from the source, with that page's URL. `lpresearch check-featured` fails if a summary number has no quote behind it. If a number cannot be quoted, make the point without it.
   - `featured_on` is the PR date and `featured_until` about 90 days later (at most 120).
   - `data_access` is `public` only if anyone can download the data the study uses.
4. Leave expired items in the file. The site moves them into the page's research library automatically.
5. Run `lpresearch check-featured`, update `updated` at the top of the file, and open a PR titled "Featured AI research: <month year>".

## Fixing or adding a feed

Edit `ai_impact/feed_sources.json`. Supported kinds are `rss`, `atom` and `openalex`; `{since}` in a URL is replaced with the start date of the collection window. Run `lpresearch feeds collect` locally (or trigger the Action by hand) and check the source's status in the new candidates file.
