# Portfolio Correlation Analysis

Desktop application (`tkinter` + `pandas` + `matplotlib`) for analyzing asset correlations and portfolio diversification using historical price data and watchlist metadata exported from **[Portfolio Performance](https://www.portfolio-performance.info/)**.

---

## Repository Overview

| File | Description |
| :--- | :--- |
| `portfolioCorrellation.py` | Main application: XML/Cache ingestion, CSV metadata matching, correlation engine, Tkinter GUI, and standalone HTML report generator. |
| `build_docs.py` | Build helper script that compiles `USER_GUIDE.md` and `DISCLAIMER.md` into `dist/README.pdf`. |
| `pyproject.toml` / `uv.lock` | Project metadata, runtime dependencies (`pandas`, `matplotlib`, `python-dateutil`), and `dev` tooling (`pyinstaller`, `fpdf2`, `markdown`) managed via `uv`. |
| `PortfolioKorrelationsanalyse.spec` | PyInstaller specification for building the standalone Windows executable (`dist/PortfolioKorrelationsanalyse.exe`). |
| `build.bat` | Automated build script (`uv sync` $\rightarrow$ `pyinstaller` $\rightarrow$ `README.pdf` generation $\rightarrow$ cleanup). |
| `SPECIFICATIONS.md` | Technical, architectural, and mathematical specifications. |
| `USER_GUIDE.md` | End-user manual (compiled automatically into `dist/README.pdf` during the build). |
| `DISCLAIMER.md` | Legal disclaimer (German & English) for both code and generated data/reports. |

---

## Developer Setup (`uv`)

### Prerequisites
- Python $\ge 3.11$
- [uv](https://docs.astral.sh/uv/) package and environment manager

### Install Dependencies & Run from Source

```powershell
# Create .venv and install locked dependencies
uv sync

# Launch the GUI application
uv run python portfolioCorrellation.py

# Run quick CLI self-test
uv run python portfolioCorrellation.py --self-test
```

---

## Building the Release Package (`dist/`)

Run the batch script to build the standalone executable and generate the end-user PDF manual (`dist/README.pdf` from `USER_GUIDE.md` + `DISCLAIMER.md`):

```powershell
.\build.bat
```

Or run the individual build steps manually:

```powershell
# 1. Build standalone Windows executable
uv run pyinstaller --noconfirm PortfolioKorrelationsanalyse.spec

# 2. Generate end-user PDF documentation (dist/README.pdf)
uv run python build_docs.py
```

---

## Documentation & Legal

- **Technical Specifications**: [SPECIFICATIONS.md](SPECIFICATIONS.md)
- **End-User Guide (German)**: [USER_GUIDE.md](USER_GUIDE.md)
- **Disclaimer**: [DISCLAIMER.md](DISCLAIMER.md)
