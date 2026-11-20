# Note style guide

Notes are published under the byline **LaborPulse Research Desk** and read by policy staff, journalists, workforce boards and researchers. Whoever drafts a note, human or Claude, follows this guide.

## Voice and structure

- Lead with the finding and what it means for a decision maker, then explain how it was estimated.
- Use plain language. Define a benefit-cost ratio or net present value the first time it appears.
- Say what the analysis does not show as clearly as what it does: name the main assumptions, the evidence they rest on and where results are sensitive.
- Write in the institutional voice ("this analysis", "the model"), never "I" or "we".
- Aim for 600 to 900 words: a `# ` title and three to five `## ` sections.
- Link to the study's methods (model card, protocol) rather than repeating them.

## Numbers

- Every number must come from the note's `facts.json`, rounded however reads best ("$7,505", "$7.5k", "98%").
- Do not compute new numbers from facts, such as differences, sums or a ratio restated as a percentage. If a derived number is worth quoting, add it to the pipeline's facts first so it is computed and tested.
- Do not bring in numbers from memory or other sources. An external statistic belongs in `facts.json` as an `external` fact with its URL.
- Calendar years are fine. Spell out small counts in words ("four sites") unless the count is itself a fact.
- If a point needs a number that is not in the facts, make the point without the number.
