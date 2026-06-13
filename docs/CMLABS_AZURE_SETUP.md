# CM Labs — Azure Setup & Credit Plan

Single source of truth for Matthew + Claire on standing up CM Labs in Azure and
maximizing the Microsoft for Startups (Founders Hub) benefits. Foundation first;
Wanda and future apps drop into this cleanly.

**Last updated:** 2026-06-08

---

## Status (as of 2026-06-06)

- ✅ Applied to **Microsoft for Startups (Founders Hub)** via the hackathon referral.
- ⏳ **Application in review** — up to 3 business days.
- 💳 Active now: **$1,000 starter credit, expires Sep 2, 2026** on **"Azure subscription 1"**.
- 🎯 On approval: **up to $150K** Azure credits (staged by level, ~2-yr window) +
  Azure OpenAI ("advanced/secure AI models") + GitHub Copilot Enterprise (1 yr) + a
  Microsoft/GitHub social feature.

> **Reality check:** "$150K" is a *ceiling unlocked in stages*, not a lump sum. Credits
> are **time-boxed, use-it-or-lose-it — not cash/runway.** Build frugally; size for the
> day the credits end.

---

## Do now — while in review (all free, no-regret, carries forward)

### 1. Identity & security
- [x] **MFA on** — Security Defaults **enabled** (confirmed 2026-06-08, tenant shows
      "protected by security defaults"). Free; did **not** buy Entra ID P2/Suite.
  - [ ] Each founder still needs to enroll **Microsoft Authenticator** (aka.ms/mfasetup).
- [x] Named logins created (2026-06-08): **claireannbayoda@cmlabs-ai.com** +
      **matthewarrogante@cmlabs-ai.com** (native tenant members). Note: the original
      `info@cmlabs-ai.com` is an **external Microsoft Account guest** — OK as break-glass,
      but don't rely on it as the only admin.
  - [x] Both founders now **Global Administrator** via named accounts (2026-06-09);
        `info@` MSA kept as 3rd break-glass admin. Still to do: enroll **Authenticator MFA**
        on both named accounts at next sign-in (aka.ms/mfasetup).
- [x] Both named accounts assigned **Owner** on the subscription (2026-06-08), so admin no
      longer depends on the external `info@` MSA. Optional cleanup: remove the redundant
      **Contributor** assignments (Owner already includes Contributor).
- [x] "Access management for Azure resources" left = **No** (break-glass elevation only).

### 2. Cost guardrails (do before creating resources)
- [x] Budgets created (2026-06-08): **Credit_Cap $500** + **Credit_Cap_20 $1,000**, monthly,
      billing-account scope, through 5/31/2028.
  - [ ] **Verify each has alert thresholds (50/75/90%) + email recipients** — a budget with
        no alerts is silent. (Budgets *alert*, they do NOT block spend.)
- [ ] When big credits land: add **subscription- or tag-scoped** budgets so per-product
      (Wanda vs future apps) spend is visible; re-set amounts/window.

### 3. Decide-once conventions
- [x] Subscription renamed **"Azure subscription 1" → "CM Labs - Founders Hub"** (ID
      a633ecb9-…; role confirmed **Owner**). Leave Azure Defender **off** (paid upsell).
- [x] **Region decided: Southeast Asia (Singapore)** as primary. (Azure OpenAI model region
      chosen later at deploy time — model availability varies by region.)
- [x] **Naming + tags established** by the first RG: **`cmlabs-wanda-dev-rg`** created
      2026-06-09 in Southeast Asia with tags `product=wanda`, `environment=dev`, `owner=matthew`.
  - Pattern locked: groups `cmlabs-<product>-<env>-rg`; resources `cmlabs-<product>-<env>-<type>`
    (e.g. `cmlabs-wanda-dev-kv`); storage drops dashes (`cmlabswandadevst`). Tag every
    resource with `product` / `environment` / `owner`. Tag names must have NO trailing spaces.
- [ ] Create `cmlabs-wanda-prod-rg` (and future-app groups) when you actually provision —
      not before.

### 4. Claim the non-credit perks (guaranteed value, off the credit clock)
- [ ] **GitHub Copilot Enterprise** (1 yr) — wire into both founders' IDEs.
      ⚠️ This is a *coding assistant*, NOT a free production LLM for Wanda, and NOT the
      GitHub Copilot SDK Wanda runs on.
- [ ] Microsoft 365 / other Founders Hub perks as they unlock.
- [x] Company domain **cmlabs-ai.com** already in use (verified in Entra; email + identity).
      Still to do: point a landing page at it (see §5).

### 5. Be ready for the social feature
- [ ] One-line pitch + simple landing page (cmlabs-ai.com) + "request beta access" form,
      so Microsoft/GitHub amplification converts instead of bouncing.

---

## Do NOT do yet
- ❌ Deploy the portal's "Try an AI app template" samples on the $1,000 (they bill real
      resources). Bookmark the Azure OpenAI one as a reference only.
- ❌ Provision Fabric capacity / VMs / hosted LLM before governance + tags are in place.
- ❌ Buy reservations or enable paid Defender plans.
- ❌ Architect anything assuming the full $150K until the *granted amount* is confirmed.

---

## On approval — verify these in the portal
- [ ] **Actual credit amount granted** at your current level (vs the $150K ceiling).
- [ ] **Expiry date** / when the ~2-year clock starts.
- [ ] Which **subscription** the credits attach to.
- [ ] What's **excluded** (some 3rd-party marketplace, certain reservations) — and
      confirm credits cover **Microsoft Fabric F-SKUs** and **Azure OpenAI**.

---

## How this funds Wanda (later, deliberately)
- **Fabric capacity** for dev + the 3 test workspaces (beta sign-off) — **pause when idle**.
- **Azure OpenAI** as a credit-funded *hosted/enterprise tier* (enterprises may prefer it
  for compliance). Note: **Claude is not on Azure** — keep a thin model-provider
  abstraction so Claude (cash/BYOK, for quality) and Azure OpenAI (credits) are swappable.
- **Key Vault** (secrets), **App Insights** (telemetry), **Static Web Apps** (landing page).
- For the Phase 2 notebook spike, use the **Fabric 60-day free trial** — it's separate
  from Azure credits, so it doesn't touch the $1,000.
