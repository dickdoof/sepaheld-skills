# Security

## Leaked API key

If a SepaHeld API key was exposed (committed, pasted into a chat, shared by mistake):

1. Revoke it immediately in SepaHeld > Einstellungen > API & Entwickler ("Widerrufen"). It stops working at once.
2. Create a new key and run `sepaheld.py configure --api-key <new key>`.
3. If it was committed to git, remove it from the history as well; revoking is what protects you.

Keys start with `sh_live_` (production) or `sh_test_` (test system), so secret scanners such as
GitHub secret scanning or Gitleaks can find them.

## Reporting a vulnerability

Please report vulnerabilities in this plugin or the SepaHeld API privately to
support@sepaheld.com (subject "Security") instead of opening a public issue.

## What the plugin does with your data

The script only talks to the SepaHeld API (`SEPAHELD_BASE_URL`, default
`https://app.backend.sepaheld.com/api`) with your API key. It stores the key and customer id in
`~/.config/sepaheld/config.json` (file mode 600) when you run `configure`, and nothing else.
