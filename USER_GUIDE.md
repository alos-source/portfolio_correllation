# Benutzerhandbuch – Portfolio Korrelationsanalyse

Willkommen bei der **Portfolio Korrelationsanalyse**! Mit diesem Programm analysierst du das Zusammenspiel (Gleichlauf vs. Diversifikation) der Wertpapiere aus deinem **Portfolio Performance**-Bestand oder deiner Watchlist.

---

## 1. Vorbereitung in Portfolio Performance

Das Programm nutzt bis zu zwei Exporte aus **[Portfolio Performance](https://www.portfolio-performance.info/)**:

1. **Portfolio-XML-Datei (Pflicht für historische Kurse)**
   - Speichere deine Datei in Portfolio Performance über `Datei -> Speichern unter...` im Format **„XML mit ungepackten Daten (*.xml)“** (Standardname z. B. `pf_daten.xml`).
   - *Hinweis:* Diese Datei enthält die täglichen historischen Schlusskurse aller Wertpapiere.

2. **Watchlist / Anlageuniversum als CSV-Datei (Optional, empfohlen)**
   - Wechsle in Portfolio Performance in die Ansicht `Alle Wertpapiere` (oder eine gewünschte Watchlist).
   - Klicke oben rechts auf das **Export-Symbol (CSV)** und speichere die Tabelle als `.csv`-Datei im selben Ordner.
   - Die Reihenfolge der Spalten in Portfolio Performance spielt keine Rolle. Wenn die Spalten `Sektor`, `Δ ATH 1 Jahr %`, `Δ zu SMA20` und `Δ zu SMA200` eingeblendet sind, werden diese Kennzahlen automatisch im Programm und im HTML-Report angezeigt.

---

## 2. Programmstart & Daten laden

1. Starte die Datei **`PortfolioKorrelationsanalyse.exe`**.
2. **Portfolio-XML / Cache wählen**:
   - Wähle deine `.xml`-Datei über **„Datei wählen...“** aus (liegt eine `pf_daten.xml` im selben Ordner, ist sie bereits vorausgewählt).
3. **CSV Anlageuniversum wählen (optional)**:
   - Falls sich eine `.csv`-Datei im Programmordner befindet, wird sie automatisch erkannt; andernfalls kannst du sie über **„CSV wählen...“** auswählen.
4. Klicke auf **„Daten laden“**:
   - **Beim ersten Laden** einer XML-Datei liest das Programm alle historischen Kurse ein (Dauer ca. 10–20 Sekunden) und legt automatisch eine schnelle Cache-Datei (`*.xml.cache.pkl`) an.
   - **Bei jedem weiteren Start** werden die Daten direkt aus diesem Cache in **unter 0,1 Sekunden** geladen.
   - *Tipp:* Wenn du deine XML-Datei später aus Portfolio Performance neu exportiert hast, erkennt das Programm das neuere Dateidatum automatisch. Über den Button **„XML neu einlesen“** kannst du das Neuladen jederzeit auch manuell erzwingen.

---

## 3. Einstellungen der Korrelationsanalyse

- **Basiswert**:
  - Tippe den Namen des gewünschten Wertpapiers ein (die Auswahlliste filtert sich automatisch während der Eingabe) oder wähle es über das Dropdown-Menü aus.
- **Zeitraum**:
  - Wähle den gewünschten Analysehorizont: `1M` (1 Monat), `3M`, `6M`, `YTD` (seit Jahresbeginn), `1Y`, `2Y`, `3Y`, `5Y`, `10Y` oder `Gesamt`.
- **Korrelationsbasis**:
  - **`Tagesrenditen (pct_change)` (Empfohlen)**: Berechnet die Korrelation auf Basis der täglichen prozentualen Kursveränderungen (Finanzmarkt-Standard).
  - **`Kursniveau (absolut)`**: Vergleicht die absoluten Kursverläufe.
- **Anzahl je Liste**:
  - Bestimmt, wie viele Wertpapiere jeweils in den Listen für Gleichlauf und Diversifikation angezeigt werden (Standard: `10`).
- **Filter-Optionen**:
  - **Sektor-Filter (CSV)**: Grenzt die Vergleichswerte gezielt auf einen bestimmten Sektor (z. B. *Gesundheitswesen*, *IT*, *Industrie*) ein.
  - **Nur Werte mit positiver Performance**: Berücksichtigt nur Vergleichswerte, die im gewählten Zeitraum eine Rendite von $\ge 0\,\%$ erzielt haben.
  - **Nur Werte aus CSV-Anlageuniversum**: Ignoriert alte/inaktive XML-Werte und vergleicht nur mit Wertpapieren, die in deiner CSV-Datei enthalten sind.

Klicke anschließend auf **„Analyse starten“**.

---

## 4. Ergebnisse interpretieren & Charts anzeigen

Die Ergebnisse teilen sich in drei Bereiche auf:

1. **Höchste Korrelation – Gleichlauf (Linke Liste, Werte nahe `+1.00`)**:
   - Diese Wertpapiere entwickeln sich sehr ähnlich wie dein Basiswert. Sie bieten **wenig Diversifikation** (potenzielles Klumpenrisiko).
2. **Niedrigste / Negative Korrelation – Diversifikation (Rechte Liste, Werte nahe `0.00` oder negativ)**:
   - Diese Wertpapiere entwickeln sich unabhängig oder gegenläufig zum Basiswert und eignen sich besonders zur **Risikostreuung im Portfolio**.
3. **Neutrale Korrelationen (`-0.15` bis `+0.15` im unteren Textfeld)**:
   - Wertpapiere ohne nennenswerten statistischen Gleichlauf im gewählten Zeitraum.

- **Kursvergleich-Chart öffnen**:
  - Ein Klick auf einen beliebigen Eintrag in der linken oder rechten Liste öffnet sofort ein Chart-Fenster, das die Wertentwicklung von Basiswert und ausgewähltem Wertpapier (normiert auf `1.00` am Starttag) direkt gegenüberstellt.

---

## 5. Interaktiven HTML-Report exportieren

Über den Button **„HTML-Report exportieren“** speicherst du die aktuelle Auswertung als eigenständige `.html`-Datei, die sich direkt im Browser öffnet und problemlos teilen oder archivieren lässt:

- **Interaktiver Chart**: Klicke im HTML-Report auf eine beliebige Tabellenzeile, um den normierten Kursvergleich oben im Report-Chart anzuzeigen.
- **Spalten sortieren**: Klicke auf eine beliebige Spaltenüberschrift (`#`, `Wertpapier`, `Sektor`, `Korrelation`, `Perf`, `Δ ATH 1J`, `Δ SMA20`, `Δ SMA200`), um die Tabelle auf- oder absteigend (`▲` / `▼`) zu sortieren.
- **Spalten filtern**:
  - Nutze die Filterzeile unter den Spaltenköpfen für Textsuche, Sektor-Auswahl oder **Zahlen-Filter mit Vergleichsoperatoren**:
  - Beispiele: `>0` in *Δ SMA200* (nur Werte über ihrem 200-Tage-Durchschnitt), `>-10` in *Δ ATH 1J* (max. 10 % unter Jahreshoch) oder `<-0.2` in *Korrelation*.
  - Über **„Filter zurücksetzen“** oben rechts werden alle aktiven Filter wieder geleert.

---

## 6. Projektseite & Quellcode

Weiterführende Informationen und Updates findest du auf GitHub:
https://github.com/alos-source/portfolio_correllation

