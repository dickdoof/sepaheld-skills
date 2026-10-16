# Payouts and reports

- `payouts` - the latest GoCardless payouts: `amount` and `deductedFees` in euros, `status`, `arrivalDate`,
  `bookedAt` (when it was booked into the ERP; null = not yet).
- `payouts --upcoming` - GoCardless creditor balances: what will be paid out next (raw GoCardless data; amounts
  there are in cents).
- `book-payout <payoutId>` (dry run, then `--confirm`) - writes the payout into the ERP as financial transactions.
  Refused if it was already booked (by hand in the app or via the API); then point the user to the app.
- `summary --days 7` - collected, open and failed amounts, success rate, new and pending mandates, chargebacks for
  the last 1-90 days. Present it as a short weekly report with the numbers that matter (collected, failed, open,
  chargebacks) and offer to look into failed payments.
