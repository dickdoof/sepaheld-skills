---
name: sepaheld
description: Manage SEPA direct debit (Lastschrift) with SepaHeld - send mandate requests (Lastschriftmandat) to contacts, collect ERP invoices, explain why an invoice was not collected, list failed payments and chargebacks (Rücklastschriften), retry or cancel payments, payouts, weekly summary, dunning (Mahnwesen) and a setup check. Use when the user mentions SepaHeld, SEPA, Lastschrift, direct debit, mandates, GoCardless collections, Mahnungen or asks about their invoices being collected, or asks what can be done with SepaHeld (Hilfe / help).
license: Apache-2.0
---

# SepaHeld (SEPA-Lastschrift / direct debit)

SepaHeld connects the user's ERP (Lexware Office, sevDesk, Moco, Xentral, Invoiz, WISO MeinBüro,
Papierkram) with GoCardless and collects invoices by SEPA direct debit. This skill drives the
SepaHeld API v2 through one script. It needs the SepaHeld **Business** plan (KI-Integration).

Run every command as:

```bash
python3 "<this skill's directory>/scripts/sepaheld.py" <command> [options]
```

Every command prints JSON. Answer the user in their language (usually German), in plain words,
never as raw JSON.

## Setup (first use)

1. Run `check`. If it says "Not configured", ask the user for their API key and customer id
   (SepaHeld > Einstellungen > API & Entwickler: create the key in the API-key card; the customer id
   is in the "KI-Integration" card on the same tab).
   Never ask them to paste the key into a file you then commit, and never echo the key back.
2. Save it: `configure --api-key <key> --customer-id <id>` (stored with permissions 600 in
   `~/.config/sepaheld/config.json`; env vars `SEPAHELD_API_KEY` / `SEPAHELD_CUSTOMER_ID` win).
3. Run `check` again. Pass on its `warnings` (key expiring within 30 days, read-only key).

## Help ("Hilfe", "Was kannst du?", "help")

When the user asks for help, what you can do with SepaHeld, or seems unsure what to ask, run
`help --lang de` (or `--lang en` for English; for other languages run `en` and translate).
It works without setup and without network. Answer from its output only, in this order:

1. `title`, then each area with its example sentences, so the user can copy one.
2. `safety` in one sentence.
3. `limits` and `notYet` only if they matter for what the user wants, or if asked.
4. If `configured` is false, the `setup` text and offer to set it up now.

Do not promise anything that is not in the output.

## Rules - always follow

- **Never act without a yes.** Every command that sends emails, moves money or writes to the ERP
  (`request-mandate`, `bulk-request-mandates`, `remind`, `collect`, `retry`, `cancel-payment`,
  `book-payout`, `stop-dunning`, `start-dunning`) first runs as a dry run (no `--confirm`, exit
  code 3). Show the user what will happen - who, which invoice, which amount, which email - and
  only after an explicit yes run the same command with `--confirm`. A yes covers only that one
  action; ask again for the next one.
- **Never guess an id.** Resolve names and invoice numbers with `contacts --query` or
  `invoices --number`. If several match, list them and ask. If none match, say so.
- **Bulk actions** always start with the dry run. `bulk-request-mandates` sends at most 50 per run
  and skips contacts without an email address or with an open request; tell the user about the
  skipped ones.
- **Errors:** pass on the `error` text. 401 = key invalid/expired/revoked (new key in the
  settings). 403/402 = plan without KI-Integration or read-only key. 429 = limit reached; the
  script already waited and retried, so tell the user when to try again (`retryAfterSeconds`).
- Do not retry a failed write with a new idempotency key unless the user asks; reuse
  `--idempotency-key` from the failed call when you retry the same action.

## What the user asks -> what to run

| User says | Run |
|---|---|
| "Hilfe" / "Was kannst du mit SepaHeld?" | `help --lang de` (see Help above) |
| "Ist meine Einrichtung in Ordnung?" | `check` (or `health`) - explain each failed check and how to fix it |
| "Schick Acme GmbH eine Mandatsanfrage" | `contacts --query "Acme"` -> pick contact -> `request-mandate <contactId>` (dry run, confirm) |
| "Hat Acme ein Mandat?" | `contacts --query "Acme"` -> `mandateStatus` |
| "Schick allen ohne Mandat eine Anfrage" | `bulk-request-mandates` (dry run, confirm) |
| "Welche Anfragen sind noch offen? Erinnere sie." | `mandate-requests` -> `remind <id>` per request (at most once per 72 h; the API refuses earlier reminders) |
| "Warum wurde RE-2024-123 nicht eingezogen?" | `invoices --number RE-2024-123` -> `diagnose <invoiceId>` |
| "Zieh RE-2024-123 jetzt ein" | `invoices --number ...` -> `collect <invoiceId>` (dry run shows the diagnosis, then confirm) |
| "Zeig fehlgeschlagene Zahlungen / Rücklastschriften" | `payments --status PAYMENT_FAILED` and `--status PAYMENT_CHARGED_BACK` (optionally `--from`) |
| "Versuch die Zahlung erneut" | `retry <paymentId>` (dry run, confirm) |
| "Storniere die ausstehende Zahlung" | `cancel-payment <paymentId>` (only `PAYMENT_PENDING` / `PAYMENT_CREATED`) |
| "Welche Auszahlungen kommen?" | `payouts --upcoming` |
| "Buch Auszahlung X ins ERP" | `book-payout <payoutId>` (dry run, confirm; already booked payouts are refused) |
| "Wochenübersicht" | `summary --days 7` |
| "Welche Mahnläufe laufen?" | `dunning` |
| "Stopp die Mahnung für Acme, hat überwiesen" | `dunning` -> pick process -> `stop-dunning <id> --reason "per Überweisung bezahlt"` |
| "Starte Mahnungen für die fehlgeschlagene Zahlung" | `start-dunning <paymentId>` |

Details per area: [mandates](references/mandates.md), [invoices and payments](references/invoices.md),
[payouts and reports](references/payouts.md), [dunning](references/dunning.md),
[setup check](references/health.md).

## Reading the diagnosis

`diagnose` returns `collectable` (true/false), `checks` (each with `name`, `passed`, `detail`) and
`nextStep`. Explain the first failed check in one sentence and offer `nextStep`, e.g. no mandate
-> offer `request-mandate`; payment terms do not match -> offer `collect` (manual transfer);
already collected -> show the payment status.
