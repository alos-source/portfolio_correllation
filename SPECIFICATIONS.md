# Program Specifications

This document is divided into two parts:
- **Part I: Generic Application & Infrastructure Specifications** — Reusable architectural patterns, UI standards, reporting capabilities, and build pipelines applicable to any Python desktop/data analysis tool.
- **Part II: Use-Case Specific Specifications** — Domain-specific data formats, financial mathematics, and correlation workflows for **Portfolio Correlation Analysis**.

---

# Part I: Generic Application & Infrastructure Specifications (Reusable Blueprint)

## 1. Technology Stack & Environment Management

| Component | Standard Specification |
| :--- | :--- |
| **Runtime & Package Manager** | Python $\ge 3.11$ managed via **`uv`** (`pyproject.toml` + locked `uv.lock` in `.venv`) |
| **Dependency Separation** | Strict separation between runtime `[project] dependencies` and build-only `[dependency-groups] dev` |
| **GUI Framework** | `tkinter` / `ttk` (Python Standard Library) |
| **Charting** | `matplotlib` with an automatic fallback to a native `tkinter.Canvas` window if `matplotlib` is unavailable |
| **Standalone HTML Reports** | Self-contained HTML5 + CSS3 + vanilla JavaScript (`<canvas>`), zero external runtime dependencies |
| **Release Packaging** | `PyInstaller` single-file Windows executable (`console=False`) + automated PDF user manual (`fpdf2` + `markdown`) |

---

## 2. Generic Persistence & Caching Patterns

### 2.1 Binary Data Cache (`<source_file>.cache.pkl`)
For large input files (e.g., multi-megabyte XML/CSV/JSON datasets), the application caches parsed data structures locally:
- **Format**: Python `pickle` (`HIGHEST_PROTOCOL`) dictionary containing a `version` integer (`CACHE_VERSION`) and the parsed payload.
- **Automatic Invalidation**:
  - The cache is loaded automatically if `mtime(cache) >= mtime(source_file)` and `cache["version"] == CACHE_VERSION` (or if the `.cache.pkl` file is selected directly).
  - If the source file has a newer modification timestamp or the cache is corrupted, the application transparently reparses the source file and overwrites the cache.
- **Manual Override**: The GUI provides an explicit button to force a fresh reload from the raw source file.

### 2.2 User Settings Persistence (`settings.json`)
- **Format**: Human-readable UTF-8 JSON file stored in the working directory (excluded from Git via `.gitignore`).
- **Scope**: Persists all user-configurable input paths, dropdown selections, numeric parameters, filter checkboxes, and the window geometry (`widthxheight+x+y`).
- **Lifecycle**:
  1. **Startup**: Loaded before constructing GUI widgets to pre-populate all fields; dropdown selections dependent on dynamic data are re-applied once data loading finishes.
  2. **Runtime & Shutdown**: Saved automatically upon loading data, executing an analysis, or closing the main window (`WM_DELETE_WINDOW` protocol handler).

---

## 3. Desktop GUI Standards

- **Window Title & Branding**: Displays the application name, semantic version, and auto-incremented build number:
  `<App Name> – v<VERSION> (Build #<BUILD_NUMBER>)`.
- **Responsive Layout**:
  - Resizable main window with defined initial and minimum dimensions (`minsize`).
  - Side-by-side comparison lists or tables must reside in a dedicated container frame using `uniform` column weights (`weight=1, uniform="..."`) to guarantee an exact 50% / 50% width split across all window sizes.
  - All list and text output widgets include both vertical and horizontal `ttk.Scrollbar` controls.
- **Type-Ahead Searchable Comboboxes**:
  - Filtering on `<KeyRelease>` always matches against an immutable reference list of all available items (`state["alle_namen_referenz"]`) so deleting characters restores previously filtered entries.
  - Navigation keys (`Up`, `Down`, `Left`, `Right`, `Tab`, `Shift`, `Ctrl`) do not reset the active filter; pressing `Return` selects the first match.
- **Resilient Error Handling**:
  - Data loaders and parsers must never call `sys.exit()` during GUI operation; all I/O and parsing errors raise standard Python exceptions caught by the GUI and presented via `messagebox.showerror` / `messagebox.showwarning`.
- **Application Footer**:
  - Left side: Full build label (`v<VERSION> | Build #<N> (<YYYY-MM-DD HH:MM>, <GIT_COMMIT>)`) and a concise legal notice.
  - Right side: Clickable link (`cursor="hand2"`) opening the project's GitHub repository in the default web browser.

