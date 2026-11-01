# Program Specifications – Portfolio Correlation Analysis

## 1. Purpose & Scope

**Portfolio Correlation Analysis** (`portfolioCorrellation.py`) is a desktop application for evaluating price and return correlations across securities managed in **Portfolio Performance**. Its primary goal is to identify diversification candidates (negative or neutral correlations) and cluster risks (high positive correlations) relative to a selected base security over configurable time horizons.

---

## 2. System Architecture & Technology Stack

| Component | Specification |
| :--- | :--- |
| **Runtime** | Python $\ge 3.11$ (managed via `uv`) |
| **Data Processing** | `pandas` ($\ge 2.2$), `numpy`, `python-dateutil` |
| **GUI Framework** | `tkinter` / `ttk` (Python Standard Library) |
| **Charting** | `matplotlib` (with automatic fallback to a native `tkinter.Canvas` chart window) |
| **HTML Reporting** | Standalone HTML5 + CSS3 + vanilla JavaScript (`<canvas>`), zero external dependencies |
| **Packaging** | `PyInstaller` single-file Windows executable (`PortfolioKorrelationsanalyse.exe`, `console=False`) |

---

## 3. Data Inputs & Persistence

### 3.1 Portfolio Performance XML (`pf_daten.xml`)
- **Source**: Uncompressed XML export from Portfolio Performance.
- **XPath Structure**:
  - `securities/security/name`: Human-readable security name.
  - `securities/security/tickerSymbol`: Primary identifier (Yahoo Finance / exchange symbol).
  - `securities/security/isin`: Secondary identifier (used as fallback identifier if `tickerSymbol` is empty, and for CSV matching).
  - `securities/security/prices/price[@t][@v]`: Daily price entries where `t` is the ISO date (`YYYY-MM-DD`) and `v` is the fixed-point integer price scaled by $10^8$.
- **Transformation**:
  - Raw price conversion:
    $$\text{Price} = \frac{\text{float}(v)}{100{,}000{,}000}$$
  - Duplicate date entries for the same security identifier are aggregated by arithmetic mean.
  - Resulting data structure: `df_kurse` (`pd.DataFrame`) with `DatetimeIndex` (`Datum`) and security identifiers (`Ticker`) as columns.

### 3.2 Local Binary Cache (`<xml_filename>.cache.pkl`)
- **Format**: Python `pickle` (`HIGHEST_PROTOCOL`) dictionary containing:
  - `version`: Cache schema version (`1`).
  - `df_kurse`: Pivoted price matrix (`Datum × Ticker`).
  - `name_to_ticker_map`: `dict[str, str]` mapping security names to column identifiers.
  - `isin_to_ticker_map`: `dict[str, str]` mapping ISIN codes to column identifiers.
- **Invalidation Policy**:
  - Automatically used if `mtime(cache) >= mtime(xml)` or if the user selects the `.cache.pkl` file directly.
  - Rebuilt automatically if the XML file is newer, or manually via the **"XML neu einlesen"** button.

### 3.3 Portfolio Performance CSV Export (`Wertpapiere_*.csv`)
- **Format**: Semicolon-separated (`;`) CSV export from Portfolio Performance's securities/watchlist view.
- **Supported Encodings**: Automatic detection across `utf-8-sig`, `utf-8`, `cp1252`, and `latin1`.
- **Column Resolution**: Header-based lookup by column name (independent of column order in Portfolio Performance):
  - **Identification Columns**: `Symbol`, `ISIN`, `Name`.
  - **Metadata Columns**:
    - `Sektor` (defaults to `"Unbekannt"` if empty/missing)
    - `Δ ATH 1 Jahr %` (defaults to `"n/a"`)
    - `Δ zu SMA20` (defaults to `"n/a"`)
    - `Δ zu SMA200` (defaults to `"n/a"`)
- **Entity Matching Priority**:
  1. Exact match on `Symbol` against price matrix columns.
  2. Exact match on `ISIN` via `isin_to_ticker_map`.
  3. Exact match on `Name` via `name_to_ticker_map`.
  4. Case-insensitive match on `Name`.

---

## 4. Analytical & Mathematical Specifications

### 4.1 Time Horizon Slicing (`get_start_date`)
The analysis window $[t_{\text{start}}, t_{\text{max}}]$ is anchored at the latest available date in the dataset ($t_{\text{max}} = \max(\text{Index})$):
- **`1M`, `3M`, `6M`**: $t_{\text{max}} - \{1, 3, 6\}\text{ months}$
- **`YTD`**: January 1 of the year of $t_{\text{max}}$
- **`1Y`, `2Y`, `3Y`, `5Y`, `10Y`**: $t_{\text{max}} - \{1, 2, 3, 5, 10\}\text{ years}$
- **`Gesamt`**: $\min(\text{Index})$ (entire available price history)

