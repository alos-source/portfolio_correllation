import os
import re
import json
import html
import webbrowser
import pickle
import glob
import xml.etree.ElementTree as ET
import pandas as pd
import sys
from dateutil.relativedelta import relativedelta
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# --- KONFIGURATION ---
XML_DATEI_PFAD = 'pf_daten.xml'  # Standard-Pfad zu Ihrer Portfolio Performance XML-Datei
CACHE_VERSION = 1
# ---------------------


def finde_standard_csv():
    """Sucht automatisch nach einer passenden CSV-Datei im aktuellen Ordner oder in dist/."""
    suchmuster = [
        "Wertpapiere_*.csv",
        "*.csv",
        os.path.join("dist", "Wertpapiere_*.csv"),
        os.path.join("dist", "*.csv"),
    ]
    for muster in suchmuster:
        treffer = sorted(glob.glob(muster))
        if treffer:
            return treffer[-1]
    return ""


# ----------------------------------------------------
# 1. FUNKTIONEN ZUM LADEN UND CACHEN DER DATEN
# ----------------------------------------------------

def get_cache_pfad(file_path):
    """Gibt den Pfad zur Cache-Datei für eine XML-Datei zurück."""
    if file_path.endswith(".cache.pkl"):
        return file_path
    return f"{file_path}.cache.pkl"


