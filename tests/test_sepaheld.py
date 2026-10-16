"""Unit tests for skills/sepaheld/scripts/sepaheld.py (stdlib only, no network)."""
import email.message
import importlib.util
import io
import json
import os
import pathlib
import stat
import tempfile
import unittest
import urllib.error
from unittest import mock

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills" / "sepaheld" / "scripts" / "sepaheld.py"
spec = importlib.util.spec_from_file_location("sepaheld", SCRIPT)
sepaheld = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sepaheld)

CONFIG = {"api_key": "sh_test_secret", "customer_id": "cust-1", "base_url": "https://example.test/api"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeOpener:
    """Returns queued responses: dicts become 200 JSON, (status, body, headers) become HTTP errors."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, tuple):
            status, body, headers = response
            message = email.message.Message()
            for key, value in (headers or {}).items():
                message[key] = value
            raise urllib.error.HTTPError(request.full_url, status, "error", message,
                                         io.BytesIO(json.dumps(body).encode()))
        return FakeResponse(json.dumps(response).encode())


def run(argv, opener):
    out = io.StringIO()
    code = sepaheld.main(argv, client_factory=lambda: sepaheld.Client(CONFIG, opener), out=out)
    return code, json.loads(out.getvalue())


class ClientTest(unittest.TestCase):
    def test_get_sends_key_and_builds_url(self):
        opener = FakeOpener({"content": [], "last": True})
        code, result = run(["contacts", "--query", "Acme GmbH", "--without-mandate"], opener)

        self.assertEqual(code, 0)
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url,
                         "https://example.test/api/public/v2/cust-1/contacts?query=Acme+GmbH&withoutMandate=true")
        self.assertEqual(request.get_header("X-api-key"), "sh_test_secret")

    def test_business_error_text_is_extracted(self):
        body = {"errorMessage": "CONFLICT_GENERAL",
                "errorDetails": ["BusinessRuleException([CONFLICT_GENERAL] Zahlung bereits eingereicht)"]}
        opener = FakeOpener((409, body, {}))
        code, result = run(["payments"], opener)

        self.assertEqual(code, sepaheld.EXIT_ERROR)
        self.assertEqual(result["status"], 409)
        self.assertTrue(result["error"].startswith("Zahlung bereits eingereicht"))

    def test_401_explains_how_to_get_a_new_key(self):
        opener = FakeOpener((401, {"status": 401, "error": "Unauthorized"}, {}))
        code, result = run(["health"], opener)

        self.assertEqual(code, sepaheld.EXIT_ERROR)
        self.assertIn("API & Entwickler", result["error"])

    def test_429_waits_and_retries(self):
        opener = FakeOpener((429, {"errorMessage": "TOO_MANY_REQUESTS"}, {"Retry-After": "2"}), {"ok": True})
        with mock.patch.object(sepaheld.time, "sleep") as sleep:
            code, result = run(["health"], opener)

        self.assertEqual(code, 0)
        self.assertEqual(result, {"ok": True})
        sleep.assert_called_once_with(2)

    def test_429_with_long_wait_is_reported(self):
        opener = FakeOpener((429, {"errorMessage": "TOO_MANY_REQUESTS"}, {"Retry-After": "3600"}))
        code, result = run(["health"], opener)

        self.assertEqual(code, sepaheld.EXIT_ERROR)
        self.assertEqual(result["details"]["retryAfterSeconds"], 3600)

    def test_not_configured(self):
        with self.assertRaises(sepaheld.ApiError):
            sepaheld.Client({"api_key": None, "customer_id": None, "base_url": "x"})


class WriteCommandTest(unittest.TestCase):
    def test_write_without_confirm_is_a_dry_run(self):
        opener = FakeOpener()
        code, result = run(["request-mandate", "c1"], opener)

        self.assertEqual(code, sepaheld.EXIT_DRY_RUN)
        self.assertTrue(result["dryRun"])
        self.assertEqual(opener.requests, [])

    def test_collect_dry_run_only_reads_the_diagnosis(self):
        opener = FakeOpener({"collectable": True, "nextStep": "COLLECT_MANUALLY"})
        code, result = run(["collect", "inv-1"], opener)

        self.assertEqual(code, sepaheld.EXIT_DRY_RUN)
        self.assertEqual([r.get_method() for r in opener.requests], ["GET"])
        self.assertTrue(opener.requests[0].full_url.endswith("/invoices/inv-1/diagnosis"))

    def test_confirmed_write_posts_with_idempotency_key(self):
        opener = FakeOpener({"result": "PAYMENT_CREATED"})
        code, result = run(["collect", "inv/1", "--confirm", "--idempotency-key", "k-1"], opener)

        self.assertEqual(code, 0)
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/invoices/inv%2F1/collect"))
        self.assertEqual(request.get_header("Idempotency-key"), "k-1")

    def test_generated_idempotency_key(self):
        opener = FakeOpener({"result": "OK"})
        run(["retry", "p1", "--confirm"], opener)

        self.assertTrue(opener.requests[0].get_header("Idempotency-key"))

    def test_stop_dunning_sends_reason(self):
        opener = FakeOpener({"result": "CANCELLED"})
        run(["stop-dunning", "d1", "--reason", "per Überweisung bezahlt", "--confirm"], opener)

        self.assertEqual(json.loads(opener.requests[0].data), {"reason": "per Überweisung bezahlt"})

    def test_bulk_request_skips_open_and_emailless_contacts(self):
        contacts = {"content": [
            {"contactId": "a", "name": "A", "email": "a@example.test"},
            {"contactId": "b", "name": "B", "email": None},
            {"contactId": "c", "name": "C", "email": "c@example.test", "openMandateRequest": True},
        ], "last": True}
        opener = FakeOpener(contacts, {"result": "MANDATE_REQUESTED"})
        code, result = run(["bulk-request-mandates", "--confirm"], opener)

        self.assertEqual(code, 0)
        self.assertEqual([c["contactId"] for c in result["sent"]], ["a"])
        self.assertEqual(sorted(s["contactId"] for s in result["skipped"]), ["b", "c"])
        self.assertTrue(opener.requests[1].full_url.endswith("/contacts/a/mandate-request"))


class CheckTest(unittest.TestCase):
    def test_warns_about_expiry_and_read_only(self):
        opener = FakeOpener({"daysUntilExpiry": 10, "scope": "READ"}, {"ok": True})
        code, result = run(["check"], opener)

        self.assertEqual(code, 0)
        self.assertEqual(len(result["warnings"]), 2)


class HelpTest(unittest.TestCase):
    def run_help(self, *extra, env=None):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(sepaheld, "CONFIG_PATH", os.path.join(directory, "missing.json")), \
                mock.patch.dict(os.environ, env or {}, clear=True):
            code = sepaheld.main(["help", *extra], client_factory=lambda: self.fail("help must not call the API"),
                                 out=out)
        return code, json.loads(out.getvalue())

    def test_german_overview_without_configuration(self):
        code, result = self.run_help()

        self.assertEqual(code, 0)
        self.assertFalse(result["configured"])
        self.assertIn("API & Entwickler", result["setup"])
        self.assertEqual([a["area"] for a in result["areas"]][:2], ["Einrichtung", "Mandate"])

    def test_english_and_configured(self):
        code, result = self.run_help("--lang", "en",
                                     env={"SEPAHELD_API_KEY": "k", "SEPAHELD_CUSTOMER_ID": "c"})

        self.assertEqual(code, 0)
        self.assertTrue(result["configured"])
        self.assertEqual(result["title"], "What I can do for you in SepaHeld")

    def test_both_languages_have_the_same_shape(self):
        de, en = sepaheld.HELP["de"], sepaheld.HELP["en"]
        self.assertEqual(de.keys(), en.keys())
        self.assertEqual([len(a["examples"]) for a in de["areas"]], [len(a["examples"]) for a in en["areas"]])
        self.assertEqual(len(de["limits"]), len(en["limits"]))
        self.assertEqual(len(de["notYet"]), len(en["notYet"]))

    def test_every_area_is_covered_by_a_command(self):
        commands = set(sepaheld.build_parser()._subparsers._group_actions[0].choices)
        for command in ("check", "contacts", "request-mandate", "bulk-request-mandates", "remind", "diagnose",
                        "collect", "payments", "retry", "cancel-payment", "payouts", "book-payout", "summary",
                        "dunning", "stop-dunning", "start-dunning"):
            self.assertIn(command, commands)


class ConfigureTest(unittest.TestCase):
    def test_config_file_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sepaheld", "config.json")
            with mock.patch.object(sepaheld, "CONFIG_PATH", path):
                code, _ = 0, None
                out = io.StringIO()
                code = sepaheld.main(["configure", "--api-key", "k", "--customer-id", "c"], out=out)

                self.assertEqual(code, 0)
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(sepaheld.load_config()["customer_id"], "c")


if __name__ == "__main__":
    unittest.main()
