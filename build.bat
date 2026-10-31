@echo off

pyinstaller PortfolioKorrelationsanalyse.spec

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
echo Die ausführbare Datei befindet sich im Ordner "dist" und heißt "PortfolioKorrelationsanalyse.exe".
pause
