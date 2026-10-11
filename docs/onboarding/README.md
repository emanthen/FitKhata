# Onboarding guides

Each guide exists in English and Nepali — print the one your staff need.
Screenshots in `images/` are real captures from the app (dev build,
2026-10-11), not mockups.

- **`front-desk-quickguide.{en,ne}.md`** — one page, daily front-desk
  tasks: sign in, check in a member, register, sell/collect payment, cash
  shift, receipts.
- **`owner-guide.{en,ne}.md`** — full setup: the onboarding wizard,
  payments, gate/printer hardware, member import, running the business day
  to day, and your own FitKhata subscription.
- **`gate-tablet-setup.{en,ne}.md`** — unboxing to a working QR scan:
  generating a pairing code, pairing the tablet, mounting it, testing
  offline mode, and troubleshooting.

Written and screenshotted against the dev build with no live backend
connected (no Docker in the environment that wrote these) — the UI chrome,
copy, and flow are real; anything needing live data to render (the
dashboard's actual numbers, a real pairing code's digits) is described
from the code, not screenshotted. Re-screenshot against a real staging
gym before handing these to the pilot gyms, and spot-check the Nepali
copy with a native speaker — it was written carefully but not reviewed by
one.
