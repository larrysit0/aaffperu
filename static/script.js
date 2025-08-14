document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const comunidadSeleccionada = urlParams.get('comunidad');

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

  statusMsg.textContent = `👥 Comunidad detectada: ${comunidadSeleccionada.toUpperCase()}`;
  cargarUbicaciones(comunidadSeleccionada);

  function cargarUbicaciones(comunidad) {
    fetch(`/api/ubicaciones/${comunidad}`)
      .then(res => {
        if (!res.ok) throw new Error(`Error al cargar ubicaciones: ${res.status}`);
        return res.json();
      })
      .then(data => {
        ubicacionesPredeterminadas = data;
        ubicacionSeleccionada = ubicacionesPredeterminadas[0];
        if (ubicacionSeleccionada) {
          statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
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
      statusMsg.textContent = "✅ Listo para enviar";
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
      statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
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
        enviarAlerta(descripcion, pos.coords.latitude, pos.coords.longitude);
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
      enviarAlerta(descripcion, lat, lon);
    }
  });

  function enviarAlerta(descripcion, lat, lon) {
    const direccion = ubicacionSeleccionada.direccion || "Dirección no disponible";
    fetch('/api/alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tipo: "Alerta Roja Activada",
        descripcion,
        ubicacion: { lat, lon },
        direccion: direccion,
        comunidad: comunidadSeleccionada
      })
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
