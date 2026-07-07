# AgenticPA — Slide-by-Slide Story
### Speaker narrative for `documents/AgenticPA_redesign.pptx` (12 slides)

How to use this: read it once top to bottom to internalize the arc, then use the bolded
**"Say this"** line per slide as your anchor — don't read the slide bullets aloud, the audience
can already read. Your job on each slide is the sentence the bullets don't say.

**The one-sentence arc of the whole deck:** *Prior auth is slow and undocumented today → we
built a pipeline where every claim gets priced, cited, and gated by code before a human ever
sees it → here's proof it works on real cases → here's the architecture and the guardrails →
here's what's next.*

Target time: ~90 seconds/slide for a 15-18 minute presentation, less on code-heavy slides,
more on Problem/Fairness/Explainability.

---

### Slide 1 — Title
**On screen:** AgenticPA — "Prior authorization, decided in minutes — with evidence on every line."

**Say this:** "We're going to show you a system that takes a prior-authorization request from
upload to decision — priced against real Medicare rates, checked against the real coverage
document, and handed to a human only when it actually needs one." Don't linger — this slide's
job is just to set the tagline in the room's ear before you say it again on slide 3.

**Transition line:** "To understand why we built it this way, start with what's broken today."

---

### Slide 2 — The Problem
**On screen:** 94% of physicians say PA delays care · 1 in 3 report a serious adverse event ·
13 of 40 hours/week lost to paperwork.

**Say this:** These aren't our numbers — cite the AMA survey source on the slide, out loud,
before the audience can ask "where's that from." Then land the actual thesis, which is buried
in the small caption text and is the most important line on the slide: *"Behind every delay
sits a manual review with no price benchmark, no cited policy evidence, and no immutable audit
trail — decisions vary reviewer to reviewer."* Say that sentence slowly. It's the whole reason
the system exists — not "AI is faster," but "manual review today has no evidence trail, and
that's the actual gap."

**Anticipate:** someone will ask "isn't the real problem under-staffing, not lack of tooling?"
Answer: both are true; this system doesn't add headcount, it makes the headcount you have only
touch the cases that need judgment, and gives them evidence pre-packaged instead of asking them
to gather it case by case.

**Transition line:** "So we built six specialists instead of one black box."

---

### Slide 3 — The Solution
**On screen:** 6 agents (Intake, Cost, Policy RAG, Alternatives, Peer Review, Summarizer).

**Say this:** Don't read the 6 names — instead say what makes this not a chatbot: *"Each of
these does exactly one verifiable job. Two of them — Cost and Policy — never call an LLM at
all, they're pure math and pure search."* Then hit the two bolded callouts on the slide as your
real content:
- "Dynamic routing" — the patient's own question decides which agents run; ambiguity fans out
  to everything rather than skipping a check.
- "Durable human-in-the-loop" — this is a real pause in the workflow engine, checkpointed to a
  database, not a status flag in a queue table.

**Anticipate:** "why 6 agents and not one big prompt?" Answer: separating concerns means each
piece can be tested, audited, and even turned off independently (admin can disable Cost or RAG
without touching the rest) — and it means the parts that decide money and coverage are pure
code, not LLM judgment.

**Transition line:** "That's the design. Here's it running on a real case."

---

### Slide 4 — Value & Impact
**On screen:** PA-104, real CMS formula, $432.90 benchmark vs $5,000 billed = +1,050%.

**Say this:** This is your proof slide — slow down here. Walk the actual number: *"This isn't
a synthetic percentage. $432.90 is the real Medicare rate for this exact procedure code in this
exact ZIP's locality, computed from the same RVU/GPCI formula CMS itself uses. The claim was
billed at $5,000. The system caught an 11x overcharge automatically, instantly, before a human
ever opened the file."* Then hit the other four numbers briskly — the 0.70 evidence floor, the
48h/2h SLA, the 100% insert-only audit trail — each as one breath, not a paragraph.

**Anticipate:** "is $5,000 a cherry-picked case?" Answer: yes, deliberately — it's one of six
curated hero cases built to demonstrate every terminal outcome (approved, denied-cost,
denied-policy, denied-clinical, info-needed, pending-human) using real source documents (the
actual AARP EOC, the actual CMS rate files), not fabricated numbers.

**Transition line:** "Here's what's actually running underneath that number."

---

### Slide 5 — Architecture
**On screen:** the fan-out/join diagram image.

**Say this:** Trace it with your hand, don't just show it: *"Intake reads the case and decides
which checks it needs. Cost and Policy run at the same time — they don't depend on each other.
They join before Peer Review, which is the one gate that decides: does a human need to see
this? If yes, the whole process genuinely pauses — not a queue, a pause — until a reviewer
acts."* One sentence, then move — this slide supports slide 8's deeper dive, don't duplicate
that content here.

**Transition line:** "That's not a diagram we drew after the fact — here's where it lives in
the codebase."

---

