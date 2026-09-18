import streamlit as st
import pandas as pd
import pickle
import numpy as np
from iapws import IAPWS97
import math
from datetime import datetime

# =====================================================================
# INTEGRATION DES KAUFMÄNNISCHEN MULTI-INDEX-RECHENKERNS
# =====================================================================
from price_engine import load_excel_market_data, berechne_excel_indizierten_preis

# =====================================================================
# GUI SEITEN-EINSTELLUNGEN & TITEL (v0.1.3)
# =====================================================================
st.set_page_config(page_title="KonOpt-P v0.1.3", layout="wide") # Auf "wide" gestellt für das 2-Spalten-Layout

st.title("KonOpt-P v0.1.3")
st.caption("*AI-based engineering assistant for pressure part design and optimization by R.Rakowski*")
st.markdown("---")

# =====================================================================
# BEIDE MODELLE UND FEATURES LADEN
# =====================================================================
@st.cache_resource
def load_all_models():
    with open('konopt_rohre_model.pkl', 'rb') as f:
        model_wand = pickle.load(f)
    with open('konopt_spannungs_model.pkl', 'rb') as f:
        model_span = pickle.load(f)
    with open('model_rohre_features.pkl', 'rb') as f:
        features = pickle.load(f)
    return model_wand, model_span, features

try:
    model_wand, model_span, model_features = load_all_models()
except Exception as e:
    st.error(f"Fehler beim Laden der Modell-Dateien. Hast du train_konopt_rohre.py erfolgreich ausgeführt? Details: {e}")
    st.stop()

# Marktdaten und kaufmännische Indizes live über price_engine laden
markt_datenbank, letzter_eintrag_monat, excel_letzte_werte, daten_quelle = load_excel_market_data()

# Kategorien aus den Feature-Namen extrahieren
werkstoff_optionen = sorted([f.replace("Werkstoff_", "") for f in model_features if f.startswith("Werkstoff_")])
norm_optionen = sorted([f.replace("Norm_", "") for f in model_features if f.startswith("Norm_")])
n_mwd_optionen = sorted([f.replace("N oder MWD_", "") for f in model_features if f.startswith("N oder MWD_")], reverse=True)

# Default-Index für N/MWD bestimmen
default_index = n_mwd_optionen.index("N") if "N" in n_mwd_optionen else 0

# =====================================================================
# INTERNE PHASENBESTIMMUNG ÜBER SESSION STATE
# =====================================================================
if "temp_medium" not in st.session_state:
    st.session_state["temp_medium"] = 100.0
if "betriebsdruck" not in st.session_state:
    st.session_state["betriebsdruck"] = 0.3

is_heissdampf = False
try:
    current_p = st.session_state["betriebsdruck"]
    current_t = st.session_state["temp_medium"]
    
    sat_fluid = IAPWS97(P=current_p, x=0)
    t_sat_c = sat_fluid.T - 273.15
    
    if abs(current_t - t_sat_c) <= 0.3:
        is_heissdampf = False  
    else:
        fluid_preview = IAPWS97(P=current_p, T=(current_t + 273.15))
        if fluid_preview.phase in ["Vapour", "Supercritical", "Gas"]:
            is_heissdampf = True
except:
    is_heissdampf = False

# =====================================================================
# NEUE HAUPTSTRUKTUR: NEBENEINANDER (EINGABEN+ERGEBNISSE LINKS | KI-OPTIMIERUNG RECHTS)
# =====================================================================
haupt_col_links, haupt_col_rechts = st.columns([0.65, 0.35])

