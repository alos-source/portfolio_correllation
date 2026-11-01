# Portfolio Correlation Analysis

A desktop application (`tkinter` + `pandas` + `matplotlib`) for analyzing asset correlations and portfolio diversification using data exported from **[Portfolio Performance](https://www.portfolio-performance.info/)**.

## Key Features

- **Fast XML Price Caching**: Parses historical daily prices from Portfolio Performance XML exports (`pf_daten.xml`) and automatically caches them locally (`*.cache.pkl`), reducing reload times from ~17 seconds to under **0.1 seconds**.
- **CSV Universe & Metadata Integration**: Optionally loads a Portfolio Performance watchlist/securities CSV export to:
  - Filter the analysis down to your curated investment universe.
  - Filter candidates by **Sector** (`Sektor`).
  - Enrich results with technical metrics (`Δ ATH 1 Jahr %`, `Δ zu SMA20`, `Δ zu SMA200`).
- **Flexible Timeframes & Methods**:
  - Time horizons: `1M`, `3M`, `6M`, `YTD`, `1Y`, `2Y`, `3Y`, `5Y`, `10Y`, and `Gesamt` (All).
  - Correlation methods: **Daily Returns (`pct_change`)** or **Absolute Price Levels**.
  - Optional filter to include only assets with positive performance over the selected period.
- **Interactive Charts & Standalone HTML Report**:
  - Click any security in the Top or Flop lists to compare normalized price performance (`1.00` at start).
  - Export a standalone, interactive **HTML Dashboard Report** with KPI cards, color-coded correlation bars, live search, and an embedded HTML5 canvas comparison chart.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package and environment manager)

## Getting Started

```powershell
# Install and sync dependencies into .venv
uv sync

# Run the application
uv run python portfolioCorrellation.py
```

## Building the Standalone Executable (`PyInstaller`)

Run the included batch script:

```powershell
.\build.bat
```

Or invoke PyInstaller directly via `uv`:

```powershell
uv run pyinstaller --noconfirm PortfolioKorrelationsanalyse.spec
```

The standalone Windows executable will be generated at `dist/PortfolioKorrelationsanalyse.exe`.

## Documentation

- See [SPECIFICATIONS.md](SPECIFICATIONS.md) for detailed functional, mathematical, and technical specifications.
- See [DISCLAIMER.md](DISCLAIMER.md) for the legal disclaimer (German & English) regarding the software and generated reports.
