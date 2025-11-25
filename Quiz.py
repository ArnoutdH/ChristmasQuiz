import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from datetime import date
from googleapiclient.discovery import build
import numpy as np
import matplotlib.pyplot as plt
import timeit
import random
import base64

# === AUTHENTICATION ===
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]

    scope = ["https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds), creds

# === DRIVE API: Find latest spreadsheet in folder ===
def get_latest_spreadsheet(creds, folder_name):
    drive_service = build('drive', 'v3', credentials=creds)

    # 🔄 Search folder by name, anywhere (not just in root)
    query_folder = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed = false"
    )
    folder_results = drive_service.files().list(q=query_folder, fields="files(id, name)").execute()
    folders = folder_results.get('files', [])

    if not folders:
        st.error(f"📁 Folder '{folder_name}' not found. Make sure it's shared with the service account.")
        return None

    folder_id = folders[0]['id']

    # Spreadsheet search stays the same...
    mime_types = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/vnd.google-apps.spreadsheet']
    mime_query = " or ".join([f"mimeType='{mime}'" for mime in mime_types])
    query_files = f"'{folder_id}' in parents and ({mime_query}) and trashed = false"

    files_results = drive_service.files().list(
        q=query_files,
        orderBy="createdTime desc",
        fields="files(id, name, createdTime)",
        pageSize=1
    ).execute()

    files = files_results.get('files', [])
    if not files:
        st.error("📄 No spreadsheets found in the folder.")
        return None

    return files[0]  

# === SPREADSHEET MANAGEMENT ===
def get_or_create_sheet(spreadsheet, sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
    except :
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        sheet.append_row(HEADERS)
    return sheet

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

    # --- Placeholders ---
    title_placeholder = st.empty()
    viewport_placeholder = st.empty()
    controls_placeholder = st.empty()
    
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
        title_placeholder.markdown('Welkom bij deze digitale quizmaster!')
        password = st.text_input('Vul hieronder het 4-letterige codewoord in:', type="password", key="password_input0")
        if st.button("Controleren"):
            if password.lower() == "muts":
                st.session_state.auth0 = True
            else:
                st.error("Het codewoord is incorrect. Probeer het opnieuw.")

    if not st.session_state.auth1 and st.session_state.auth0:
        title_placeholder.markdown('Vul de logikwis-oplossing in:')
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
                random.shuffle(nieuwe)
                st.session_state.gehusselde_opties[key] = nieuwe
        
        opties = st.session_state.gehusselde_opties   # Gebruik de versie die blijft bestaan

        # Bewaar ook de tabel-invoer in session_state zodat dat niet verspringt
        if "tabel" not in st.session_state:
            st.session_state.tabel = {rij: {kol: None for kol in headers} for rij in range(1, 4)}

        st.subheader("Vul je oplossing in")

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
        
        st.header("Controle")
        if st.button("Controleer oplossing:")
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
        st.header('Geef de EERSTE LETTER van onderstaande omschrijvingen als antwoord (zet de artiesten van jong (A) naar oud (B)):')
        st.write('1. Eerste (artiesten)naam van persoon A \n2. Tweede (artiesten)naam van persoon A \n3. Eerste (artiesten)naam van persoon B \n4. Tweede (artiesten)naam van persoon B.')
        password = st.text_input('Vul hieronder de 4 letters in:', type="password", key="password_input2")
        if st.button("Controleren"):
            if password.lower() == "esej":
                st.session_state.auth2 = True
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
        <button onclick="document.getElementById('myAudio').play()">▶️ Play</button>
        <button onclick="document.getElementById('myAudio').pause()">⏸️ Pauze</button>
        <button onclick="document.getElementById('myAudio').currentTime=0; document.getElementById('myAudio').pause()">🔄 Reset</button>
        """

        st.markdown(audio_player, unsafe_allow_html=True)

    if not st.session_state.auth3 and (st.session_state.auth0 and st.session_state.auth1 and st.session_state.auth2):
        st.header('Geef het codewoord hieronder op:')
        password = st.text_input('Vul hieronder het codewoord in:', type="password", key="password_input3")
        if st.button("Controleren"):
            if password.lower() == "sneeuw":
                st.session_state.auth3 = True
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
        <button onclick="document.getElementById('myAudio').play()">▶️ Play</button>
        <button onclick="document.getElementById('myAudio').pause()">⏸️ Pauze</button>
        <button onclick="document.getElementById('myAudio').currentTime=0; document.getElementById('myAudio').pause()">🔄 Reset</button>
        """

        st.markdown(audio_player, unsafe_allow_html=True)



    
    if st.session_state.auth0 and st.session_state.auth1 and st.session_state.auth2 and st.session_state.auth3:
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
        title_placeholder.markdown("""
        ### Vind de uitgang van het doolhof
        Let op: je kan slechts direct om je heen kijken. Het doolhof is 15×15 groot.  
        **Blauw = start, geel = huidige locatie, rood = uitgang.**
        """)
    
        # --- Check exit ---
        if maze[st.session_state.r][st.session_state.c] == "E":
            # Wis oude viewport en controls
            controls_placeholder.empty()
    
            # Update titel/status
            title_placeholder.markdown("Je hebt de uitgang gevonden!")
    
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
            clicked=controls_placeholder.button("➡️ Doorgaan")
            with col3:
                if clicked:
                    viewport_placeholder.empty()
                    controls_placeholder.empty()
                    title_placeholder.title(f'Je hebt de escaperoom verlaten, GEFELICITEERD! \nJe tijd is {timeit.timeit()}.')
    
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
                    if st.button("⬆️"):
                        move("up")
                # Rij 2: Left, Down, Right
                c1, c2, c3 = st.columns([1,1,1])
                with c1:
                    if st.button("⬅️"):
                        move("left")
                with c2:
                    if st.button("⬇️"):
                        move("down")
                with c3:
                    if st.button("➡️"):
                        move("right")
            # --- Toon lokale viewport ---
            fig = show_viewport()
            viewport_placeholder.pyplot(fig, use_container_width=True)
    
if __name__ == "__main__":
    main()