# ---------------------------------------------------------------------
# HAUPTSPALTE LINKS: Parameter-Eingabemaske & Standard-Ergebnisspalten
# ---------------------------------------------------------------------
with haupt_col_links:
    st.subheader("⚙️ Parameter für die Rohrdimensionierung")

    col1, col2, col3 = st.columns(3)

    wanddicke_optionen = [1.6, 1.8, 2, 2.3, 2.6, 2.9, 3.2, 3.6, 4, 4.5, 5, 5.6, 6.3, 7.1, 8, 8.8, 10, 11, 12.5, 14.2, 16, 17.5, 20, 22.2, 25, 28, 30, 32, 36, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100]

    with col2:
        wanddicke_vorh = st.selectbox("Vorhandene Wanddicke [mm]", options=wanddicke_optionen)
        n_or_mwd = st.selectbox("N: Nominal / MWD: Mindestwand", options=n_mwd_optionen, index=default_index)
        korrosion = st.number_input("Korrosionszuschlag [mm]", min_value=0.0, max_value=10.0, value=0.0, step=0.5, format="%.1f")
        verschwaechung = st.number_input("Verschwächungsbeiwert [-]", min_value=0.01, max_value=1.0, value=1.0, step=0.05)
        schweissnaht = st.number_input("Wertigkeit Rundschweißnaht [-]", min_value=0.01, max_value=1.0, value=0.8, step=0.05)

    with col3:
        temp_medium = st.number_input("Mediumtemperatur [°C]", min_value=0.0, max_value=800.0, step=10.0, key="temp_medium")
        
        if not is_heissdampf:
            beheizungsart = st.selectbox("Beheizungsart", options=["unbeheizt", "abgedeckt", "Berührung", "Strahlung"])
            if "unbeheizt" in beheizungsart:
                zuschlag = 0.0
            elif "abgedeckt" in beheizungsart:
                zuschlag = 20.0
            elif "Berührung" in beheizungsart:
                zuschlag = min(15.0 + 2.0 * wanddicke_vorh, 50.0)
            else:
                zuschlag = 50.0
        else:
            beheizungsart = st.selectbox("Beheizungsart", options=["unbeheizt, nach Mischstelle", "unbeheizt, vor Mischstelle", "abgedeckt", "Berührung", "Strahlung"])
            if "nach Mischstelle" in beheizungsart:
                zuschlag = 5.0
            elif "vor Mischstelle" in beheizungsart:
                zuschlag = 15.0
            elif "abgedeckt" in beheizungsart:
                zuschlag = 20.0
            elif "Berührung" in beheizungsart:
                zuschlag = 35.0
            else:
                zuschlag = 50.0
                
        st.caption(f"ℹ️ Temperaturzuschlag: **+{zuschlag:.1f} °C**")
        
        betriebsdruck = st.number_input("Betriebsdruck [MPa]", min_value=0.0, max_value=100.0, step=0.1, key="betriebsdruck")
        hydro_druck = st.number_input("Hydrostatischer Druck [MPa]", min_value=0.0, max_value=10.0, value=0.0, step=0.01)
        
        if (betriebsdruck * 10.0) < 40.0:
            druck_zuschlag = betriebsdruck * 0.10
        else:
            druck_zuschlag = betriebsdruck * 0.05
            
        massenstrom_th = st.number_input("Massenstrom [t/h]", min_value=0.0, max_value=1000.0, value=5.0, step=0.5)

    with col1:
        if "P235GH" in werkstoff_optionen:
            werkstoff_default_index = werkstoff_optionen.index("P235GH")
        else:
            werkstoff_default_index = 0
        
        werkstoff = st.selectbox("Werkstoff", options=werkstoff_optionen, index=werkstoff_default_index)
        norm = st.selectbox("Norm", options=norm_optionen)
        
        manuelle_temp_aktivieren = st.checkbox("Manuelle T Eingabe", value=False)
        standard_berechnungstemp = float(temp_medium + zuschlag)
        
        temp = st.number_input(
            "Berechnungstemperatur [°C]", 
            min_value=0.0, 
            max_value=800.0, 
            value=standard_berechnungstemp, 
            step=10.0,
            disabled=not manuelle_temp_aktivieren,
            help="Wird standardmäßig automatisch aus Mediumtemperatur + Zuschlag gebildet."
        )
        
        manuelle_druck_aktivieren = st.checkbox("Manuelle p Eingabe", value=False)
        standard_berechnungsdruck = float(betriebsdruck + druck_zuschlag + hydro_druck)
        
        druck = st.number_input(
            "Berechnungsdruck [MPa]", 
            min_value=0.0, 
            max_value=100.0, 
            value=standard_berechnungsdruck, 
            step=0.1,
            disabled=not manuelle_druck_aktivieren,
            help="Wird standardmäßig automatisch aus Betriebsdruck + Zuschlag (<40bar:10%, >=40bar:5%) + Hydr. Druck gebildet."
        )
        
        durchmesser_optionen = [21.3, 26.9, 33.7, 42.4, 48.3, 60.3, 76.1, 88.9, 114.3, 139.7, 168.3, 219.1, 273, 323.9, 355.6, 406.4, 457, 508, 610, 711, "---", 10.2, 12, 12.7, 13.5, 14, 16, 17.2, 18, 19, 20, 22, 25, 25.4, 30, 31.8, 32, 35, 38, 40, 44.5, 51, 54, 57, 63.5, 70, 73, 82.5, 101.6, 108, 127, 133, 141.3, 152.4, 159, 177.8, 193.7, 244.5, 559, 660]
        
        def format_trenner(val):
            if val == "---":
                return "────────────────"
            return f"{val}"
        
        durchmesser = st.selectbox("Außendurchmesser [mm]", options=durchmesser_optionen, format_func=format_trenner)
        if durchmesser == "---":
            durchmesser = 711

    # Grenzbereichs-Validierungen
    if werkstoff == "13CrMo4-5" and temp > 550.0:
        st.error("🚨 **Kritischer Bereich:** Temperaturen über 550 °C liegen außerhalb des zulässigen Einsatzbereiches für 13CrMo4-5! Keine Berechnung möglich.")
        st.stop()
    elif werkstoff == "X10CrMoVNb9-1" and temp > 620.0:
        st.error("🚨 **Kritischer Bereich:** Temperaturen über 620 °C liegen außerhalb des zulässigen Einsatzbereiches für X10CrMoVNb9-1!")
        st.stop()
    elif werkstoff == "16Mo3" and temp > 530.0:
        st.error("🚨 **Kritischer Bereich:** Temperaturen über 530 °C liegen außerhalb des validierten Kriechbereichs für 16Mo3!")
        st.stop()
    elif werkstoff == "P235GH" and temp > 400.0:
        st.error("🚨 **Kritischer Bereich:** Temperaturen über 400 °C liegen weit über dem zulässigen Geltungsbereich für P235GH!")
        st.stop()
    elif werkstoff == "10CrMo9-10" and temp > 580.0:
        st.error("🚨 **Kritischer Bereich:** Temperaturen über 580 °C liegen außerhalb des validierten Bereichs für 10CrMo9-10!")
        st.stop()

    werkstoff_ki = "X10CrMoVNb9-1" if werkstoff == "1.4903" else werkstoff

    span_features = [c for c in model_features if c.startswith("Werkstoff_")] + ["Berechnungstemp"]
    input_span = pd.DataFrame(0.0, index=[0], columns=span_features)
    input_span["Berechnungstemp"] = temp
    if f"Werkstoff_{werkstoff_ki}" in input_span.columns:
        input_span[f"Werkstoff_{werkstoff_ki}"] = 1.0

    # KORREKTUR: Array-Skalarfehler behoben via [0]
    spannung_prognose = float(model_span.predict(input_span)[0])
    st.info(f"🔮 **KI-Hintergrund-Ermittlung:** Für **{werkstoff}** bei **{temp}°C Berechnungs-T** prognostiziert das Spannungsmodell **{spannung_prognose:.2f} MPa** zulässige Spannung.")

    st.markdown("---")
    res_col_links, res_col_rechts = st.columns(2)

