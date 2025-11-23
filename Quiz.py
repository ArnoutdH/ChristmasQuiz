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
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

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

    # --- Colors ---
    colors = {
        "#": (0.1, 0.1, 0.1),
        ".": (1, 1, 1),
        "S": (0.2, 0.6, 1),
        "E": (1, 0.3, 0.3),
        "P": (1, 0.8, 0),
    }

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

    # --- Initialize session state ---
    if "r" not in st.session_state or "c" not in st.session_state:
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c] == "S":
                    st.session_state.r = r
                    st.session_state.c = c

    # --- Placeholders ---
    title_placeholder = st.empty()
    viewport_placeholder = st.empty()
    controls_placeholder = st.empty()
    
    # --- Toegang ---
    title_placeholder.title('Vul hieronder het 4-letterige wachtwoord in:')
    ww=st.text_input('')
    while ww.lower() != muts:
        viewport_placeholder.markdown('Het wachtwoord is NIET correct, probeer het opnieuw.')
        ww=st.text_input('')
    viewport_placeholder=st.empty()
    
    # --- Status / Titel ---
    title_placeholder.markdown("""
    ### Vind de uitgang van het doolhof
    Let op: je kan slechts direct om je heen kijken. Het doolhof is 15×15 groot.  
    **Blauw = start, geel = huidige locatie, rood = uitgang.**
    """)

    # --- Check exit ---
    if maze[st.session_state.r][st.session_state.c] == "E":
        # Wis oude viewport en controls
        title_placeholder.empty()
        controls_placeholder.empty()

        # Update titel/status
        title_placeholder.markdown("🎉 JE HEBT DE UITGANG GEVONDEN! 🎉")

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
                title_placeholder.title('Je hebt de escaperoom verlaten, GEFELICITEERD! \nJe tijd is opgeslagen.')

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
