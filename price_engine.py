import math
import os
import pandas as pd

# =====================================================================
# CONFIG: REALE PREISBASIS (BEREINIGT UM LZ-BASISKOMPONENTEN)
# =====================================================================
KG_PREISE_KLEINMENGE = {
    "P235GH": 3.24, "16Mo3": 3.70, "13CrMo4-5": 6.20, "10CrMo9-10": 6.10,     
    "X10CrMoVNb9-1": 10.80, "Edelstahl 1.4541": 13.80, "Edelstahl 1.4571": 11.50  
}

KG_PREISE_GROSSMENGE = {
    "P235GH": 1.42, "16Mo3": 1.30, "13CrMo4-5": 2.30, "10CrMo9-10": 1.80,     
    "X10CrMoVNb9-1": 4.25, "Edelstahl 1.4541": 6.40, "Edelstahl 1.4571": 8.70
}

# =====================================================================
# DATA LOADING: INTERNE EXCEL-SCHNITTSTELLE
# =====================================================================
def load_excel_market_data():
    """Liest die Triple-Index-Excel-Datenbank ein. Ermittelt absolute Pfade."""
    basis_pfad = os.path.dirname(os.path.abspath(__file__))
    excel_pfad = os.path.join(basis_pfad, "04_Rohrpreise", "Rohr_Marktindizes.xlsx")
    
    standard_daten = {
        "2023-04": {"Strom": 100.74, "Stahl": 980.00, "Schrott": 385.00, "LZ_16Mo3": 420.0, "LZ_13CrMo4-5": 610.0, "LZ_10CrMo9-10": 1110.0, "LZ_X10CrMoVNb9-1": 2180.0},
        "2024-03": {"Strom": 64.70,  "Stahl": 830.00, "Schrott": 360.00, "LZ_16Mo3": 380.0, "LZ_13CrMo4-5": 550.0, "LZ_10CrMo9-10": 1000.0, "LZ_X10CrMoVNb9-1": 1640.0},
        "2025-10": {"Strom": 84.40,  "Stahl": 850.00, "Schrott": 348.00, "LZ_16Mo3": 395.0, "LZ_13CrMo4-5": 590.0, "LZ_10CrMo9-10": 1080.0, "LZ_X10CrMoVNb9-1": 1790.0},
        "2026-09": {"Strom": 137.74, "Stahl": 935.00, "Schrott": 398.50, "LZ_16Mo3": 490.0, "LZ_13CrMo4-5": 725.0, "LZ_10CrMo9-10": 1325.0, "LZ_X10CrMoVNb9-1": 2120.0}
    }
    
    if not os.path.exists(excel_pfad):
        return standard_daten, "2026-09", (137.74, 935.00, 398.50, 490.0, 725.0, 1325.0, 2120.0), f"INTERN (Datei unter '{excel_pfad}' nicht gefunden!)"
        
    try:
        df = pd.read_excel(excel_pfad, dtype={0: str})
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(subset=[df.columns[0], df.columns[1], df.columns[2], df.columns[3]])
        
        db_aus_excel = {}
        for _, row in df.iterrows():
            m_key = str(row.iloc[0]).strip()
            db_aus_excel[m_key] = {
                "Strom": float(row.iloc[1]),
                "Stahl": float(row.iloc[2]),
                "Schrott": float(row.iloc[3]),
                "LZ_16Mo3": float(row.iloc[4]) if len(row) > 4 else 0.0,
                "LZ_13CrMo4-5": float(row.iloc[5]) if len(row) > 5 else 0.0,
                "LZ_10CrMo9-10": float(row.iloc[6]) if len(row) > 6 else 0.0,
                "LZ_X10CrMoVNb9-1": float(row.iloc[7]) if len(row) > 7 else 0.0,
            }
        
        letzter_monat_excel = str(df.iloc[-1, 0]).strip()
        letzter_strom = float(df.iloc[-1, 1])
        letzter_stahl = float(df.iloc[-1, 2])
        letzter_schrott = float(df.iloc[-1, 3])
        
        letzte_lz = (
            letzter_strom, letzter_stahl, letzter_schrott,
            float(df.iloc[-1, 4]) if df.shape[1] > 4 else 0.0,
            float(df.iloc[-1, 5]) if df.shape[1] > 5 else 0.0,
            float(df.iloc[-1, 6]) if df.shape[1] > 6 else 0.0,
            float(df.iloc[-1, 7]) if df.shape[1] > 7 else 0.0
        )
        
        return db_aus_excel, letzter_monat_excel, letzte_lz, "LOKAL (Erfolgreich aus Excel geladen)"
    except Exception as e:
        return standard_daten, "2026-09", (137.74, 935.00, 398.50, 490.0, 725.0, 1325.0, 2120.0), f"FALLBACK (Fehler: {str(e)})"