# ---------------------------------------------------------------------
# LINKE UNTERSPALTE: Ergebnisse der Rohrdimensionierung
# ---------------------------------------------------------------------
with res_col_links:
    st.subheader("📐 Rohrdimensionierung")
    
    input_data = pd.DataFrame(0.0, index=[0], columns=model_features)
    input_data["Berechnungstemp"] = temp  
    input_data["Berechnungsdruck"] = druck  
    input_data["Aussendurchmesser"] = durchmesser
    input_data["Wanddicke"] = wanddicke_vorh
    input_data["Korrosionszuschlag"] = korrosion
    input_data["Verschwaechungsbeiwert"] = verschwaechung
    input_data["Wertigkeit Rundschweissnaht"] = schweissnaht
    input_data["Zulaessige Spannung_KI"] = spannung_prognose

    v_min_val = min(verschwaechung, schweissnaht)
    nenner = (2 * spannung_prognose * v_min_val) + druck

    if nenner > 0:
        input_data["Physikalische_Wanddicke_Formel"] = (druck * durchmesser) / nenner
    else:
        input_data["Physikalische_Wanddicke_Formel"] = 0.0

    if f"Werkstoff_{werkstoff}" in input_data.columns:
        input_data[f"Werkstoff_{werkstoff}"] = 1.0
    elif f"Werkstoff_{werkstoff_ki}" in input_data.columns:
        input_data[f"Werkstoff_{werkstoff_ki}"] = 1.0
        
    if f"Norm_{norm}" in input_data.columns:
        input_data[f"Norm_{norm}"] = 1.0
    if f"N oder MWD_{n_or_mwd}" in input_data.columns:
        input_data[f"N oder MWD_{n_or_mwd}"] = 1.0

    prediction = 4.0
    if st.button("🚀 Wanddicke prognostizieren", type="primary", use_container_width=True):
        # KORREKTUR: Array-Skalarfehler behoben via [0]
        prediction = float(model_wand.predict(input_data)[0])
        
        st.success("**KI-Berechnung abgeschlossen**")
        st.metric(label="Prognostizierte Wanddicke (ohne Zuschläge)", value=f"{prediction:.2f} mm")
        
        # 1. Dynamischer, degressiver KI-Sicherheitszuschlag
        ki_zuschlag = max(0.1, 1.5 * math.exp(-0.15 * prediction))
        erforderliche_gesamtdicke = prediction + korrosion + ki_zuschlag
        
        d = float(durchmesser)
        t = float(wanddicke_vorh)
        td_verhaeltnis = t / d
        
        # Toleranzabzug entfällt bei Mindestwandstärke (MWD) vollständig
        if n_or_mwd == "N":
            if d <= 219.1:
                toleranz_abzug = max(t * 0.125, 0.4)
            else:
                if td_verhaeltnis <= 0.025: toleranz_abzug = t * 0.20
                elif td_verhaeltnis <= 0.05: toleranz_abzug = t * 0.15
                elif td_verhaeltnis <= 0.10: toleranz_abzug = t * 0.125
                else: toleranz_abzug = t * 0.10
        else:
            toleranz_abzug = 0.0
        
        wanddicke_vorh_min = t - toleranz_abzug
        
        st.caption(f"ℹ️ **Dynamischer KI-Zuschlag:** +{ki_zuschlag:.2f} mm (statistisch degressiv an Vorhersage angepasst).")
        if n_or_mwd == "N":
            st.caption(f"ℹ️ **Toleranzprüfung (Nominalwand):** Ein Untermaß von maximal **-{toleranz_abzug:.2f} mm** ist zulässig. Minimale Wanddicke: **{wanddicke_vorh_min:.2f} mm**.")
        else:
            st.caption(f"ℹ️ **Toleranzprüfung (Mindestwand):** Bei MWD gilt kein herstellerseitiges Untermaß (+0%). Nutzkraft: **{wanddicke_vorh_min:.2f} mm**.")

        if wanddicke_vorh_min >= erforderliche_gesamtdicke:
            st.markdown(f"**Status zur vorhandenen Wandstärke (v={wanddicke_vorh} mm, min={wanddicke_vorh_min:.2f} mm):**\n### ✅ Ausreichend")
        else:
            st.markdown(f"**Status zur vorhandenen Wandstärke (v={wanddicke_vorh} mm, min={wanddicke_vorh_min:.2f} mm):**\n### ⚠️ Kritisch")
            st.error(f"Vorhandene Wandstärke unter Berücksichtigung von Toleranz und KI-Zuschlag zu gering! Mindestens **{erforderliche_gesamtdicke:.2f} mm** erforderlich.")

