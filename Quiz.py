import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from datetime import date
from googleapiclient.discovery import build

# === CONFIGURATION ===
HEADERS = ["Datum", "Kilometers", "Bestemming", "Reden"]  # Column headers
names = ["Arnout", "Astrid", 'Anders...']

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
    st.title("📋 Gegevens over mijn reis invoeren:")
    
    selected = st.selectbox("Wie: ", names)
    if selected == "Anders...":
        custom_name = st.text_input("Vul de naam in:")
        sheet_name = custom_name.strip()
    else:
        sheet_name = selected

    datum = st.date_input("Wanneer: ", value=date.today())
    formatted_datum = datum.strftime("%d-%m-%Y")

    kilometers = st.number_input("Hoeveel kilometers: ", min_value=0.0, format="%.1f", step=1.0,value=0.0)
    bestemming = st.text_input("Bestemming: ")
    reden = st.text_input("Waarom: ")
    
    # Authenticate gspread client
    client, creds = get_gspread_client()
    
    # Find latest spreadsheet in 'Kilometers' folder
    latest_file = get_latest_spreadsheet(creds=creds, folder_name='Kilometers')
    if latest_file:
        st.write(f"Gebruikt nieuwste spreadsheet: {latest_file['name']}")
        spreadsheet = client.open_by_key(latest_file['id'])
    else:
        st.warning("Geen spreadsheet gevonden in de 'Kilometers' map.")
        return

    # Get or create the worksheet (tab) inside spreadsheet
    sheet = get_or_create_sheet(spreadsheet, sheet_name)

    if st.button("Verzenden"):
        if not datum or not kilometers or not sheet_name:
            st.warning("Vul alle velden in.")
            return

        try:
            sheet.append_row([formatted_datum, kilometers, bestemming, reden])
            st.success(f"✅ Gegevens succesvol toegevoegd aan het tabblad: {sheet_name}")
        except Exception as e:
            st.error(f"❌ Fout bij het verzenden: {e}")

if __name__ == "__main__":
    main()
