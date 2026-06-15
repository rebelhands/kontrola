import streamlit as st
import cv2
import numpy as np
import os
import pandas as pd
from datetime import datetime
import glob

# Nastavení vzhledu stránky
st.set_page_config(page_title="Kontrola Kvality - Zabezpečeno", layout="centered")

# --- FUNKCE PRO PŘIHLÁŠENÍ ---
def prihlaseni():
    st.subheader("🔒 Přihlášení do systému kontroly kvality")
    uzivatel = st.text_input("Uživatelské jméno:")
    heslo = st.text_input("Heslo:", type="password")
    
    # Údaje pro přihlášení
    SPRÁVNÉ_JMÉNO = "admin"
    SPRÁVNÉ_HESLO = "kvalita2026"
    
    if st.button("Přihlásit se"):
        if uzivatel == SPRÁVNÉ_JMÉNO and heslo == SPRÁVNÉ_HESLO:
            st.session_state.prihlasen = True
            st.success("Přihlášení úspěšné!")
            st.rerun()
        else:
            st.error("Nesprávné uživatelské jméno nebo heslo!")

# Inicializace stavu přihlášení
if "prihlasen" not in st.session_state:
    st.session_state.prihlasen = False

# Pokud uživatel NENÍ přihlášen, ukážeme pouze přihlašovací okno
if not st.session_state.prihlasen:
    prihlaseni()
else:
    # --- ZDE ZAČÍNÁ SAMOTNÁ APLIKACE PO PŘIHLÁŠENÍ ---
    if st.sidebar.button("Odhlásit se 🚪"):
        st.session_state.prihlasen = False
        st.rerun()
        
    st.sidebar.write("---")

    CSV_FILE = "historie_skenu.csv"
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=["Čas", "Artikl", "Výsledek", "Detail"]).to_csv(CSV_FILE, index=False)

    def ziskej_seznam_vzoru():
        soubory = glob.glob("sablona_*.png")
        vzory = [f.replace("sablona_", "").replace(".png", "") for f in soubory]
        return vzory if vzory else ["Vzorový Box"]

    # --- BOČNÍ MENU ---
    st.sidebar.title("Navigace")
    volba = st.sidebar.radio("Přejít na:", ["Scan Box", "History", "Analytics", "Settings"])

    def zpracuj_obrazek(upload_file):
        if upload_file is not None:
            file_bytes = np.asarray(bytearray(upload_file.read()), dtype=np.uint8)
            return cv2.imdecode(file_bytes, 1)
        return None

    # --- 1. SCAN BOX ---
    if volba == "Scan Box":
        st.header("Skenování a Kontrola Pozice")
        dostupne_vzory = ziskej_seznam_vzoru()
        vybrany_artikl = st.selectbox("Vyber artikl, který jdeš kontrolovat:", dostupne_vzory)

        zdroj = st.radio("Vyber zdroj obrazu:", ["Nahrát soubor (Fotku)", "Použít webkameru"], horizontal=True)
        img_file = None
        
        if zdroj == "Nahrát soubor (Fotku)":
            img_file = st.file_uploader("Vyber fotku krabice ke kontrole", type=["png", "jpg", "jpeg"])
        else:
            img_file = st.camera_input("Zóna kamery")

        if img_file:
            frame = zpracuj_obrazek(img_file)
            if frame is not None:
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sablona_path = f'sablona_{vybrany_artikl}.png'
                
                if os.path.exists(sablona_path):
                    template = cv2.imread(sablona_path, cv2.IMREAD_GRAYSCALE)
                    w, h = template.shape[::-1]
                    
                    res = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)

                    MIN_SHODA = 0.70
                    OČEKÁVANÉ_X, OČEKÁVANÉ_Y = gray_frame.shape[1] // 2, gray_frame.shape[0] // 2
                    TOLERANCE = 60

                    stred_x = max_loc[0] + (w // 2)
                    stred_y = max_loc[1] + (h // 2)

                    if max_val >= MIN_SHODA:
                        rozdil_x = abs(stred_x - OČEKÁVANÉ_X)
                        rozdil_y = abs(stred_y - OČEKÁVANÉ_Y)

                        if rozdil_x <= TOLERANCE and rozdil_y <= TOLERANCE:
                            st.success(f"### 🎉 PASS \nArtikl [{vybrany_artikl}] je v pořádku. Shoda: {max_val*100:.1f}%")
                            novy_zaznam = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), vybrany_artikl, "PASS", "V pořádku"]
                        else:
                            st.error(f"### ❌ ERROR \nArtikl [{vybrany_artikl}] je posunutý! (Odchylka X: {rozdil_x}px, Y: {rozdil_y}px)")
                            novy_zaznam = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), vybrany_artikl, "ERROR", f"Posunuto o X:{rozdil_x} Y:{rozdil_y}"]
                    else:
                        st.error(f"### ❌ ERROR \nArtikl [{vybrany_artikl}] nebyl nalezen nebo chybí součástky!")
                        novy_zaznam = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), vybrany_artikl, "ERROR", "Nenalezeno"]
                    
                    df = pd.read_csv(CSV_FILE)
                    df.loc[len(df)] = novy_zaznam
                    df.to_csv(CSV_FILE, index=False)
                else:
                    st.warning(f"Pro artikl '{vybrany_artikl}' neexistuje soubor šablony. Vytvoř ho v Settings.")

    # --- 2. HISTORY ---
    elif volba == "History":
        st.header("📋 Historie skenů")
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            st.dataframe(df.iloc[::-1], use_container_width=True)
        else:
            st.info("Zatím nebyly provedeny žádné skeny.")

    # --- 3. ANALYTICS ---
    elif volba == "Analytics":
        st.header("📊 Statistiky kontrol")
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Celkem skenů", len(df))
            col2.metric("Dobré (PASS)", len(df[df["Výsledek"] == "PASS"]))
            col3.metric("Špatné (ERROR)", len(df[df["Výsledek"] == "ERROR"]))
            st.subheader("Graf výsledků")
            st.bar_chart(df["Výsledek"].value_counts())
        else:
            st.info("Žádná data pro analýzu.")

    # --- 4. SETTINGS ---
    elif volba == "Settings":
        st.header("⚙️ Správa vzorů a šablon")
        st.subheader("1. Vytvořit nebo přepsat vzor")
        nazev_novy = st.text_input("Zadej UNIKÁTNÍ název pro tento artikl:", "Vzorový Box")
        
        zdroj_sablony = st.radio("Vyber způsob zadání vzoru:", ["Nahrát fotku vzoru", "Vyfotit webkamerou"], horizontal=True)
        vzor_foto = None
        
        if zdroj_sablony == "Nahrát fotku vzoru":
            vzor_foto = st.file_uploader("Nahraj fotku ideálního boxu", type=["png", "jpg", "jpeg"])
        else:
            vzor_foto = st.camera_input("Vyfoť vzor")
            
        if vzor_foto:
            img = zpracuj_obrazek(vzor_foto)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape
                vyrez = gray[h//2-100:h//2+100, w//2-100:w//2+100]
                
                bezpecny_nazev = "".join([c for c in nazev_novy if c.isalpha() or c.isdigit() or c in " _-"]).strip()
                cv2.imwrite(f'sablona_{bezpecny_nazev}.png', vyrez)
                st.success(f"🎉 Vzor '{bezpecny_nazev}' byl úspěšně uložen!")
                
        st.write("---")
        st.subheader("2. Aktuálně uložené vzory v systému")
        st.write(ziskej_seznam_vzoru())