def lade_und_bereinige_daten(file_path, erzwinge_neuladen=False):
    """
    Lädt PP-XML-Daten (oder direkt aus dem lokalen Cache), bereinigt sie und gibt zurück:
    (df_kurse, name_to_ticker_map, isin_to_ticker_map, aus_cache_geladen)
    """
    if not file_path:
        raise FileNotFoundError("Kein Dateipfad angegeben.")

    cache_pfad = get_cache_pfad(file_path)

    # 1. Prüfen, ob ein gültiger und aktueller Cache existiert
    if not erzwinge_neuladen and os.path.exists(cache_pfad):
        nutze_cache = False
        if file_path.endswith(".cache.pkl"):
            nutze_cache = True
        elif os.path.exists(file_path):
            if os.path.getmtime(cache_pfad) >= os.path.getmtime(file_path):
                nutze_cache = True
        else:
            # Falls nur noch die Cache-Datei vorhanden ist, trotzdem nutzbar
            nutze_cache = True

        if nutze_cache:
            try:
                with open(cache_pfad, "rb") as f:
                    cache_data = pickle.load(f)
                if isinstance(cache_data, dict) and cache_data.get("version") == CACHE_VERSION:
                    return (
                        cache_data["df_kurse"],
                        cache_data["name_to_ticker_map"],
                        cache_data.get("isin_to_ticker_map", {}),
                        True,
                    )
            except Exception:
                # Falls Cache beschädigt ist, normal aus XML neu laden
                pass

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Die Datei '{file_path}' wurde nicht gefunden. Bitte prüfen Sie den Pfad.")

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Konnte die XML-Datei nicht parsen. Ist die Datei beschädigt?\nDetails: {e}") from e

    name_to_ticker_map = {}
    isin_to_ticker_map = {}
    ticker_series_list = {}

    for security_element in root.findall('securities/security'):
        name_element = security_element.find('name')
        security_name = name_element.text.strip() if (name_element is not None and name_element.text) else 'Unbekannter Wert'

        ticker_element = security_element.find('tickerSymbol')
        ticker_symbol = ticker_element.text.strip() if (ticker_element is not None and ticker_element.text) else None

        isin_element = security_element.find('isin')
        isin_code = isin_element.text.strip() if (isin_element is not None and isin_element.text) else None

        # Verwende TickerSymbol oder alternativ ISIN als eindeutige Kennung
        effektiver_ticker = ticker_symbol if ticker_symbol else isin_code
        if not effektiver_ticker:
            continue

        if security_name and security_name not in name_to_ticker_map:
            name_to_ticker_map[security_name] = effektiver_ticker

        if isin_code and isin_code not in isin_to_ticker_map:
            isin_to_ticker_map[isin_code] = effektiver_ticker

        prices_element = security_element.find('prices')
        if prices_element is not None:
            dates = []
            values = []
            for price_element in prices_element.findall('price'):
                date_str = price_element.get('t')
                value_raw = price_element.get('v')
                if date_str and value_raw is not None:
                    try:
                        values.append(float(value_raw) / 100000000.0)
                        dates.append(date_str)
                    except (TypeError, ValueError):
                        continue

            if dates:
                s = pd.Series(values, index=dates, dtype="float64")
                s = s.groupby(level=0).mean()
                if effektiver_ticker in ticker_series_list:
                    combined = pd.concat([ticker_series_list[effektiver_ticker], s])
                    ticker_series_list[effektiver_ticker] = combined.groupby(level=0).mean()
                else:
                    ticker_series_list[effektiver_ticker] = s

    if not ticker_series_list:
        return pd.DataFrame(), {}, {}, False

    df_kurse = pd.DataFrame(ticker_series_list)
    df_kurse.index = pd.to_datetime(df_kurse.index)
    df_kurse = df_kurse.sort_index()

    if 'N/A' in df_kurse.columns:
        df_kurse = df_kurse.drop(columns=['N/A'])

    # Cache speichern für schnelles Laden beim nächsten Start
    try:
        with open(cache_pfad, "wb") as f:
            pickle.dump(
                {
                    "version": CACHE_VERSION,
                    "df_kurse": df_kurse,
                    "name_to_ticker_map": name_to_ticker_map,
                    "isin_to_ticker_map": isin_to_ticker_map,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
    except Exception:
        pass

    return df_kurse, name_to_ticker_map, isin_to_ticker_map, False


def lade_csv_metadaten(csv_path, name_to_ticker_map, isin_to_ticker_map, vorhandene_ticker):
    """
    Lädt die Portfolio Performance CSV-Datei (Anlageuniversum / Wertpapiere) und
    ordnet die Metadaten (Sektor, Δ ATH 1 Jahr %, Δ zu SMA20, Δ zu SMA200) den Tickern zu.
    """
    if not csv_path or not os.path.exists(csv_path):
        raise FileNotFoundError(f"Die CSV-Datei '{csv_path}' wurde nicht gefunden.")

    df_csv = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            df_csv = pd.read_csv(csv_path, sep=";", encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    if df_csv is None:
        raise ValueError("Die CSV-Datei konnte mit keiner unterstützten Textkodierung gelesen werden.")

    vorhandene_ticker_set = set(vorhandene_ticker)
    lower_name_map = {k.lower(): v for k, v in name_to_ticker_map.items()}

    def clean_str(val, default="n/a"):
        if pd.isna(val):
            return default
        s = str(val).strip()
        return s if s else default

    ticker_meta = {}
    for _, row in df_csv.iterrows():
        csv_name = clean_str(row.get("Name"), "")
        csv_symbol = clean_str(row.get("Symbol"), "")
        csv_isin = clean_str(row.get("ISIN"), "")

        matched_ticker = None
        if csv_symbol and csv_symbol in vorhandene_ticker_set:
            matched_ticker = csv_symbol
        elif csv_isin and csv_isin in isin_to_ticker_map:
            matched_ticker = isin_to_ticker_map[csv_isin]
        elif csv_name and csv_name in name_to_ticker_map:
            matched_ticker = name_to_ticker_map[csv_name]
        elif csv_name and csv_name.lower() in lower_name_map:
            matched_ticker = lower_name_map[csv_name.lower()]
        elif csv_symbol:
            matched_ticker = csv_symbol

        if not matched_ticker:
            continue

        sektor = clean_str(row.get("Sektor"), "Unbekannt")
        ath_1y = clean_str(row.get("Δ ATH 1 Jahr %"), "n/a")
        sma20 = clean_str(row.get("Δ zu SMA20"), "n/a")
        sma200 = clean_str(row.get("Δ zu SMA200"), "n/a")

        ticker_meta[matched_ticker] = {
            "csv_name": csv_name,
            "isin": csv_isin,
            "sektor": sektor,
            "ath_1y": ath_1y,
            "sma20": sma20,
            "sma200": sma200,
        }

        # Falls der Name aus der CSV noch nicht im Mapping ist, aber der Ticker in den Kursdaten existiert
        if csv_name and matched_ticker in vorhandene_ticker_set and csv_name not in name_to_ticker_map:
            name_to_ticker_map[csv_name] = matched_ticker

    return ticker_meta


# ----------------------------------------------------
# 2. HILFSFUNKTIONEN
# ----------------------------------------------------

def get_start_date(zeitraum, df):
    """Berechnet das Startdatum basierend auf dem letzten Datum in den Daten."""
    heute = df.index.max()
    if zeitraum == '1M':
        return heute - relativedelta(months=1)
    elif zeitraum == '3M':
        return heute - relativedelta(months=3)
    elif zeitraum == '6M':
        return heute - relativedelta(months=6)
    elif zeitraum == 'YTD':
        return pd.Timestamp(year=heute.year, month=1, day=1)
    elif zeitraum == '1Y':
        return heute - relativedelta(years=1)
    elif zeitraum == '2Y':
        return heute - relativedelta(years=2)
    elif zeitraum == '3Y':
        return heute - relativedelta(years=3)
    elif zeitraum == '5Y':
        return heute - relativedelta(years=5)
    elif zeitraum == '10Y':
        return heute - relativedelta(years=10)
    return df.index.min()  # Gesamt


def type_ahead_search(event, combobox, alle_werte):
    """Filtert die Combobox-Liste nach aktueller Eingabe anhand der vollständigen Referenzliste."""
    if event.keysym in ("Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R", "Tab"):
        return
    eingabe = combobox.get().lower()
    if not eingabe:
        combobox['values'] = alle_werte
        return
    gefiltert = [v for v in alle_werte if eingabe in v.lower()]
    combobox['values'] = gefiltert if gefiltert else alle_werte
    if event.keysym == "Return" and gefiltert:
        combobox.set(gefiltert[0])


def format_meta_info(ticker, csv_metadata):
    """Formatiert die CSV-Metadaten (Sektor, Δ ATH 1Y, Δ SMA20, Δ SMA200) für die Textausgabe."""
    if not csv_metadata or ticker not in csv_metadata:
        return ""
    m = csv_metadata[ticker]
    return (
        f" | Sektor: {m['sektor']}"
        f" | Δ ATH 1J: {m['ath_1y']}"
        f" | Δ SMA20: {m['sma20']}"
        f" | Δ SMA200: {m['sma200']}"
    )


def gui_korrelation_analyse(
    df_kurse_alle,
    name_to_ticker_map,
    basis_name,
    zeitraum,
    anzahl,
    listbox_top,
    listbox_flop,
    ausgabe_widget,
    csv_metadata=None,
    methode="returns",
):
    """Führt die Korrelationsanalyse aus und zeigt die Ergebnisse inkl. CSV-Metadaten im GUI."""
    basis_ticker = name_to_ticker_map.get(basis_name)
    if not basis_ticker or basis_ticker not in df_kurse_alle.columns:
        ausgabe_widget.delete(1.0, tk.END)
        ausgabe_widget.insert(tk.END, f"FEHLER: Basiswert '{basis_name}' nicht in den Kursdaten gefunden.\n")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        return

    start_datum = get_start_date(zeitraum, df_kurse_alle)
    df_temp = df_kurse_alle[df_kurse_alle.index >= start_datum].copy()
    df_temp_basis = df_temp.dropna(subset=[basis_ticker])

    if df_temp_basis.empty:
        ausgabe_widget.delete(1.0, tk.END)
        ausgabe_widget.insert(tk.END, f"FEHLER: Keine Daten für Basiswert '{basis_name}' im Zeitraum {zeitraum} gefunden.\n")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        return

    if methode == "returns":
        df_corr_input = df_temp_basis.pct_change(fill_method=None)
        methode_label = "Tagesrenditen (pct_change)"
    else:
        df_corr_input = df_temp_basis
        methode_label = "Kursniveau (absolut)"

    min_tage = max(5, min(20, df_temp_basis.shape[0] // 2))
    korrelationen = df_corr_input.corr(min_periods=min_tage)[basis_ticker].sort_values(ascending=False)
    korrelationen = korrelationen.drop(basis_ticker, errors='ignore').dropna()

    if korrelationen.empty:
        ausgabe_widget.delete(1.0, tk.END)
        ausgabe_widget.insert(tk.END, f"Keine ausreichenden gemeinsamen Handelstage (mind. {min_tage}) mit anderen Werten gefunden.\n")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        return

    top_korrelation = korrelationen.head(anzahl)
    flop_korrelation = korrelationen.tail(anzahl).sort_values(ascending=True)
    ticker_to_name_map = {}
    for k, v in name_to_ticker_map.items():
        if v not in ticker_to_name_map:
            ticker_to_name_map[v] = k

    # Ausgabe formatieren
    basis_meta_str = format_meta_info(basis_ticker, csv_metadata)
    ausgabe_widget.delete(1.0, tk.END)
    ausgabe_widget.insert(tk.END, f"Korrelationsanalyse für Basiswert: {basis_name} ({basis_ticker}){basis_meta_str}\n")
    ausgabe_widget.insert(
        tk.END,
        f"Zeitraum: {zeitraum} ({df_temp_basis.index.min().date()} bis {df_temp_basis.index.max().date()}) | Methode: {methode_label}\n",
    )
    ausgabe_widget.insert(tk.END, f"Handelstage des Basiswerts in der Analyse: {df_temp_basis.shape[0]}\n\n")

    def berechne_performance(df, ticker):
        serie = df[ticker].dropna()
        if len(serie) < 2:
            return None
        return (serie.iloc[-1] / serie.iloc[0] - 1) * 100

    # Listen füllen
    listbox_top.delete(0, tk.END)
    ausgabe_widget.insert(tk.END, f"🚀 TOP {anzahl} HÖCHSTE KORRELATIONEN (Diversifikation niedrig):\n")
    for t, v in top_korrelation.items():
        name = ticker_to_name_map.get(t, t)
        perf = berechne_performance(df_temp_basis, t)
        perf_str = f"{perf:+.2f}%" if perf is not None else "n/a"
        meta_str = format_meta_info(t, csv_metadata)
        sektor_kurz = f" [{csv_metadata[t]['sektor']}]" if (csv_metadata and t in csv_metadata) else ""
        listbox_top.insert(tk.END, f"{name} ({t}) | Korr: {v:.2f}{sektor_kurz}")
        ausgabe_widget.insert(tk.END, f"• {name} ({t}): Korr={v:.4f}, Perf={perf_str}{meta_str}\n")

    listbox_flop.delete(0, tk.END)
    ausgabe_widget.insert(tk.END, f"\n🛡️ TOP {anzahl} NIEDRIGSTE / NEGATIVE KORRELATIONEN (Diversifikation hoch):\n")
    for t, v in flop_korrelation.items():
        name = ticker_to_name_map.get(t, t)
        perf = berechne_performance(df_temp_basis, t)
        perf_str = f"{perf:+.2f}%" if perf is not None else "n/a"
        meta_str = format_meta_info(t, csv_metadata)
        sektor_kurz = f" [{csv_metadata[t]['sektor']}]" if (csv_metadata and t in csv_metadata) else ""
        listbox_flop.insert(tk.END, f"{name} ({t}) | Korr: {v:.2f}{sektor_kurz}")
        ausgabe_widget.insert(tk.END, f"• {name} ({t}): Korr={v:.4f}, Perf={perf_str}{meta_str}\n")

    # Abschnitt für neutrale Korrelationen (sortiert nach Nähe zu 0.0)
    neutral_min = -0.15
    neutral_max = 0.15
    neutral_alle = korrelationen[(korrelationen >= neutral_min) & (korrelationen <= neutral_max)]
    neutral_korrelation = neutral_alle.reindex(neutral_alle.abs().sort_values().index).head(max(anzahl * 2, 20))
    ausgabe_widget.insert(tk.END, f"\n⚖️ NEUTRALE KORRELATIONEN (-0.15 bis +0.15, Top {len(neutral_korrelation)} nächste zu 0):\n")
    if neutral_korrelation.empty:
        ausgabe_widget.insert(tk.END, "Keine Werte mit neutraler Korrelation gefunden.\n")
    else:
        for t, v in neutral_korrelation.items():
            name = ticker_to_name_map.get(t, t)
            perf = berechne_performance(df_temp_basis, t)
            perf_str = f"{perf:+.2f}%" if perf is not None else "n/a"
            meta_str = format_meta_info(t, csv_metadata)
            ausgabe_widget.insert(tk.END, f"• {name} ({t}): Korr={v:.4f}, Perf={perf_str}{meta_str}\n")

    # Für Chart-Auswahl: Mapping von Listbox-Index zu Ticker
    listbox_top.ticker_map = [t for t in top_korrelation.index]
    listbox_flop.ticker_map = [t for t in flop_korrelation.index]
    listbox_top.basis_ticker = basis_ticker
    listbox_flop.basis_ticker = basis_ticker
    listbox_top.df_temp_basis = df_temp_basis
    listbox_flop.df_temp_basis = df_temp_basis
    listbox_top.csv_metadata = csv_metadata
    listbox_flop.csv_metadata = csv_metadata
    listbox_top.ticker_to_name = ticker_to_name_map
    listbox_flop.ticker_to_name = ticker_to_name_map

    # Datenstruktur für HTML-Export aufbereiten
    def baue_zeilen(serie):
        zeilen = []
        for t, v in serie.items():
            m = csv_metadata.get(t, {}) if csv_metadata else {}
            zeilen.append({
                "name": ticker_to_name_map.get(t, t),
                "ticker": t,
                "korr": float(v),
                "perf": berechne_performance(df_temp_basis, t),
                "sektor": m.get("sektor", "—"),
                "ath_1y": m.get("ath_1y", "—"),
                "sma20": m.get("sma20", "—"),
                "sma200": m.get("sma200", "—"),
            })
        return zeilen

    # Zeitreihen für interaktiven HTML-Chart vorbereiten
    relevante_ticker = list(
        dict.fromkeys(
            list(top_korrelation.index)
            + list(flop_korrelation.index)
            + list(neutral_korrelation.index[:30])
        )
    )
    chart_series = {}
    for t in relevante_ticker:
        if t == basis_ticker or t not in df_temp_basis.columns:
            continue
        paare = df_temp_basis[[basis_ticker, t]].dropna()
        if len(paare) < 2:
            continue
        chart_series[t] = {
            "name": ticker_to_name_map.get(t, t),
            "dates": [d.strftime("%Y-%m-%d") for d in paare.index],
            "basis_norm": [round(float(x), 4) for x in (paare[basis_ticker] / paare[basis_ticker].iloc[0])],
            "sel_norm": [round(float(x), 4) for x in (paare[t] / paare[t].iloc[0])],
        }

    basis_meta = csv_metadata.get(basis_ticker, {}) if csv_metadata else {}
    return {
        "basis_name": basis_name,
        "basis_ticker": basis_ticker,
        "basis_perf": berechne_performance(df_temp_basis, basis_ticker),
        "basis_sektor": basis_meta.get("sektor", "—"),
        "basis_ath_1y": basis_meta.get("ath_1y", "—"),
        "basis_sma20": basis_meta.get("sma20", "—"),
        "basis_sma200": basis_meta.get("sma200", "—"),
        "zeitraum": zeitraum,
        "start_datum": str(df_temp_basis.index.min().date()),
        "end_datum": str(df_temp_basis.index.max().date()),
        "handelstage": int(df_temp_basis.shape[0]),
        "methode_label": methode_label,
        "anzahl": anzahl,
        "top_rows": baue_zeilen(top_korrelation),
        "flop_rows": baue_zeilen(flop_korrelation),
        "neutral_rows": baue_zeilen(neutral_korrelation),
        "chart_series": chart_series,
    }


def generiere_html_report(report_daten, datei_pfad):
    """Erzeugt einen interaktiven, modernen Standalone-HTML-Report der Korrelationsanalyse."""
    esc = html.escape

    def fmt_perf_badge(perf):
        if perf is None:
            return '<span class="badge badge-neutral">n/a</span>'
        cls = "badge-pos" if perf >= 0 else "badge-neg"
        return f'<span class="badge {cls}">{perf:+.2f}%</span>'

    def fmt_delta_cell(val_str):
        s = str(val_str).strip()
        if not s or s in ("—", "n/a"):
            return '<span class="muted">—</span>'
        if s.startswith("-"):
            return f'<span class="text-neg">{esc(s)}</span>'
        return f'<span class="text-pos">{esc(s)}</span>'

    def fmt_korr_bar(korr):
        prozent = min(100.0, abs(korr) * 100.0)
        if korr >= 0.15:
            bar_cls = "bar-high"
            txt_cls = "korr-high"
        elif korr <= -0.15:
            bar_cls = "bar-neg"
            txt_cls = "korr-neg"
        else:
            bar_cls = "bar-neutral"
            txt_cls = "korr-neutral"
        return f"""
        <div class="korr-cell">
            <span class="korr-val {txt_cls}">{korr:+.4f}</span>
            <div class="korr-bar-track">
                <div class="korr-bar-fill {bar_cls}" style="width: {prozent:.1f}%"></div>
            </div>
        </div>
        """

    def baue_tabelle(zeilen, leer_hinweis):
        if not zeilen:
            return f'<p class="empty-msg">{esc(leer_hinweis)}</p>'
        trs = []
        for idx, r in enumerate(zeilen, start=1):
            t_attr = esc(r["ticker"])
            trs.append(f"""
            <tr class="clickable-row" onclick="selectSecurity('{t_attr}')" data-ticker="{t_attr}">
                <td class="rank-col">{idx}</td>
                <td>
                    <div class="sec-name">{esc(r['name'])}</div>
                    <div class="sec-ticker">{esc(r['ticker'])}</div>
                </td>
                <td><span class="sector-pill">{esc(r['sektor'])}</span></td>
                <td>{fmt_korr_bar(r['korr'])}</td>
                <td class="num-col">{fmt_perf_badge(r['perf'])}</td>
                <td class="num-col">{fmt_delta_cell(r['ath_1y'])}</td>
                <td class="num-col">{fmt_delta_cell(r['sma20'])}</td>
                <td class="num-col">{fmt_delta_cell(r['sma200'])}</td>
            </tr>
            """)
        return f"""
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Wertpapier</th>
                        <th>Sektor</th>
                        <th>Korrelation</th>
                        <th class="num-col">Perf ({esc(report_daten['zeitraum'])})</th>
                        <th class="num-col">Δ ATH 1J</th>
                        <th class="num-col">Δ SMA20</th>
                        <th class="num-col">Δ SMA200</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(trs)}
                </tbody>
            </table>
        </div>
        """

    erstellt_am = datetime.now().strftime("%d.%m.%Y %H:%M")
    basis_perf_html = fmt_perf_badge(report_daten.get("basis_perf"))
    filter_badges = "".join(
        f'<span class="filter-chip">{esc(f)}</span>' for f in report_daten.get("aktive_filter", [])
    )

    # Ersten Vergleichswert für den Initial-Chart bestimmen
    initial_ticker = ""
    if report_daten["flop_rows"]:
        initial_ticker = report_daten["flop_rows"][0]["ticker"]
    elif report_daten["top_rows"]:
        initial_ticker = report_daten["top_rows"][0]["ticker"]

    chart_json = json.dumps(report_daten["chart_series"], ensure_ascii=False)

    html_inhalt = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Korrelationsreport – {esc(report_daten['basis_name'])} ({esc(report_daten['zeitraum'])})</title>
<style>
    :root {{
        --bg: #0f172a;
        --card: #1e293b;
        --card-hover: #26354d;
        --border: #334155;
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --pos: #10b981;
        --neg: #f43f5e;
        --warn: #f59e0b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.5;
        padding: 28px 20px 60px;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    header {{
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        padding-bottom: 20px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 24px;
    }}
    .title-group h1 {{ font-size: 1.65rem; font-weight: 700; letter-spacing: -0.02em; }}
    .title-group p {{ color: var(--muted); font-size: 0.92rem; margin-top: 4px; }}
    .filter-bar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .filter-chip {{
        background: rgba(56, 189, 248, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.3);
        color: var(--accent);
        font-size: 0.78rem;
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 500;
    }}
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
        margin-bottom: 24px;
    }}
    .kpi-card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px 16px;
    }}
    .kpi-label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .kpi-value {{ font-size: 1.15rem; font-weight: 600; margin-top: 4px; }}
    .chart-card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 28px;
    }}
    .chart-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 14px;
    }}
    .chart-header h2 {{ font-size: 1.1rem; font-weight: 600; }}
    .chart-hint {{ color: var(--muted); font-size: 0.84rem; }}
    canvas {{ width: 100%; height: 320px; display: block; }}
    .grid-2col {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));
        gap: 24px;
        margin-bottom: 28px;
    }}
    .section-card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 20px;
    }}
    .section-title {{
        font-size: 1.08rem;
        font-weight: 600;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .section-sub {{ color: var(--muted); font-size: 0.83rem; margin-bottom: 14px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
    th {{
        text-align: left;
        color: var(--muted);
        font-weight: 600;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
    }}
    td {{
        padding: 10px 8px;
        border-bottom: 1px solid rgba(51, 65, 85, 0.55);
        vertical-align: middle;
    }}
    tr.clickable-row {{ cursor: pointer; transition: background 0.12s; }}
    tr.clickable-row:hover {{ background: var(--card-hover); }}
    tr.clickable-row.active-row {{
        background: rgba(56, 189, 248, 0.14);
        outline: 1px solid rgba(56, 189, 248, 0.4);
    }}
    .rank-col {{ color: var(--muted); width: 28px; font-weight: 600; }}
    .num-col {{ text-align: right; white-space: nowrap; }}
    .sec-name {{ font-weight: 600; color: var(--text); }}
    .sec-ticker {{ font-size: 0.76rem; color: var(--muted); }}
    .sector-pill {{
        display: inline-block;
        background: rgba(148, 163, 184, 0.14);
        color: #cbd5e1;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.76rem;
    }}
    .badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }}
    .badge-pos {{ background: rgba(16, 185, 129, 0.16); color: #34d399; }}
    .badge-neg {{ background: rgba(244, 63, 94, 0.16); color: #fb7185; }}
    .badge-neutral {{ background: rgba(148, 163, 184, 0.15); color: var(--muted); }}
    .text-pos {{ color: #34d399; font-weight: 500; }}
    .text-neg {{ color: #fb7185; font-weight: 500; }}
    .muted {{ color: var(--muted); }}
    .korr-cell {{ min-width: 115px; }}
    .korr-val {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-weight: 700; font-size: 0.85rem; }}
    .korr-high {{ color: #fbbf24; }}
    .korr-neg {{ color: #34d399; }}
    .korr-neutral {{ color: #38bdf8; }}
    .korr-bar-track {{
        width: 100%;
        height: 5px;
        background: rgba(148, 163, 184, 0.18);
        border-radius: 4px;
        margin-top: 4px;
        overflow: hidden;
    }}
    .korr-bar-fill {{ height: 100%; border-radius: 4px; }}
    .bar-high {{ background: linear-gradient(90deg, #f59e0b, #ef4444); }}
    .bar-neg {{ background: linear-gradient(90deg, #10b981, #06b6d4); }}
    .bar-neutral {{ background: #38bdf8; }}
    .empty-msg {{ color: var(--muted); font-style: italic; padding: 12px 0; }}
    .search-box {{
        background: var(--bg);
        border: 1px solid var(--border);
        color: var(--text);
        padding: 7px 12px;
        border-radius: 8px;
        font-size: 0.86rem;
        width: 260px;
    }}
    @media print {{
        body {{ background: #fff; color: #000; padding: 0; }}
        .kpi-card, .chart-card, .section-card {{ border: 1px solid #ccc; background: #fff; }}
    }}
</style>
</head>
<body>
<div class="container">
    <header>
        <div class="title-group">
            <h1>Portfolio Korrelationsanalyse: {esc(report_daten['basis_name'])} ({esc(report_daten['basis_ticker'])})</h1>
            <p>Zeitraum: <strong>{esc(report_daten['zeitraum'])}</strong> ({esc(report_daten['start_datum'])} bis {esc(report_daten['end_datum'])}) &bull; Methode: {esc(report_daten['methode_label'])} &bull; Erstellt am {erstellt_am}</p>
            <div class="filter-bar">{filter_badges}</div>
        </div>
        <div>
            <input type="text" id="tableSearch" class="search-box" placeholder="Wertpapier oder Sektor filtern..." oninput="filterTables(this.value)">
        </div>
    </header>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Basiswert Perf ({esc(report_daten['zeitraum'])})</div>
            <div class="kpi-value">{basis_perf_html}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Sektor (Basiswert)</div>
            <div class="kpi-value">{esc(report_daten['basis_sektor'])}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Basis Δ ATH 1J / SMA200</div>
            <div class="kpi-value">{fmt_delta_cell(report_daten['basis_ath_1y'])} <span class="muted">/</span> {fmt_delta_cell(report_daten['basis_sma200'])}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Handelstage im Zeitraum</div>
            <div class="kpi-value">{report_daten['handelstage']} Tage</div>
        </div>
    </div>

    <div class="chart-card">
        <div class="chart-header">
            <h2 id="chartTitle">Relativer Kursvergleich (normiert auf 1.00 zum Start)</h2>
            <span class="chart-hint">💡 Klicken Sie auf eine beliebige Zeile in den Tabellen unten, um den Kursverlauf hier im Chart zu vergleichen.</span>
        </div>
        <canvas id="compChart" width="1200" height="320"></canvas>
    </div>

    <div class="grid-2col">
        <div class="section-card">
            <div class="section-title">🛡️ Top {report_daten['anzahl']} Niedrigste / Negative Korrelationen</div>
            <div class="section-sub">Hohes Diversifikationspotenzial gegenüber {esc(report_daten['basis_name'])}</div>
            {baue_tabelle(report_daten['flop_rows'], 'Keine Werte gefunden.')}
        </div>

        <div class="section-card">
            <div class="section-title">🚀 Top {report_daten['anzahl']} Höchste Korrelationen</div>
            <div class="section-sub">Gleichlaufende Entwicklung (niedrige Diversifikation)</div>
            {baue_tabelle(report_daten['top_rows'], 'Keine Werte gefunden.')}
        </div>
    </div>

    <div class="section-card">
        <div class="section-title">⚖️ Neutrale Korrelationen (-0.15 bis +0.15)</div>
        <div class="section-sub">Unabhängige Kursentwicklung im gewählten Zeitraum ({len(report_daten['neutral_rows'])} Treffer)</div>
        {baue_tabelle(report_daten['neutral_rows'], 'Keine Werte mit neutraler Korrelation im Zeitraum gefunden.')}
    </div>
</div>

<script>
const CHART_DATA = {chart_json};
const BASIS_NAME = {json.dumps(report_daten['basis_name'], ensure_ascii=False)};
const BASIS_TICKER = {json.dumps(report_daten['basis_ticker'], ensure_ascii=False)};

function selectSecurity(ticker) {{
    document.querySelectorAll('tr.clickable-row').forEach(tr => {{
        tr.classList.toggle('active-row', tr.getAttribute('data-ticker') === ticker);
    }});
    drawChart(ticker);
}}

function drawChart(ticker) {{
    const canvas = document.getElementById('compChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    const entry = CHART_DATA[ticker];
    if (!entry || !entry.dates || entry.dates.length < 2) {{
        ctx.fillStyle = '#94a3b8';
        ctx.font = '14px sans-serif';
        ctx.fillText('Bitte wählen Sie ein Wertpapier aus der Tabelle.', 30, h / 2);
        return;
    }}

    document.getElementById('chartTitle').textContent =
        `Relativer Vergleich (normiert auf 1.00): ${{BASIS_NAME}} (${{BASIS_TICKER}}) vs. ${{entry.name}} (${{ticker}})`;

    const pad = {{ top: 24, right: 30, bottom: 34, left: 56 }};
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    const allVals = entry.basis_norm.concat(entry.sel_norm);
    let minVal = Math.min(...allVals);
    let maxVal = Math.max(...allVals);
    if (maxVal - minVal < 0.05) {{ minVal -= 0.05; maxVal += 0.05; }}
    const yPad = (maxVal - minVal) * 0.08;
    minVal -= yPad;
    maxVal += yPad;

    const xOf = i => pad.left + (i / (entry.dates.length - 1)) * plotW;
    const yOf = v => pad.top + (1 - (v - minVal) / (maxVal - minVal)) * plotH;

    // Grid lines
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.16)';
    ctx.lineWidth = 1;
    const steps = 5;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    for (let s = 0; s <= steps; s++) {{
        const val = minVal + (s / steps) * (maxVal - minVal);
        const y = yOf(val);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(2) + 'x', pad.left - 8, y + 4);
    }}

    // 1.00 baseline
    if (minVal < 1.0 && maxVal > 1.0) {{
        const y1 = yOf(1.0);
        ctx.strokeStyle = 'rgba(248, 250, 252, 0.25)';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(pad.left, y1);
        ctx.lineTo(w - pad.right, y1);
        ctx.stroke();
        ctx.setLineDash([]);
    }}

    // X-axis dates
    ctx.textAlign = 'center';
    const dateCount = Math.min(6, entry.dates.length);
    for (let d = 0; d < dateCount; d++) {{
        const idx = Math.round((d / (dateCount - 1)) * (entry.dates.length - 1));
        ctx.fillText(entry.dates[idx], xOf(idx), h - 10);
    }}

    function plotSeries(arr, color) {{
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = 0; i < arr.length; i++) {{
            const x = xOf(i);
            const y = yOf(arr[i]);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }}
        ctx.stroke();
    }}

    plotSeries(entry.basis_norm, '#38bdf8');
    plotSeries(entry.sel_norm, '#10b981');

    // Legend
    ctx.textAlign = 'left';
    ctx.font = '600 12px sans-serif';
    ctx.fillStyle = '#38bdf8';
    ctx.fillText(`● Basis: ${{BASIS_NAME}} (${{entry.basis_norm[entry.basis_norm.length - 1].toFixed(2)}}x)`, pad.left + 8, pad.top + 14);
    ctx.fillStyle = '#10b981';
    ctx.fillText(`● Auswahl: ${{entry.name}} (${{entry.sel_norm[entry.sel_norm.length - 1].toFixed(2)}}x)`, pad.left + 310, pad.top + 14);
}}

function filterTables(query) {{
    const q = query.trim().toLowerCase();
    document.querySelectorAll('tbody tr').forEach(tr => {{
        const text = tr.innerText.toLowerCase();
        tr.style.display = (!q || text.includes(q)) ? '' : 'none';
    }});
}}

window.addEventListener('resize', () => {{
    const active = document.querySelector('tr.active-row');
    if (active) drawChart(active.getAttribute('data-ticker'));
}});

window.addEventListener('DOMContentLoaded', () => {{
    const initTicker = {json.dumps(initial_ticker)};
    if (initTicker) selectSecurity(initTicker);
}});
</script>
</body>
</html>
"""
    with open(datei_pfad, "w", encoding="utf-8") as f:
        f.write(html_inhalt)



def zeige_chart(listbox):
    """Zeigt einen Chart mit Basiswert und selektiertem Wert, beide normiert auf 1 zum Start."""
    try:
        idx = listbox.curselection()[0]
    except IndexError:
        return
    if not hasattr(listbox, "ticker_map") or idx >= len(listbox.ticker_map):
        return

    ticker = listbox.ticker_map[idx]
    basis_ticker = listbox.basis_ticker
    df = listbox.df_temp_basis
    csv_metadata = getattr(listbox, "csv_metadata", None)
    ticker_to_name = getattr(listbox, "ticker_to_name", {})

    # Nur gemeinsame Handelstage beider Werte
    df_chart = df[[basis_ticker, ticker]].dropna()
    if df_chart.empty:
        messagebox.showerror("Fehler", "Keine gemeinsamen Handelstage für die gewählten Werte.")
        return

    # Normierung auf 1 zum Start
    norm_basis = df_chart[basis_ticker] / df_chart[basis_ticker].iloc[0]
    norm_sel = df_chart[ticker] / df_chart[ticker].iloc[0]

    basis_label = f"{ticker_to_name.get(basis_ticker, basis_ticker)} ({basis_ticker})"
    sel_label = f"{ticker_to_name.get(ticker, ticker)} ({ticker})"
    zusatz_titel = ""
    if csv_metadata and ticker in csv_metadata:
        m = csv_metadata[ticker]
        zusatz_titel = f"\n{sel_label} — Sektor: {m['sektor']} | Δ ATH 1J: {m['ath_1y']} | Δ SMA20: {m['sma20']} | Δ SMA200: {m['sma200']}"

    if plt is not None:
        plt.figure(figsize=(10, 5.5))
        plt.plot(df_chart.index, norm_basis, label=f"Basis: {basis_label}")
        plt.plot(df_chart.index, norm_sel, label=f"Auswahl: {sel_label}")
        plt.title(f"Relative Entwicklung ab Start (normiert auf 1){zusatz_titel}", fontsize=10)
        plt.xlabel("Datum")
        plt.ylabel("Relative Entwicklung")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()
        return

    # Nativer Tkinter-Canvas-Chart (Fallback falls matplotlib nicht installiert ist)
    win = tk.Toplevel()
    win.title(f"Kursvergleich: {basis_label} vs. {sel_label}")
    win.geometry("860x480")
    win.configure(bg="#0f172a")

    lbl_head = tk.Label(
        win,
        text=f"Relative Entwicklung ab Start (normiert auf 1.00){zusatz_titel}",
        bg="#0f172a",
        fg="#f8fafc",
        font=("Segoe UI", 10, "bold"),
        pady=8,
    )
    lbl_head.pack(fill="x")

    canvas = tk.Canvas(win, bg="#1e293b", highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    dates_str = [d.strftime("%Y-%m-%d") for d in df_chart.index]
    b_vals = [float(x) for x in norm_basis]
    s_vals = [float(x) for x in norm_sel]

    def zeichne_tk_chart(event=None):
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 100 or h < 100 or len(dates_str) < 2:
            return
        pad_l, pad_r, pad_t, pad_b = 60, 30, 32, 38
        pw = w - pad_l - pad_r
        ph = h - pad_t - pad_b

        alle = b_vals + s_vals
        min_v, max_v = min(alle), max(alle)
        if max_v - min_v < 0.05:
            min_v -= 0.05
            max_v += 0.05
        yp = (max_v - min_v) * 0.08
        min_v -= yp
        max_v += yp

        def x_of(i):
            return pad_l + (i / (len(dates_str) - 1)) * pw

        def y_of(v):
            return pad_t + (1.0 - (v - min_v) / (max_v - min_v)) * ph

        # Horizontales Gitter
        for step in range(6):
            val = min_v + (step / 5.0) * (max_v - min_v)
            y = y_of(val)
            canvas.create_line(pad_l, y, w - pad_r, y, fill="#334155", dash=(2, 2))
            canvas.create_text(pad_l - 8, y, text=f"{val:.2f}x", fill="#94a3b8", anchor="e", font=("Segoe UI", 8))

        # Datums-Achse
        anz_d = min(6, len(dates_str))
        for d_i in range(anz_d):
            idx_d = round((d_i / (anz_d - 1)) * (len(dates_str) - 1))
            canvas.create_text(x_of(idx_d), h - 14, text=dates_str[idx_d], fill="#94a3b8", font=("Segoe UI", 8))

        # Linien zeichnen
        b_pts = []
        s_pts = []
        for i in range(len(dates_str)):
            b_pts.extend((x_of(i), y_of(b_vals[i])))
            s_pts.extend((x_of(i), y_of(s_vals[i])))

        canvas.create_line(*b_pts, fill="#38bdf8", width=2)
        canvas.create_line(*s_pts, fill="#10b981", width=2)

        # Legende
        canvas.create_text(
            pad_l + 8,
            pad_t - 14,
            text=f"● Basis: {basis_label} ({b_vals[-1]:.2f}x)",
            fill="#38bdf8",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            pad_l + 340,
            pad_t - 14,
            text=f"● Auswahl: {sel_label} ({s_vals[-1]:.2f}x)",
            fill="#10b981",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )

    canvas.bind("<Configure>", zeichne_tk_chart)


def filter_positive_performance(df, tickers):
    """Gibt nur die Ticker zurück, deren Performance im Zeitraum >= 0% ist."""
    positive_tickers = []
    for t in tickers:
        serie = df[t].dropna()
        if len(serie) < 2:
            continue
        perf = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
        if perf >= 0:
            positive_tickers.append(t)
    return positive_tickers


def starte_gui():
    """Startet die Tkinter-GUI mit XML/Cache-Lader sowie CSV-Metadaten- und Sektor-Filterung."""
    root = tk.Tk()
    root.title("Portfolio Korrelationsanalyse (XML/Cache + CSV-Metadaten)")

    # App-State
    state = {
        "df_kurse_alle": None,
        "name_to_ticker_map": {},
        "isin_to_ticker_map": {},
        "csv_metadata": {},
        "alle_namen_referenz": [],
        "letzter_report": None,
    }

    # --- Zeile 0: XML / Cache Pfad ---
    tk.Label(root, text="Portfolio-XML / Cache:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    entry_xml = tk.Entry(root, width=50)
    entry_xml.grid(row=0, column=1, padx=5, pady=5, sticky="we")
    entry_xml.insert(0, XML_DATEI_PFAD)

    def waehle_xml_datei():
        pfad = filedialog.askopenfilename(
            title="Portfolio Performance XML oder Cache wählen",
            filetypes=[("XML / Cache Dateien", "*.xml *.cache.pkl"), ("XML Dateien", "*.xml"), ("Alle Dateien", "*.*")]
        )
        if pfad:
            entry_xml.delete(0, tk.END)
            entry_xml.insert(0, pfad)

    btn_xml_datei = tk.Button(root, text="Datei wählen...", command=waehle_xml_datei)
    btn_xml_datei.grid(row=0, column=2, padx=5, pady=5)

    # --- Zeile 1: CSV Pfad (Metadaten & Anlageuniversum) ---
    tk.Label(root, text="CSV Anlageuniversum:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    entry_csv = tk.Entry(root, width=50)
    entry_csv.grid(row=1, column=1, padx=5, pady=5, sticky="we")
    standard_csv = finde_standard_csv()
    if standard_csv:
        entry_csv.insert(0, standard_csv)

    def waehle_csv_datei():
        pfad = filedialog.askopenfilename(
            title="Portfolio Performance CSV wählen",
            filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")]
        )
        if pfad:
            entry_csv.delete(0, tk.END)
            entry_csv.insert(0, pfad)
            if state["df_kurse_alle"] is not None:
                aktualisiere_csv_daten(zeige_fehler=True)

    btn_csv_datei = tk.Button(root, text="CSV wählen...", command=waehle_csv_datei)
    btn_csv_datei.grid(row=1, column=2, padx=5, pady=5)

    # Status-Anzeige
    lbl_status = tk.Label(root, text="Bitte 'Daten laden' klicken.", fg="gray")
    lbl_status.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=2)

    def aktualisiere_basiswert_liste():
        """Aktualisiert die Auswahlliste für den Basiswert."""
        if state["df_kurse_alle"] is None:
            return
        namen = sorted(state["name_to_ticker_map"].keys())
        state["alle_namen_referenz"] = namen
        aktuelle_auswahl = combo_basis.get()
        combo_basis.config(values=namen, state="normal")
        if aktuelle_auswahl not in namen:
            combo_basis.set("")

    def aktualisiere_csv_daten(zeige_fehler=False):
        csv_pfad = entry_csv.get().strip()
        if not csv_pfad:
            state["csv_metadata"] = {}
            combo_sektor.config(values=["Alle Sektoren"], state="disabled")
            combo_sektor.set("Alle Sektoren")
            chk_csv_filter.config(state="disabled")
            csv_filter_var.set(False)
            return False

        try:
            meta = lade_csv_metadaten(
                csv_pfad,
                state["name_to_ticker_map"],
                state["isin_to_ticker_map"],
                state["df_kurse_alle"].columns,
            )
            state["csv_metadata"] = meta
            sektoren = sorted({m["sektor"] for m in meta.values() if m.get("sektor")})
            combo_sektor.config(values=["Alle Sektoren"] + sektoren, state="readonly")
            combo_sektor.set("Alle Sektoren")
            chk_csv_filter.config(state="normal")
            csv_filter_var.set(True)
            aktualisiere_basiswert_liste()
            return True
        except Exception as e:
            state["csv_metadata"] = {}
            combo_sektor.config(values=["Alle Sektoren"], state="disabled")
            combo_sektor.set("Alle Sektoren")
            chk_csv_filter.config(state="disabled")
            csv_filter_var.set(False)
            if zeige_fehler:
                messagebox.showwarning("CSV Hinweis", f"CSV-Datei konnte nicht geladen werden:\n{e}")
            return False

    def lade_daten(erzwinge_xml=False):
        xml_pfad = entry_xml.get().strip()
        lbl_status.config(text="Lade Kursdaten... Bitte warten.", fg="blue")
        root.update_idletasks()
        try:
            df_kurse_alle, name_to_ticker_map, isin_to_ticker_map, aus_cache = lade_und_bereinige_daten(
                xml_pfad, erzwinge_neuladen=erzwinge_xml
            )
        except Exception as e:
            lbl_status.config(text="Fehler beim Laden der Daten.", fg="red")
            messagebox.showerror("Fehler", f"Fehler beim Laden der Datei:\n{e}")
            return

        if df_kurse_alle is None or df_kurse_alle.empty or not name_to_ticker_map:
            lbl_status.config(text="Keine gültigen Kursdaten gefunden.", fg="red")
            messagebox.showerror("Fehler", "Keine gültigen Kursdaten in der Datei gefunden.")
            return

        state["df_kurse_alle"] = df_kurse_alle
        state["name_to_ticker_map"] = name_to_ticker_map
        state["isin_to_ticker_map"] = isin_to_ticker_map

        csv_geladen = aktualisiere_csv_daten(zeige_fehler=False)
        aktualisiere_basiswert_liste()

        combo_zeitraum.config(state="readonly")
        combo_methode.config(state="readonly")
        entry_anzahl.config(state="normal")
        btn_analyse.config(state="normal")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        text_ausgabe.delete(1.0, tk.END)

        quelle_str = "Cache (.cache.pkl)" if aus_cache else "XML (Cache aktualisiert)"
        csv_str = f" | CSV: {len(state['csv_metadata'])} Werte zugeordnet" if csv_geladen else " | Keine CSV geladen"
        lbl_status.config(
            text=f"Geladen aus {quelle_str}: {df_kurse_alle.shape[1]} Wertpapiere{csv_str}",
            fg="green",
        )

    btn_laden = tk.Button(root, text="Daten laden", command=lambda: lade_daten(False))
    btn_laden.grid(row=0, column=3, padx=5, pady=5)

    btn_cache_neu = tk.Button(root, text="XML neu einlesen", command=lambda: lade_daten(True))
    btn_cache_neu.grid(row=1, column=3, padx=5, pady=5)

    # --- Zeile 3: Basiswert Combobox ---
    tk.Label(root, text="Basiswert:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    combo_basis = ttk.Combobox(root, values=[], width=45, state="disabled")
    combo_basis.grid(row=3, column=1, padx=5, pady=5, sticky="w")
    combo_basis.bind(
        '<KeyRelease>',
        lambda event: type_ahead_search(event, combo_basis, state["alle_namen_referenz"]),
    )

    # --- Zeile 4: Zeitraum & Korrelationsmethode ---
    tk.Label(root, text="Zeitraum:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    rahmen_zeit_methode = tk.Frame(root)
    rahmen_zeit_methode.grid(row=4, column=1, columnspan=3, sticky="w", padx=5, pady=5)

    zeitraum_werte = ['1M', '3M', '6M', 'YTD', '1Y', '2Y', '3Y', '5Y', '10Y', 'Gesamt']
    combo_zeitraum = ttk.Combobox(rahmen_zeit_methode, values=zeitraum_werte, width=10, state="disabled")
    combo_zeitraum.pack(side="left", padx=(0, 15))
    combo_zeitraum.set('1Y')

    tk.Label(rahmen_zeit_methode, text="Korrelationsbasis:").pack(side="left", padx=(0, 5))
    methode_werte = ['Tagesrenditen (pct_change)', 'Kursniveau (absolut)']
    combo_methode = ttk.Combobox(rahmen_zeit_methode, values=methode_werte, width=26, state="disabled")
    combo_methode.pack(side="left")
    combo_methode.set('Tagesrenditen (pct_change)')

    # --- Zeile 5: Anzahl Ergebnisse & Sektor-Filter ---
    tk.Label(root, text="Anzahl Top/Flop:").grid(row=5, column=0, sticky="w", padx=5, pady=5)
    rahmen_anzahl_sektor = tk.Frame(root)
    rahmen_anzahl_sektor.grid(row=5, column=1, columnspan=3, sticky="w", padx=5, pady=5)

    entry_anzahl = tk.Entry(rahmen_anzahl_sektor, width=10, state="disabled")
    entry_anzahl.pack(side="left", padx=(0, 15))
    entry_anzahl.insert(0, "10")

    tk.Label(rahmen_anzahl_sektor, text="Sektor-Filter (CSV):").pack(side="left", padx=(0, 5))
    combo_sektor = ttk.Combobox(rahmen_anzahl_sektor, values=["Alle Sektoren"], width=28, state="disabled")
    combo_sektor.pack(side="left")
    combo_sektor.set("Alle Sektoren")

    # --- Zeile 6: Filter-Checkboxen & Analyse-Button ---
    filter_var = tk.BooleanVar(value=False)
    chk_filter = tk.Checkbutton(root, text="Nur Werte mit positiver Performance", variable=filter_var)
    chk_filter.grid(row=6, column=1, padx=5, pady=2, sticky="w")

    csv_filter_var = tk.BooleanVar(value=False)
    chk_csv_filter = tk.Checkbutton(
        root,
        text="Nur Werte aus CSV-Anlageuniversum",
        variable=csv_filter_var,
        state="disabled",
    )
    chk_csv_filter.grid(row=6, column=2, columnspan=2, padx=5, pady=2, sticky="w")

    def starte_analyse():
        df_kurse_alle = state["df_kurse_alle"]
        name_to_ticker_map = state["name_to_ticker_map"]
        csv_metadata = state["csv_metadata"]

        basis_name = combo_basis.get().strip()
        basis_ticker = name_to_ticker_map.get(basis_name)
        if not basis_ticker or basis_ticker not in df_kurse_alle.columns:
            messagebox.showerror("Fehler", "Bitte wählen Sie einen gültigen Basiswert aus.")
            return

        zeitraum = combo_zeitraum.get()
        methode = "returns" if "pct_change" in combo_methode.get() else "prices"

        try:
            anzahl = int(entry_anzahl.get())
            if anzahl <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fehler", "Bitte geben Sie eine positive ganze Zahl für die Anzahl ein.")
            return

        start_datum = get_start_date(zeitraum, df_kurse_alle)
        df_temp = df_kurse_alle[df_kurse_alle.index >= start_datum].copy()
        df_temp_basis = df_temp.dropna(subset=[basis_ticker])

        kandidaten_ticker = [t for t in df_temp_basis.columns if t != basis_ticker]

        # 1. Filter: Nur Werte aus CSV-Anlageuniversum
        if csv_filter_var.get() and csv_metadata:
            kandidaten_ticker = [t for t in kandidaten_ticker if t in csv_metadata]

        # 2. Filter: Sektor-Filter aus CSV
        gewaehlter_sektor = combo_sektor.get()
        if gewaehlter_sektor and gewaehlter_sektor != "Alle Sektoren" and csv_metadata:
            kandidaten_ticker = [
                t for t in kandidaten_ticker
                if t in csv_metadata and csv_metadata[t].get("sektor") == gewaehlter_sektor
            ]

        # 3. Filter: Nur positive Performance im Zeitraum
        if filter_var.get():
            kandidaten_ticker = filter_positive_performance(df_temp_basis, kandidaten_ticker)

        df_gefiltert = df_temp_basis[[basis_ticker] + kandidaten_ticker]

        aktive_filter = []
        if csv_filter_var.get() and csv_metadata:
            aktive_filter.append("Nur CSV-Anlageuniversum")
        if gewaehlter_sektor and gewaehlter_sektor != "Alle Sektoren":
            aktive_filter.append(f"Sektor: {gewaehlter_sektor}")
        if filter_var.get():
            aktive_filter.append("Nur positive Performance")
        if not aktive_filter:
            aktive_filter.append("Alle verfügbaren Wertpapiere")

        ergebnis = gui_korrelation_analyse(
            df_gefiltert,
            name_to_ticker_map,
            basis_name,
            zeitraum,
            anzahl,
            listbox_top,
            listbox_flop,
            text_ausgabe,
            csv_metadata=csv_metadata,
            methode=methode,
        )
        if ergebnis:
            ergebnis["aktive_filter"] = aktive_filter
            state["letzter_report"] = ergebnis
            btn_export_html.config(state="normal")
        else:
            state["letzter_report"] = None
            btn_export_html.config(state="disabled")

    def exportiere_html():
        report = state.get("letzter_report")
        if not report:
            messagebox.showwarning("Hinweis", "Bitte starten Sie zuerst eine Analyse.")
            return

        sicherer_name = re.sub(r"[^A-Za-z0-9_-]+", "_", report["basis_name"]).strip("_")
        standard_dateiname = f"Korrelationsreport_{sicherer_name}_{report['zeitraum']}_{datetime.now().strftime('%Y%m%d')}.html"

        datei_pfad = filedialog.asksaveasfilename(
            title="HTML-Report speichern",
            defaultextension=".html",
            initialfile=standard_dateiname,
            filetypes=[("HTML-Datei", "*.html"), ("Alle Dateien", "*.*")],
        )
        if not datei_pfad:
            return

        try:
            generiere_html_report(report, datei_pfad)
            webbrowser.open(f"file://{os.path.abspath(datei_pfad)}")
            lbl_status.config(text=f"HTML-Report exportiert: {os.path.basename(datei_pfad)}", fg="green")
        except Exception as e:
            messagebox.showerror("Fehler beim Export", f"Der HTML-Report konnte nicht gespeichert werden:\n{e}")

    btn_analyse = tk.Button(root, text="Analyse starten", state="disabled", command=starte_analyse)
    btn_analyse.grid(row=6, column=0, padx=5, pady=8, sticky="we")

    btn_export_html = tk.Button(root, text="HTML-Report exportieren", state="disabled", command=exportiere_html)
    btn_export_html.grid(row=3, column=2, columnspan=2, padx=5, pady=5, sticky="we")

    # --- Zeile 7 & 8: Listen für die Ergebnisse ---
    tk.Label(root, text="Top-Korrelationen (Klick öffnet Chart):").grid(row=7, column=0, columnspan=2, sticky="w", padx=5)
    listbox_top = tk.Listbox(root, width=50, height=10)
    listbox_top.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky="we")
    listbox_top.bind('<<ListboxSelect>>', lambda e: zeige_chart(listbox_top))

    tk.Label(root, text="Flop-Korrelationen (Klick öffnet Chart):").grid(row=7, column=2, columnspan=2, sticky="w", padx=5)
    listbox_flop = tk.Listbox(root, width=50, height=10)
    listbox_flop.grid(row=8, column=2, columnspan=2, padx=5, pady=5, sticky="we")
    listbox_flop.bind('<<ListboxSelect>>', lambda e: zeige_chart(listbox_flop))

    # --- Zeile 9: Textfeld für die detaillierte Ausgabe ---
    text_ausgabe = tk.Text(root, width=105, height=14)
    text_ausgabe.grid(row=9, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")

    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(9, weight=1)

    root.mainloop()


# ----------------------------------------------------
# HAUPTPROGRAMM (Main-Guard)
# ----------------------------------------------------

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        df_test = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [1.5, 2.5, 3.5]})
        _ = df_test.pct_change().corr()
        sys.exit(0)
    starte_gui()