### Slide 6 — Code
**On screen:** file tree + real formulas (CMS rate math, hybrid RAG, LLM client fail-safe).

**Say this:** Pick exactly one line to make concrete, don't try to narrate the whole tree:
*"`llm_client.py` is one interface behind a 10-second timeout — if the LLM doesn't answer in
time, the case fails safe to human review. That single line is why an LLM outage can never
turn into a silent auto-approval."* Then close with the deck's own line: *"Every feature is
marked real or mocked in the code itself — we're not going to tell you something is real that
isn't, because the code already says so."*

**Anticipate:** "what LLM provider are you using?" Answer: it's pluggable — Gemini, OpenAI, or
Bedrock Claude behind one interface, chosen by an environment variable, not hardcoded to a
single vendor.

**Transition line:** "So what actually stops the LLM from making the call by itself?"

---

### Slide 7 — Innovation: The LLM never decides alone
**On screen:** 5 numbered points — deterministic gates, fail-safe not fail-open, cited RAG,
feedback flywheel, insert-only audit.

**Say this:** This is the trust slide — treat it that way. Say the header sentence exactly:
*"The LLM can add a reason to escalate a case. It can never remove one."* That's the single
most important sentence in the whole deck for a skeptical audience — repeat it if you have to.
Then pick the *feedback flywheel* point to make concrete: *"When a reviewer corrects a field,
that correction is stored by diagnosis code family, and shown back to the extraction agent the
next time a similar code comes through — so the system's accuracy compounds with usage instead
of staying static."*

**Anticipate:** "how do you know the LLM is actually following that rule and not just
convincingly claiming to?" Answer: it isn't a rule the LLM follows — it's enforced in code
outside the LLM call. The hard-gate flags are computed by plain Python *before* the LLM ever
runs; the LLM's output is OR'd into an already-True/False flag, so even if the LLM tried to say
"approve this," the code path to auto-approve has already been closed for that case.

**Transition line:** "Trust also means being honest about disparity — here's how we handle
fairness."

---

### Slide 8 — Responsible AI · Fairness
**On screen:** cohort charts (age band, region, provider, service) with a "CI excludes cohort
mean" flag, and a **Method** toggle switching between the Wilson-interval view and a Bayesian
Beta-Binomial posterior view (posterior mean, 95% credible interval, P(worse than overall)).

**Say this:** State the two halves as two separate sentences, because conflating them is the
single most common mistake in this room: *"First — we measure disparity. This is computed live
from real finalized cases, not a mock. Second — and this is the part people don't expect — that
measurement never touches the decision pipeline. It cannot route, reweight, or block a case."*
Then say why, briefly, because "why not fix it automatically" is the obvious next question in
everyone's head: *"Auto-correcting an individual's outcome based on their cohort's aggregate
stats would itself be an invisible demographic decision — worse than today's problem, not
better. So we disclose it for a human to investigate instead."* Close with what actually
protects against a bad decision: *"the per-case hard gates never look at demographics at all —
only at how confident the extraction was, how far off the price was, how strong the policy
match was."*

Then show the toggle: *"We give two independent statistical lenses on the same data, not one.
The Wilson interval answers 'is this gap bigger than sampling noise could explain.' The
Bayesian view — a real Beta-Binomial posterior, not a label — answers a more direct question:
'given everything we've observed, what's the probability this cohort is actually worse than
average.' Same underlying cases, two ways of being honest about uncertainty, both computed with
real, hand-verifiable statistics — no black-box library, no invented number."*

**Anticipate — this slide draws the most pushback, prepare for it:**
- "So what does prevent bias, if not this chart?" → the hard gates in Peer Review, which are
  blind to demographics by construction (answered above — have it ready verbatim).
- "Race, income, disability — why aren't those tracked?" → they're never captured anywhere in
  the data model; age and ZIP-derived region are proxies, and ZIP-as-region is a known weak
  proxy — say this before they do, it reads as rigor, not a gap.
- "3-case minimum sounds arbitrary." → it's a floor against literal noise (a 1-of-1 cohort
  reporting 100% or 0%), not a claim of statistical significance. The Wilson interval has no
  p-value or multiple-comparison correction, which is exactly why the Bayesian view exists
  alongside it — a weakly-informative prior pulls small-n cohorts back toward the population
  average instead of reporting a noisy 100%/0%, and that's a genuinely different (and
  complementary) way of handling the same small-sample problem, not window dressing.
- "Isn't 'Bayesian fairness' just a buzzword here?" → no — walk them to the code if asked:
  `_betainc`/`_beta_quantile` in `backend/app/core/fairness.py` are a hand-rolled regularized
  incomplete beta function (the same algorithm inside `scipy.special.betainc`), the prior is a
  disclosed `Beta(4·overall_rate, 4·(1-overall_rate))`, and every number is unit-tested
  (`backend/tests/test_fairness.py`) against known closed forms.

