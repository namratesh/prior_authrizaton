# Understanding the Fairness Check — In Plain English

*A non-technical guide to the "Bias & Fairness" numbers in the Admin Portal, and why we show them two different ways.*

---

## 1. What problem are we solving?

Our system decides prior-authorization (PA) requests as "Approved" or "Denied." We want to make sure it isn't quietly treating some groups of patients differently than others — for example, older patients, patients in a certain region, or patients seeing a certain provider.

So we split all decided cases into groups ("cohorts") — like **Age 65-74**, **Age 75-84**, **Northeast**, **South** — and check: *does this group's approval rate look different from everyone else's?*

That sounds simple, but there's a trap: **small groups lie to you.**

---

## 2. The trap: small numbers look scary even when they mean nothing

Imagine a cohort with only 3 finalized cases, and all 3 happened to be denied. That's a 0% approval rate. Looks alarming, right?

But flip 3 coins — plain fair coins, no bias at all — and there's a **1-in-8 chance** all three land tails. A 0%-approved cohort of size 3 could easily be pure random luck, not discrimination.

If we just displayed raw approval rates, a dashboard full of tiny cohorts would flag "problems" that aren't real problems, and reviewers would learn to ignore the dashboard entirely (the classic way fairness tools lose people's trust).

So before anything else, we throw out any cohort with fewer than 3 finalized cases — it's not shown at all, not even with a warning label, because there isn't enough data to say anything meaningful.

For everything else, we use **two different, well-established statistical lenses** side by side, because they answer subtly different questions and protect against different mistakes.

---

## 3. Lens #1: Wilson Score Interval — "How confident are we, really?"

**The plain-English question it answers:**
*"Given how few or how many cases we've seen, how wide is our uncertainty around this group's true approval rate?"*

### Why not just use the raw percentage?

Say a cohort has 3 cases and all 3 were approved → raw rate = 100%.
Another cohort has 300 cases and 291 were approved → raw rate = 97%.

Naively, the first cohort "looks better." But it's obviously not — 3 cases tells us almost nothing, while 300 cases is a strong signal. A raw percentage on its own doesn't know the difference.

### What Wilson does about it

The Wilson interval turns "97% out of 300" and "100% out of 3" into a **range of plausible true values**, e.g.:

| Cohort | Cases | Raw rate | Wilson range (95% confidence) |
|---|---|---|---|
| Age 65-74 | 300 | 97.0% | 94.5% – 98.4% (narrow — we trust this) |
| Under 65 | 3 | 100.0% | 43.9% – 100.0% (wide — we barely trust this) |

The small cohort's range is *huge* — it honestly admits "the true rate could be anywhere from 44% to 100%, we just don't have enough cases to know better." The large cohort's range is narrow and precise.

We then flag a cohort as a **"significant disparity"** only when its entire Wilson range sits *below* the overall approval rate across all cases — meaning even in the most generous reading of the data, this group is still doing worse than average. That's a deliberately conservative bar, designed so we don't cry wolf on noise.

**Analogy:** it's like a poll. "60% support, ±1%, from 10,000 people" is trustworthy. "60% support, ±30%, from 10 people" tells you almost nothing — Wilson is the math that produces that "±" margin honestly, especially for extreme percentages (near 0% or 100%) where naive methods get overconfident.

---

## 4. Lens #2: Bayesian Analysis — "What's our best real-world guess, and how likely is it that this group is actually worse?"

**The plain-English question it answers:**
*"Taking into account what we already know about approval rates in general, what's our best estimate for this specific group — and how likely is it that this group's true rate is below average?"*

### Why add a second method at all?

Wilson is honest about uncertainty, but it treats every cohort in isolation — as if we knew *nothing* going in. In reality, we do know something: we know the overall approval rate across the whole hospital/system, say **85%**. It would be strange to totally ignore that when we only have 3 cases to look at for one small group.

