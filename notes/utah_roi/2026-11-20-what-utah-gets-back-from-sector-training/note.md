---
title: "What Utah gets back from sector training"
byline: "LaborPulse Research Desk"
date: "2026-11-20"
study: "utah_roi"
model_version: "0.1.0"
status: "published"
topic: "Returns to a WorkAdvance-style sector training program in Utah, and the mismatch between who pays and who gains"
---
# What Utah gets back from sector training

Sector training that prepares adults for specific in-demand jobs is one of the few workforce strategies with strong randomized evidence behind it. This analysis asks what Utah would get back if it offered a program modeled on WorkAdvance, a four-site randomized trial of sector training, to a cohort of 1,000 eligible adults.

The short answer is that the program creates far more value than it costs, but most of that value goes to participants and the federal government, not to the state budget that would pay for it. Whether Utah should fund sector training is therefore less a question of whether it works than of who pays.

## The program pays off for society

At a net cost of $7,505 per person offered, the model estimates a societal net present value of $28,325 per person over 10 years. Net present value is the total of benefits minus costs, with future years discounted back to today's dollars (here at a 3% real rate). The societal benefit-cost ratio, benefits divided by costs, is 4.77.

That result is not fragile. Across 10,000 simulation draws that vary the effect sizes, costs, discount rate and other inputs together, 98% of draws show positive societal net benefits. Even near the bottom of the simulated range, at the fifth percentile, societal net benefits are $4,489 per person. The conservative scenario stacks several cautious assumptions at once: a higher discount rate, lower completion, higher costs, no value for fringe benefits, and a charge for participants' time. Under it, the benefit-cost ratio is still 2.23.

The program would need to deliver only 21% of the reference earnings gain to break even for society. Holding effects fixed, it could cost up to $35,830 per person before society comes out behind.

## Participants capture most of the gains

Most of the value shows up as higher earnings for the people who enroll. Participants gain a net $28,024 per person offered, a benefit-cost ratio of 4.59 from their own perspective. These are intent-to-treat estimates: they average over everyone offered the program, including those who never finish it, so they do not overstate the gain by counting only completers.

## Utah's budget does not break even on its own

The picture changes from the state's point of view. If Utah pays the full cost, the state government's benefit-cost ratio is 0.17, a net cost of $6,242 per person. None of the 10,000 simulation draws show the state breaking even. Higher earnings do raise state tax revenue, but nowhere near enough to cover a program the state pays for alone.

The federal government, meanwhile, gains $6,543 per person in that same arrangement, mostly through higher federal tax receipts. Counting all levels of government together, the benefit-cost ratio is 1.04, roughly break-even, with positive net benefits in 41.5% of draws.

This is the central finding: sector training is a good public investment, but its fiscal returns land mostly in Washington while the cost lands in Salt Lake City.

## Funding design matters as much as program design

Because the mismatch is about who pays, how the program is funded changes the state's return a great deal:

- **Utah pays alone:** state benefit-cost ratio of 0.17.
- **Utah and the federal government split the cost equally:** the state ratio rises to 0.34, while the federal ratio is 1.74, so the federal side still comes out ahead.
- **Public funding with an employer contribution:** the state ratio rises to 0.48, a net state cost of $1,363 per person.
- **Public funding with philanthropic first-loss support:** the state ratio is 0.42.

None of these arrangements makes the program self-financing for the state on fiscal returns alone. They show that braiding federal workforce dollars, employer co-investment and philanthropy into the funding mix can greatly reduce what the state gives up to produce the societal return.

## What this analysis does not show

The causal evidence comes from WorkAdvance sites outside Utah, so how well the results carry over to Utah providers and labor markets is the largest open question. Provider quality matters most: on its own, it explains 54% of the variation in simulated societal returns. Using each WorkAdvance provider's own effects and costs, the societal benefit-cost ratio ranges from 3.39 at the weakest site to 10.32 at the strongest. Choosing and supporting strong providers is the biggest lever a Utah program would have.

The model also leaves out some things. It assumes no savings on public assistance until credible linked evidence is available, which likely understates government returns. Its tax module is a simplified approximation rather than a full tax microsimulation. And it counts only the first 10 years after enrollment, with no value assumed beyond that.

The full assumptions, evidence registry and sensitivity results are in the study's [model card](https://github.com/tylerdial1818/labor-pulse-research/blob/main/studies/utah_roi/docs/model_card.md) and [analysis protocol](https://github.com/tylerdial1818/labor-pulse-research/blob/main/studies/utah_roi/docs/analysis_protocol.md). Every number in this note is computed by the open-source pipeline in the [LaborPulse Research repository](https://github.com/tylerdial1818/labor-pulse-research).
