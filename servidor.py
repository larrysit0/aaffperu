import os
import requests
import json
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

print("--- INICIO DEL SCRIPT ---")

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 🔐 TOKEN del bot y credenciales de Twilio (variables de entorno)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# URL de tu webapp en Railway
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://tu-app.up.railway.app")

if not TELEGRAM_BOT_TOKEN:
    print("--- ADVERTENCIA: TELEGRAM_BOT_TOKEN NO está configurado. ---")

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None
    print("--- ADVERTENCIA: Variables de Twilio NO configuradas. Las llamadas no funcionarán. ---")

COMUNIDADES_DIR = 'comunidades'

def load_community_json(comunidad_nombre):
    filepath = os.path.join(COMUNIDADES_DIR, f"{comunidad_nombre.lower()}.json")
    if not os.path.exists(filepath):
        print(f"--- Archivo JSON NO encontrado: {filepath} ---")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            comunidad_info = json.load(f)
            return comunidad_info
    except Exception as e:
        print(f"--- ERROR al cargar '{filepath}': {e} ---")
        return None

def get_user_community(user_id):
    """Busca en qué comunidad está registrado el usuario"""
    for filename in os.listdir(COMUNIDADES_DIR):
        if filename.endswith('.json'):
            comunidad_nombre = filename[:-5]  # Remover .json
            comunidad_info = load_community_json(comunidad_nombre)
            if comunidad_info:
                miembros = comunidad_info.get('miembros', [])
                for miembro in miembros:
                    if str(miembro.get('telegram_id')) == str(user_id):
                        return comunidad_nombre
    return None

@app.route('/healthz')
def health_check():
    return "OK", 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/comunidad/<comunidad>', methods=['GET'])
def get_comunidad_data(comunidad):
    comunidad_info = load_community_json(comunidad)
    if comunidad_info:
        return jsonify(comunidad_info)
    return jsonify({}), 404

@app.route('/api/alert', methods=['POST'])
def handle_alert():
    print("--- Alerta recibida (POST). ---")
    data = request.json
    
    comunidad_nombre = data.get('comunidad')
    user_telegram = data.get('user_telegram', {})
    user_name = user_telegram.get('first_name', 'Anónimo')
    
    print(f"--- Alerta activada por: {user_name} en la comunidad: {comunidad_nombre} ---")

    if not comunidad_nombre:
        return jsonify({"error": "Nombre de comunidad no proporcionado"}), 400

    comunidad_info = load_community_json(comunidad_nombre)
    if not comunidad_info:
        return jsonify({"error": f"Comunidad '{comunidad_nombre}' no encontrada"}), 404

    chat_id = comunidad_info.get('chat_id')
    miembros = comunidad_info.get('miembros', [])

    if not chat_id:
        return jsonify({"error": "ID del chat de Telegram no configurado para esta comunidad"}), 500

    lat = data.get('ubicacion', {}).get('lat')
    lon = data.get('ubicacion', {}).get('lon')
    map_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" if lat and lon else "Ubicación no disponible"
    user_id = user_telegram.get('id', 'N/A')
    user_mention = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    tipo = data.get('tipo', 'Alerta no especificada')
    descripcion = data.get('descripcion', 'Sin descripción')
    direccion = data.get('direccion', 'Dirección no disponible')

    miembros_a_notificar = [m for m in miembros if m.get('alertas_activadas') and str(m.get('telegram_id')) != str(user_id)]
    
    if miembros_a_notificar:
        print("--- Enviando alertas privadas a miembros... ---")
        for miembro in miembros_a_notificar:
            id_miembro = miembro.get('telegram_id')
            nombre_miembro = miembro.get('nombre', 'miembro')
            mensaje_privado = (
                f"<b>🚨 ALERTA DE EMERGENCIA 🚨</b>\n"
                f"<b>Tipo:</b> {tipo}\n"
                f"<b>Comunidad:</b> {comunidad_nombre.upper()}\n"
                f"<b>Usuario que activó la alarma:</b> {user_mention}\n"
                f"<b>Descripción:</b> {descripcion}\n"
                f"<b>Ubicación:</b> <a href='{map_link}'>Ver en Google Maps</a>\n"
                f"<b>Dirección:</b> {direccion}\n\n"
                f"¡{nombre_miembro}, por favor, revisa el grupo para más detalles!"
            )
            send_telegram_message(id_miembro, mensaje_privado)
    
    if twilio_client and TWILIO_PHONE_NUMBER:
        print("--- Iniciando llamadas telefónicas. ---")
        for miembro in miembros_a_notificar:
            numero_telefono = miembro.get('telefono')
            if numero_telefono:
                print(f"--- Llamando a un miembro de la comunidad... ---")
                try:
                    make_phone_call(numero_telefono)
                except Exception as e:
                    print(f"--- ERROR al hacer llamada: {e} ---")

    mensaje_grupo = (
        f"<b>🚨 ALERTA ROJA ACTIVADA EN LA COMUNIDAD {comunidad_nombre.upper()}</b>\n"
        f"<b>Activada por:</b> {user_mention}\n"
        f"<b>Descripción:</b> {descripcion}\n"
        f"<b>Ubicación:</b> <a href='{map_link}'>Ver en Google Maps</a>\n"
        f"<b>Dirección:</b> {direccion}\n\n"
        f"ℹ️ Se han enviado notificaciones a los miembros registrados y se ha iniciado el protocolo de llamadas."
    )
    send_telegram_message(chat_id, mensaje_grupo)

    print("--- Alerta procesada exitosamente. ---")
    return jsonify({"status": "Alerta enviada."})

