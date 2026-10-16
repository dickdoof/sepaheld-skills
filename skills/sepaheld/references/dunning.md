# Dunning (Mahnwesen)

SepaHeld sends payment reminders when a payment fails, if dunning is switched on (SepaHeld > Mahnwesen).

- `dunning` - all dunning processes: `status` (`ACTIVE` running, `COMPLETED`, `CANCELLED_PAID`, `CANCELLED_MANUAL`),
  `currentLevel`, `invoiceNumber`, `amount`, `debtorContactName`, `debtorEmails`, `lastSentAt`, `emailLog`.
- `stop-dunning <processId> --reason "<why>"` (dry run, then `--confirm`) - stops further reminders and stores the
  reason (e.g. "per Überweisung bezahlt"). Always ask the user for the reason if they did not give one.
- `start-dunning <paymentId>` (dry run, then `--confirm`) - starts dunning for a failed or charged back payment
  that has none yet. Refused when dunning is switched off or no email address is known for the payer.
