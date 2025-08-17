# 🚨 Alerta roja - SECCIÓN MODIFICADA
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

    # 🔥 NUEVA LÓGICA: Llamar a todos los miembros EXCEPTO al que activó la alarma
    telegram_id_reportante = None
    
    # Obtener el telegram_id del usuario que reporta
    if telegram_user_id:
        telegram_id_reportante = str(telegram_user_id)
    elif comunidad in usuarios_sos_activos:
        telegram_id_reportante = str(usuarios_sos_activos[comunidad])
    
    print(f"🚫 No se llamará al usuario con Telegram ID: {telegram_id_reportante}")
    
    llamadas_realizadas = 0
    llamadas_omitidas = 0
    
    for miembro in miembros:
        telefono = miembro.get('telefono')
        telegram_id_miembro = str(miembro.get('telegram_id', ''))
        
        if not telefono:
            continue
            
        # 🚫 OMITIR llamada si es el usuario que reportó la emergencia
        if telegram_id_reportante and telegram_id_miembro == telegram_id_reportante:
            print(f"🚫 Omitiendo llamada al reportante: {miembro.get('nombre')} ({telefono})")
            llamadas_omitidas += 1
            continue
            
        try:
            client.calls.create(
                twiml='<Response><Say voice="alice" language="es-ES">Emergencia. Alarma vecinal. Revisa tu celular.</Say></Response>',
                from_=TWILIO_FROM_NUMBER,
                to=telefono
            )
            print(f"📞 Llamada iniciada a {miembro.get('nombre')}: {telefono}")
            llamadas_realizadas += 1
        except Exception as e:
            print(f"❌ Error al llamar a {telefono}: {e}")

    print(f"📊 Resumen de llamadas: {llamadas_realizadas} realizadas, {llamadas_omitidas} omitidas")

    return jsonify({'status': f'Alerta enviada a la comunidad {comunidad}'}), 200