**Transition line:** "Fairness is about aggregate disparity. Explainability is about a single
decision — here's what that looks like."

---

### Slide 9 — Responsible AI · Explainability
**On screen:** the reviewer rationale panel for PA-104 — hard-gate flag, cited rationale,
per-field confidence, agent trace, interrupt lifecycle, **plus the new "Why This Decision"
panel**: each fired flag with a severity bar, a "% of decision" share, and an exact
counterfactual line.

**Say this:** Read the actual rationale text on the slide aloud, verbatim — it's the strongest
evidence in the deck: *"Billed $5,000.00 for upper GI endoscopy vs CMS benchmark $432.90 —
variance +1,055%, far above the +20% gate."* Then make the point explicit: *"No rationale in
this system ever says 'the cost seems high.' It cites the exact numbers, the exact CMS
locality, the exact EOC page. If a reviewer or an auditor asks 'why was this flagged,' the
answer is already written down, in numbers, before they even ask."*

Then go one layer deeper with the counterfactual panel — this is the new material, spend real
time here: *"We don't just say the gate fired. We say exactly what would have had to be true
for it not to. For this case: 'billed amount would need to be $519.48 or less' — not
approximately, the exact number, derived from the same CMS formula that flagged it in the first
place. And when more than one flag fires on the same case, we rank them — this case is 89%
driven by the cost variance and 11% by a borderline extraction-confidence gap, so a reviewer
knows what to look at first instead of reading four flags with no sense of which one actually
mattered."* Close the loop explicitly: *"This isn't SHAP or LIME — there's no black-box model
to explain here. It's the actual threshold math, inverted and shown back to the reviewer."*
Close on the interrupt lifecycle diagram: *"Approve, modify, or deny resumes the case forward.
'Clarify' loops back to the exact same pause point — no new case is created, no state is
lost."*

**Anticipate:** "why not just use SHAP/LIME since that's the standard?" → those explain a
trained model's internal weights; there is no trained model in this decision path to explain —
`evaluate_hard_gates` is deterministic threshold comparisons, already fully transparent in the
source. What's genuinely missing without this feature is the *inverse* — the counterfactual —
which SHAP doesn't give you either. That's what `backend/app/core/explainability.py` adds.

**Transition line:** "All of this is running today, not a mockup — here's the honest state of
readiness."

---

### Slide 10 — Feasibility
**On screen:** "Working now" vs "Next."

**Say this:** Read "Working now" with confidence, it's true and demonstrated: docker-compose
up, real migrations, 6 hero cases plus 20 QA scenarios, live-tunable thresholds, insert-only
audit trail. Then read "Next" with the same tone, not apologetically: *"Real SSO instead of the
mocked login, a live clinical-guidelines source behind Alternatives, more than one payer's
policy corpus, and load-tested scaling."* Land the closing line as the actual thesis of the
slide: *"Stateless API, a checkpointed workflow, and managed data stores — getting to pilot
doesn't require an architectural rewrite, it requires filling in labeled gaps."*

**Anticipate:** "how long to close the 'Next' list?" Have a rough order-of-magnitude answer
ready (weeks vs quarters) appropriate to your actual team size — don't leave this open-ended if
you're presenting to people who'll ask for a roadmap date.

**Transition line:** "None of this is hidden — here's feedback we already acted on."

---

### Slide 11 — Mentorship
**On screen:** three mentor quotes, each paired with the concrete code change that answered it.

**Say this:** This slide's value is "we don't just note feedback, we can point at the commit."
Say each pairing as cause→effect: *"'Never let the LLM be the last word on money or coverage' —
that's why every hard gate is now deterministic code, and the LLM can only add escalation
reasons."* *"'If you claim auditability, show it' — that's why audit_logs is now insert-only at
the database level, enforced by a trigger, plus a Trace Explorer in the Admin Portal."*
*"'Demo your failure modes, not just approvals' — that's why the hero cases include an
info-needed case and a case deliberately left pending human approval, not just clean
approvals."* Remember to swap the placeholder mentor names/quotes before presenting live if
this is a real judged event.

**Transition line:** "That's the system. Happy to take it anywhere you want to go deeper."

---

### Slide 12 — Thank You
**Say this:** Nothing clever needed — restate the tagline once more, briefly, then open the
floor: *"Prior authorization, decided in minutes, with evidence on every line. Questions."*
Keep the GitHub link visible; don't read it aloud.

---

## If you only remember five lines for the whole deck

1. "Cost and Policy never call an LLM — they're pure math and pure search."
2. "The LLM can add a reason to escalate. It can never remove one."
3. "We measure fairness disparity two ways — a frequentist confidence interval and a real
   Bayesian posterior — but neither measurement ever touches an individual decision; the hard
   gates that do, never look at demographics."
4. "Every rationale cites exact numbers and exact pages — and for every fired gate, we can also
   tell you the exact number that would have avoided it."
5. "Every mock is labeled in the code itself, not discovered by a skeptical question."
