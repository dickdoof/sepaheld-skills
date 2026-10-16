# Invoices and payments

## Find an invoice

`invoices --number RE-2024-123` returns matching invoices (exact matches first) with the ERP invoice `id` - use that
id for `diagnose` and `collect`. Results come from SepaHeld payments (also paid invoices) and from the open invoices
in the ERP. `payment` is the SepaHeld payment if one exists.

## Why was an invoice (not) collected? - `diagnose <invoiceId>`

Checks, in SepaHeld's order: `PAYMENT` (already a payment?), `INVOICE_STATUS` (open?), `INVOICE_TYPE` (collected in
this plan?), `CONTACT`, `SUBSCRIPTION`, `GOCARDLESS`, `PAYMENT_TERMS` (does the payment condition match the one chosen
in SepaHeld - only needed for *automatic* collection), `MANDATE`.

`nextStep` and what to offer:

| nextStep | Offer |
|---|---|
| `REQUEST_MANDATE` | `request-mandate <contactId>` |
| `REMIND_MANDATE_REQUEST` | `mandate-requests` -> `remind <id>` |
| `COLLECT_MANUALLY` | `collect <invoiceId>` |
| `RETRY_PAYMENT` | `retry <paymentId>` (`payment.id` in the diagnosis) |
| `FIX_SETUP` | `check` and explain the failed checks |
| `WAIT` | nothing - collection is running or done; show `payment.status` |
| `NONE` | nothing to collect (e.g. invoice paid or without contact) - explain `nextStepText` |

`automaticCollection: true` means SepaHeld collects it by itself; `collectable: true` means `collect` would create a
payment now.

## Collect now - `collect <invoiceId>`

Manual transfer without the payment-term check. The dry run shows the diagnosis; confirm only after the user agreed
to the invoice number and amount. Results: `PAYMENT_CREATED` (with `payment`), or `MANDATE_REQUESTED` when the
contact has no mandate yet (SepaHeld then emails a mandate request; the invoice is collected after signing).
An invoice that already has a running or finished payment is refused.

## Payments

- `payments --status PAYMENT_FAILED` (also `PAYMENT_CHARGED_BACK`, `PAYMENT_LATE_FAILURE`, `PAYMENT_PENDING`,
  `PAYMENT_SUBMITTED`, `PAYMENT_CONFIRMED`, `PAYMENT_PAID_OUT`, `PAYMENT_CANCELLED`, `MANDATE_EXPIRED`), optional
  `--from 2026-10-01 --to 2026-10-31`, `--invoice-number`. Amounts are in euros.
- `retry <paymentId>` - collects the invoice of a failed payment again (only failed / charged back / cancelled /
  expired-mandate payments, once per payment).
- `cancel-payment <paymentId>` - only `PAYMENT_PENDING` / `PAYMENT_CREATED`, before GoCardless submits it to the
  bank. If GoCardless already submitted it, the API says so and nothing changes.

Status meaning: `PENDING`/`CREATED` = scheduled, `SUBMITTED` = at the bank, `CONFIRMED` = collected,
`PAID_OUT` = paid out to the user, `FAILED`/`LATE_FAILURE` = not collected, `CHARGED_BACK` = payer reversed it.
