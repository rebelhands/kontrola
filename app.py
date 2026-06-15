import streamlit as st
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import os

# --- NASTAVENÍ STRÁNKY A ZABEZPEČENÍ ---
st.set_page_config(page_title="Kontrola Kvality Krabic", layout="centered")

# Inicializace přihlášení, pokud neexistuje
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state.logged_in:
    st.title("🔒 Vstup do systému")
    
    jmeno = st.text_input("Uživatelské jméno (např. admin):")
    heslo = st.text_input("Heslo:", type="password")
    
    if st.button("Přihlásit se"):
        # BEZPEČNÁ KONTROLA HESLA PŘES TREZOR CLOUDU
        if jmeno == "admin" and heslo == st.secrets["credentials"]["password"]:
            st.session_state.logged_in = True
            st.success("Přihlášení úspěšné!")
            st.rerun()
        else:
            st.error("Nesprávné jméno nebo heslo!")
    st.stop()

# --- HLAVNÍ PROGRAM (PO PŘIHLÁŠENÍ) ---
st.title("📦 Kontrola kvality potisku krabic")

# Nastavení složek pro cloudové prostředí
SABLO_DIR = "sablony"
HISTORIE_FILE = "historie_skenu.csv"

if not os.path.exists(SABLO_DIR):
    os.makedirs(SABLO_DIR)

# Pomocná funkce pro načtení historie
def nacist_historii():
    if os.path.exists(HISTORIE_FILE):
        return pd.read_csv(HISTORIE_FILE)
    else:
        return pd.DataFrame(columns=["Datum a čas", "Produkt", "Výsledek", "Shoda (%)"])

# --- MENU A NAVIGACE ---
volba = st.sidebar.radio("Navigace", ["Skenování", "Historie", "Nastavení (Šablony)"])

# 1. SEKCE: SKENOVÁNÍ
if volba == "Skenování":
    st.header("📸 Nové ověření krabice")
    
    # Výběr produktu podle dostupných šablon
    sablony_soubory = [f for f in os.listdir(SABLO_DIR) if f.endswith('.png')]
    if not sablony_soubory:
        st.warning("V systému nejsou žádné šablony. Jděte do Nastavení a přidejte vzor.")
    else:
        produkty = [os.path.splitext(f)[0].replace("sablona_", "") for f in sablony_soubory]
        vybrany_produkt = st.selectbox("Vyberte vyráběný produkt:", produkty)
        
        # tolerance od uživatele
        tolerance = st.slider("Tolerance citlivosti (pixelů):", 1, 50, 25)
        
        # Kamera na mobilu/PC
        foto = st.camera_input("Vyfoťte hotovou krabici")
        
        if foto is not None:
            # Načtení vyfoceného obrázku
            file_bytes = np.asarray(bytearray(foto.read()), dtype=np.uint8)
            img_sken = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            # Načtení šablony
            img_sablona = cv2.imread(os.path.join(SABLO_DIR, f"sablona_{vybrany_produkt}.png"), cv2.IMREAD_COLOR)
            
            # Zajištění stejné velikosti pro porovnání
            img_sken_res = cv2.resize(img_sken, (img_sablona.shape[1], img_sablona.shape[0]))
            
            # Výpočet rozdílu (porovnání pixelů)
            rozdil = cv2.absdiff(img_sablona, img_sken_res)
            rozdil_gray = cv2.cvtColor(rozdil, cv2.COLOR_BGR2GRAY)
            _, thresholded = cv2.threshold(rozdil_gray, tolerance, 255, cv2.THRESH_BINARY)
            
            Chybne_pixely = np.sum(thresholded == 255)
            celkem_pixelu = thresholded.size
            shoda = ((celkem_pixelu - Chybne_pixely) / celkem_pixelu) * 100
            
            # Vyhodnocení (např. limit 95% pro úspěch)
            if shoda >= 95.0:
                vysledek = "OK (V pořádku)"
                st.success(f"Výsledek: {vysledek} | Shoda: {shoda:.2f}%")
            else:
                vysledek = "ZMETEK (Chyba potisku)"
                st.error(f"Výsledek: {vysledek} | Shoda: {shoda:.2f}%")
                
                # Ukázka chyb pro operátora
                st.subheader("Zvýrazněné rozdíly (červená místa = chyby):")
                rozdil_viz = img_sken_res.copy()
                rozdil_viz[thresholded == 255] = [0, 0, 255] # červená barva
                st.image(cv2.cvtColor(rozdil_viz, cv2.COLOR_BGR2RGB))
            
            # Zápis do historie
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
    st.header("📊 Historie kontrol z dílny")
    df_historie = nacist_historii()
    
    if df_historie.empty:
        st.info("Zatím nebyly provedeny žádné kontroly.")
    else:
        st.dataframe(df_historie, use_container_width=True)
        
        # Tlačítko pro stažení Excelu/CSV tabulky
        csv = df_historie.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Stáhnout celou historii (CSV)", csv, "historie_kvality.csv", "text/csv")

# 3. SEKCE: NASTAVENÍ (ŠABLONY)
elif volba == "Nastavení (Šablony)":
    st.header("⚙️ Správa referenčních šablon")
    
    novy_nazev = st.text_input("Název nového produktu (např. krabice_Bosh):").strip()
    foto_sablony = st.camera_input("Vyfoťte vzorový (dokonalý) kus jako šablonu")
    
    if st.button("Uložit jako novou šablonu"):
        if novy_nazev == "":
            st.error("Zadejte prosím název produktu!")
        elif foto_sablony is None:
            st.error("Musíte vyfotit vzorový kus!")
        else:
            file_bytes = np.asarray(bytearray(foto_sablony.read()), dtype=np.uint8)
            img_sablona = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            # Uložení obrázku do složky šablon
            cesta_sablona = os.path.join(SABLO_DIR, f"sablona_{novy_nazev}.png")
            cv2.imwrite(cesta_sablona, img_sablona)
            st.success(f"Šablona pro produkt '{novy_nazev}' byla úspěšně uložena!")
            st.rerun()
            
    # Přehled stávajících šablon s možností smazání
    st.subheader("Aktuální šablony v systému:")
    sablony_soubory = [f for f in os.listdir(SABLO_DIR) if f.endswith('.png')]
    
    if not sablony_soubory:
        st.info("Nejsou uloženy žádné šablony.")
    else:
        for f in sablony_soubory:
            prod_name = os.path.splitext(f)[0].replace("sablona_", "")
            col1, col2 = st.columns([4, 1])
            col1.write(f"📦 {prod_name}")
            if col2.button("Smazat", key=f):
                os.remove(os.path.join(SABLO_DIR, f))
                st.success(f"Smazáno: {prod_name}")
                st.rerun()

# Odhlášení na spodu bočního panelu
st.sidebar.markdown("---")
if st.sidebar.button("🔓 Odhlásit se"):
    st.session_state.logged_in = False
    st.rerun()