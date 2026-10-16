# Setup check

`check` runs `api-key` (scope, expiry) and `health`. `health` returns `ok` and these checks:

| Check | If it fails, tell the user |
|---|---|
| `ERP_CONNECTED` | connect the ERP in SepaHeld (Einstellungen > Integrationen) |
| `ERP_ACCESS` | reconnect the ERP; the access expired |
| `PAYMENT_CONDITION` | choose the payment condition(s) in SepaHeld that are also used on the invoices |
| `GOCARDLESS_CONNECTED` | reconnect GoCardless |
| `GOCARDLESS_VERIFIED` | finish the verification at GoCardless (or wait for the review) |
| `COMPANY_DATA` | company name / city missing or different between ERP and GoCardless |
| `SUBSCRIPTION` | the SepaHeld subscription is not active or incomplete |

Each check has a German `detail` text you can paraphrase. `tier` is the SepaHeld plan (`business` needed).
