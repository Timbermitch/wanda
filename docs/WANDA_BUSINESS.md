# Wanda — Business Model (plain-language one-pager)

A simple shared reference for Matthew + Claire on **how Wanda makes money**.
Numbers here are **placeholders to validate with real testers**, not final prices.

**Model:** Open-core + Azure Marketplace SaaS
**Last updated:** 2026-06-10

---

## The model in one breath

> Give the basic tool away **free** so people try it. Charge a **monthly fee** for the
> version that runs **automatically** for their whole team. Sell that paid version inside
> **Microsoft's app store (Azure Marketplace)** so it lands on the customer's existing
> Microsoft bill. Your costs are tiny, so most of what they pay is **profit**.

---

## The two parts

| | Free (the hook) | Paid (the money) |
|---|---|---|
| **What** | The notebook version — run it yourself | Wanda runs **automatically** on the workspace |
| **Features** | Manual investigation, one person | Auto-trigger on failures, **Teams/Slack alerts**, failure **history**, whole **team**, support |
| **Who pays the LLM** | The user (bring-your-own API key) | Bundled by us (with caps) or customer's own Azure OpenAI |
| **Cost to us** | **$0** (they bring their own key) | Tiny (see below) |
| **Its job** | Adoption, trust, word-of-mouth | Revenue |

The clever bit: because the free tier is **bring-your-own-key**, free users cost us **nothing** —
they're pure top-of-funnel.

---

## Where the profit comes from

Profit = **what they pay − what it costs us to run.** What it costs us is tiny.

*(Illustrative — real price is what the beta will tell us.)*

| Per customer / month | |
|---|---|
| They pay us | **$200** |
| Our cost (LLM tokens ≈ cents per investigation + a little hosting) | **~$40** |
| **Profit** | **~$160 (≈80%)** |

The product barely costs more to serve 100 customers than 10, so profit **stacks**:

| Paying customers | ~Monthly profit |
|---|---|
| 10 | ~$1,600 |
| 50 | ~$8,000 |
| 100 | ~$16,000 |

That "costs stay flat while revenue grows" is the whole reason software is profitable.

---

## Why Azure Marketplace matters

Big companies **pre-pay Microsoft** a pile of money each year (their Azure commitment).
Buying Wanda from the Marketplace spends *that already-committed money* — so it's an easy
"yes": no new budget, no procurement fight. Microsoft handles billing and takes a **small
cut (~3%)**. This is our biggest selling advantage, and it leans on the Microsoft
relationship we already have.

---

## The flow (free → paid)

```
Free notebook  →  an engineer loves it  →  their team wants it automatic + in Slack
      →  they buy the paid tier on Azure Marketplace  →  we collect monthly
      →  costs stay tiny  →  profit = the gap
```

---

## When are WE (the company) profitable?

Infra is **covered by Azure credits** for now and it's just the two of us, so fixed costs
are low:

- A **handful** of customers covers hosting.
- A **few dozen** could cover salaries.
- After that, each new customer is mostly profit.

---

## What makes or breaks it (the honest part)

- ✅ **Real painkiller** — engineers lose hours to pipeline root-cause analysis; time saved
  is worth real money.
- ✅ **Great unit economics** — cents of tokens replace an hour of a $50–150/hr engineer.
- ✅ **Microsoft tailwind + relationship** — growing Fabric user base, Marketplace, Founders Hub.
- ⚠️ **Biggest risk: Microsoft could build it into Fabric themselves.** Be faster/better, and
  become the thing they'd rather buy/partner with than rebuild.
- ⚠️ **Narrow market (Fabric-only)** — right for focus now; expand later if it works.
- ⚠️ **Trust bar is high** — a *wrong* root cause is worse than none. Accuracy is the product.
- ⚠️ **Useful ≠ paid** — must confirm people will actually pay.

---

## The one number we don't know yet

**Price.** The beta exists to find it. The question to ask every tester:

> *"If Wanda ran automatically and posted the report to your Slack the moment a pipeline
> failed — would you pay $200/month for it? What about $100? $500?"*

Their answers turn this napkin math into a real plan.

---

## Beta access model (how testers run Wanda) — finalized 2026-06-10

**Beta = free for testers. No Anthropic account, no API billing, no Service Principal.**

- Tester gets a **CM Labs beta token** → runs Wanda **free**.
- Behind a **CM Labs proxy**, the LLM defaults to the **quality bake-off winner**:
  **Azure OpenAI (GPT-4o)** if it's good enough (credit-funded, ~$0 cash to us), else
  **Claude** (cash, trivial + capped).
- **BYOK optional** (their own Claude or Azure OpenAI key) for enterprise/power users.
- Proxy + telemetry hosted on **Azure credits** → doubles as the seed of the Stage 3 backend.
- Why provide it free: target audience **Data Engineering Pilipinas** (~38k, education-first,
  friction-sensitive). Max participation > saving trivial, capped LLM cost.

**Product (Stage 3, later) = freemium:** free **Azure OpenAI** tier + **Claude "Recommended"**
premium tier (BYOK or paid). Do **not** paywall the better model *during beta* — beta needs
the cleanest possible signal.

## What we are NOT doing yet
- ❌ Building the hosted/automated backend before the beta proves people want it.
- ❌ Setting a final price before testers react.
- ❌ Expanding beyond Microsoft Fabric.