def make_phone_call(to_number):
    global twilio_client, TWILIO_PHONE_NUMBER
    mensaje_voz = "Emergencia, revisa tu celular."
    response = VoiceResponse()
    response.say(mensaje_voz, voice='woman', language='es-ES')
    try:
        call = twilio_client.calls.create(
            twiml=str(response),
            to=to_number,
            from_=TWILIO_PHONE_NUMBER
        )
    except Exception:
        raise

def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"--- Mensaje enviado exitosamente a {chat_id}. ---")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"--- ERROR al enviar mensaje a {chat_id}: {e} ---")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.json
        print(f"--- Webhook recibido: {update} ---")
        
        message = update.get('message')
        if message:
            chat_id = message['chat']['id']
            user = message['from']
            user_id = user['id']
            user_name = user.get('first_name', 'Usuario')
            text = message.get('text', '').lower().strip()
            
            print(f"--- Mensaje recibido de {user_name} (ID: {user_id}): {text} ---")
            
            # Comando SOS para abrir la webapp de emergencia
            if text == 'sos':
                print(f"--- Comando SOS detectado de usuario {user_id} ---")
                
                # Buscar la comunidad del usuario
                comunidad = get_user_community(user_id)
                
                if comunidad:
                    # Crear URL de la webapp con parámetros del usuario y comunidad
                    webapp_url = f"{WEBAPP_URL}?comunidad={comunidad}&id={user_id}&first_name={user.get('first_name', '')}&last_name={user.get('last_name', '')}&username={user.get('username', '')}"
                    
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "🚨 ACTIVAR EMERGENCIA 🚨",
                                    "web_app": { "url": webapp_url }
                                }
                            ]
                        ]
                    }
                    
                    mensaje = (
                        f"🚨 <b>SISTEMA DE EMERGENCIA ACTIVADO</b> 🚨\n\n"
                        f"Hola {user_name}, has activado el sistema de emergencia de la comunidad <b>{comunidad.upper()}</b>.\n\n"
                        f"Presiona el botón de abajo para abrir la webapp de emergencia y describir la situación.\n\n"
                        f"⚠️ <b>IMPORTANTE:</b> Solo usa este sistema en caso de emergencia real."
                    )
                    
                    send_telegram_message(chat_id, mensaje, reply_markup=reply_markup)
                    
                else:
                    # Usuario no registrado en ninguna comunidad
                    mensaje = (
                        f"❌ <b>Usuario no registrado</b>\n\n"
                        f"Hola {user_name}, no estás registrado en ninguna comunidad.\n\n"
                        f"Contacta al administrador de tu comunidad para ser registrado en el sistema de emergencias."
                    )
                    send_telegram_message(chat_id, mensaje)
            
            # Comando para obtener ID (como tenías antes)
            elif text == 'miregistro':
                webapp_url = f"{WEBAPP_URL}?modo=registro"
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Obtener mi ID",
                                "web_app": { "url": webapp_url }
                            }
                        ]
                    ]
                }
                mensaje = "Presiona el botón para obtener tu ID de Telegram."
                send_telegram_message(chat_id, mensaje, reply_markup=reply_markup)
            
            # Comando de ayuda
            elif text in ['/start', '/help', 'ayuda']:
                mensaje = (
                    f"👋 <b>Bienvenido al Sistema de Emergencias</b>\n\n"
                    f"Comandos disponibles:\n"
                    f"• <b>sos</b> - Activar sistema de emergencia\n"
                    f"• <b>miregistro</b> - Obtener tu ID de Telegram\n"
                    f"• <b>ayuda</b> - Mostrar esta ayuda\n\n"
                    f"⚠️ El comando 'sos' solo funciona si estás registrado en una comunidad."
                )
                send_telegram_message(chat_id, mensaje)
                
    except Exception as e:
        print(f"--- ERROR GENERAL en el webhook: {e} ---")
    
    return jsonify({"status": "ok"}), 200

@app.route('/api/register', methods=['POST'])
def register_id():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        if telegram_id:
            return jsonify({"status": "ID recibido y registrado."}), 200
        else:
            return jsonify({"error": "ID no proporcionado"}), 400
    except Exception as e:
        return jsonify({"error": "Error interno del servidor"}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
