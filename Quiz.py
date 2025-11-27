import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from datetime import date
from googleapiclient.discovery import build
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import random
import base64

# === MAIN APP ===
def main():
    st.set_page_config(layout="wide")    

    def color(c):
        return np.array(colors[c])

    # --- Move function ---
    def move(direction):
        r, c = st.session_state.r, st.session_state.c
        if direction == "up":
            nr, nc = r - 1, c
        elif direction == "down":
            nr, nc = r + 1, c
        elif direction == "left":
            nr, nc = r, c - 1
        elif direction == "right":
            nr, nc = r, c + 1
        else:
            return

        if 0 <= nr < ROWS and 0 <= nc < COLS and maze[nr][nc] != "#":
            st.session_state.r, st.session_state.c = nr, nc

    # --- Viewport function ---
    def show_viewport():
        r, c = st.session_state.r, st.session_state.c
        view = np.zeros((3, 3, 3))
        for i, dr in enumerate([-1, 0, 1]):
            for j, dc in enumerate([-1, 0, 1]):
                rr = r + dr
                cc = c + dc
                if (rr, cc) == (r, c):
                    view[i, j] = color("P")
                elif 0 <= rr < ROWS and 0 <= cc < COLS:
                    view[i, j] = color(maze[rr][cc])
                else:
                    view[i, j] = color("#")
        fig, ax = plt.subplots(figsize=(2,2))
        ax.imshow(view)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig
    
    # --- Toegang ---
    # Auth status alleen aanmaken als die nog niet bestaat
    if "auth0" not in st.session_state:
        st.session_state.auth0 = False
    if "auth1" not in st.session_state:
        st.session_state.auth1 = False
    if "auth2" not in st.session_state:
        st.session_state.auth2 = False
    if "auth3" not in st.session_state:
        st.session_state.auth3 = False
    
    if not st.session_state.auth0:
        st.title('Welkom bij deze digitale quizmaster!')
        st.header('Belangrijke informatie:')
        st.write('ALLE VOORTGANG op deze site gaat verloren bij het herladen (refreshen) van deze pagina! \nBeter is het om op een knop (bijvoorbeeld een "Controleren"-knop) te klikken om te herladen of om de huidige pagina te ontdoen van de vorige. \nSoms kan ook het beeld verspringen, zoom even uit om te checken of dit het geval is. \nDit is een eigen-gemaakte website, niet alles werkt zo goed als ik zou willen :)...')
        st.write('Ondanks dat de site standaard uitgerust is met extra knoppen (rechtsboven als -onder), mag/hoef je deze niet te gebruiken. Bij het mogeljk niet functioneren van de site kunnen deze knoppen dit niet oplossen; neem contact op met Arnout :)')
        
        st.header('Codewoord om door te gaan:')
        password = st.text_input('Vul hieronder het 4-letterige codewoord in:', type="password", key="password_input0")
        if st.button("Controleren",key=0):
            if password.lower() == "muts":
                st.session_state.auth0 = True
                st.success("Correct!")
            else:
                st.error("Het codewoord is incorrect. Probeer het opnieuw.")

    if not st.session_state.auth1 and st.session_state.auth0:
        st.header('Ho-Ho-Holykwis')
        st.subheader('Wie krijgt welk cadeau, waar ligt deze en welke kleur inpakpapier is gebruikt?')
        st.write('LET OP: vul de antwoordregels in op volgorde van Anne-Bram-Clara. \n(De al weergegeven antwoorden zijn willekeurig gekozen en dienen aangepast te worden).')
        
        headers = ["Wie", "Waar", "Wat", "Welke kleur"]

        # Originele opties
        opties_origineel = {
            "Wie": ["Anne", "Bram", "Clara"],
            "Waar": ["Kerstkrans", "Kerstboom", "Kerststal"],
            "Wat": ["Kersttrui", "Kerstlampjes", "Kerstmok"],
            "Welke kleur": ["Geel", "Rood", "Groen"]}
        
        headers = list(opties_origineel.keys())

        # Maak een stabiele shuffle die niet opnieuw wordt gedaan
        if "gehusselde_opties" not in st.session_state:
            st.session_state.gehusselde_opties = {}
            for key, lijst in opties_origineel.items():
                nieuwe = lijst.copy()
                if key != 'Wie':
                    random.shuffle(nieuwe)
                st.session_state.gehusselde_opties[key] = nieuwe
        
        opties = st.session_state.gehusselde_opties   # Gebruik de versie die blijft bestaan

        # Bewaar ook de tabel-invoer in session_state zodat dat niet verspringt
        if "tabel" not in st.session_state:
            st.session_state.tabel = {rij: {kol: None for kol in headers} for rij in range(1, 4)}

        for row in range(1, 4):
            cols = st.columns(4)
            for i, kolom in enumerate(headers):
                st.session_state.tabel[row][kolom] = cols[i].selectbox(
                    f"{kolom} (rij {row})",
                    opties[kolom],
                    key=f"{kolom}_{row}"
                )
        
        tabel_data = st.session_state.tabel    
        correct_solution = {
            1: {"Wie": "Anne", "Waar": "Kerstkrans", "Wat": "Kersttrui", "Welke kleur": "Geel"},
            2: {"Wie": "Bram", "Waar": "Kerstboom", "Wat": "Kerstlampjes", "Welke kleur": "Rood"},
            3: {"Wie": "Clara", "Waar": "Kerststal", "Wat": "Kerstmok", "Welke kleur": "Groen"}}
        
        st.header("Controle:")
        if st.button("Controleren",key=1):
            alles_correct = True
            for rij in range(1, 4):
                for kolom in headers:
                    if tabel_data[rij][kolom] != correct_solution[rij][kolom]:
                        alles_correct = False
                        break
                if not alles_correct:
                    break
        
            if alles_correct:
                st.success("Correct!")
                st.session_state.auth1=True
            else:
                st.error("Probeer het opnieuw, er is minimaal 1 veld verkeerd ingevuld!")

    if not st.session_state.auth2 and (st.session_state.auth0 and st.session_state.auth1):
        st.header('Google Translates it')
        st.subheader('Geef de EERSTE LETTER van onderstaande omschrijvingen als antwoord (zet de artiesten van jong (A) naar oud (B)):')
        st.write('1. Eerste (artiesten)naam van persoon A \n2. Tweede (artiesten)naam van persoon A \n3. Eerste (artiesten)naam van persoon B \n4. Tweede (artiesten)naam van persoon B.')
        password = st.text_input('Vul hieronder de 4 letters in:', type="password", key="password_input2")
        if st.button("Controleren",key=2):
            if password.lower() == "esej":
                st.session_state.auth2 = True
                st.success("Correct!")
            else:
                st.error("Het is niet correct. Probeer het opnieuw.")
        
        # Bestand openen
        audio_file = open("10.Translate_liedtekst.mp3", "rb").read()
        audio_base64 = base64.b64encode(audio_file).decode()
        
        # HTML audio player met controls
        audio_player = f"""
        <audio id="myAudio" controls>
          <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
          Your browser does not support the audio element.
        </audio>
        <br>
        """

        st.markdown(audio_player, unsafe_allow_html=True)

    if not st.session_state.auth3 and (st.session_state.auth0 and st.session_state.auth1 and st.session_state.auth2):
        st.header('MedleyMistery')
        st.subheader('Raad het codewoord:')
        password = st.text_input('Vul hieronder het codewoord in:', type="password", key="password_input3")
        if st.button("Controleren",key=3):
            if password.lower() == "sneeuw":
                st.session_state.auth3 = True
                st.succes('Correct!')
            else:
                st.error("Het is niet correct. Probeer het opnieuw.")
        
        # Bestand openen
        audio_file = open("6.Muziekcompilatie.mp3", "rb").read()
        audio_base64 = base64.b64encode(audio_file).decode()
        
        # HTML audio player met controls
        audio_player = f"""
        <audio id="myAudio" controls>
          <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
          Your browser does not support the audio element.
        </audio>
        <br>
        """

        st.markdown(audio_player, unsafe_allow_html=True)
    
    if st.session_state.auth0 and st.session_state.auth1 and st.session_state.auth2 and st.session_state.auth3:
        # --- Placeholders ---
        viewport_placeholder = st.empty()
        controls_placeholder = st.empty()
       
        # --- MAZE ---
        maze = [
           "###############",
           "#S...#.#......#",
           "#.##.#.###.####",
           "#.#..#.#......#",
           "#.#.##.#.###.##",
           "#.#....#.#.#..#",
           "#.####.#.#.##.#",
           "#....###.#.#..#",
           "####.#...#...##",
           "#....#.#.#.#.##",
           "#.####.#.###.##",
           "#.#....#.#....#",
           "#.#.##.####.###",
           "#....##E......#",
           "###############"
        ]
    
        ROWS = len(maze)
        COLS = len(maze[0])
    
        # --- Colors ---
        colors = {
            "#": (0.1, 0.1, 0.1),
            ".": (1, 1, 1),
            "S": (0.2, 0.6, 1),
            "E": (1, 0.3, 0.3),
            "P": (1, 0.8, 0)}
    
        # --- Initialize session state ---
        if "r" not in st.session_state or "c" not in st.session_state:
            for r in range(ROWS):
                for c in range(COLS):
                    if maze[r][c] == "S":
                        st.session_state.r = r
                        st.session_state.c = c
        
        # --- Status / Titel ---
        st.header('Doolhof-je-zoek')
        st.subheader('Je kan slechts direct om je heen kijken (3x3) en het doolhof is 15×15 blokjes groot.')
        st.write('Blauw = start, geel = huidige locatie, rood = uitgang. Je hebt papier tot je beschikking ;)...')
        
        # --- Check exit ---
        if maze[st.session_state.r][st.session_state.c] == "E":
            # Maak volledig doolhof
            full_maze = np.zeros((ROWS, COLS, 3))
            for r in range(ROWS):
                for c in range(COLS):
                    full_maze[r, c] = colors[maze[r][c]]
    
            # Toon figuur
            fig, ax = plt.subplots(figsize=(8,8))
            ax.imshow(full_maze)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title("Volledig doolhof", fontsize=16)
            viewport_placeholder.pyplot(fig, use_container_width=True)
    
            # Doorgaan knop rechts onder
            col1, col2, col3 = st.columns([3,3,1])
            clicked=controls_placeholder.button("Je hebt de uitgang gevonden! \nKlik hier om door te gaan.",key=4)
            with col3:
                if clicked:
                    viewport_placeholder.empty()
                    controls_placeholder.empty(f'Je hebt de escaperoom verlaten, GEFELICITEERD! \nJe tijd is {datetime.now().strftime("%H:%M")}.')
    
        else:
            # --- Mobielvriendelijke joystick ---
            with controls_placeholder.container():
                st.markdown("""
                    <style>
                    div.stButton > button {
                        height: 60px;
                        width: 80px;
                        font-size: 40px;
                    }
                    </style>
                """, unsafe_allow_html=True)
    
                # Rij 1: Up
                c1, c2, c3 = st.columns([1,1,1])
                with c2:
                    if st.button("⬆️",key='4a'):
                        move("up")
                # Rij 2: Left, Down, Right
                c1, c2, c3 = st.columns([1,1,1])
                with c1:
                    if st.button("⬅️",key='4b'):
                        move("left")
                with c2:
                    if st.button("⬇️",key='4c'):
                        move("down")
                with c3:
                    if st.button("➡️",key='4d'):
                        move("right")
            # --- Toon lokale viewport ---
            fig = show_viewport()
            viewport_placeholder.pyplot(fig, use_container_width=True)
    
if __name__ == "__main__":
    main()
