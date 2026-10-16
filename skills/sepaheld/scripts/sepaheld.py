#!/usr/bin/env python3
"""SepaHeld command line client for AI assistants (Claude Code, Codex).

Talks to the SepaHeld API v2 (KI-Integration, Business plan) with an API key.
Only the Python standard library is used.

Configuration (environment variables win over the config file):
  SEPAHELD_API_KEY       API key from SepaHeld > Einstellungen > API & Entwickler
  SEPAHELD_CUSTOMER_ID   your SepaHeld customer id (Einstellungen > API & Entwickler > KI-Integration)
  SEPAHELD_BASE_URL      default https://app.backend.sepaheld.com/api
  config file            ~/.config/sepaheld/config.json (written by `configure`)

Every command prints JSON. Commands that change something (send emails, move
money, write to the ERP) only run with --confirm; without it they print a dry
run of what would happen and exit with code 3.
"""

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://app.backend.sepaheld.com/api"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "sepaheld", "config.json")
MAX_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 60
BULK_MANDATE_LIMIT = 50
EXPIRY_WARNING_DAYS = 30

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_DRY_RUN = 3


class ApiError(Exception):
    def __init__(self, status, message, body=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.body = body


def load_config():
    config = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as error:
        raise ApiError(None, f"Cannot read {CONFIG_PATH}: {error}")
    return {
        "api_key": os.environ.get("SEPAHELD_API_KEY") or config.get("api_key"),
        "customer_id": os.environ.get("SEPAHELD_CUSTOMER_ID") or config.get("customer_id"),
        "base_url": (os.environ.get("SEPAHELD_BASE_URL") or config.get("base_url") or DEFAULT_BASE_URL).rstrip("/"),
    }


BUSINESS_DETAIL = re.compile(r"\[[A-Z_]+\]\s*(.*?)\)?$", re.S)


def error_text(parsed, raw):
    """Readable error text from a SepaHeld error body.

    Business errors come as {"errorMessage": "CONFLICT_GENERAL", "errorDetails":
    ["BusinessRuleException([CONFLICT_GENERAL] the actual text)"]}; filter errors as
    {"status": 401, "error": "Unauthorized", "message": "..."}.
    """
    if not isinstance(parsed, dict):
        return (raw or "").strip()
    for detail in parsed.get("errorDetails") or []:
        match = BUSINESS_DETAIL.search(str(detail))
        if match and match.group(1).strip():
            return match.group(1).strip()
    for field in ("errorMessage", "message", "error"):
        if parsed.get(field):
            return str(parsed[field]).strip()
    return (raw or "").strip()


def explain(status, message):
    """Turns HTTP errors into a sentence the assistant can pass on to the user."""
    hints = {
        401: "The API key is missing, invalid, expired or revoked. Create a new key in SepaHeld "
             "(Einstellungen > API & Entwickler) and run `configure` again.",
        402: "This needs an active SepaHeld subscription with the KI-Integration (Business plan).",
        403: "Not allowed: either the plan does not include the KI-Integration (Business plan) "
             "or the API key is read-only.",
        404: "Not found. If every call returns 404, the KI-Integration is not enabled yet for this "
             "environment, or the id is wrong.",
        409: "Conflict: the action is not possible in the current state (see message).",
        429: "Rate limit reached. Wait and try again later (see retryAfterSeconds).",
    }
    hint = hints.get(status)
    return f"{message} {hint}".strip() if hint else message


class Client:
    def __init__(self, config, opener=None):
        if not config.get("api_key") or not config.get("customer_id"):
            raise ApiError(None, "Not configured. Set SEPAHELD_API_KEY and SEPAHELD_CUSTOMER_ID or run "
                                 "`sepaheld.py configure --api-key ... --customer-id ...`.")
        self.config = config
        self.opener = opener or urllib.request.build_opener()

    def url(self, path, query=None):
        base = f"{self.config['base_url']}/public/v2/{urllib.parse.quote(self.config['customer_id'])}/{path}"
        query = {key: value for key, value in (query or {}).items() if value not in (None, "", False)}
        return base + ("?" + urllib.parse.urlencode(query) if query else "")

    def request(self, method, path, query=None, body=None, idempotency_key=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "X-API-Key": self.config["api_key"],
            "Accept": "application/json",
            "User-Agent": f"sepaheld-skill/{VERSION}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(MAX_RETRIES + 1):
            request = urllib.request.Request(self.url(path, query), data=data, headers=headers, method=method)
            try:
                with self.opener.open(request, timeout=60) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as error:
                raw = error.read().decode("utf-8", errors="replace")
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if error.code == 429 and attempt < MAX_RETRIES and retry_after and retry_after.isdigit() \
                        and int(retry_after) <= MAX_RETRY_WAIT_SECONDS:
                    time.sleep(int(retry_after))
                    continue
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    parsed = None
                message = error_text(parsed, raw)
                failure = ApiError(error.code, explain(error.code, (message or f"HTTP {error.code}").strip()),
                                   parsed)
                if error.code == 429 and retry_after:
                    failure.body = {**(parsed or {}), "retryAfterSeconds": int(retry_after) if retry_after.isdigit()
                                    else retry_after}
                raise failure
            except urllib.error.URLError as error:
                raise ApiError(None, f"Cannot reach SepaHeld at {self.config['base_url']}: {error.reason}")
        raise ApiError(429, explain(429, "Rate limit reached."))

    def get(self, path, query=None):
        return self.request("GET", path, query=query)

    def post(self, path, body=None, idempotency_key=None):
        return self.request("POST", path, body=body if body is not None else {},
                            idempotency_key=idempotency_key or str(uuid.uuid4()))


# ---------------------------------------------------------------------------------------------
# commands


def dry_run(action, details):
    return EXIT_DRY_RUN, {
        "dryRun": True,
        "action": action,
        "details": details,
        "next": "Show this to the user. Only after an explicit yes, run the same command again with --confirm.",
    }


def cmd_configure(args, _client_factory):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    current = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            current = json.load(handle)
    for field in ("api_key", "customer_id", "base_url"):
        value = getattr(args, field)
        if value:
            current[field] = value
    descriptor = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2)
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    return EXIT_OK, {"saved": CONFIG_PATH, "fields": sorted(current.keys())}


def cmd_check(_args, client_factory):
    client = client_factory()
    key = client.get("api-key")
    health = client.get("health")
    warnings = []
    days = key.get("daysUntilExpiry")
    if isinstance(days, int) and days <= EXPIRY_WARNING_DAYS:
        warnings.append(f"The API key expires in {days} days. Create a new key in SepaHeld (Einstellungen > API & Entwickler) "
                        "and run `configure` again.")
    if key.get("scope") == "READ":
        warnings.append("This API key is read-only: lookups work, actions are refused.")
    return EXIT_OK, {"apiKey": key, "health": health, "warnings": warnings}


def cmd_health(_args, client_factory):
    return EXIT_OK, client_factory().get("health")


def cmd_contacts(args, client_factory):
    result = client_factory().get("contacts", {
        "query": args.query, "withoutMandate": "true" if args.without_mandate else None,
        "page": args.page, "size": args.size})
    return EXIT_OK, result


def cmd_mandate_requests(_args, client_factory):
    return EXIT_OK, client_factory().get("mandate-requests")


def cmd_request_mandate(args, client_factory):
    if not args.confirm:
        return dry_run("Send a SEPA mandate request" + ("" if args.no_email else " by email"),
                       {"contactId": args.contact_id, "sendEmail": not args.no_email})
    return EXIT_OK, client_factory().post(f"contacts/{q(args.contact_id)}/mandate-request",
                                          {"sendEmail": not args.no_email}, args.idempotency_key)


def cmd_bulk_request_mandates(args, client_factory):
    client = client_factory()
    limit = min(args.limit, BULK_MANDATE_LIMIT)
    candidates, skipped, page = [], [], 0
    while len(candidates) < limit:
        result = client.get("contacts", {"withoutMandate": "true", "page": page, "size": 100})
        items = result.get("content") or result.get("items") or []
        for contact in items:
            if contact.get("openMandateRequest"):
                skipped.append({"contactId": contact.get("contactId"), "name": contact.get("name"),
                                "reason": "mandate request already open"})
            elif not contact.get("email"):
                skipped.append({"contactId": contact.get("contactId"), "name": contact.get("name"),
                                "reason": "no email address"})
            elif len(candidates) < limit:
                candidates.append({"contactId": contact.get("contactId"), "name": contact.get("name"),
                                   "email": contact.get("email")})
        if result.get("last", True) or not items:
            break
        page += 1

    if not args.confirm:
        return dry_run(f"Send mandate requests by email to {len(candidates)} contacts without a mandate "
                       f"(at most {BULK_MANDATE_LIMIT} per run)", {"contacts": candidates, "skipped": skipped})

    sent, failed = [], []
    for contact in candidates:
        try:
            client.post(f"contacts/{q(contact['contactId'])}/mandate-request", {"sendEmail": True})
            sent.append(contact)
        except ApiError as error:
            failed.append({**contact, "error": error.message})
            if error.status in (401, 402, 403):
                break
    return EXIT_OK if not failed else EXIT_ERROR, {"sent": sent, "failed": failed, "skipped": skipped}


def cmd_remind(args, client_factory):
    if not args.confirm:
        return dry_run("Re-send the mandate request email", {"mandateRequestId": args.flow_id})
    return EXIT_OK, client_factory().post(f"mandate-requests/{q(args.flow_id)}/remind", {}, args.idempotency_key)


def cmd_invoices(args, client_factory):
    return EXIT_OK, client_factory().get("invoices", {"number": args.number})


def cmd_diagnose(args, client_factory):
    return EXIT_OK, client_factory().get(f"invoices/{q(args.invoice_id)}/diagnosis")


def cmd_collect(args, client_factory):
    if not args.confirm:
        client = client_factory()
        diagnosis = client.get(f"invoices/{q(args.invoice_id)}/diagnosis")
        return dry_run("Collect this invoice now by SEPA direct debit (manual transfer)",
                       {"invoiceId": args.invoice_id, "diagnosis": diagnosis})
    return EXIT_OK, client_factory().post(f"invoices/{q(args.invoice_id)}/collect", {}, args.idempotency_key)


def cmd_payments(args, client_factory):
    return EXIT_OK, client_factory().get("payments", {
        "status": args.status, "from": args.from_date, "to": args.to_date,
        "invoiceNumber": args.invoice_number, "page": args.page, "size": args.size})


def cmd_retry(args, client_factory):
    if not args.confirm:
        return dry_run("Collect this failed payment again", {"paymentId": args.payment_id})
    return EXIT_OK, client_factory().post(f"payments/{q(args.payment_id)}/retry", {}, args.idempotency_key)


def cmd_cancel_payment(args, client_factory):
    if not args.confirm:
        return dry_run("Cancel this pending payment before it is submitted to the bank",
                       {"paymentId": args.payment_id})
    return EXIT_OK, client_factory().post(f"payments/{q(args.payment_id)}/cancel", {}, args.idempotency_key)


def cmd_payouts(args, client_factory):
    return EXIT_OK, client_factory().get("payouts/upcoming" if args.upcoming else "payouts")


def cmd_book_payout(args, client_factory):
    if not args.confirm:
        return dry_run("Book this payout in the ERP (financial transactions)", {"payoutId": args.payout_id})
    return EXIT_OK, client_factory().post(f"payouts/{q(args.payout_id)}/book", {}, args.idempotency_key)


def cmd_summary(args, client_factory):
    return EXIT_OK, client_factory().get("summary", {"days": args.days})


def cmd_dunning(_args, client_factory):
    return EXIT_OK, client_factory().get("dunning/processes")


def cmd_stop_dunning(args, client_factory):
    if not args.confirm:
        return dry_run("Stop this dunning process (no further reminders)",
                       {"dunningProcessId": args.process_id, "reason": args.reason})
    return EXIT_OK, client_factory().post(f"dunning/processes/{q(args.process_id)}/cancel",
                                          {"reason": args.reason}, args.idempotency_key)


def cmd_start_dunning(args, client_factory):
    if not args.confirm:
        return dry_run("Start payment reminders (dunning) for this failed payment", {"paymentId": args.payment_id})
    return EXIT_OK, client_factory().post(f"payments/{q(args.payment_id)}/dunning", {}, args.idempotency_key)


def q(value):
    return urllib.parse.quote(str(value), safe="")


# ---------------------------------------------------------------------------------------------
# argument parsing


def build_parser():
    parser = argparse.ArgumentParser(prog="sepaheld.py", description="SepaHeld API v2 client (KI-Integration).")
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, handler, help_text, write=False):
        sub = commands.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler)
        if write:
            sub.add_argument("--confirm", action="store_true",
                             help="actually do it (only after the user said yes to the dry run)")
            sub.add_argument("--idempotency-key", help="reuse when retrying the same action")
        return sub

    sub = add("configure", cmd_configure, "save API key / customer id to the config file")
    sub.add_argument("--api-key")
    sub.add_argument("--customer-id")
    sub.add_argument("--base-url")

    add("check", cmd_check, "verify the setup: key scope and expiry, connections")
    add("health", cmd_health, "is the SepaHeld setup OK?")

    sub = add("contacts", cmd_contacts, "search ERP contacts with their mandate status")
    sub.add_argument("--query", help="name, company or email (fuzzy)")
    sub.add_argument("--without-mandate", action="store_true")
    sub.add_argument("--page", type=int)
    sub.add_argument("--size", type=int)

    add("mandate-requests", cmd_mandate_requests, "list open mandate requests")

    sub = add("request-mandate", cmd_request_mandate, "send a mandate request to one contact", write=True)
    sub.add_argument("contact_id")
    sub.add_argument("--no-email", action="store_true", help="create the request without emailing it")

    sub = add("bulk-request-mandates", cmd_bulk_request_mandates,
              "send mandate requests to contacts without a mandate", write=True)
    sub.add_argument("--limit", type=int, default=BULK_MANDATE_LIMIT)

    sub = add("remind", cmd_remind, "re-send an open mandate request", write=True)
    sub.add_argument("flow_id")

    sub = add("invoices", cmd_invoices, "find an ERP invoice by its number")
    sub.add_argument("--number", required=True)

    sub = add("diagnose", cmd_diagnose, "explain why an invoice was (not) collected")
    sub.add_argument("invoice_id")

    sub = add("collect", cmd_collect, "collect an invoice now (manual transfer)", write=True)
    sub.add_argument("invoice_id")

    sub = add("payments", cmd_payments, "list payments, e.g. failed ones")
    sub.add_argument("--status", help="e.g. PAYMENT_FAILED, PAYMENT_CHARGED_BACK, PAYMENT_PENDING")
    sub.add_argument("--from", dest="from_date", help="ISO date, e.g. 2026-10-01")
    sub.add_argument("--to", dest="to_date", help="ISO date")
    sub.add_argument("--invoice-number")
    sub.add_argument("--page", type=int)
    sub.add_argument("--size", type=int)

    sub = add("retry", cmd_retry, "collect a failed payment again", write=True)
    sub.add_argument("payment_id")

    sub = add("cancel-payment", cmd_cancel_payment, "cancel a pending payment", write=True)
    sub.add_argument("payment_id")

    sub = add("payouts", cmd_payouts, "list payouts")
    sub.add_argument("--upcoming", action="store_true")

    sub = add("book-payout", cmd_book_payout, "book a payout in the ERP", write=True)
    sub.add_argument("payout_id")

    sub = add("summary", cmd_summary, "summary of the last days")
    sub.add_argument("--days", type=int, default=7)

    add("dunning", cmd_dunning, "list dunning processes")

    sub = add("stop-dunning", cmd_stop_dunning, "stop a dunning process", write=True)
    sub.add_argument("process_id")
    sub.add_argument("--reason", required=True, help='e.g. "paid by bank transfer"')

    sub = add("start-dunning", cmd_start_dunning, "start dunning for a failed payment", write=True)
    sub.add_argument("payment_id")
    return parser


def main(argv=None, client_factory=None, out=sys.stdout):
    args = build_parser().parse_args(argv)
    factory = client_factory or (lambda: Client(load_config()))
    try:
        code, result = args.handler(args, factory)
    except ApiError as error:
        code, result = EXIT_ERROR, {"error": error.message, "status": error.status, "details": error.body}
    json.dump(result, out, indent=2, ensure_ascii=False, default=str)
    out.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