Rows where the selected base security has no valid price (`NaN`) are removed prior to correlation computation.

### 4.2 Correlation Calculation
Two selectable modes are supported:
1. **Daily Returns (`Tagesrenditen (pct_change)`) — Default**:
   $$r_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$$
   Computes the pairwise Pearson correlation coefficient $\rho_{B, i} \in [-1, +1]$ between the daily return series of the base security $B$ and each candidate security $i$ without forward-filling missing prices (`fill_method=None`).
2. **Absolute Price Levels (`Kursniveau (absolut)`)**:
   Computes the pairwise Pearson correlation coefficient directly on the raw price series $P_{B,t}$ and $P_{i,t}$.

- **Minimum Overlap Constraint (`min_periods`)**:
  $$\text{min\_tage} = \max\left(5, \min\left(20, \left\lfloor\frac{N_{\text{base}}}{2}\right\rfloor\right)\right)$$
  Candidates with fewer than $\text{min\_tage}$ overlapping observations with the base security are excluded.

### 4.3 Period Performance Calculation
For any security $i$ within the active analysis window:
$$\text{Perf}_i(\%) = \left(\frac{P_{i, t_{\text{last}}}}{P_{i, t_{\text{first}}}} - 1\right) \times 100$$
where $t_{\text{first}}$ and $t_{\text{last}}$ are the first and last non-null trading days of security $i$ within the sliced period (requires at least 2 observations).

### 4.4 Candidate Filtering Pipeline
Before ranking correlations, candidate securities pass through up to three optional filters in sequence:
1. **CSV Universe Filter** (*"Nur Werte aus CSV-Anlageuniversum"*): Retains only securities matched in the loaded CSV file.
2. **Sector Filter** (*"Sektor-Filter (CSV)"*): Retains only securities whose CSV `Sektor` equals the selected sector (when not set to `"Alle Sektoren"`).
3. **Positive Performance Filter** (*"Nur Werte mit positiver Performance"*): Retains only securities with $\text{Perf}_i(\%) \ge 0\%$.

### 4.5 Result Classification
- **Top $N$ Positive Correlations**: Highest $\rho_{B, i}$ sorted descending (low diversification / high co-movement).
- **Top $N$ Lowest / Negative Correlations**: Lowest $\rho_{B, i}$ sorted ascending (high diversification / hedging potential).
- **Neutral Correlations**: Securities with $-0.15 \le \rho_{B, i} \le +0.15$, sorted ascending by $|\rho_{B, i}|$ (closest to $0.0$), capped at $\max(2N, 20)$ entries.

### 4.6 Chart Normalization
When comparing the base security $B$ and a selected security $S$, only overlapping trading days where both have valid prices are used (`dropna()`), and both series are normalized to `1.00` at the first overlapping date $t_0$:
$$\hat{P}_{i,t} = \frac{P_{i,t}}{P_{i,t_0}}$$

---

## 5. User Interface & Reporting Specifications

### 5.1 Desktop GUI (`starte_gui`)
- **File Bar**: Selection and loading of XML/Cache and CSV files, status indicator, and cache rebuild trigger.
- **Analysis Controls**:
  - Type-ahead searchable `Combobox` for the base security (`Basiswert`).
  - Dropdowns for `Zeitraum`, `Korrelationsbasis`, and `Sektor-Filter`.
  - Numeric input for `Anzahl Top/Flop` ($N > 0$).
  - Checkboxes for positive performance and CSV-universe restriction.
- **Interactive Output**:
  - Side-by-side `Listbox` widgets for Top and Flop correlations; selecting any entry opens a normalized price comparison chart.
  - Detailed text log showing exact correlation values, period performance, and CSV metadata.

### 5.2 Standalone HTML Report (`generiere_html_report`)
- **Single-File Architecture**: Self-contained UTF-8 `.html` document with embedded CSS and JSON time-series data.
- **KPI Summary Cards**: Base security performance, sector, `Δ ATH 1J / Δ SMA200`, and number of trading days.
- **Interactive HTML5 Canvas Chart**: Clicking any row in the Top, Flop, or Neutral tables dynamically plots the normalized price comparison against the base security.
- **Live Client-Side Filter**: Instant text search filtering table rows by security name, ticker, or sector.
- **Print Stylesheet**: `@media print` rules for clean PDF/paper printing.

