@echo off

echo --- SYNCHRONISIERE UMGEBUNG MIT UV ---
uv sync

echo.
echo --- ERSTELLE EXE MIT PYINSTALLER (VIA UV) ---
uv run pyinstaller --noconfirm PortfolioKorrelationsanalyse.spec

echo.
echo --- ERSTELLE README.PDF IM DIST-ORDNER ---
uv run python build_docs.py

echo.
echo --- AUFRÄUMEN ---

REM Löscht den temporären Build-Ordner
if exist build rmdir /s /q build
echo Temporärer 'build' Ordner gelöscht.

REM Kopiert die XML- und Cache-Datei in den 'dist'-Ordner (optional, aber nützlich für Tests)
if exist pf_daten.xml copy pf_daten.xml dist\
if exist pf_daten.xml.cache.pkl copy pf_daten.xml.cache.pkl dist\
echo XML- und Cache-Datei in den 'dist' Ordner kopiert.

echo.
echo --- FERTIG ---
echo Die ausführbare Datei und README.pdf befinden sich im Ordner "dist".
pause
