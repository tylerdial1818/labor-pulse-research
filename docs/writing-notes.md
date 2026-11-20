# Writing a research note

Notes are drafted by Claude in a LaborPulse project thread, in the same way as any other work in this repo. Nothing calls the Anthropic API, so there is no API key to manage and no per-note API cost.

## Asking for a note

In the LaborPulse project, ask for a note in plain words, for example: "Write a research note on what Utah gets back from sector training, focused on who pays." Claude then follows the steps below and opens a pull request.

## Steps (for whoever drafts the note)

1. **Branch.** Start from `main` on a branch named `note/<short-slug>`.
2. **Look at the facts.** `lpresearch facts utah-roi` lists every number the note may use, with a description of each.
3. **Set up the folder.** `lpresearch new-note utah-roi --title "What Utah gets back from sector training"` runs the pipeline and creates `notes/utah_roi/<date>-<slug>/` with `note.md` (front matter and a placeholder) and `facts.json` (the facts snapshot).
4. **Write.** Replace the placeholder with the note, following [note-style.md](note-style.md). Background is in `studies/<study>/docs/`, especially the model card and analysis protocol.
5. **Verify.** `lpresearch verify -v --facts notes/utah_roi/<folder>/facts.json notes/utah_roi/<folder>/note.md` must report 0 unverified numbers. Fix each failure by matching a fact or dropping the figure. If a number genuinely belongs in the note, add it to the pipeline's facts in a separate change.
6. **Mark it for publishing and index it.** Set `status: "published"` in the front matter (leave it as `"draft"` to merge a note without putting it on the site), then run `lpresearch index-notes` to update `notes/index.json`.
7. **Check.** `lpresearch check-notes` and `pytest` must pass.
8. **Open the pull request.** Title it `Note: <title>`, and say in the body what the note argues and which facts it relies on most. The pull request is the editorial review: check interpretation, caveats and tone, edit freely, and merge to publish.

## How a note reaches the site

The LaborPulse site reads `notes/index.json` and each `note.md` from this repository's `main` branch and shows every note whose status is `published` at `laborpulse.org/research`. It rechecks about once an hour, so a merged note appears within the hour with no site deploy.

## What CI enforces

`lpresearch check-notes` runs on every pull request. It fails when:

- a number in a note does not match a fact in that note's `facts.json`
- a snapshot value no longer equals what the pipeline computes today (so a model change flags every note whose numbers moved)
- a note still contains the `new-note` placeholder
- a note's status is not `draft` or `published`
- `notes/index.json` is out of date
