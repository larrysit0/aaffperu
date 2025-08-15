from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from datetime import datetime
import os
import json
import requests

# 📦 Twilio para llamadas
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)
CORS(app)

# 📁 Carpeta con los datos de las comunidades
DATA_FILE = os.path.join(os.path.dirname(__file__), 'comunidades')

# 🔑 Credenciales Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')

# 🤖 Token de tu bot de Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 🌐 URL base de tu servidor (cambiar por tu dominio real)
BASE_URL = os.getenv('BASE_URL', 'https://tu-servidor.com')

# 🎯 Cliente Twilio
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# 📝 Diccionario temporal para almacenar el usuario que activó SOS
usuarios_sos_activos = {}

# 🌐 Página principal
@app.route('/')
def index():
    return render_template('index.html')

# 🔍 Lista de comunidades
@app.route('/api/comunidades')
def listar_comunidades():
    comunidades = []
    if os.path.exists(DATA_FILE):
        for archivo in os.listdir(DATA_FILE):
            if archivo.endswith('.json'):
                comunidades.append(archivo.replace('.json', ''))
    return jsonify(comunidades)

# 📍 Ubicaciones de una comunidad
@app.route('/api/ubicaciones/<comunidad>')
def ubicaciones_de_comunidad(comunidad):
    path = os.path.join(DATA_FILE, f"{comunidad}.json")
    if not os.path.exists(path):
        return jsonify({"error": "Comunidad no encontrada"}), 404
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict):
        return jsonify(data.get("miembros", []))
    else:
        return jsonify(data)