---

## 4. Interactive Standalone HTML Reporting

Exported reports are generated as a single, self-contained `.html` file that can be shared or archived without external assets or internet access:
- **Dashboard Layout**: Dark-mode financial dashboard aesthetic with responsive CSS Grid KPI cards and print-friendly `@media print` overrides.
- **Interactive HTML5 Canvas Chart**:
  - Time-series data is embedded as compact JSON inside the HTML file.
  - Clicking any row in any result table highlights the row and dynamically redraws the `<canvas>` comparison chart (automatically scaled for `window.devicePixelRatio`).
- **Client-Side Column Sorting (`sortTable`)**:
  - Every table header (`<th>`) is clickable and toggles between ascending (`▲`) and descending (`▼`) order.
  - Numeric columns parse localized number/percentage strings via `data-sort` attributes and always place empty/missing values (`—` / `n/a`) at the bottom of the table.
- **Per-Column & Global Filtering (`applyAllFilters`)**:
  - **Global Search**: Instant text filter across all tables.
  - **Column Filter Row**: Dedicated filter inputs per column—text inputs for string columns, `<select>` dropdowns for categorical columns, and numeric expression inputs supporting comparison operators (`>`, `>=`, `<`, `<=`, `=`, e.g., `>0` or `<-15`) for numeric columns.
  - **Reset Button**: One-click button to clear all active column and global filters.
- **Embedded Disclaimer & Attribution Footer**:
  - Every exported HTML file includes a permanent legal disclaimer box, the exact `BUILD_LABEL` of the generating software, and a link to the GitHub repository.

---

## 5. Build Pipeline, Versioning & Documentation (`build.bat` / `build_docs.py`)

1. **Documentation Split**:
   - `README.md`: Developer- and GitHub-focused documentation (architecture, `uv` setup, build commands).
   - `USER_GUIDE.md`: End-user manual written in the application's UI language, free of developer/build internals.
   - `SPECIFICATIONS.md`: Technical and domain specifications.
   - `DISCLAIMER.md`: Bilingual legal disclaimer covering both software and generated reports/data.
2. **Automated Build Metadata (`build_docs.py` $\rightarrow$ `build_info.py`)**:
   - Executed **before** PyInstaller during `build.bat`.
   - Reads `version` from `pyproject.toml`, increments `BUILD_NUMBER` by `+1`, captures the current timestamp (`BUILD_DATE`) and short Git commit hash (`GIT_COMMIT`), and writes `build_info.py`.
3. **Automated User Manual PDF (`dist/README.pdf`)**:
   - `build_docs.py` compiles `USER_GUIDE.md` (prefixed with `BUILD_LABEL`) and `DISCLAIMER.md` into `dist/README.pdf` using Unicode TrueType system fonts (`Segoe UI` and `Consolas`).
4. **Executable Packaging & Self-Test**:
   - `uv run pyinstaller --noconfirm <App>.spec` bundles the application.
   - The main script supports a headless `--self-test` CLI flag to verify that all compiled C-extensions (`numpy`, `pandas`) load and execute cleanly inside the packaged `.exe`.

---
---

# Part II: Use-Case Specific Specifications (Portfolio Correlation Analysis)

## 6. Domain Purpose & Scope

**Portfolio Correlation Analysis** (`portfolioCorrellation.py`) evaluates historical price and return correlations across securities exported from **Portfolio Performance**. It helps identify diversification candidates (negative or neutral correlations) and cluster risks (high positive correlations) relative to a chosen base security (`Basiswert`).

---

## 7. Domain Data Sources & Entity Matching

### 7.1 Portfolio Performance XML (`pf_daten.xml`)
- **XPath Structure**:
  - `securities/security/name`: Security display name.
  - `securities/security/tickerSymbol`: Primary identifier (Yahoo Finance / exchange ticker).
  - `securities/security/isin`: Secondary identifier (used as fallback identifier if `tickerSymbol` is empty, and for CSV matching).
  - `securities/security/prices/price[@t][@v]`: Daily quotes where `t` is the ISO date (`YYYY-MM-DD`) and `v` is the fixed-point integer price scaled by $10^8$:
    $$\text{Price} = \frac{\text{float}(v)}{100{,}000{,}000}$$
