# Mandates (Lastschriftmandate)

A payer must sign a SEPA mandate (via GoCardless) before SepaHeld can collect their invoices.
SepaHeld emails a *mandate request* with a link; once the payer signs, waiting invoices are collected.

## Commands

- `contacts --query "<name or email>"` - ERP contacts with `mandateStatus`:
  - `ACTIVE` mandate exists, invoices are collected
  - `REQUESTED` request sent, waiting for the payer (`openMandateRequest: true`, `mandateRequestId`)
  - `ERROR` the last request failed
  - `NONE` no mandate, no request
- `contacts --without-mandate` - everyone who still needs one (paged: `--page`, `--size`; `last: true` on the last page).
- `mandate-requests` - open requests, newest first, with `emails`, `createdAt`, `invoiceNumbers` (invoices waiting
  for this mandate) and `lastRemindedAt`.
- `request-mandate <contactId>` (dry run, then `--confirm`) - creates the request and emails the link.
  `--no-email` creates it without email (the user then shares the link themselves - rarely wanted).
- `bulk-request-mandates [--limit N]` (dry run, then `--confirm`) - at most 50 contacts per run; skips contacts
  without email or with an open request and lists them under `skipped`.
- `remind <mandateRequestId>` (dry run, then `--confirm`) - emails the link again. The API refuses a reminder within
  72 hours of the request or the last reminder and says when the next one is possible.

## Tips

- If a contact has no email address, the request fails ("End-customer does not have any email address"): tell the
  user to add an email to the contact in their ERP.
- `contacts` calls the ERP live and is limited to 3 calls per minute; search once, then work with the results.
