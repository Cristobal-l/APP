import { useState, useEffect } from 'react';

function App() {
  // --- ESTADOS DE LA APLICACIÓN ---
  const [aiText, setAiText] = useState("Sistema listo. Presiona 'Encender Sistema' para iniciar.");
  const [imageSrc, setImageSrc] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(0);
  
  // NUEVO: Estado para saber si el monitor está encendido o apagado
  const [isSystemActive, setIsSystemActive] = useState(false);

  useEffect(() => {
    // Si el sistema no está activo, no hacemos ninguna petición al backend
    if (!isSystemActive) return;

    // Función que consulta al servidor de Vercel/Localhost
    const fetchLatestData = async () => {
      try {
        // ⚠️ REEMPLAZAR con la URL de tu Vercel (ej: 'https://tu-backend.vercel.app/latest-info')
        const response = await fetch('http://localhost:5001/latest-info');
        const data = await response.json();

        // Si el timestamp es nuevo, actualizamos los datos en pantalla
        if (data.timestamp > lastUpdate) {
          setAiText(data.description);
          
          // Construimos la URL de la imagen (evitando la caché con el parámetro t)
          // ⚠️ REEMPLAZAR 'localhost:5001' por tu URL de Vercel cuando lo suban
          setImageSrc(`http://localhost:5001/latest-image?t=${data.timestamp}`);
          setLastUpdate(data.timestamp);
        }
      } catch (error) {
        console.error("Error consultando al servidor:", error);
        setAiText("⚠️ Error de conexión con el servidor de VIA.");
      }
    };

    // Ejecutar inmediatamente al activar el botón
    fetchLatestData();

    // Crear el ciclo repetitivo cada 2 segundos (Polling)
    const intervalId = setInterval(fetchLatestData, 2000);

    // Limpiar el ciclo si apagamos el sistema o cerramos la página
    return () => clearInterval(intervalId);
  }, [lastUpdate, isSystemActive]); // El ciclo reacciona si cambia el estado del botón

  // Función encargada de encender/apagar el switch
  const toggleSystem = () => {
    if (isSystemActive) {
      // Al apagar, limpiamos los datos de la pantalla
      setIsSystemActive(false);
      setAiText("Sistema detenido. Presiona 'Encender Sistema' para reiniciar.");
      setImageSrc(null);
      setLastUpdate(0);
    } else {
      // Al encender, activamos las peticiones
      setIsSystemActive(true);
      setAiText("🧠 Conectando con el backend de VIA... Esperando datos.");
    }
  };

  // --- INTERFAZ GRÁFICA (LO QUE SE VE EN PANTALLA) ---
  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif', maxWidth: '600px', margin: '0 auto' }}>
      <h2>Monitor de Visión VIA 👁️</h2>
      
      {/* NUEVO: Botón interactivo de Control de Estado */}
      <div style={{ textAlign: 'center', marginBottom: '25px' }}>
        <button 
          onClick={toggleSystem}
          style={{
            padding: '12px 24px',
            fontSize: '16px',
            fontWeight: 'bold',
            borderRadius: '30px',
            border: 'none',
            cursor: 'pointer',
            color: '#fff',
            // El color cambia dinámicamente: Verde si está apagado (listo para encender), Rojo si está activo
            backgroundColor: isSystemActive ? '#e63946' : '#2a9d8f',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            transition: 'all 0.2s ease'
          }}
        >
          {isSystemActive ? '🛑 Detener Sistema VIA' : '🚀 Encender Sistema VIA'}
        </button>
        <p style={{ marginTop: '10px', fontSize: '0.9em', color: '#666' }}>
          Estado del Monitor: <strong>{isSystemActive ? "🟢 EN LÍNEA" : "🔴 APAGADO"}</strong>
        </p>
      </div>

      {/* Recuadro con la respuesta textual de OpenAI */}
      <div style={{ padding: '15px', backgroundColor: '#eef2f5', borderRadius: '8px', marginBottom: '20px' }}>
        <h3 style={{ marginTop: 0, color: '#333' }}>Último Dictado de la IA:</h3>
        <p style={{ whiteSpace: 'pre-wrap', fontSize: '1.1em', lineHeight: '1.5', color: '#111' }}>
          {aiText}
        </p>
      </div>

      {/* Visualizador de la última imagen enviada por el ESP32 */}
      {imageSrc ? (
        <div>
          <h4 style={{ color: '#555' }}>Captura de Cámara:</h4>
          <img 
            src={imageSrc} 
            alt="Última foto procesada" 
            style={{ width: '100%', maxHeight: '450px', objectFit: 'cover', borderRadius: '8px', border: '2px solid #ccc' }} 
          />
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '50px', border: '2px dashed #ccc', borderRadius: '8px', color: '#888' }}>
          {isSystemActive ? "Esperando que el dispositivo envíe una foto..." : "Enciende el sistema para ver la cámara."}
        </div>
      )}
    </div>
  );
}

export default App;