# =====================================================================
# RECHENKERN (65% STAHL / 15% SCHROTT / 20% STROM ALS ENERGIE-AUSGLEICH)
# =====================================================================
def berechne_excel_indizierten_preis(d_aussen, dicke, werkstoff_name, groesser_5t, 
                                      us_pruefung, mit_fixlaenge, werte_damals, werte_heute):
    """
    Berechnet die Rohrpreise im direkten Abgleich Damals vs. Heute.
    Unterstützt Triple-Indexierung und additive Legierungszuschläge.
    """
    if d_aussen <= 0 or dicke <= 0 or dicke >= (d_aussen / 2): return None
    
    # 1. Rohrgewicht ermitteln
    gewicht_pro_meter_kg = (math.pi * (d_aussen - dicke) * dicke * 7.85) / 1000.0
    
    # 2. Basis-Preis kg bestimmen
    basis_preis_kg = KG_PREISE_GROSSMENGE.get(werkstoff_name, 1.80) if groesser_5t else \
                     KG_PREISE_KLEINMENGE.get(werkstoff_name, 4.00)
                     
    # 3. Kaufmännische Sonderzuschläge anwenden
    if us_pruefung and werkstoff_name in ["10CrMo9-10", "13CrMo4-5", "16Mo3"]:
        basis_preis_kg *= 2.15
    if mit_fixlaenge:
        basis_preis_kg *= 1.15
        
    # 4. Triple-Index-Hebel mit Gas-Kompensation (65% / 15% / 20%)
    faktor_stahl = werte_heute["Stahl"] / werte_damals["Stahl"]
    faktor_schrott = werte_heute["Schrott"] / werte_damals["Schrott"]
    faktor_strom = werte_heute["Strom"] / werte_damals["Strom"]
    
    faktor_markt = (faktor_stahl * 0.65) + (faktor_schrott * 0.15) + (faktor_strom * 0.20)
    
    # Basispreise indizieren
    indizierter_basis_preis_heute = basis_preis_kg * faktor_markt
    
    # 5. Additive Legierungszuschläge auslesen (Euro/kg)
    lz_schluessel = f"LZ_{werkstoff_name}"
    lz_damals_kg = (werte_damals.get(lz_schluessel, 0.0) / 1000.0)
    lz_heute_kg = (werte_heute.get(lz_schluessel, 0.0) / 1000.0)
    
    # Preiszusammensetzung Damals vs Heute
    kg_preis_damals = basis_preis_kg + lz_damals_kg
    kg_preis_heute = indizierter_basis_preis_heute + lz_heute_kg
    
    return {
        "Gewicht": gewicht_pro_meter_kg,
        "KG_Damals_Gesamt": kg_preis_damals,
        "Meter_Damals": gewicht_pro_meter_kg * kg_preis_damals,
        "KG_Heute_Gesamt": kg_preis_heute,
        "Meter_Heute": gewicht_pro_meter_kg * kg_preis_heute,
        "Hebel_Prozent": (faktor_markt - 1.0) * 100,
        "LZ_Damals_kg": lz_damals_kg,
        "LZ_Heute_kg": lz_heute_kg
    }