# ---------------------------------------------------------------------
# RECHTE UNTERSPALTE: Ergebnisse der Strömungsmechanik
# ---------------------------------------------------------------------
with res_col_rechts:
    st.subheader("💨 Strömungsmechanik")
    
    volumenstrom_m3h = 0.0
    v_min, v_max = 0.0, 999.0
    vgb_info_text = ""
    massenstrom = massenstrom_th * 1000.0
    
    if isinstance(durchmesser, (int, float)) and druck > 0 and temp_medium > 0:
        try:
            try:
                sat_fluid = IAPWS97(P=druck, x=0)
                t_sat_c = sat_fluid.T - 273.15  
            except:
                t_sat_c = -999.0  
            
            if abs(temp_medium - t_sat_c) <= 0.3 and t_sat_c > 0:
                fluid = IAPWS97(P=druck, x=0.5)  
                phase_raw = "Two-phase"
                dichte = fluid.rho
            else:
                fluid = IAPWS97(P=druck, T=(temp_medium + 273.15))  
                dichte = fluid.rho       
                phase_raw = fluid.phase 
            
            phase_text = {"Liquid": "Wasser", "Two-phase": "Naßdampf", "Vapour": "Heißdampf", "Supercritical": "Überkritisch", "Gas": "Gasförmig"}.get(phase_raw, str(phase_raw))
            druck_bar = druck * 10.0
            
            if phase_raw == "Liquid":
                leitungstypen_wasser = {
                    "Speisewasserdruckleitung (2 - 6 m/s)": (2.0, 6.0), "Speisewasserzulaufleitung (0.5 - 2.5 m/s)": (0.5, 2.5),
                    "Kondensatleitung (1 - 3 m/s)": (1.0, 3.0), "Kondensatzusatzwasserleitung (2 - 3 m/s)": (2.0, 3.0),
                    "Kühlwasserpumpen-Druckleitung (1.5 - 2.5 m/s)": (1.5, 2.5), "Kühlwasserpumpen-Zulaufleitung (< 1.0 m/s)": (0.0, 1.0),
                    "Kühlwasserpumpen-Saugleitung (< 0.5 m/s)": (0.0, 0.5), "Trink- und Gebrauchwasserleitung (2 - 3 m/s)": (2.0, 3.0)
                }
                ausgewaehlter_typ = st.selectbox("Leitungstyp (nach VGB R507L)", options=list(leitungstypen_wasser.keys()))
                v_min, v_max = leitungstypen_wasser[ausgewaehlter_typ]
                vgb_info_text = f"VGB-Bereich für {ausgewaehlter_typ.split(' (')}"
            else:
                regelwerk_optionen = ["Standard-Dampfleitung (nach VGB R507L)", "Ausblaseleitung: Sehr kurz (< 5xDN) [FDBR 12/97]", "Ausblaseleitung: Länger (> 5xDN) [FDBR 12/97]", "Trommelentnahme: Heißdampfkessel (nur Leitbleche) [WN34-1100]", "Trommelentnahme: Heißdampfkessel (Demister) [WN34-1100]", "Trommelentnahme: Sattdampfkessel [WN34-1100]"]
                ausgewaehltes_regelwerk = st.selectbox("Anwendungsfall / Regelwerk Dampf", options=regelwerk_optionen)
                
                if ausgewaehltes_regelwerk == "Standard-Dampfleitung (nach VGB R507L)":
                    if druck_bar <= 1.5: v_min, v_max = (10.0, 20.0) if phase_raw == "Two-phase" else (0.0, 70.0)
                    elif druck_bar <= 10.0: v_min, v_max = (10.0, 20.0) if phase_raw == "Two-phase" else (0.0, 60.0)
                    elif druck_bar <= 40.0: v_min, v_max = (20.0, 40.0)
                    elif druck_bar <= 125.0: v_min, v_max = (30.0, 60.0)
                    elif druck_bar <= 200.0: v_min, v_max = (50.0, 70.0)
                    else: v_min, v_max = (40.0, 60.0)
                    vgb_info_text = f"VGB Dampf-Normbereich bei {druck_bar:.1f} bar"
                elif "Sehr kurz" in ausgewaehltes_regelwerk: v_min, v_max = 200.0, 250.0
                elif "Länger" in ausgewaehltes_regelwerk: v_min, v_max = 100.0, 120.0
                elif "nur Leitbleche" in ausgewaehltes_regelwerk: v_min, v_max = 0.0, 5.0
                elif "Demister" in ausgewaehltes_regelwerk: v_min, v_max = 5.0, 999.0
                elif "Sattdampfkessel" in ausgewaehltes_regelwerk: v_min, v_max = 5.0, 10.0
                vgb_info_text = f"Regelwerk: {ausgewaehltes_regelwerk}"
            
            innendurchmesser_m = (durchmesser - 2 * wanddicke_vorh) / 1000.0
            if innendurchmesser_m > 0 and dichte > 0:
                flaeche_m2 = (math.pi * (innendurchmesser_m ** 2)) / 4
                volumenstrom_m3h = massenstrom / dichte
                geschwindigkeit_ms = (volumenstrom_m3h / 3600.0) / flaeche_m2
                
                st.metric(label="Aggregatzustand (Phase)", value=phase_text)
                st.metric(label="Mediums-Dichte", value=f"{dichte:.1f} kg/m³")
                st.metric(label="Betriebsvolumenstrom", value=f"{volumenstrom_m3h:.1f} m³/h")
                st.metric(label="Strömungsgeschwindigkeit", value=f"{geschwindigkeit_ms:.2f} m/s")
                st.caption(f"ℹ️ **Klassifizierung:** {vgb_info_text}")
                
                if geschwindigkeit_ms > v_max: st.warning(f"⚠️ Überschreitet Maximum von {v_max} m/s!")
                elif geschwindigkeit_ms < v_min: st.info(f"ℹ️ Unterschreitet empfohlenes Minimum von {v_min} m/s.")
                else: st.success("✅ Geschwindigkeit liegt optimal im Normbereich.")
        except Exception as e:
            st.warning(f"⚠️ IAPWS-Rechenfehler: {e}")
    else:
        st.info("Bitte Betriebsparameter vervollständigen.")

