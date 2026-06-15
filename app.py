import streamlit as st
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import os

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Kontrola Kvality", layout="centered")

# Inicializace přihlášení
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state.logged_in:
    st.title("🔒 Vstup do systému")
    jmeno = st.text_input("Uživatelské jméno:")
    heslo = st.text_input("Heslo:", type="password")
    
    if st.button("Přihlásit se"):
        if jmeno == "admin" and heslo == st.secrets["credentials"]["password"]:
            st.session_state.logged_in = True
            st.success("Přihlášení úspěšné!")
            st.rerun()
        else:
            st.error("Nesprávné jméno nebo heslo!")
    st.stop()

# --- HLAVNÍ PROGRAM ---
st.title("📦 Kontrola kvality")

SABLO_DIR = "sablony"
HISTORIE_FILE = "historie_skenu.csv"

if not os.path.exists(SABLO_DIR):
    os.makedirs(SABLO_DIR)

def nacist_historii():
    if os.path.exists(HISTORIE_FILE):
        return pd.read_csv(HISTORIE_FILE)
    return pd.DataFrame(columns=["Datum a čas", "Produkt", "Výsledek", "Shoda (%)"])

volba = st.sidebar.radio("Navigace", ["Skenování", "Historie", "Nastavení (Šablony)"])

# 1. SEKCE: SKENOVÁNÍ
if volba == "Skenování":
    st.header("📸 Nové ověření krabice")
    
    sablony_soubory = [f for f in os.listdir(SABLO_DIR) if f.endswith('.png')]
    if not sablony_soubory:
        st.warning("V systému nejsou žádné šablony. Jděte do Nastavení.")
    else:
        produkty = [os.path.splitext(f)[0].replace("sablona_", "") for f in sablony_soubory]
        vybrany_produkt = st.selectbox("Vyberte produkt:", produkty)
        tolerance = st.slider("Tolerance citlivosti:", 1, 50, 25)
        
        st.markdown("---")
        st.subheader("Spustit kameru")
        
        # TLAČÍTKO PRO AKTIVACI FOŤÁKU - forcing mobilní kompatibility
        spustit = st.checkbox("Zapnout/Vypnout hledáček kamery")
        
        if spustit:
            foto = st.camera_input("Vyfoťte krabici")
            
            if foto is not None:
                file_bytes = np.asarray(bytearray(foto.read()), dtype=np.uint8)
                img_sken = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                img_sablona = cv2.imread(os.path.join(SABLO_DIR, f"sablona_{vybrany_produkt}.png"), cv2.IMREAD_COLOR)
                
                img_sken_res = cv2.resize(img_sken, (img_sablona.shape[1], img_sablona.shape[0]))
                rozdil = cv2.absdiff(img_sablona, img_sken_res)
                rozdil_gray = cv2.cvtColor(rozdil, cv2.COLOR_BGR2GRAY)
                _, thresholded = cv2.threshold(rozdil_gray, tolerance, 255, cv2.THRESH_BINARY)
                
                Chybne_pixely = np.sum(thresholded == 255)
                celkem_pixelu = thresholded.size
                shoda = ((celkem_pixelu - Chybne_pixely) / celkem_pixelu) * 100
                
                if shoda >= 95.0:
                    vysledek = "OK"
                    st.success(f"Výsledek: OK | Shoda: {shoda:.2f}%")
                else:
                    vysledek = "ZMETEK"
                    st.error(f"Výsledek: ZMETEK | Shoda: {shoda:.2f}%")
                    st.subheader("Chyby (červená místa):")
                    rozdil_viz = img_sken_res.copy()
                    rozdil_viz[thresholded == 255] = [0, 0, 255]
                    st.image(cv2.cvtColor(rozdil_viz, cv2.COLOR_BGR2RGB))
                
                nova_data = pd.DataFrame({
                    "Datum a čas": [datetime.now().strftime("%d.%m.%Y %H:%M:%S")],
                    "Produkt": [vybrany_produkt],
                    "Výsledek": [vysledek],
                    "Shoda (%)": [f"{shoda:.2f}"]
                })
                df_historie = nacist_historii()
                df_historie = pd.concat([nova_data, df_historie], ignore_index=True)
                df_historie.to_csv(HISTORIE_FILE, index=False)

# 2. SEKCE: HISTORIE
elif volba == "Historie":
    st.header("📊 Historie")
    df_historie = nacist_historii()
    if df_historie.empty:
        st.info("Žádné záznamy.")
    else:
        st.dataframe(df_historie, use_container_width=True)

# 3. SEKCE: NASTAVENÍ
elif volba == "Nastavení (Šablony)":
    st.header("⚙️ Správa šablon")
    novy_nazev = st.text_input("Název produktu:").strip()
    
    aktivovat_sablone = st.checkbox("Zapnout kameru pro vyfocení šablony")
    if aktivovat_sablone:
        foto_sablony = st.camera_input("Vyfoťte vzorový kus")
        
        if st.button("Uložit šablonu"):
            if novy_nazev == "" or foto_sablony is None:
                st.error("Vyplňte název a vyfoťte šablonu!")
            else:
                file_bytes = np.asarray(bytearray(foto_sablony.read()), dtype=np.uint8)
                img_sablona = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                cv2.imwrite(os.path.join(SABLO_DIR, f"sablona_{novy_nazev}.png"), img_sablona)
                st.success("Uloženo!")
                st.rerun()

    st.subheader("Aktuální šablony:")
    sablony_soubory = [f for f in os.listdir(SABLO_DIR) if f.endswith('.png')]
    for f in sablony_soubory:
        prod_name = os.path.splitext(f)[0].replace("sablona_", "")
        col1, col2 = st.columns([4, 1])
        col1.write(f"📦 {prod_name}")
        if col2.button("Smazat", key=f):
            os.remove(os.path.join(SABLO_DIR, f))
            st.rerun()