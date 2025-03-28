import os
from notion_client import Client
from datetime import datetime, date, timedelta
import pytz
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from google.auth.transport.requests import Request
import json

#########################################
# Variables de entorno esperadas:
# NOTION_API_KEY                  -> Token secreto de Notion
# NOTION_DATABASE_ID              -> ID de la base de datos Notion que contiene las tareas
# GOOGLE_CALENDAR_API_KEY         -> Clave o token para Google Calendar
# TEAMS_WEBHOOK_URL               -> Webhook de Microsoft Teams
# GOOGLE_CALENDAR_CREDENTIALS_JSON -> Contenido del archivo credentials.json
#########################################

load_dotenv()

# Lee los valores de los secrets (variables de entorno)
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
GOOGLE_CALENDAR_CREDENTIALS_JSON = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_JSON", "")

# Crea un archivo credentials.json usando el contenido almacenado en el secret
if GOOGLE_CALENDAR_CREDENTIALS_JSON:
    with open('credentials.json', 'w') as f:
        f.write(GOOGLE_CALENDAR_CREDENTIALS_JSON)

def get_notion_tasks():
    """
    Obtiene tareas de una base de datos Notion con propiedades:
      - 'Task' (title)
      - 'Due Date' (date)
      - 'Complete' (checkbox)

    Retorna lista de dicts con:
      {
        "titulo": str or "(Sin título)",
        "fecha": str (YYYY-MM-DD) or None,
        "complete": bool
      }
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    print(f"URL Notion: {url}") 
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    data = {}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    results = response.json().get("results", [])
    tareas = []

    for page in results:
        prop_task = page["properties"].get("Task", {})
        title_entries = prop_task.get("title", [])
        if len(title_entries) > 0:
            titulo = title_entries[0]["plain_text"]
        else:
            titulo = "(Sin título)"

        fecha_iso = None
        prop_due = page["properties"].get("Due Date", {})
        if prop_due.get("type") == "date":
            date_dict = prop_due.get("date")
            if date_dict:
                fecha_iso = date_dict.get("start")

        esta_completa = False
        prop_complete = page["properties"].get("Complete", {})
        if prop_complete.get("type") == "checkbox":
            esta_completa = prop_complete.get("checkbox", False)

        tareas.append({
            "titulo": titulo,
            "fecha": fecha_iso[:10] if fecha_iso else None,
            "complete": esta_completa
        })

    return tareas

# Alcance para Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_google_calendar_service():
    """Autentica con Google Calendar sin abrir un navegador en GitHub Actions."""
    creds = None
    credentials_json = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON")

    if not credentials_json:
        raise ValueError("❌ ERROR: La variable de entorno GOOGLE_CALENDAR_CREDENTIALS_JSON no está definida.")

    # Convertir el JSON almacenado en una variable de entorno a un diccionario
    creds_data = json.loads(credentials_json)

    # Crear flujo de autenticación
    flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)

    # Ejecutar la autenticación sin interfaz gráfica
    creds = flow.run()  

    return creds

def get_calendar_id_by_summary(service, summary_name="Calendario"):
    """
    Retrieves the calendar ID for a calendar with the given summary (name).
    Returns the calendar ID if found; otherwise, returns None.
    """
    calendar_list = service.calendarList().list().execute()
    for calendar in calendar_list.get("items", []):
        if calendar.get("summary") == summary_name:
            return calendar.get("id")
    return None

def get_google_calendar_events_yesterday_today():
    """
    Fetches events from the Google Calendar named 'Calendario'
    between yesterday 00:00:00 UTC and today 23:59:59 UTC.
    Returns a list of dicts with {'titulo': '...', 'fecha': 'YYYY-MM-DD'}.
    """
    service = get_google_calendar_service()
    calendar_id = get_calendar_id_by_summary(service, "Calendario")
    if not calendar_id:
        print("Calendar 'Calendario' not found.")
        return []

    now_utc = datetime.utcnow()
    today_00_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_00_utc = today_00_utc - timedelta(days=1)
    today_23_59_utc = today_00_utc + timedelta(days=1, seconds=-1)

    time_min = yesterday_00_utc.isoformat() + 'Z'
    time_max = today_23_59_utc.isoformat() + 'Z'
    print("Fetching events from:", time_min, "to:", time_max)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    items = events_result.get('items', [])
    results = []
    for ev in items:
        summary = ev.get('summary', 'Sin título')
        start = ev['start'].get('dateTime', ev['start'].get('date'))
        date_str = start[:10] if start else None
        results.append({"titulo": summary, "fecha": date_str})
    return results

def get_google_calendar_events():
    """
    Example function to fetch the upcoming events from the Google Calendar named 'Calendario'.
    Returns a list of dicts with {'titulo': '...', 'fecha': 'YYYY-MM-DD'}.
    """
    service = get_google_calendar_service()
    calendar_id = get_calendar_id_by_summary(service, "Calendario")
    if not calendar_id:
        print("Calendar 'Calendario' not found.")
        return []

    now = datetime.utcnow().isoformat() + 'Z'
    print("Getting the upcoming 10 events from current time:", now)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    results = []
    for ev in events:
        summary = ev.get('summary', 'Sin título')
        start = ev['start'].get('dateTime', ev['start'].get('date'))
        fecha_str = start[:10] if start else None
        results.append({"titulo": summary, "fecha": fecha_str})
    return results

def separar_ayer_hoy(lista):
    """
    Separa una lista de diccionarios [{'titulo': '...', 'fecha': 'YYYY-MM-DD'}, ...]
    en dos listas: una para eventos de ayer y otra para eventos de hoy.
    Ignora los elementos que no tengan una fecha válida.
    """
    hoy = date.today()
    ayer = hoy - timedelta(days=1)

    ayer_list = []
    hoy_list = []

    for elemento in lista:
        fecha_iso = elemento.get("fecha")
        if not fecha_iso:
            continue

        try:
            fecha_dt = date.fromisoformat(fecha_iso)
        except ValueError:
            continue

        if fecha_dt == ayer:
            ayer_list.append(elemento["titulo"])
        elif fecha_dt == hoy:
            hoy_list.append(elemento["titulo"])

    return (ayer_list, hoy_list)

def enviar_a_power_automate(mensaje):
    """
    Envía un mensaje a Power Automate para que lo publique en Teams
    usando el webhook configurado.
    """
    if not TEAMS_WEBHOOK_URL:
        print("❌ TEAMS_WEBHOOK_URL no está configurado.")
        return
    
    mensaje = mensaje.replace('"', '')

    payload = {
        "mensaje": mensaje,
        "autor": "Maria Paula Diaz"
    }

    print("Payload a enviar:", payload)
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(TEAMS_WEBHOOK_URL, json=payload, headers=headers)
        response.raise_for_status()
        print("✅ Mensaje enviado correctamente a Teams.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar mensaje: {e}")
        if response is not None:
            print(f"🔍 Respuesta del servidor: {response.text}")

def main():
    # 1) Obtener tareas de Notion
    tareas_notion = get_notion_tasks()
    # 2) Obtener eventos del calendario
    eventos_calendar = get_google_calendar_events_yesterday_today()

    # 3) Unir ambas listas
    todos = tareas_notion + eventos_calendar

    # 4) Separar en listas de ayer y hoy
    ayer_list, hoy_list = separar_ayer_hoy(todos)

    # 5) Construir mensaje
    mensaje = (
        "**¿Qué completé ayer?**\n\n" +
        ("- " + "\n- ".join(ayer_list) if ayer_list else "Ninguna tarea/evento ayer") + "\n\n" +
        "**¿En qué trabajaré hoy?**\n\n" +
        ("- " + "\n- ".join(hoy_list) if hoy_list else "Ninguna tarea/evento hoy") + "\n\n" +
        "**¿Tienes algún obstáculo o necesitas ayuda?**\n\n" +
        "No."
    )

    # 6) Enviar a Teams
    enviar_a_power_automate(mensaje)

    print("Script ejecutado correctamente")

if __name__ == "__main__":
    main()
