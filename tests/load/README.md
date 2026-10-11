# Load tests (H2)

Four [k6](https://k6.io) scenarios matching the H2 hardening prompt's own
list. **None of these have been run against a live target** -- there's no
staging environment or `k6` binary in the environment that wrote them.
They're syntax-checked (`node --input-type=module --check`) and structurally
reviewed against the real endpoint shapes, nothing more. Run them for real
before trusting any number out of them.

| Script | Endpoint | Target |
|---|---|---|
| `gate-batch-sync.js` | `POST /api/v1/gate/checkins:batch` | p95 < 600ms (write) |
| `member-search.js` | `GET /api/v1/members/?q=` | p95 < 300ms (read) |
| `owner-dashboard.js` | `GET /api/v1/reports/dashboard-summary` | p95 < 300ms (read) |
| `payment-initiate.js` | `POST /api/v1/billing/payments` | p95 < 600ms (write) |

## Seeding data first

Every script needs real data from the target environment -- there is no
way around this, these endpoints are gated by real auth:

- **`gate-batch-sync.js`**: a JSON array of raw device tokens from 2,000
  (or however many you can realistically seed) paired `GateDevice` rows.
  Pair them via the normal `/gate/pair` flow, or write a one-off management
  command that calls `attendance.services.register_gate_device` directly
  and dumps the raw tokens -- there's no bulk-pairing endpoint today.
  Point `DEVICE_TOKENS_FILE` at it.
- **`member-search.js`** / **`owner-dashboard.js`**: a staff JWT
  (`accounts.tokens.issue_tokens_for_user`, or just log in normally against
  the target) and that staff's gym id. The search benchmark is only
  meaningful against a gym with realistic volume -- `make seed`'s 10,000
  members (Phase 2's own acceptance target), not an empty dev gym.
- **`payment-initiate.js`**: a JSON array of `Invoice` ids in `draft`
  status, each with a total well above NPR 1.00 (the script pays a tiny
  partial amount repeatedly so it never flips to `issued` and starts
  hitting the idempotent-already-paid short-circuit instead of the real
  write path). Point `INVOICE_IDS_FILE` at it.

## Running

```bash
k6 run -e BASE_URL=https://staging-api.fitkhata.com \
       -e STAFF_JWT=<token> -e GYM_ID=<uuid> \
       tests/load/member-search.js
```

`gate-batch-sync.js` and `payment-initiate.js` additionally need their
`*_FILE` env var pointed at a seeded JSON array (see above); without one
they fall back to a single placeholder value purely so the script doesn't
crash -- that fallback proves the script *runs*, not that it *means*
anything as a load test.
