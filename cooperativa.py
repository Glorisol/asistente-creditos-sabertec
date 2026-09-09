import streamlit as st
from gtts import gTTS
import os
import re
import speech_recognition as sr
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Refresca la aplicación cada 10 minutos (600,000 milisegundos)
# Esto mantiene la sesión de Python viva
st_autorefresh(interval=600000, limit=None, key="mantenimiento_activo")
from google import genai
from google.genai import types

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(
    page_title="Asistente de Créditos | Sabertec B2B",
    page_icon="⚡",
    layout="centered"
)

FORZAR_ERROR_CUOTA = False 

st.markdown("""
    <style>
    .main-header {
        text-align: center;
        background-color: #0d47a1;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    </style>
    <div class="main-header">
        <h3 style="margin:0;">Cooperativa Modelo - Agente IA Financiero</h3>
    </div>
""", unsafe_allow_html=True)

# Botón en la barra lateral para salir / reiniciar la sesión por completo de forma limpia
with st.sidebar:
    st.markdown("### Control de Sesión")
    if st.button("🔄 Finalizar / Reiniciar"):
        st.session_state.clear()
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "Hola. Soy su asesor financiero virtual. Utilice el grabador de audio para dictar su solicitud."
        }
    ]

if "audio_counter" not in st.session_state:
    st.session_state.audio_counter = 0

def texto_a_voz(texto_respuesta):
    try:
        texto_limpio = texto_respuesta.replace("📝", "").replace("**", "").replace("*", "").replace("#", "").replace("-", " ")
        tts = gTTS(text=texto_limpio, lang='es', slow=False)
        audio_path = "respuesta_agente.mp3"
        tts.save(audio_path)
        return audio_path
    except Exception:
        return None

# CAPA 1: Transcripción local del audio del socio
def transcribir_audio_local(audio_bytes):
    temp_audio_path = "temp_audio.wav"
    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)
        
    r = sr.Recognizer()
    try:
        with sr.AudioFile(temp_audio_path) as source:
            audio_data = r.record(source)
            texto = r.recognize_google(audio_data, language="es-ES")
            return texto
    except sr.UnknownValueError:
        return "No se pudo entender el audio. Intente hablar más claro."
    except sr.RequestError:
        return "Error de conexión con el servicio de transcripción."
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

# Función para corregir textos pegados (números y letras juntos)
def limpiar_texto_pegado(texto):
    texto_corregido = re.sub(r'(\d)([a-zA-ZáéíóúÁÉÍÓÚñÑ])', r'\1 \2', texto)
    texto_corregido = re.sub(r'([a-zA-ZáéíóúÁÉÍÓÚñÑ])(\d)', r'\1 \2', texto_corregido)
    return texto_corregido

# CAPA 2: El Agente IA con el modelo exacto
def obtener_respuesta_agente_ia(texto_socio):
    if FORZAR_ERROR_CUOTA:
        return "Estimado socio, en este momento el sistema presenta alta demanda. Por favor, intente de nuevo en unos segundos."

    system_instruction = """
    Eres el Agente Virtual Senior de Admisión y Créditos de una Cooperativa financiera. Razonas con empatía y precisión analítica.
    Instrucciones estrictas y obligatorias:
    1. TASA DE INTERÉS: Fija del 1.5% mensual (18% anual).
    2. CAPACIDAD DE PAGO: La cuota mensual estimada no debe superar el 35% del sueldo declarado del socio. Analiza e interpreta los montos que te proporcione en lenguaje natural.
    3. POLÍTICA DE MORA: 5% de recargo administrativo sobre cuota vencida.
    4. FORMATO DE TEXTO: Separa siempre con espacios claros los números, unidades y palabras. No unas cifras con letras.
    5. PROTOCOLO DE CIERRE CONDICIONAL:
        - Si el socio NO APLICA al préstamo (su cuota supera el 35% del sueldo o faltan datos críticos como ingresos), NO incluyas la pregunta de asesores. En su lugar, pregunta amablemente si desea realizar otra consulta o evaluar un monto menor.
        - Si el socio SÍ APLICA al préstamo, incluye obligatoriamente la pregunta de cierre: "¿Desea saber dónde dirigirse para realizar el pedido de manera formal o desea que lo comunique inmediatamente con un asesor especialista?"
    """
    
    contents = []
    historial_reciente = st.session_state.messages[-6:] if len(st.session_state.messages) > 6 else st.session_state.messages
    
    for msg in historial_reciente:
        role = "user" if msg["role"] == "user" else "model"
        contenido_limpio = msg["content"].replace("📝 **Transcripción:** ", "")
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=contenido_limpio)]))
    
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=texto_socio)]
    ))

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=contents,
            config=config,
        )
        return limpiar_texto_pegado(response.text)
    except Exception as e:
        error_str = str(e)
        if "503" in error_str or "UNAVAILABLE" in error_str or "high demand" in error_str:
            return "Estimado socio, en este momento nuestros servidores están experimentando alta demanda. Por favor, intente de nuevo en unos segundos."
        elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            return "Hemos alcanzado temporalmente el límite de consultas. Por favor, aguarde unos segundos y vuelva a intentarlo."
        else:
            return "Disculpe, ocurrió un inconveniente temporal procesando su solicitud. Por favor, intente nuevamente."

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

st.markdown("### 🎙️ Canal de Voz - Agente Inteligente")

# Usamos un contador dinámico en la key para limpiar el componente tras cada envío
audio_key = f"audio_input_element_{st.session_state.audio_counter}"
audio_file_native = st.audio_input("Grabe su consulta de crédito aquí", key=audio_key)
texto_chat = st.chat_input("O escriba su consulta financiera aquí...")

if audio_file_native is not None:
    audio_bytes = audio_file_native.getvalue()
    
    with st.spinner("🎧 Transcribiendo audio del socio..."):
        texto_transcrito = transcribir_audio_local(audio_bytes)
        
    if texto_transcrito and not texto_transcrito.startswith("No se pudo") and not texto_transcrito.startswith("Error"):
        texto_con_formato = f"📝 **Transcripción:** {texto_transcrito}"
        
        with st.spinner("🤖 El Agente IA procesando políticas de crédito..."):
            respuesta_agente = obtener_respuesta_agente_ia(texto_transcrito)
            
        if respuesta_agente:
            st.session_state.messages.append({"role": "user", "content": texto_con_formato})
            st.session_state.messages.append({"role": "assistant", "content": respuesta_agente})
            # Incrementamos el contador para resetear el widget de audio por completo
            st.session_state.audio_counter += 1
            st.rerun()
    else:
        st.warning(texto_transcrito)

elif texto_chat:
    with st.spinner("🤖 El Agente IA procesando consulta..."):
        respuesta_agente = obtener_respuesta_agente_ia(texto_chat)
        
    if respuesta_agente:
        st.session_state.messages.append({"role": "user", "content": texto_chat})
        st.session_state.messages.append({"role": "assistant", "content": respuesta_agente})
        st.rerun()
