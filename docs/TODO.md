# CGM Monitor — ToDo

Stand: 2026-06-16

## Reporting — Upload / Zustellung

### Beschlossenes Konzept: `upload_report` wird parametrierbar
Ein Service-Aufruf = ein verschlüsseltes ZIP. Policy (was/wann/wohin, Prüf-Gate)
lebt in den HA-Automatisierungen, nicht im Code.

Parameter:
- `subjects` — Liste; leer = alle
- `files` — `glucose`, `events`, `full` (glucose+events gemischt), `report` (HTML); mehrere möglich; Default `glucose`
- `folder` — Unterordner unter dem fixen Basis-Pfad; wird automatisch angelegt; leer = Basis-Pfad
- `date` — Default gestern

Zielordner: Basis (URL/User/Pass/Pfad) fix in der Config; Unterordner pro Aufruf
benannt und bei Bedarf erstellt (MKCOL je Ebene).

- [x] `upload_report` umgebaut: subjects/files/folder Parameter, ein ZIP pro Aufruf.
- [x] Log-Hinweis NUR wenn ein Subject GAR KEINE Glucose-Werte hat (wenige Werte = normal, kein Log).
- [ ] In HA-Automatisierungen die konkreten Aufrufe einrichten (Kunde: glucose; Intern: alles; usw.).
- [ ] Prüf-Gate / "Tag vollständig" designen (manuell vs. HA-Häkchen) — erstellen und upload sind getrennte Automatisierungen.

## Reporting — Format des "schönen" Reports

- [ ] Report bleibt evtl. nicht (nur) HTML. Projektleiter hätte gern etwas
      "Unveränderbares" wie **PDF**. Noch zu prüfen/entscheiden.
      → `files: report` würde dann ggf. PDF statt/zusätzlich zu HTML liefern.

## Reporting — send_report

- [ ] send_report vermutlich obsolet (durch Nextcloud-Upload ersetzt) —
      NICHT löschen, bis Auftraggeber-Lösung final ist.
- [ ] Auftraggeber will evtl. eigenen MS SharePoint statt Nextcloud → dafür
      noch KEINE Übertragungslösung (im blödesten Fall manuelles Rüberkopieren).
- [ ] `services.yaml`-Beschreibung von send_report sagt "PDF", erzeugt wird HTML.

## Events

- [ ] Event-Speicherung nacharbeiten und ergänzen.
- [ ] Danach: Events im Report nachträglich änderbar machen.
- [ ] Kunde bekommt vorerst NUR Glucose automatisiert/täglich; Events verzögert/separat.

## Ideen (offen, noch nicht vereinbart)

- [ ] Klinische Kennzahlen im HTML/PDF-Report (Time in Range, Mittelwert, GMI, CV) —
      AGP-Standard. Vorschlag von Claude, mit Betty noch nicht abgestimmt.
