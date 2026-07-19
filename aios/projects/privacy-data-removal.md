# Privacy Data-Removal Tracker — Aashishsingh Rajput
_Started 2026-07-10 · Details: Aashishsingh Anilkumar Rajput · Navi Mumbai, Maharashtra, India · ashumedico@gmail.com_

> **Reality check (honest scope):** As an India resident, the US consumer people-search ecosystem
> (Spokeo, BeenVerified, WhitePages, Radaris) has **nothing** on you — confirmed by search. Your real
> exposure is **B2B contact brokers** that scrape LinkedIn/professional data. GDPR/CCPA don't legally
> bind for an India resident, but most brokers honour opt-outs globally; India's **DPDP Act 2023** is the
> domestic basis. Status tags: [CONFIRMED] listed · [LIKELY] scrapes same data, verify · [CLEAR] nothing found.

## PROMPT 1 — THE SITES

| # | Site | Status | What it shows | Opt-out link | Next step | Row status |
|---|---|---|---|---|---|---|
| 1 | **RocketReach** | [CONFIRMED] | Name, Ferring role, **email + phone** | rocketreach.co/privacy → "Opt Out / Claim" | Submit removal + verify email | needs-me |
| 2 | **The Org** | [CONFIRMED] | Name, title, org chart | theorg.com → profile → "Remove/claim" or privacy@theorg.com | Email removal request | needs-me |
| 3 | **ResearchGate** | [CONFIRMED] | Academic profile | Account settings → deactivate/private, or support | Make private if unwanted | needs-me |
| 4 | **ZoomInfo** | [LIKELY] | Name, title, contact | zoominfo.com/about-zoominfo/privacy-center (remove) | Submit removal | needs-me |
| 5 | **Apollo.io** | [LIKELY] | Contact data | apollo.io/opt-out (or privacy@apollo.io) | Submit removal | needs-me |
| 6 | **Lusha** | [LIKELY] | Contact | lusha.com/opt-out | Submit removal | needs-me |
| 7 | **SignalHire** | [LIKELY] | Contact | signalhire.com/privacy-policy → remove | Submit removal | needs-me |
| 8 | **ContactOut** | [LIKELY] | Email | contactout.com/opt-out | Submit removal | needs-me |
| — | Spokeo / BeenVerified / WhitePages / Radaris | [CLEAR] | nothing (India resident) | — | none | done |

## PROMPT 2 — THE REMOVAL REQUEST (one template, consistent details)

> Paste into each site's form, or email to their privacy address. Insert the specific profile URL per site.

```
Subject: Data Removal & Opt-Out Request — Aashishsingh Anilkumar Rajput

To the Privacy/Data Protection team,

I am writing to request the permanent removal and deletion of all my personal
information from your database, and that you cease selling, sharing, licensing,
or displaying it.

My details:
• Full name: Aashishsingh Anilkumar Rajput
• Location: Navi Mumbai, Maharashtra, India
• Email: ashumedico@gmail.com
• Listing/profile URL: [PASTE THE EXACT URL]

I do not consent to the processing of my personal data. Please delete my record
and suppress it from future re-listing. Where applicable, I exercise my rights of
erasure and to object to processing (EU GDPR Art. 17 & 21 / CCPA §1798.105), and
my rights under India's Digital Personal Data Protection Act, 2023.

Please confirm completion in writing to this email within 30 days.

Regards,
Aashishsingh Anilkumar Rajput
```

## PROMPT 3 — SUBMISSION (honest capability boundary)
I **cannot auto-submit** these forms — this environment has no live browser/Cowork automation tool.
What I CAN do is above: click-ready opt-out links + the exact request text + which need email verification.
- **Needs email verification → check inbox `ashumedico@gmail.com`:** RocketReach, ZoomInfo, ContactOut.
- Execute either yourself (10 min) OR in a Cowork/browser-enabled session; mark each row done/skipped here.

## PROMPT 4 — KEEP ME GONE
Weekly recheck scheduled (see cron). Each run: re-search the 8 sites, re-submit any ignored request,
re-remove any re-listing. Any site ignoring **2+ requests** → draft an FTC / India Grievance-Officer
(DPDP) complaint. Weekly summary of what's left.
_Note: the scheduler is session-limited (7-day auto-expiry) — for a permanent weekly job we'd need a hook._