# ---------------------------------------------------------------------
# HAUPTSPALTE RECHTS: ASSISTENT FÜR KI-OPTIMIERUNGSVORSCHLÄGE & PREISE
# ---------------------------------------------------------------------
with haupt_col_rechts:
    # =====================================================================
    # BETRIEBSANWEISUNG VOM NETZWERK LADEN
    # =====================================================================
    st.subheader("📖 Dokumentation")
    pdf_pfad = r"S:\Produktiv\100 Transfer\Rakowski\KonOpt-P_v.0.1\benutzerhandbuch_konopt_p.pdf"

    try:
        with open(pdf_pfad, "rb") as f:
            pdf_daten = f.read()
        
        st.download_button(
            label="📑 Betriebsanweisung / Handbuch öffnen",
            data=pdf_daten,
            file_name="benutzerhandbuch_konopt_p.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception:
        st.warning("⚠️ Benutzerhandbuch auf dem S-Laufwerk aktuell nicht erreichbar.")
        
    st.markdown("---") # Trennlinie zum nachfolgenden Optimierungs-Assistenten
    st.subheader("💡 KI-Optimierungsvorschläge")
    st.caption("Ausgewogene, sichere Geometriealternativen im optimalen VGB/FDBR-Strömungsfenster:")
    st.markdown("---")

    # Werkstoff-Hierarchie und deren harte obere Temperaturgrenzen
    werkstoff_hierarchie = ["P235GH", "16Mo3", "13CrMo4-5", "10CrMo9-10", "X10CrMoVNb9-1"]
    temp_grenzen = {
        "P235GH": 400.0,
        "16Mo3": 530.0,
        "13CrMo4-5": 550.0,
        "10CrMo9-10": 580.0,
        "X10CrMoVNb9-1": 620.0
    }
    
    def get_hoeherwertigen_werkstoff(curr, aktuelle_temp):
        if curr in werkstoff_hierarchie:
            start_idx = werkstoff_hierarchie.index(curr)
            for idx in range(start_idx + 1, len(werkstoff_hierarchie)):
                test_werkstoff = werkstoff_hierarchie[idx]
                if aktuelle_temp <= temp_grenzen[test_werkstoff]:
                    return test_werkstoff
        return curr

    gueltige_kombinationen = []

    # Sicherheits-Check: Nur rechnen, wenn alle Basisparameter & die Spannung vorliegen
    if isinstance(durchmesser, (int, float)) and druck > 0 and temp_medium > 0 and massenstrom_th > 0 and volumenstrom_m3h > 0 and spannung_prognose > 0:
        
        # Durchmesser starr auf Uservorgabe fixieren
        d_test = float(durchmesser) 
        
        for t_test in wanddicke_optionen:
            di_m = (d_test - 2 * t_test) / 1000.0
            if di_m <= 0: continue
                
            flaeche = (math.pi * (di_m ** 2)) / 4
            v_test = (volumenstrom_m3h / 3600.0) / flaeche
            
            if v_min <= v_test <= v_max:
                td_ratio = t_test / d_test
                
                if n_or_mwd == "N":
                    if d_test <= 219.1:
                        tol_abzug = max(t_test * 0.125, 0.4)
                    else:
                        if td_ratio <= 0.025: tol_abzug = t_test * 0.20
                        elif td_ratio <= 0.05: tol_abzug = t_test * 0.15
                        elif td_ratio <= 0.10: tol_abzug = t_test * 0.125
                        else: tol_abzug = t_test * 0.10
                else:
                    tol_abzug = 0.0
                
                t_vorh_min_test = float(round(t_test - tol_abzug, 2))
                v_min_val = min(verschwaechung, schweissnaht)
                nenner_test = (2 * spannung_prognose * v_min_val) + druck
                
                if nenner_test > 0:
                    try:
                        p_wand_test = prediction
                    except NameError:
                        p_wand_test = (druck * d_test) / nenner_test
                    
                    zuschlag_ki_test = max(0.1, 1.5 * math.exp(-0.15 * p_wand_test))
                    erf_gesamt_test = float(round(p_wand_test + korrosion + zuschlag_ki_test, 2))
                    
                    if t_vorh_min_test >= erf_gesamt_test:
                        gueltige_kombinationen.append({"D": d_test, "T": t_test, "v": v_test})

        if gueltige_kombinationen:
            df_gueltig = pd.DataFrame(gueltige_kombinationen).sort_values(by="T")
            records = df_gueltig.to_dict(orient="records")
            opt1 = records[0]
            
            df_alternative = df_gueltig[df_gueltig["T"] > opt1["T"]]
            if not df_alternative.empty:
                alternative_records = df_alternative.to_dict(orient="records")
                opt2 = alternative_records[0]
            else:
                opt2 = opt1
            
            besserer_werkstoff = get_hoeherwertigen_werkstoff(werkstoff, temp)

            # =====================================================================
            # CRITICAL FIX: ERST EINGABEFELDER DEKLARIEREN (DAMIT VARIABLE EXISTIERT)
            # =====================================================================
            st.markdown("### 📊 Integrierter Preisabgleich der Optionen")
            
            st.caption("📋 **Kaufmännische Parameter & Aufschläge**")
            c_box1, c_box2 = st.columns(2)
            with c_box1:
                datum_angebot = st.date_input("Historische Preisbasis", value=datetime(2023, 4, 25))
                menge_ueber_5t = st.checkbox("Großmenge (> 5 Tonnen)")
            with c_box2:
                mit_us_pruefung = st.checkbox("Mit US-Prüfung auf Querfehler")
                mit_fixlaenge = st.checkbox("Fixlängen-Lieferung")
            
            st.markdown("---")

            # Zeitstempel Keys generieren
            monat_damals_key = datum_angebot.strftime("%Y-%m")
            monat_heute_key = datetime.now().strftime("%Y-%m")
            
            werte_damals_base = markt_datenbank.get(monat_damals_key, {"Strom": 100.74, "Stahl": 980.00, "Schrott": 385.00})
            if monat_heute_key in markt_datenbank:
                werte_heute_base = markt_datenbank[monat_heute_key]
                label_heute = f"Stand {monat_heute_key}"
            else:
                werte_heute_base = {"Strom": excel_letzte_werte, "Stahl": excel_letzte_werte, "Schrott": excel_letzte_werte}
                label_heute = f"Stand {letzter_eintrag_monat}"

            # Interne Render-Engine für die Kachelausgabe
            def render_minimal_pricing(d_in, t_in, mat_in, op_title):
                w_damals = werte_damals_base.copy()
                w_heute = werte_heute_base.copy()
                w_damals[f"LZ_{mat_in}"] = markt_datenbank.get(monat_damals_key, {}).get(f"LZ_{mat_in}", 0.0)
                
                # Prüft sichere Fallback Strukturen für das Tupel
                if monat_heute_key in markt_datenbank:
                    w_heute[f"LZ_{mat_in}"] = markt_datenbank.get(monat_heute_key, {}).get(f"LZ_{mat_in}", 0.0)
                else:
                    w_heute[f"LZ_{mat_in}"] = excel_letzte_werte[3] if len(excel_letzte_werte) > 3 else 0.0

                calc = berechne_excel_indizierten_preis(
                    d_aussen=float(d_in), dicke=float(t_in), werkstoff_name=mat_in,
                    groesser_5t=menge_ueber_5t, us_pruefung=mit_us_pruefung, mit_fixlaenge=mit_fixlaenge,
                    werte_damals=w_damals, werte_heute=w_heute
                )
                if calc:
                    with st.expander(f"➔ {op_title} ({d_in} x {t_in} mm)", expanded=True):
                        c_m1, c_m2 = st.columns(2)
                        with c_m1: 
                            st.metric(label=f"Preis damals ({monat_damals_key})", value=f"{calc['Meter_Damals']:.2f} €/m")
                        with c_m2: 
                            st.metric(label=f"Live-Preis ({label_heute.split(' ')[-1]})", value=f"{calc['Meter_Heute']:.2f} €/m", delta=f"{(calc['Meter_Heute'] - calc['Meter_Damals']):+.2f} €/m")

            # UI Ausgaben der drei Optionen (Nutzen jetzt die Variablen fehlerfrei)
            st.info("🎯 **Option 1: Auf den Punkt ausgelegt**")
            st.markdown(f"* **Werkstoff:** `{werkstoff}` | **Dimension:** **{opt1['D']} x {opt1['T']} mm** | **Geschwindigkeit:** `{opt1['v']:.2f} m/s` *(Optimal)*")
            render_minimal_pricing(opt1['D'], opt1['T'], werkstoff, "Preise Option 1")
            st.markdown("---")
            
            st.info("⚖️ **Option 2: Alternative mit konstruktiver Reserve**")
            st.markdown(f"* **Werkstoff:** `{werkstoff}` | **Dimension:** **{opt2['D']} x {opt2['T']} mm** | **Geschwindigkeit:** `{opt2['v']:.2f} m/s`")
            render_minimal_pricing(opt2['D'], opt2['T'], werkstoff, "Preise Option 2")
            st.markdown("---")
            
            st.success("💎 **Option 3: Höherwertiger Werkstoff**")
            st.markdown(f"* **Werkstoff:** `{besserer_werkstoff}` *(Legierungs-Upgrade)* | **Dimension:** **{opt1['D']} x {opt1['T']} mm** | **Geschwindigkeit:** `{opt1['v']:.2f} m/s`")
            render_minimal_pricing(opt1['D'], opt1['T'], besserer_werkstoff, "Preise Option 3")
        else:
            st.warning("⚠️ Keine passende Geometrie gefunden.")
    else:
        st.info("Bitte füllen Sie links alle System- und Betriebsparameter vollständig aus, um die KI-Vorschlagsmaschine zu aktivieren.")