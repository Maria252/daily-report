import os
import requests
import datetime

#########################################
# Variables de entorno esperadas:
# NOTION_API_KEY          -> Token secreto de Notion
# NOTION_DATABASE_ID      -> ID de la base de datos Notion que contiene las tareas 
# GOOGLE_CALENDAR_API_KEY -> Clave o token para Google Calendar 
# TEAMS_WEBHOOK_URL       -> Webhook de Microsoft Teams 
#########################################

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
GOOGLE_CALENDAR_API_KEY = os.environ.get("GOOGLE_CALENDAR_API_KEY", "")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

def get_notion_tasks():
    """
    Obtiene tareas desde una base de datos de Notion.
    Retorna una lista de dicts, cada uno con 'titulo' y 'fecha' (formato YYYY-MM-DD).
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # Ajusta 'filter' o 'sort' según tus necesidades
    data = {}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    results = response.json().get("results", [])

    tareas = []
    for page in results:
        # Aquí debes extraer la propiedad que contenga el título
        # y la propiedad que contenga la fecha (Due Date).
        # Ejemplo ficticio:

        titulo = "Sin título"
        fecha_iso = None

        # Supongamos que tienes una propiedad "Name" tipo título:
        if "Name" in page["properties"]:
            titulo_rich = page["properties"]["Name"].get("title", [])
            if len(titulo_rich) > 0:
                titulo = titulo_rich[0]["plain_text"]

        # Supongamos que tienes una propiedad "DueDate" tipo date:
        if "DueDate" in page["properties"]:
            date_prop = page["properties"]["DueDate"].get("date", {})
            fecha_iso = date_prop.get("start")  # e.g. '2025-03-26'

        # Si no hay fecha, podrías saltar o poner un valor por defecto
        if fecha_iso:
            tareas.append({
                "titulo": titulo,
                "fecha": fecha_iso[:10]  # YYYY-MM-DD
            })

    return tareas

def get_google_calendar_events():
    """
    Obtiene eventos desde Google Calendar (versión simplificada).
    Retorna lista de dicts con 'titulo' y 'fecha' (YYYY-MM-DD).
    """
    # En la práctica, usarías la API oficial de Google con OAuth o una API key
    # Esto es solo un placeholder de ejemplo.

    # Ejemplo: supongamos que tienes un endpoint o ya la respuesta parseada:
    eventos = [
        # Simulando dos eventos: uno de hoy, otro de ayer
        {"titulo": "Reunión con equipo", "fecha": "2025-03-25"},
        {"titulo": "Presentación de resultados", "fecha": "2025-03-26"},
    ]

    return eventos

def separar_ayer_hoy(lista):
    """
    Separa una lista de dicts [{'titulo': '...', 'fecha': 'YYYY-MM-DD'}, ...]
    en dos listas: (ayer_list, hoy_list).
    """
    hoy = datetime.date.today()           # p.ej. 2025-03-26
    ayer = hoy - datetime.timedelta(days=1)

    ayer_list = []
    hoy_list = []

    for elemento in lista:
        fecha_iso = elemento["fecha"]     # e.g. '2025-03-26'
        fecha_dt = datetime.date.fromisoformat(fecha_iso)  # datetime.date(2025,3,26)

        if fecha_dt == ayer:
            ayer_list.append(elemento["titulo"])
        elif fecha_dt == hoy:
            hoy_list.append(elemento["titulo"])

    return (ayer_list, hoy_list)

# 5.4 Función para enviar datos a Power Automate (Teams Chat)
def enviar_a_power_automate(mensaje):
    teams_flow_url = os.environ.get("TEAMS_FLOW_URL", "")
    if not teams_flow_url:
        print("No hay TEAMS_FLOW_URL configurado.")
        return

    payload = {
        "mensaje": mensaje,
        "autor": "Python Script"
    }

    resp = requests.post(teams_flow_url, json=payload)
    if resp.status_code < 300:
        print("Mensaje enviado a Power Automate con éxito.")
    else:
        print(f"Error al enviar mensaje: {resp.text}")

def main():
    # 1) Obtener tareas de Notion
    tareas_notion = get_notion_tasks()
    # 2) Obtener eventos del calendario
    eventos_calendar = get_google_calendar_events()

    # 3) Unir ambas listas si quieres procesarlas en conjunto
    todos = tareas_notion + eventos_calendar

    # 4) Separar en listas de ayer y hoy
    ayer_list, hoy_list = separar_ayer_hoy(todos)

    # 5) Construir mensaje
    mensaje = "¿Qué completé ayer?\n"
    if ayer_list:
        mensaje += "\n".join(f"- {t}" for t in ayer_list)
    else:
        mensaje += "- Ninguna tarea/evento ayer"

    mensaje += "\n\n¿En qué trabajaré hoy?\n"
    if hoy_list:
        mensaje += "\n".join(f"- {t}" for t in hoy_list)
    else:
        mensaje += "- Ninguna tarea/evento hoy"

    mensaje += "\n\n¿Tienes algún obstáculo o necesitas ayuda?\nNo."

    # 6) Enviar a Teams
    enviar_a_power_automate(mensaje)

    print("Script ejecutado correctamente")

if __name__ == "__main__":
    main()