# 🚨 Alerta roja
@app.route('/api/alert', methods=['POST'])
def recibir_alerta():
    data = request.get_json()
    print("📦 Datos recibidos:", data)

    tipo = data.get('tipo')
    descripcion = data.get('descripcion')
    ubicacion = data.get('ubicacion', {})
    direccion = data.get('direccion')
    comunidad = data.get('comunidad')
    # Nuevo: obtener el telegram_user_id si está disponible
    telegram_user_id = data.get('telegram_user_id')

    lat = ubicacion.get('lat')
    lon = ubicacion.get('lon')

    if not descripcion or not lat or not lon or not comunidad:
        return jsonify({'error': 'Faltan datos'}), 400

    archivo_comunidad = os.path.join(DATA_FILE, f"{comunidad}.json")
    if not os.path.exists(archivo_comunidad):
        return jsonify({'error': 'Comunidad no encontrada'}), 404

    with open(archivo_comunidad, 'r', encoding='utf-8') as f:
        datos_comunidad = json.load(f)

    miembros = datos_comunidad.get('miembros', [])
    telegram_chat_id = datos_comunidad.get('telegram_chat_id')

    # 🎯 AQUÍ ESTÁ LA CORRECCIÓN: Buscar al miembro específico
    miembro_reportante = None
    
    # Prioridad 1: Si tenemos telegram_user_id, buscar por ese ID
    if telegram_user_id:
        for miembro in miembros:
            if str(miembro.get('telegram_id')) == str(telegram_user_id):
                miembro_reportante = miembro
                print(f"👤 Usuario encontrado por Telegram ID: {miembro['nombre']}")
                break
    
    # Prioridad 2: Si no hay telegram_user_id, buscar en usuarios_sos_activos
    if not miembro_reportante and comunidad in usuarios_sos_activos:
        user_id_sos = usuarios_sos_activos[comunidad]
        for miembro in miembros:
            if str(miembro.get('telegram_id')) == str(user_id_sos):
                miembro_reportante = miembro
                print(f"👤 Usuario encontrado por SOS activo: {miembro['nombre']}")
                # Limpiar el registro después de usar
                del usuarios_sos_activos[comunidad]
                break
    
    # Si no encontramos al usuario específico, usar el primer miembro como fallback
    if not miembro_reportante and miembros:
        miembro_reportante = miembros[0]
        print("⚠️ No se pudo identificar al usuario específico, usando el primer miembro como fallback")
    
    # Usar los datos del miembro reportante
    if miembro_reportante:
        nombre_reportante = miembro_reportante.get('nombre', 'Usuario desconocido')
        direccion_reportante = miembro_reportante.get('direccion', direccion or 'Dirección no disponible')
        
        # Si están usando ubicación en tiempo real, mantener lat/lon recibidos
        # Si no, usar la ubicación predeterminada del miembro
        if not data.get('ubicacion_tiempo_real', False):
            geo_miembro = miembro_reportante.get('geolocalizacion', {})
            if geo_miembro:
                lat = geo_miembro.get('lat', lat)
                lon = geo_miembro.get('lon', lon)
    else:
        nombre_reportante = 'Usuario desconocido'
        direccion_reportante = direccion or 'Dirección no disponible'

    mensaje = f"""
🚨 <b>ALERTA VECINAL</b> 🚨

<b>Comunidad:</b> {comunidad.upper()}
<b>👤 Reportado por:</b> {nombre_reportante}
<b>📍 Dirección:</b> {direccion_reportante}
<b>📝 Descripción:</b> {descripcion}
<b>📍 Ubicación:</b> https://maps.google.com/maps?q={lat},{lon}
<b>🕐 Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""

    enviar_telegram(telegram_chat_id, mensaje)

    # Llamar a todos los miembros
    for miembro in miembros:
        telefono = miembro.get('telefono')
        if not telefono:
            continue
        try:
            client.calls.create(
                twiml='<Response><Say voice="alice" language="es-ES">Emergencia. Alarma vecinal. Revisa tu celular.</Say></Response>',
                from_=TWILIO_FROM_NUMBER,
                to=telefono
            )
            print(f"📞 Llamada iniciada a {telefono}")
        except Exception as e:
            print(f"❌ Error al llamar a {telefono}: {e}")

    return jsonify({'status': f'Alerta enviada a la comunidad {comunidad}'}), 200

# 🤖 Webhook de Telegram - Recibe comandos
@app.route('/webhook/telegram', methods=['POST'])
def webhook_telegram():
    try:
        data = request.get_json()
        print("📨 Webhook recibido:", data)
        
        # Verificar si es un mensaje
        if 'message' not in data:
            return jsonify({'status': 'ok'})
        
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip().lower()
        
        # Obtener información del usuario
        user = message.get('from', {})
        user_id = user.get('id')
        first_name = user.get('first_name', 'Sin nombre')
        username = user.get('username', 'Sin username')
        
        # Verificar comando sos (sin barra)
        if text == 'sos':
            # Obtener la comunidad basada en el chat_id
            comunidad = obtener_comunidad_por_chat_id(chat_id)
            
            if not comunidad:
                enviar_mensaje_telegram(chat_id, "❌ Este chat no está registrado en ninguna comunidad.")
                return jsonify({'status': 'ok'})
            
            # 🎯 GUARDAR EL USER_ID que activó SOS
            usuarios_sos_activos[comunidad] = user_id
            print(f"👤 SOS activado por usuario {first_name} (ID: {user_id}) en comunidad {comunidad}")
            
            # Crear botón Web App con el user_id incluido
            webapp_url = f"{BASE_URL}?comunidad={comunidad}&user_id={user_id}"
            
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🚨 ABRIR BOTÓN DE EMERGENCIA 🚨",
                        "url": webapp_url
                    }
                ]]
            }
            
            mensaje_respuesta = "🚨"
            
            enviar_mensaje_telegram(chat_id, mensaje_respuesta, keyboard)
        
        # Verificar comando MIREGISTRO2222 (con respuesta visual)
        elif text == 'miregistro2222':
            # Registrar en logs de Railway
            print(f"👤 REGISTRO: Usuario '{first_name}' (@{username}) - ID: {user_id} - Chat: {message.get('chat', {}).get('title', 'Chat privado')} ({chat_id})")
            
            # Mensaje de confirmación hermoso y centrado
            mensaje_registro = """  ┏━━━━━━━━━━━━━━━━━━━┓
  ┃  👐 REGISTRADO 👐  ┃
  ┗━━━━━━━━━━━━━━━━━━━┛
  🦾 Bienvenido al sistema 🦾"""
            
            # Enviar respuesta visual
            enviar_mensaje_telegram(chat_id, mensaje_registro)
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        return jsonify({'status': 'error'}), 500

# 🔍 Obtener comunidad por chat_id
def obtener_comunidad_por_chat_id(chat_id):
    """Busca la comunidad que corresponde a un chat_id específico"""
    if not os.path.exists(DATA_FILE):
        return None
    
    for archivo in os.listdir(DATA_FILE):
        if archivo.endswith('.json'):
            path = os.path.join(DATA_FILE, archivo)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Verificar si el chat_id coincide
                if data.get('telegram_chat_id') == str(chat_id):
                    return archivo.replace('.json', '')
            except Exception as e:
                print(f"❌ Error leyendo {archivo}: {e}")
                continue
    
    return None

# 📡 Enviar mensaje a Telegram (función original)
def enviar_telegram(chat_id, mensaje):
    if not chat_id:
        print("❌ No se encontró chat_id de Telegram para esta comunidad.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload)
        if response.ok:
            print(f"✅ Mensaje Telegram enviado al grupo {chat_id}")
        else:
            print(f"❌ Error Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar mensaje Telegram: {e}")

# 📡 Enviar mensaje a Telegram con teclado (nueva función)
def enviar_mensaje_telegram(chat_id, mensaje, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        payload["reply_markup"] = keyboard

    try:
        response = requests.post(url, json=payload)
        if response.ok:
            print(f"✅ Mensaje con botón enviado al chat {chat_id}")
        else:
            print(f"❌ Error enviando mensaje: {response.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar mensaje: {e}")

# 🎤 Ruta de voz
@app.route('/twilio-voice', methods=['POST'])
def twilio_voice():
    response = VoiceResponse()
    response.say("Emergencia. Alarma vecinal. Revisa tu celular.", voice='alice', language='es-ES')
    return Response(str(response), mimetype='application/xml')

# ▶️ Ejecutar servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
