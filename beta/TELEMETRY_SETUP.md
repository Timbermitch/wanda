# Stand up the Wanda telemetry endpoint (~5 minutes, free, no Azure)

Your telemetry **client** ([src/wanda/telemetry.py](../src/wanda/telemetry.py)) is already built and
shipping in the wheel. It's opt-in, anonymous, and sends only operational metrics
(mode, duration, counts, outcome, token usage) plus an anonymous install id —
**never** pipeline/table names, query text, report content, or secrets. The one
missing piece is a URL to receive it. This sets one up on your Google account so a
single run anywhere lights up a row in a spreadsheet.

> Why not Azure? A Functions endpoint works too, but it's quota-gated on the
> Founders Hub subscription and is more to babysit. Apps Script is free, instant,
> and matches the client's plain JSON POST exactly. Move to Azure later if volume
> ever justifies it.

## Steps

1. Go to **[sheets.new](https://sheets.new)** to create a blank Google Sheet. Name
   it e.g. `Wanda beta telemetry`. (The script auto-creates an `events` tab with
   headers on the first event — you don't add columns yourself.)
2. In that sheet: **Extensions → Apps Script**.
3. Delete the placeholder `myFunction` code, then paste the entire contents of
   [beta/telemetry_collector.gs](telemetry_collector.gs). Save (Ctrl+S).
4. **Deploy → New deployment → ⚙ → Web app.**
   - **Description:** `wanda telemetry`
   - **Execute as:** *Me*
   - **Who has access:** *Anyone* ← required so testers' machines can POST without a login
   - Click **Deploy**, then **Authorize access** and accept the Google prompt
     (it's your own script writing to your own sheet).
5. Copy the **Web app URL** (ends in `/exec`). That's your endpoint.

## Verify it works

Paste the `/exec` URL into a browser — you should see
`{"ok":true,"service":"wanda-telemetry","rows":0}`. Then send a real test event:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"event":"run","status":"ok","mode":"INVESTIGATION","install_id":"test","wanda_version":"0.1.2","python":"3.11","os":"Windows","duration_seconds":12.3,"tool_calls":3,"turns":4,"usage":{"input_tokens":900,"output_tokens":400,"cache_read_input_tokens":9000}}' \
  "<YOUR_EXEC_URL>"
```

A row should appear in the `events` tab within a second or two.

## Wire it in — pick one

- **Bake it into the wheel (default-on endpoint for everyone):** set
  `DEFAULT_TELEMETRY_URL = "<YOUR_EXEC_URL>"` in
  [src/wanda/telemetry.py](../src/wanda/telemetry.py) line 29, bump the version,
  rebuild. Testers still have to opt in with `WANDA_TELEMETRY=on` — the URL alone
  sends nothing. *(Tell me the URL and I'll make this edit + version bump.)*
- **Per-tester, no rebuild:** hand testers `WANDA_TELEMETRY_URL=<YOUR_EXEC_URL>`
  in the invite alongside `WANDA_TELEMETRY=on`. Good for a first small cohort
  before you commit a URL into the package.

## Updating the script later

If you edit `telemetry_collector.gs`, redeploy as **Manage deployments → edit →
New version** to keep the **same URL**. A brand-new deployment mints a new URL and
would orphan any testers already pointed at the old one.

## What you'll see (and how to read it)

One row per run. The columns that matter:
- **install_id** — distinct testers (count unique values = your real active-user number).
- **status / error** — `ok` vs `error` + the exception class. A pile of the same
  error class = a real on-ramp bug to fix.
- **mode, duration_seconds, tool_calls, turns** — is the agent actually doing work.
- **usage tokens** — real cost per run.
- **event=feedback** rows carry **useful** (👍/👎) + **note**.

The moment this has rows, "silence" stops being ambiguous: you can finally tell
*nobody ran it* (no rows) apart from *people ran it and it worked* (ok rows, no
complaints). That distinction decides everything you do next.
