document.addEventListener('DOMContentLoaded', () => {
    const BACKEND_URL = "https://alarma-production.up.railway.app";

    console.log("✅ Script cargado. Backend URL:", BACKEND_URL);

    const urlParams = new URLSearchParams(window.location.search);
    const comunidadSeleccionada = urlParams.get('comunidad');

    if (!comunidadSeleccionada) {
        alert("❌ No se especificó la comunidad en la URL.");
        return;
    }
    console.log("✅ Comunidad seleccionada:", comunidadSeleccionada);

    let userData = null;
    let comunidadMiembros = [];
    let currentUserMemberData = null;

    const textarea = document.getElementById('descripcion');
    const boton = document.getElementById('btnEmergencia');
    const statusMsg = document.getElementById('statusMsg');
    const toggleRealTime = document.getElementById('toggleRealTime');

    const userIdFromUrl = urlParams.get('id');
    const userFirstNameFromUrl = urlParams.get('first_name');

    if (userIdFromUrl) {
        userData = {
            id: userIdFromUrl,
            first_name: userFirstNameFromUrl,
            last_name: urlParams.get('last_name') || '',
            username: urlParams.get('username') || ''
        };
        console.log("✅ Datos del usuario obtenidos de la URL:", userData);
        statusMsg.textContent = `👋 Hola ${userData.first_name} en ${comunidadSeleccionada.toUpperCase()}`;
    } else if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe) {
        userData = window.Telegram.WebApp.initDataUnsafe.user;
        console.log("✅ Datos del usuario de Telegram cargados:", userData);
        if (userData && userData.first_name) {
            statusMsg.textContent = `👋 Hola ${userData.first_name} en ${comunidadSeleccionada.toUpperCase()}`;
        } else {
            statusMsg.textContent = `👥 Comunidad detectada: ${comunidadSeleccionada.toUpperCase()}`;
        }
    } else {
        console.warn("⚠️ No se pudieron obtener los datos del usuario.");
        statusMsg.textContent = `👥 Comunidad detectada: ${comunidadSeleccionada.toUpperCase()}`;
    }

    cargarDatosComunidad(comunidadSeleccionada);

    async function cargarDatosComunidad(comunidad) {
        try {
            const res = await fetch(`${BACKEND_URL}/api/comunidad/${comunidad}`);
            if (!res.ok) throw new Error(`Error al cargar datos de la comunidad: ${res.status}`);
            const comunidadData = await res.json();
            
            comunidadMiembros = comunidadData.miembros || [];
            console.log("✅ Miembros de la comunidad cargados:", comunidadMiembros);

            if (userData && userData.id) {
                currentUserMemberData = comunidadMiembros.find(m => String(m.telegram_id) === String(userData.id));
                if (currentUserMemberData) {
                    console.log("✅ Datos registrados del usuario actual encontrados:", currentUserMemberData);
                } else {
                    console.warn("⚠️ Usuario actual no encontrado en la lista de miembros de la comunidad.");
                }
            }
        } catch (error) {
            console.error("❌ Error en cargarDatosComunidad:", error.message);
            statusMsg.textContent = "❌ No se pudieron cargar los datos de la comunidad.";
            boton.disabled = true;
            boton.classList.remove('enabled');
            return;
        }
        updateStatusMessageBasedOnToggle();
    }

    function updateStatusMessageBasedOnToggle() {
        if (toggleRealTime.checked) {
            statusMsg.textContent = "📍 Usando ubicación en tiempo real";
        } else if (currentUserMemberData && currentUserMemberData.direccion) {
            statusMsg.textContent = `📍 Tu dirección registrada: ${currentUserMemberData.direccion}`;
        } else {
            statusMsg.textContent = "⚠️ Ubicación no disponible. Por favor, activa GPS.";
        }
    }

    textarea.addEventListener('input', () => {
        const texto = textarea.value.trim();
        if (texto.length >= 4 && texto.length <= 300) {
            boton.disabled = false;
            boton.classList.add('enabled');
            statusMsg.textContent = "✅ Listo para enviar";
            updateStatusMessageBasedOnToggle();
        } else {
            boton.disabled = true;
            boton.classList.remove('enabled');
            statusMsg.textContent = "⏳ Esperando acción del usuario...";
            updateStatusMessageBasedOnToggle();
        }
    });

    toggleRealTime.addEventListener('change', () => {
        updateStatusMessageBasedOnToggle();
    });

    boton.addEventListener('click', () => {
        console.log("➡️ Evento 'click' en el botón detectado.");
        const descripcion = textarea.value.trim();

        if (!descripcion || !comunidadSeleccionada) {
            console.error("❌ Validación fallida: faltan datos necesarios (descripción o comunidad).");
            alert("❌ Faltan datos necesarios");
            return;
        }
        
        // CORREGIDO: SE ELIMINÓ LA VALIDACIÓN DE currentUserMemberData
        // Ahora se intenta obtener la ubicación de cualquier forma, sin importar si el usuario está en el JSON.

        boton.disabled = true;
        boton.textContent = "Enviando...";
        statusMsg.textContent = "🔄 Enviando alerta...";

        let latEnvio = null;
        let lonEnvio = null;
        let direccionEnvio = "Dirección no disponible";

        if (currentUserMemberData && currentUserMemberData.direccion) {
            direccionEnvio = currentUserMemberData.direccion;
        }

        if (toggleRealTime.checked && navigator.geolocation) {
            console.log("➡️ Solicitando ubicación en tiempo real...");
            navigator.geolocation.getCurrentPosition(pos => {
                latEnvio = pos.coords.latitude;
                lonEnvio = pos.coords.longitude;
                console.log("✅ Ubicación obtenida (tiempo real). Llamando a enviarAlerta.");
                enviarAlerta(descripcion, latEnvio, lonEnvio, direccionEnvio, userData);
            }, () => {
                console.error("❌ Error al obtener ubicación en tiempo real. Cayendo a ubicación registrada si existe.");
                alert("❌ No se pudo obtener ubicación en tiempo real. Usando tu ubicación registrada.");
                handleFallbackLocation(descripcion, userData, direccionEnvio);
            });
        } else {
            handleFallbackLocation(descripcion, userData, direccionEnvio);
        }
    });

    function handleFallbackLocation(descripcion, userData, direccionFija) {
        let latEnvio = null;
        let lonEnvio = null;
        let direccionEnvio = direccionFija;

        if (currentUserMemberData && currentUserMemberData.geolocalizacion) {
            latEnvio = currentUserMemberData.geolocalizacion.lat;
            lonEnvio = currentUserMemberData.geolocalizacion.lon;
            direccionEnvio = currentUserMemberData.geolocalizacion.direccion || direccionFija;
            console.log("➡️ Fallback: Usando ubicación registrada del miembro.");
            enviarAlerta(descripcion, latEnvio, lonEnvio, direccionEnvio, userData);
        } else {
            console.error("❌ Fallback: No se encontró ubicación válida (ni registrada ni en tiempo real).");
            // Se envía la alarma con la ubicación disponible, incluso si es nula
            enviarAlerta(descripcion, latEnvio, lonEnvio, direccionEnvio, userData);
        }
    }

    function enviarAlerta(descripcion, lat, lon, direccion, userData) {
        console.log("➡️ ENVIAR ALERTA: La función ha sido llamada.");
        
        const userTelegramData = userData ? {
            id: userData.id,
            first_name: userData.first_name,
            last_name: userData.last_name || '',
            username: userData.username || ''
        } : {
            id: 'Desconocido',
            first_name: 'Anónimo',
            last_name: '',
            username: ''
        };

        console.log("📤 Datos de usuario a enviar:", userTelegramData);
        console.log("📤 Datos de ubicación a enviar:", { lat, lon, direccion });

        fetch(`${BACKEND_URL}/api/alert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo: "Alerta Roja Activada",
                descripcion,
                ubicacion: { lat, lon },
                direccion: direccion,
                comunidad: comunidadSeleccionada,
                user_telegram: userTelegramData
            })
        })
            .then(res => {
                console.log("✅ Respuesta del servidor recibida (Headers):", res.status);
                if (!res.ok) {
                    throw new Error(`Error del servidor: ${res.status} ${res.statusText}`);
                }
                return res.json();
            })
            .then(data => {
                console.log("✅ Respuesta del servidor (JSON):", data);
                alert(data.status || "✅ Alerta enviada correctamente.");
                resetFormulario();
            })
            .catch(err => {
                console.error("❌ Error en la llamada fetch:", err);
                alert("❌ Error al enviar alerta. Consulta la consola para más detalles.");
                resetFormulario();
            });
    }

    function resetFormulario() {
        boton.disabled = true;
        boton.textContent = "🚨 Enviar Alerta Roja";
        textarea.value = "";
        boton.classList.remove('enabled');
        updateStatusMessageBasedOnToggle();
    }
});
