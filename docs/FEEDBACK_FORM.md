# Wanda beta — feedback form (question set)

Paste these into a Google Form / Tally and share the link in the tester invite and
in `docs/GETTING_STARTED.md` + the notebook's closing cell. Keep it ~2 minutes —
short forms get answered. The three things this beta must learn are **accuracy**,
**time saved**, and **willingness to pay**; every question below feeds one of those.

Suggested form title: **Wanda beta — how did it go?**
Intro line: *Thanks for testing Wanda. ~2 minutes. Your answers decide what we build next.*

---

### Setup (did the on-ramp work?)
1. **Were you able to install and run Wanda?** *(single choice)*
   - Yes, smoothly
   - Yes, but setup was painful
   - No — I got stuck *(→ Q2)*
2. **If you got stuck, where?** *(single choice)*
   - Installing the package / ODBC driver
   - Creating the Service Principal
   - Granting workspace access
   - Anthropic API key / billing
   - Running it / pipeline name
   - Other *(short text)*
3. **About how long did first-time setup take?** *(single choice)* — <10 min · 10–20 · 20–40 · >40 · gave up

### Accuracy (did it work?)
4. **Did Wanda find the actual root cause?** *(single choice)*
   - Yes, correct and specific
   - Partially — right area, wrong detail
   - No — wrong or unhelpful
5. **How clear and actionable was the report?** *(1–5 scale)* — 1 = confusing, 5 = I could act on it immediately
6. **What did it get wrong, or what confused you?** *(long text, optional)*

### Value (time saved)
7. **Roughly how long would this investigation have taken you by hand?** *(single choice)* — <15 min · 15–60 min · 1–2 hrs · >2 hrs
8. **How much time did Wanda save you on this one?** *(single choice)* — None · A little · ~Half · Most of it
9. **Would you use Wanda in your real workflow?** *(single choice)* — Yes, regularly · Sometimes · No

### Willingness to pay (the business question)
10. **If Wanda reliably saved you this time, would your team pay for it?** *(single choice)*
    - Yes
    - Maybe, depends on price
    - No / would expect it free in Fabric
11. **What feels fair per data engineer per month?** *(single choice)* — $0 (must be free) · $1–15 · $16–40 · $41–75 · $75+ · My company decides, not me
12. **Who would have to approve buying a tool like this?** *(short text, optional)* — e.g. me, my lead, data platform team, procurement

### Open
13. **The one thing that would make Wanda a must-have for you?** *(long text)*
14. **Anything else?** *(long text, optional)*
15. **OK to follow up with you?** *(optional email)*

---

## Reading the results (what "ready to keep going" looks like)
- **Accuracy:** majority answering Q4 = "Yes, correct" and Q5 ≥ 4. If not, fix the engine before scaling.
- **Time saved:** Q7 mostly "1–2 hrs / >2 hrs" *and* Q8 mostly "Most of it" — that's the value prop confirmed.
- **Willingness to pay:** Q10 "Yes/Maybe" + a clustered Q11 price band is the single strongest signal that this is a business, not just a useful script. A wall of "free in Fabric" (Q10) is the risk to watch — that's the Microsoft-builds-it-natively threat showing up in the data.
