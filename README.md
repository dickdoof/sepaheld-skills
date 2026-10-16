# SepaHeld® für Claude & Codex

SEPA-Lastschrift aus dem KI-Assistenten: Mandate anfragen, Rechnungen einziehen, nachsehen,
warum eine Rechnung nicht eingezogen wurde, fehlgeschlagene Zahlungen, Auszahlungen und
Mahnwesen – direkt in [Claude Code](https://claude.com/claude-code) oder Codex.

[English below](#english)

> **Voraussetzung:** ein SepaHeld-Konto im Tarif **Business** (enthält die KI-Integration).
> Mehr dazu: <https://sepaheld.com/ki-integration/>

## Was der Assistent kann

| Sie sagen | Der Assistent |
|---|---|
| „Ist meine SepaHeld-Einrichtung in Ordnung?“ | prüft Tarif, ERP, GoCardless, Verifizierung und Zahlungsbedingung |
| „Schick Acme GmbH eine Mandatsanfrage“ | sucht den Kontakt und schickt die Anfrage (nach Ihrem Ja) |
| „Schick allen ohne Mandat eine Anfrage“ | Massenversand, höchstens 50 pro Durchlauf |
| „Welche Anfragen sind noch offen? Erinnere sie.“ | listet offene Anfragen, erinnert höchstens alle 72 h |
| „Warum wurde RE-2024-123 nicht eingezogen?“ | Diagnose mit dem nächsten Schritt |
| „Zieh RE-2024-123 jetzt ein“ | manueller Einzug (nach Ihrem Ja) |
| „Zeig fehlgeschlagene Zahlungen und Rücklastschriften“ | Liste, auf Wunsch erneut einziehen oder stornieren |
| „Welche Auszahlungen kommen? Buch Auszahlung X ins ERP.“ | Auszahlungen und Buchung ins ERP |
| „Wochenübersicht“ | Zusammenfassung der letzten 7 Tage |
| „Stopp die Mahnung für Acme, hat überwiesen“ | Mahnlauf mit Grund beenden, oder einen neuen starten |

**Sicherheit:** Alles, was E-Mails verschickt, Geld bewegt oder ins ERP schreibt, zeigt der
Assistent zuerst als Vorschau und führt es erst nach Ihrem ausdrücklichen Ja aus. Der API-Schlüssel
läuft nach höchstens 12 Monaten ab, kann jederzeit widerrufen werden und es gibt eine reine
Lese-Variante.

## Einrichtung

1. In SepaHeld unter **Einstellungen > API & Entwickler** einen API-Schlüssel erstellen
   („Nur lesen“, wenn der Assistent nur nachsehen soll) und kopieren. In der Karte
   **KI-Integration** auf derselben Seite steht Ihre Kundennummer.
2. Plugin installieren:

   **Claude Code**

   ```text
   /plugin marketplace add dickdoof/sepaheld-skills
   /plugin install sepaheld@sepaheld
   ```

   **Codex:** Das Repository enthält ein Codex-Plugin (`.codex-plugin/plugin.json`) und einen
   Marketplace (`.agents/plugins/marketplace.json`). Fügen Sie das Repository in Codex als
   Plugin-Marketplace hinzu und installieren Sie das Plugin `sepaheld`. Alternativ kopieren Sie
   den Ordner `skills/sepaheld` in Ihr Codex-Skills-Verzeichnis.
3. Fragen Sie z. B. „Ist meine SepaHeld-Einrichtung in Ordnung?“. Beim ersten Mal fragt der
   Assistent nach API-Schlüssel und Kundennummer und speichert sie in
   `~/.config/sepaheld/config.json` (nur für Sie lesbar, Rechte 600).

Statt der Datei gehen auch Umgebungsvariablen: `SEPAHELD_API_KEY`, `SEPAHELD_CUSTOMER_ID`.

Benötigt wird nur Python 3.9 oder neuer, keine weiteren Pakete.

## Grenzen

Pro Kunde gelten Limits (z. B. 30 Anfragen pro Minute und 1.000 pro Tag; Einzüge höchstens einer
alle 10 Sekunden und 30 pro Tag). Bei Erreichen wartet das Skript kurz und versucht es erneut,
sonst sagt der Assistent, wann es wieder geht.

## Support und Sicherheit

- Fragen: support@sepaheld.com
- Sicherheitslücken und verlorene Schlüssel: siehe [SECURITY.md](SECURITY.md)

---

## English

SEPA direct debit from your AI assistant: request mandates, collect invoices, find out why an
invoice was not collected, handle failed payments, payouts and dunning – in Claude Code or Codex.

**Requires** a SepaHeld account on the **Business** plan (includes the AI integration).

**Setup**

1. In SepaHeld go to **Einstellungen > API & Entwickler** (Settings > API & developers), create an
   API key (read-only if the assistant should only look things up) and copy it. The
   **KI-Integration** card on the same tab shows your customer ID.
2. Install the plugin. Claude Code:

   ```text
   /plugin marketplace add dickdoof/sepaheld-skills
   /plugin install sepaheld@sepaheld
   ```

   Codex: the repository ships a Codex plugin (`.codex-plugin/plugin.json`) and a marketplace
   (`.agents/plugins/marketplace.json`); add this repository as a plugin marketplace in Codex and
   install `sepaheld`, or copy `skills/sepaheld` into your Codex skills directory.
3. Ask e.g. "Is my SepaHeld setup OK?". The first time, the assistant asks for the API key and
   customer ID and stores them in `~/.config/sepaheld/config.json` (mode 600), or set
   `SEPAHELD_API_KEY` / `SEPAHELD_CUSTOMER_ID`.

Anything that sends emails, moves money or writes to the ERP is shown as a preview first and only
runs after your explicit yes. Needs Python 3.9+ and nothing else.

## Development

```bash
python3 -m unittest discover -s tests -v
claude plugin validate .
```

## License and trademark

The code is licensed under the [Apache License 2.0](LICENSE). SepaHeld® is a registered trademark
of d-automation GmbH in the European Union; the license does not grant rights to the name or
logo – see [NOTICE](NOTICE). Modified versions must not be published under the SepaHeld name.