- **Aggregation**: Duplicate date entries for the same security identifier are averaged; the resulting price matrix `df_kurse` has `DatetimeIndex` (`Datum`) as rows and security identifiers (`Ticker`) as columns.

### 7.2 Portfolio Performance Watchlist / Universe CSV (`Wertpapiere_*.csv`)
- **Format**: Semicolon-separated (`;`) CSV export from Portfolio Performance (`utf-8-sig`, `utf-8`, `cp1252`, or `latin1`).
- **Header-Based Column Resolution** (independent of column order in Portfolio Performance):
  - **Identifiers**: `Symbol`, `ISIN`, `Name`.
  - **Extracted Metadata**:
    - `Sektor` (fallback: `"Unbekannt"`)
    - `Δ ATH 1 Jahr %` (fallback: `"n/a"`)
    - `Δ zu SMA20` (fallback: `"n/a"`)
    - `Δ zu SMA200` (fallback: `"n/a"`)
- **Entity Matching Priority**:
  1. Exact match on `Symbol` against `df_kurse` columns.
  2. Exact match on `ISIN` via `isin_to_ticker_map`.
  3. Exact match on `Name` via `name_to_ticker_map`.
  4. Case-insensitive match on `Name`.

---

## 8. Financial & Mathematical Specifications

### 8.1 Time Horizon Slicing (`get_start_date`)
Anchored at the latest available date in the dataset ($t_{\text{max}} = \max(\text{Index})$):
- **Short/Medium Term**: `1M` ($-1\text{ month}$), `3M` ($-3\text{ months}$), `6M` ($-6\text{ months}$), `YTD` ($\text{Jan 1 of } \text{year}(t_{\text{max}})$).
- **Long Term**: `1Y`, `2Y`, `3Y`, `5Y`, `10Y` ($-\{1, 2, 3, 5, 10\}\text{ years}$), `Gesamt` ($\min(\text{Index})$).

Rows where the selected base security has no valid price (`NaN`) are dropped prior to correlation analysis.

### 8.2 Correlation Calculation Modes
1. **Daily Returns (`Tagesrenditen (pct_change)`) — Default**:
   $$r_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$$
   Computes pairwise Pearson correlation $\rho_{B, i} \in [-1, +1]$ on daily returns without forward-filling missing prices (`fill_method=None`).
2. **Absolute Price Levels (`Kursniveau (absolut)`)**:
   Computes pairwise Pearson correlation directly on raw price series $P_{B,t}$ and $P_{i,t}$.

- **Adaptive Minimum Overlap (`min_periods`)**:
  $$\text{min\_tage} = \max\left(5, \min\left(20, \left\lfloor\frac{N_{\text{base}}}{2}\right\rfloor\right)\right)$$

### 8.3 Period Performance Formula
For any security $i$ with at least 2 valid observations in the active window $[t_{\text{first}}, t_{\text{last}}]$:
$$\text{Perf}_i(\%) = \left(\frac{P_{i, t_{\text{last}}}}{P_{i, t_{\text{first}}}} - 1\right) \times 100$$

### 8.4 Three-Stage Candidate Filtering Pipeline
1. **CSV Universe Filter** (*"Nur Werte aus CSV-Anlageuniversum"*): Retains only securities present in the loaded CSV file.
2. **Sector Filter** (*"Sektor-Filter (CSV)"*): Retains only securities matching the selected `Sektor`.
3. **Positive Performance Filter** (*"Nur Werte mit positiver Performance"*): Retains only securities with $\text{Perf}_i(\%) \ge 0\%$.

### 8.5 Result Classification & Chart Normalization
- **Highest Correlation – Co-Movement (*Höchste Korrelation – Gleichlauf*)**: Top $N$ highest $\rho_{B, i}$ sorted descending.
- **Lowest / Negative Correlation – Diversification (*Niedrigste / Negative Korrelation – Diversifikation*)**: Top $N$ lowest $\rho_{B, i}$ sorted ascending.
- **Neutral Correlations (*Neutrale Korrelationen*)**: Securities with $-0.15 \le \rho_{B, i} \le +0.15$, sorted ascending by $|\rho_{B, i}|$ (closest to $0.0$), capped at $\max(2N, 20)$ entries.
- **Chart Normalization**: Overlapping price series of base security $B$ and comparison security $S$ are normalized to `1.00` at their first common trading day $t_0$:
  $$\hat{P}_{i,t} = \frac{P_{i,t}}{P_{i,t_0}}$$
