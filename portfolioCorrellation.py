import xml.etree.ElementTree as ET
import pandas as pd
import sys
from dateutil.relativedelta import relativedelta
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
import matplotlib.pyplot as plt

# --- KONFIGURATION ---
XML_DATEI_PFAD = 'pf_daten.xml' # ANPASSEN: Pfad zu Ihrer Portfolio Performance XML-Datei
# ---------------------

# ----------------------------------------------------
# 1. FUNKTION ZUM LADEN UND BEREINIGEN DER DATEN (Unverändert)
# ----------------------------------------------------

def lade_und_bereinige_daten(file_path):
    """Lädt PP-XML-Daten, bereinigt sie, gibt ein pivotisiertes DataFrame und ein Mapping Name->Ticker zurück."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"FEHLER: Die Datei '{file_path}' wurde nicht gefunden. Bitte prüfen Sie den Pfad.")
        sys.exit(1)
    except ET.ParseError:
        print("FEHLER: Konnte die XML-Datei nicht parsen. Ist die Datei beschädigt?")
        sys.exit(1)

    all_security_data = []
    name_to_ticker_map = {} 

    for security_element in root.findall('securities/security'):
        name_element = security_element.find('name')
        security_name = name_element.text if name_element is not None else 'Unbekannter Wert'
        
        ticker_element = security_element.find('tickerSymbol')
        ticker_symbol = ticker_element.text if ticker_element is not None else 'N/A'
        
        if ticker_symbol != 'N/A' and security_name:
            if security_name not in name_to_ticker_map:
                name_to_ticker_map[security_name] = ticker_symbol
        
        prices_element = security_element.find('prices')
        
        if prices_element is not None:
            for price_element in prices_element.findall('price'):
                date_str = price_element.get('t')
                value_raw = price_element.get('v')
                
                try:
                    value_float = float(value_raw) / 100000000.0 
                except (TypeError, ValueError):
                    value_float = None

                all_security_data.append({
                    'Name': security_name,
                    'Ticker': ticker_symbol,
                    'Datum': date_str,
                    'Kurs': value_float
                })

    df = pd.DataFrame(all_security_data)
    df['Datum'] = pd.to_datetime(df['Datum'])
    
    df_clean = df.groupby(['Datum', 'Ticker'])['Kurs'].mean().reset_index()
    df_kurse = df_clean.pivot(index='Datum', columns='Ticker', values='Kurs')
    
    if 'N/A' in df_kurse.columns:
        df_kurse = df_kurse.drop(columns=['N/A'])

    return df_kurse, name_to_ticker_map

# ----------------------------------------------------
# 2. HILFSFUNKTIONEN
# ----------------------------------------------------

def get_start_date(zeitraum, df):
    """Berechnet das Startdatum basierend auf dem letzten Datum in den Daten."""
    heute = df.index.max() 
    if zeitraum == '1Y':
        return heute - relativedelta(years=1)
    elif zeitraum == '3Y':
        return heute - relativedelta(years=3)
    elif zeitraum == '5Y':
        return heute - relativedelta(years=5)
    return df.index.min() # Gesamt

def type_ahead_search(event, combobox, values):
    """Filtert die Combobox-Liste nach aktueller Eingabe, setzt aber keine automatische Auswahl."""
    eingabe = combobox.get().lower()
    gefiltert = [v for v in values if eingabe in v.lower()]
    combobox['values'] = gefiltert if gefiltert else values
    # Keine automatische Auswahl!
    # Optional: Bei Enter-Taste Auswahl setzen
    if event.keysym == "Return" and gefiltert:
        combobox.set(gefiltert[0])

def gui_korrelation_analyse(df_kurse_alle, name_to_ticker_map, basis_name, zeitraum, anzahl, listbox_top, listbox_flop, ausgabe_widget):
    """Führt die Korrelationsanalyse aus und zeigt die Ergebnisse als Listen im GUI."""
    basis_ticker = name_to_ticker_map.get(basis_name)
    if not basis_ticker:
        ausgabe_widget.delete(1.0, tk.END)
        ausgabe_widget.insert(tk.END, f"FEHLER: Basiswert '{basis_name}' nicht gefunden.\n")
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

    korrelationen = df_temp_basis.corr()[basis_ticker].sort_values(ascending=False)
    korrelationen = korrelationen.drop(basis_ticker, errors='ignore').dropna()
    
    if korrelationen.empty:
        ausgabe_widget.delete(1.0, tk.END)
        ausgabe_widget.insert(tk.END, "Keine gemeinsamen Handelstage mit anderen Werten gefunden.\n")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        return

    top_korrelation = korrelationen.head(anzahl)
    flop_korrelation = korrelationen.tail(anzahl) 
    ticker_to_name_map = {v: k for k, v in name_to_ticker_map.items()}

    # Ausgabe formatieren
    ausgabe_widget.delete(1.0, tk.END)
    ausgabe_widget.insert(tk.END, f"Korrelationsanalyse für Basiswert: {basis_name} ({basis_ticker})\n")
    ausgabe_widget.insert(tk.END, f"Zeitraum: {zeitraum} ({df_temp_basis.index.min().date()} bis {df_temp_basis.index.max().date()})\n")
    ausgabe_widget.insert(tk.END, f"Handelstage des Basiswerts in der Analyse: {df_temp_basis.shape[0]}\n\n")

    # Hilfsfunktion für Performance
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
        perf_str = f"{perf:.2f}%" if perf is not None else "n/a"
        listbox_top.insert(tk.END, f"{name} ({t})")
        ausgabe_widget.insert(tk.END, f"{name}: Korr={v:.4f}, Perf={perf_str}\n")

    listbox_flop.delete(0, tk.END)
    ausgabe_widget.insert(tk.END, f"\n🛡️ TOP {anzahl} NEGATIVE KORRELATIONEN (Diversifikation hoch):\n")
    for t, v in flop_korrelation.items():
        name = ticker_to_name_map.get(t, t)
        perf = berechne_performance(df_temp_basis, t)
        perf_str = f"{perf:.2f}%" if perf is not None else "n/a"
        listbox_flop.insert(tk.END, f"{name} ({t})")
        ausgabe_widget.insert(tk.END, f"{name}: Korr={v:.4f}, Perf={perf_str}\n")

    # Abschnitt für neutrale Korrelationen
    neutral_min = -0.15
    neutral_max = 0.15
    neutral_korrelation = korrelationen[(korrelationen >= neutral_min) & (korrelationen <= neutral_max)]
    ausgabe_widget.insert(tk.END, f"\n⚖️ NEUTRALE KORRELATIONEN (-0.15 bis +0.15):\n")
    if neutral_korrelation.empty:
        ausgabe_widget.insert(tk.END, "Keine Werte mit neutraler Korrelation gefunden.\n")
    else:
        for t, v in neutral_korrelation.items():
            name = ticker_to_name_map.get(t, t)
            perf = berechne_performance(df_temp_basis, t)
            perf_str = f"{perf:.2f}%" if perf is not None else "n/a"
            ausgabe_widget.insert(tk.END, f"{name}: Korr={v:.4f}, Perf={perf_str}\n")

    # Für Chart-Auswahl: Mapping von Listbox-Index zu Ticker
    listbox_top.ticker_map = [t for t in top_korrelation.index]
    listbox_flop.ticker_map = [t for t in flop_korrelation.index]
    listbox_top.basis_ticker = basis_ticker
    listbox_flop.basis_ticker = basis_ticker
    listbox_top.df_temp_basis = df_temp_basis
    listbox_flop.df_temp_basis = df_temp_basis

def zeige_chart(listbox):
    """Zeigt einen Chart mit Basiswert und selektiertem Wert, beide normiert auf 1 zum Start."""
    try:
        idx = listbox.curselection()[0]
    except IndexError:
        return
    ticker = listbox.ticker_map[idx]
    basis_ticker = listbox.basis_ticker
    df = listbox.df_temp_basis

    # Nur gemeinsame Handelstage beider Werte
    df_chart = df[[basis_ticker, ticker]].dropna()
    if df_chart.empty:
        messagebox.showerror("Fehler", "Keine gemeinsamen Handelstage für die gewählten Werte.")
        return

    # Normierung auf 1 zum Start
    norm_basis = df_chart[basis_ticker] / df_chart[basis_ticker].iloc[0]
    norm_sel = df_chart[ticker] / df_chart[ticker].iloc[0]

    plt.figure(figsize=(10,5))
    plt.plot(df_chart.index, norm_basis, label=f"Basiswert ({basis_ticker})")
    plt.plot(df_chart.index, norm_sel, label=f"Selektiert ({ticker})")
    plt.title("Relative Entwicklung ab Start (normiert auf 1)")
    plt.xlabel("Datum")
    plt.ylabel("Relative Entwicklung")
    plt.legend()
    plt.tight_layout()
    plt.show()

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
    """Startet die Tkinter-GUI mit Dateiauswahldialog für den XML-Pfad und dynamischem Laden der Daten."""
    root = tk.Tk()
    root.title("Portfolio Korrelationsanalyse")

    # XML-Pfad Eingabefeld
    tk.Label(root, text="Portfolio-XML Pfad:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    entry_xml = tk.Entry(root, width=50)
    entry_xml.grid(row=0, column=1, padx=5, pady=5)
    entry_xml.insert(0, "pf_daten.xml")

    # Button zum Öffnen des Dateidialogs
    def waehle_datei():
        pfad = filedialog.askopenfilename(
            title="Portfolio Performance XML wählen",
            filetypes=[("XML Dateien", "*.xml"), ("Alle Dateien", "*.*")]
        )
        if pfad:
            entry_xml.delete(0, tk.END)
            entry_xml.insert(0, pfad)

    btn_datei = tk.Button(root, text="Datei wählen...", command=waehle_datei)
    btn_datei.grid(row=0, column=2, padx=5, pady=5)

    # Button zum Laden der Daten
    def lade_daten():
        xml_pfad = entry_xml.get()
        try:
            df_kurse_alle, name_to_ticker_map = lade_und_bereinige_daten(xml_pfad)
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Laden der Datei:\n{e}")
            return
        if df_kurse_alle is None or not name_to_ticker_map:
            messagebox.showerror("Fehler", "Keine gültigen Daten gefunden.")
            return

        # Nach erfolgreichem Laden: GUI-Elemente aktivieren und befüllen
        namen_liste = sorted(name_to_ticker_map.keys())
        combo_basis.config(values=namen_liste, state="normal")
        combo_basis.set("")
        combo_zeitraum.config(state="normal")
        entry_anzahl.config(state="normal")
        btn_analyse.config(state="normal")
        listbox_top.delete(0, tk.END)
        listbox_flop.delete(0, tk.END)
        text_ausgabe.delete(1.0, tk.END)

        # Analysefunktion für Button
        def starte_analyse():
            basis_name = combo_basis.get()
            zeitraum = combo_zeitraum.get()
            try:
                anzahl = int(entry_anzahl.get())
                if anzahl <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Fehler", "Bitte geben Sie eine positive ganze Zahl für die Anzahl ein.")
                return

            # Filter für positive Performance
            if filter_var.get():
                # Nur Werte mit positiver Performance
                start_datum = get_start_date(zeitraum, df_kurse_alle)
                df_temp = df_kurse_alle[df_kurse_alle.index >= start_datum].copy()
                df_temp_basis = df_temp.dropna(subset=[name_to_ticker_map.get(basis_name)])
                alle_ticker = [t for t in df_temp_basis.columns if t != name_to_ticker_map.get(basis_name)]
                positive_tickers = filter_positive_performance(df_temp_basis, alle_ticker)
                # DataFrame nur mit positiven Tickern
                df_temp_basis = df_temp_basis[[name_to_ticker_map.get(basis_name)] + positive_tickers]
                # Übergib gefiltertes DataFrame an Analyse
                gui_korrelation_analyse(
                    df_temp_basis, name_to_ticker_map, basis_name, zeitraum, anzahl,
                    listbox_top, listbox_flop, text_ausgabe
                )
            else:
                gui_korrelation_analyse(
                    df_kurse_alle, name_to_ticker_map, basis_name, zeitraum, anzahl,
                    listbox_top, listbox_flop, text_ausgabe
                )

        btn_analyse.config(command=starte_analyse)

    btn_laden = tk.Button(root, text="Daten laden", command=lade_daten)
    btn_laden.grid(row=0, column=3, padx=5, pady=5)

    # Basiswert Combobox (initial deaktiviert)
    tk.Label(root, text="Basiswert:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    combo_basis = ttk.Combobox(root, values=[], width=30, state="disabled")
    combo_basis.grid(row=1, column=1, padx=5, pady=5)
    combo_basis.bind('<KeyRelease>', lambda event: type_ahead_search(event, combo_basis, combo_basis['values']))

    # Zeitraum Combobox (initial deaktiviert)
    tk.Label(root, text="Zeitraum:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    zeitraum_werte = ['1Y', '3Y', '5Y', 'Gesamt']
    combo_zeitraum = ttk.Combobox(root, values=zeitraum_werte, width=10, state="disabled")
    combo_zeitraum.grid(row=2, column=1, padx=5, pady=5)
    combo_zeitraum.set('1Y')

    # Anzahl Ergebnisse (initial deaktiviert)
    tk.Label(root, text="Anzahl Top/Flop Ergebnisse:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    entry_anzahl = tk.Entry(root, width=10, state="disabled")
    entry_anzahl.grid(row=3, column=1, padx=5, pady=5)
    entry_anzahl.insert(0, "10")

    # Button zur Analyse (initial deaktiviert)
    btn_analyse = tk.Button(root, text="Analyse starten", state="disabled")
    btn_analyse.grid(row=4, column=0, columnspan=2, pady=10)

    # Checkbox für Filter
    filter_var = tk.BooleanVar(value=False)
    chk_filter = tk.Checkbutton(root, text="Nur Werte mit positiver Performance berücksichtigen", variable=filter_var)
    chk_filter.grid(row=4, column=2, padx=5, pady=5, sticky="w")

    # Listen für die Ergebnisse
    tk.Label(root, text="Top-Korrelationen:").grid(row=5, column=0, sticky="w", padx=5)
    listbox_top = tk.Listbox(root, width=35, height=10)
    listbox_top.grid(row=6, column=0, padx=5, pady=5)
    listbox_top.bind('<<ListboxSelect>>', lambda e: zeige_chart(listbox_top))

    tk.Label(root, text="Flop-Korrelationen:").grid(row=5, column=1, sticky="w", padx=5)
    listbox_flop = tk.Listbox(root, width=35, height=10)
    listbox_flop.grid(row=6, column=1, padx=5, pady=5)
    listbox_flop.bind('<<ListboxSelect>>', lambda e: zeige_chart(listbox_flop))

    # Textfeld für die Ausgabe
    text_ausgabe = tk.Text(root, width=70, height=10)
    text_ausgabe.grid(row=7, column=0, columnspan=2, padx=5, pady=5)

    root.mainloop()

# ----------------------------------------------------
# HAUPTPROGRAMM (Main-Guard)
# ----------------------------------------------------

if __name__ == "__main__":
    starte_gui()