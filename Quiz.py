import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from datetime import date
from googleapiclient.discovery import build
import numpy as np
import matplotlib.pyplot as plt

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
    
    # --- Colors for visualization ---
    colors = {
        "#": (0.1, 0.1, 0.1),
        ".": (1, 1, 1),
        "S": (0.2, 0.6, 1),
        "E": (1, 0.3, 0.3),
        "P": (1, 0.8, 0),
    }
    
    def color(c):
        return np.array(colors[c])
    
    # --- Init session state ---
    if "r" not in st.session_state:
        # find start
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c] == "S":
                    st.session_state.r = r
                    st.session_state.c = c
    
    # --- View functie ---
    def show():
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
    
        # figuur kleiner maken en automatisch containerbreedte gebruiken
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.imshow(view)
        ax.set_xticks([])
        ax.set_yticks([])
        st.pyplot(fig, use_container_width=True)
    
    # --- Titel ---
    st.title("Vind de uitgang van het doolhof.")
    st.write("Let op: je kan slechts direct om je heen kijken. Het doolhof is 15×15 groot.")
    st.write("**Blauw = start, geel = huidige locatie, rood = uitgang.**")
    
    # --- Viewport tonen ---
    show()
    
    # --- Mobielvriendelijke joystick controls ---
    st.write("### Besturing")
    
    # Voeg een container toe met een max-width zodat alles netjes past op mobiel
    with st.container():
        # Gebruik CSS om knoppen groot en mobielvriendelijk te maken
        st.markdown("""
            <style>
            div.stButton > button {
                height: 60px;
                font-size: 24px;
            }
            </style>
        """, unsafe_allow_html=True)
    
        # Rij 1: ⬆️
        c1, c2, c3 = st.columns([1,1,1])
        with c2:
            if st.button("⬆️"):
                nr, nc = st.session_state.r - 1, st.session_state.c
                if maze[nr][nc] != "#":
                    st.session_state.r, st.session_state.c = nr, nc
    
        # Rij 2: ⬅️ ⬇️ ➡️
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            if st.button("⬅️"):
                nr, nc = st.session_state.r, st.session_state.c - 1
                if maze[nr][nc] != "#":
                    st.session_state.r, st.session_state.c = nr, nc
    
        with c2:
            if st.button("⬇️"):
                nr, nc = st.session_state.r + 1, st.session_state.c
                if maze[nr][nc] != "#":
                    st.session_state.r, st.session_state.c = nr, nc
    
        with c3:
            if st.button("➡️"):
                nr, nc = st.session_state.r, st.session_state.c + 1
                if maze[nr][nc] != "#":
                    st.session_state.r, st.session_state.c = nr, nc
    
    # --- Check exit ---
    if maze[st.session_state.r][st.session_state.c] == "E":
        st.success("🎉 JE HEBT DE UITGANG GEVONDEN! 🎉")
    
        # Maak een numpy-array van het volledige doolhof
        img = np.zeros((ROWS, COLS, 3))
        for r in range(ROWS):
            for c in range(COLS):
                img[r, c] = colors[maze[r][c]]
    
        # ---- Figuur bijna schermvullend en mobielvriendelijk ----
        fig, ax = plt.subplots(figsize=(8, 8))  # groot op desktop
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title("Volledig doolhof", fontsize=16)
    
        # Gebruik containerbreedte zodat het op mobiel past
        st.pyplot(fig, use_container_width=True)
    
        # ---- Doorgaan knop rechts-onder ----
        # Plaats knop in een container met drie kolommen, knop in rechterkolom
        col1, col2, col3 = st.columns([3, 3, 1])
        with col3:
            if st.button("➡️ Doorgaan"):
                st.session_state.r = 0  # voorbeeld: reset speler
                st.session_state.c = 0
                st.experimental_rerun()  # herlaad pagina of ga naar volgende stap


if __name__ == "__main__":
    main()
