document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const comunidadSeleccionada = urlParams.get('comunidad');
  const telegramUserId = urlParams.get('user_id'); // 🎯 Nuevo: capturar user_id

  if (!comunidadSeleccionada) {
    alert("❌ No se especificó la comunidad en la URL.");
    return;
  }

  let ubicacionesPredeterminadas = [];
  let ubicacionSeleccionada = null;

  const textarea = document.getElementById('descripcion');
  const boton = document.getElementById('btnEmergencia');
  const statusMsg = document.getElementById('statusMsg');
  const toggleRealTime = document.getElementById('toggleRealTime');

  // 🎯 Mostrar información del usuario si está disponible
  if (telegramUserId) {
    statusMsg.textContent = `👥 Comunidad: ${comunidadSeleccionada.toUpperCase()} | Usuario ID: ${telegramUserId}`;
  } else {
    statusMsg.textContent = `👥 Comunidad detectada: ${comunidadSeleccionada.toUpperCase()}`;
  }
  
  cargarUbicaciones(comunidadSeleccionada);

  function cargarUbicaciones(comunidad) {
    fetch(`/api/ubicaciones/${comunidad}`)
      .then(res => {
        if (!res.ok) throw new Error(`Error al cargar ubicaciones: ${res.status}`);
        return res.json();
      })
      .then(data => {
        ubicacionesPredeterminadas = data;
        
        // 🎯 BUSCAR LA UBICACIÓN DEL USUARIO ESPECÍFICO
        if (telegramUserId) {
          const usuarioEspecifico = data.find(miembro => 
            String(miembro.telegram_id) === String(telegramUserId)
          );
          
          if (usuarioEspecifico) {
            ubicacionSeleccionada = usuarioEspecifico;
            statusMsg.textContent = `📍 Usuario: ${usuarioEspecifico.nombre} - ${usuarioEspecifico.direccion}`;
            console.log(`👤 Usuario identificado: ${usuarioEspecifico.nombre}`);
          } else {
            // Si no se encuentra el usuario específico, usar el primer miembro
            ubicacionSeleccionada = ubicacionesPredeterminadas[0];
            console.warn("⚠️ Usuario no encontrado en el JSON, usando fallback");
            if (ubicacionSeleccionada) {
              statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
            }
          }
        } else {
          // Sin user_id, usar el primer miembro
          ubicacionSeleccionada = ubicacionesPredeterminadas[0];
          if (ubicacionSeleccionada) {
            statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
          }
        }
      })
      .catch(error => {
        console.error("❌ Error:", error.message);
        statusMsg.textContent = "❌ No se pudieron cargar las ubicaciones.";
      });
  }

  textarea.addEventListener('input', () => {
    const texto = textarea.value.trim();
    if (texto.length >= 4 && texto.length <= 300) {
      boton.disabled = false;
      boton.classList.add('enabled');
      if (ubicacionSeleccionada) {
        statusMsg.textContent = `✅ Listo para enviar (${ubicacionSeleccionada.nombre})`;
      } else {
        statusMsg.textContent = "✅ Listo para enviar";
      }
    } else {
      boton.disabled = true;
      boton.classList.remove('enabled');
      statusMsg.textContent = "⏳ Esperando acción del usuario...";
    }
  });

  toggleRealTime.addEventListener('change', () => {
    if (toggleRealTime.checked) {
      statusMsg.textContent = "📍 Usando ubicación en tiempo real";
    } else if (ubicacionSeleccionada) {
      statusMsg.textContent = `📍 Usuario: ${ubicacionSeleccionada.nombre} - ${ubicacionSeleccionada.direccion}`;
    }
  });

  boton.addEventListener('click', () => {
    const descripcion = textarea.value.trim();

    if (!descripcion || !comunidadSeleccionada || !ubicacionSeleccionada) {
      alert("❌ Faltan datos necesarios");
      return;
    }

    boton.disabled = true;
    boton.textContent = "Enviando...";
    statusMsg.textContent = "🔄 Enviando alerta...";

    if (toggleRealTime.checked && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(pos => {
        enviarAlerta(descripcion, pos.coords.latitude, pos.coords.longitude, true);
      }, () => {
        alert("❌ No se pudo obtener ubicación en tiempo real.");
        resetFormulario();
      });
    } else {
      if (!ubicacionSeleccionada.geolocalizacion) {
        alert("❌ No se ha seleccionado una ubicación válida.");
        resetFormulario();
        return;
      }
      const { lat, lon } = ubicacionSeleccionada.geolocalizacion;
      enviarAlerta(descripcion, lat, lon, false);
    }
  });

  function enviarAlerta(descripcion, lat, lon, esUbicacionTiempoReal) {
    const direccion = ubicacionSeleccionada.direccion || "Dirección no disponible";
    
    // 🎯 Preparar el payload con toda la información necesaria
    const payload = {
      tipo: "Alerta Roja Activada",
      descripcion,
      ubicacion: { lat, lon },
      direccion: direccion,
      comunidad: comunidadSeleccionada,
      ubicacion_tiempo_real: esUbicacionTiempoReal
    };

    // 🎯 Agregar telegram_user_id si está disponible
    if (telegramUserId) {
      payload.telegram_user_id = telegramUserId;
    }

    console.log("📦 Enviando payload:", payload);

    fetch('/api/alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        alert(data.status || "✅ Alerta enviada correctamente.");
        resetFormulario();
        
        // Si estamos en Telegram Web App, cerrar después del envío
        if (window.Telegram && window.Telegram.WebApp) {
          setTimeout(() => {
            window.Telegram.WebApp.close();
          }, 2000);
        }
      })
      .catch(err => {
        console.error("❌ Error al enviar alerta:", err);
        alert("❌ Error al enviar alerta.");
        resetFormulario();
      });
  }

  function resetFormulario() {
    boton.disabled = true;
    boton.textContent = "🚨 Enviar Alerta Roja";
    statusMsg.textContent = "⏳ Esperando acción del usuario...";
    textarea.value = "";
    boton.classList.remove('enabled');
  }

  // Configurar Telegram Web App si está disponible
  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  }
});
