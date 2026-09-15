# Wanda beta — getting real testers (stop broadcasting, start recruiting)

**The problem:** a post to the ~38k Data Engineering Pilipinas community produced
silence. That's the expected result of a broadcast, not a verdict on Wanda. A
crowd scrolls past; a beta is **named people you talk to directly.** This file is
the playbook to get from 0 → your first 3 instrumented runs on *other people's*
workspaces — which is also your roadmap's beta sign-off bar
("run cleanly on at least 3 different Fabric workspaces, not just ours").

> Do [TELEMETRY_SETUP.md](TELEMETRY_SETUP.md) first. Until the endpoint is live you
> can't tell "nobody tried it" from "it worked and they said nothing" — and you'll
> keep guessing.

---

## Step 1 — Qualify, don't blast

Wanda only delivers value to someone who **has a Microsoft Fabric workspace with a
pipeline that fails or misbehaves**, and access to investigate it. Most community
members, at any moment, don't. So don't ask "who wants to try a tool?" — ask:

> "Do you run **data pipelines in Microsoft Fabric**, and have you hit a failure
> that took a while to debug?"

Only the people who say yes are real testers. Aim for **5–10 qualified names**, not
a headcount. Your roadmap already lists warm contacts to start with: Ve Sharma,
Venkat, Paula, Ilya, Cecilia.

## Step 2 — The ask is a 20-minute call, not a link

A link gets bookmarked and forgotten. A scheduled session gets done — and you get
to *watch* (Step 4), which is where the real learning is.

### DM template (warm contact)

> Hi [Name] — I built a small tool, **Wanda**, that investigates *why* a Microsoft
> Fabric pipeline failed and writes up the root cause (the kind of thing that
> usually eats an afternoon of digging through run logs and notebooks).
>
> I'm not after a big favour — I want to **watch one real person try it for 20
> minutes** on a pipeline of yours and tell me where it's clunky. Brutal feedback
> is the point. Could we grab 20 min this week? I'll be on the call to unblock you
> if anything snags.

### DM template (community member who replied to a post)

> Thanks for raising your hand! Quick qualifier so I don't waste your time: do you
> have a **Fabric pipeline that's failed recently** you could point this at? If
> yes — want to do a 20-min screen-share where you try it and I take notes on
> what's confusing? That session is worth more to me than any number of installs.

## Step 3 — Make the first run frictionless

Before the call, send the three things they'll need so the 20 minutes is spent on
*Wanda*, not setup:
1. The template notebook + [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md).
2. Whether they're using **their own Anthropic key** (BYOK) — and if not, that you
   can supply a capped key for the session.
3. A heads-up that running **inside a Fabric notebook** means no Service Principal
   (token mode — verified live). This is your biggest friction-killer; lead with it.

If they *don't* have a live failure to investigate, have a **deliberately-broken
sample pipeline** ready (or a 90-second recording of a real run) so they still feel
the "oh, it found it" moment. Nobody judges a debugger with nothing to debug.

## Step 4 — Watch them install it (the highest-leverage hour you have)

On the call, **share screen and stay quiet.** Don't help unless they're truly
stuck. Note every hesitation — each one is a real bug in the on-ramp.

Checklist to fill in live (one per tester):

| Step | Watch for | Result |
|---|---|---|
| Open / import the notebook into Fabric | Does the import just work? | ☐ smooth ☐ snag: ____ |
| `pip install wanda-fabric` | Any resolver / version error? | ☐ smooth ☐ snag: ____ |
| Paste Anthropic key (or use supplied) | Do they know where to get one? cost worry? | ☐ smooth ☐ snag: ____ |
| Auth to Fabric (token mode) | Does `getToken("pbi")` path confuse them? | ☐ smooth ☐ snag: ____ |
| `wanda.investigate("<pipeline>")` | Do they know which name to type? | ☐ smooth ☐ snag: ____ |
| Read the report | First reaction — believable? actionable? | ☐ "wow" ☐ "meh" ☐ wrong |
| **Time from open → report** | The roadmap bar is **under 15 min** | _____ min |

The single number that matters: **did they get from "open notebook" to "a report"
in under 15 minutes without you typing for them?** If no, that gap *is* your next
sprint.

## Step 5 — Capture the verdict before they leave the call

Don't let the session end on "cool, thanks." While it's fresh, get the three
things the beta exists to learn (full set in [docs/FEEDBACK_FORM.md](../docs/FEEDBACK_FORM.md)):

1. **Accuracy** — "Did it find the *actual* root cause, or just the right area?"
2. **Time saved** — "How long would that have taken you by hand?"
3. **Willingness to pay** — "If it reliably saved you that time, would your team
   pay for it — and what feels fair per engineer per month?"

Either walk them through the feedback form on the call, or ask these out loud and
write the answers down yourself. A verbal answer on the call beats a form they'll
fill in "later" (they won't).

---

## What good looks like after 2 weeks

- **3+ distinct `install_id`s** in the telemetry sheet, each with at least one
  `status=ok` run → roadmap sign-off criterion met.
- **3+ live "watch them install" sessions** with the checklist filled in.
- A clear read on the on-ramp's worst snag (you'll see the same one repeat).
- First real signal on accuracy + willingness-to-pay from Step 5.

If those are true, the beta has actually *started* and you can scale outreach with
confidence. If they're not, you now know exactly which step is bleeding testers —
which is infinitely more useful than "the community went quiet."