The Bayesian approach uses that overall rate as a starting assumption (called a **"prior"**), then updates it as real cases come in. The more cases a cohort has, the more its own data overrides that starting assumption; the fewer cases, the more it leans on the overall average.

### Worked example

Overall approval rate across the system: **85%**.

A brand-new cohort — "Provider #482" — has only 3 finalized cases, all 3 denied (raw rate 0%).

- **Naive raw number:** "0% approved!" — sounds like a five-alarm fire.
- **Bayesian estimate:** starts from the assumption "most cohorts hover around 85%," then factors in the 3 denials. Result: our best estimate shifts down to something like **~35-40%**, not 0%. It's clearly *lower* than average (worth watching) but the method refuses to overreact to 3 data points by declaring total failure.

As more cases come in for Provider #482, this estimate stops leaning on the system-wide average and starts reflecting Provider #482's actual pattern.

### The headline number: "P(worse than average)"

Instead of a range, the Bayesian method also produces one clean, intuitive number: **the probability that this group's true approval rate is actually below the overall average**, given everything we've seen.

- `p_worse_than_overall = 0.92` → *"There's a 92% chance this group is genuinely doing worse than average."* Easy to say in a meeting, easy for a non-statistician to act on.
- `p_worse_than_overall = 0.55` → *"Basically a coin flip — we don't really know yet."*

**Analogy:** it's like a doctor's initial diagnosis. Before running any tests, you assume a patient is probably healthy (that's the "prior," based on the general population). Then symptoms and test results (the cohort's actual data) shift that assumption up or down. A doctor who ignored general population base rates and treated every single symptom as if it appeared in a vacuum would over-diagnose constantly — that's what happens if you only look at raw percentages of tiny groups.

---

## 5. Side by side — why we didn't just pick one

| | Wilson Score Interval | Bayesian Posterior |
|---|---|---|
| **Question it answers** | "How wide is our uncertainty band?" | "What's our best estimate, and how likely is this group worse than average?" |
| **Starting assumption** | None — looks at each cohort alone | Starts from the system-wide average, updates with data |
| **Best suited for** | Being conservative / not crying wolf | Giving a single, decision-ready probability |
| **Behavior with tiny cohorts** | Produces a very wide, honest range | Pulls the estimate toward the overall average ("shrinkage") |
| **Output you see** | A range, e.g. 44%–100% | A single estimate + one probability, e.g. "~38% approved, 92% chance worse than average" |

They usually **agree** when a cohort has enough cases. They can **disagree** when a cohort is very small — and that disagreement is itself useful information: it's a signal that says *"we genuinely don't have enough data yet, look at this with two lenses before drawing conclusions."*

This is why the Admin Portal has a **Method toggle** (Frequentist / Bayesian) on the same chart — same underlying cases, two honest ways of reading them, so a reviewer isn't stuck trusting a single number.

---

## 6. What this dashboard is — and isn't

- **It is a monitor**, not an automatic decision-maker. Nothing here changes any patient's PA outcome automatically. It's a flag for a human reviewer to look closer.
- **It does not prove discrimination.** A flagged cohort means "this pattern is worth investigating," not "this is confirmed bias." There could be legitimate clinical reasons for a difference.
- **The starting assumption (the "prior") is a modeling choice**, not an objective truth — we chose it to be the overall system average, which is a reasonable, defensible default, but it's still a choice.
- **Tiny cohorts (fewer than 3 cases) aren't shown at all** — silence on a group means "not enough data yet," not "no issue."

---

## 7. TL;DR for a busy reader

> We check if any patient group is approved less often than others. Because small groups produce noisy, misleading percentages, we don't trust raw numbers alone. We use **two independent statistical checks** — one that gives an honest "how sure are we" range (Wilson), and one that gives a single "how likely is this really worse than average" probability, informed by the overall system average (Bayesian). When both agree, we're confident. When they disagree, that itself tells us we need more data before concluding anything.
