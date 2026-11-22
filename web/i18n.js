"use strict";
// ======================================================================
// NetLab — Español / English. La interfaz se traduce con este diccionario y
// lo que escribe la IA (exámenes, prácticas, tutor) sale en el idioma elegido.
// ======================================================================
// el idioma lo guarda NetLab (así todas las ventanas coinciden); por defecto, inglés
// Antes, si esta petición fallaba (a veces el servidor rechaza conexiones mientras la página pide ~20 cosas a la vez),
// se perdían TODAS las traducciones del modelo sin avisar y media app salía en español. Ahora: 3 intentos,
// caché en localStorage y, si aun así falla, se reintenta en segundo plano y se retraduce la página.
const _I18N = (() => {
  for (let i = 0; i < 3; i++) {
    try {
      const x = new XMLHttpRequest(); x.open("GET", "/api/i18n", false); x.send();
      if (x.status === 200) { try { localStorage.setItem("i18n_cache", x.responseText); } catch {} return JSON.parse(x.responseText); }
    } catch {}
  }
  try { const c = localStorage.getItem("i18n_cache"); if (c) return { ...JSON.parse(c), _deCache: true }; } catch {}
  return null;
})();
const IDIOMA_UI = _I18N?.idioma || (() => { try { return localStorage.getItem("idioma_ui") || "en"; } catch { return "en"; } })();
const EN = {
  // menú
  "Ruta de temas": "Learning path", "🧠 Repaso": "🧠 Review", "Teoría": "Theory", "Práctica": "Practice", "Examen": "Exam",
  "Subneteo": "Subnetting", "Arrastrar y soltar": "Drag & drop", "Laboratorios JITL": "JITL labs", "Constructor": "Builder",
  "Guías": "Guides", "Historial": "History", "Ajustes": "Settings", "⚔️ Red vs Blue": "⚔️ Red vs Blue",
  // encabezados
  "Práctica de Packet Tracer": "Packet Tracer practice", "Constructor de topologías": "Topology builder", "Tu progreso": "Your progress",
  "🧠 Cuaderno de errores": "🧠 Mistake notebook", "Simulacro tipo CCNA": "CCNA-style mock exam", "Analizar mi propia captura": "Analyze my own capture",
  "Buscar en tus guías": "Search your guides", "Memoria de video": "Video memory", "Tus lecciones": "Your lessons", "Siguiente misión": "Next mission",
  "De básico a superior, siguiendo el temario del CCNA 200-301. Un tema queda dominado con 8/10 o más.": "From basic to advanced, following the CCNA 200-301 blueprint. A topic is mastered at 8/10 or more.",
  "Describe lo que quieres o elige un tema. La práctica se autovalida antes de llegarte.": "Describe what you want or pick a topic. The practice validates itself before you get it.",
  "Opción múltiple y comandos de IOS. Puedes escribir comandos abreviados (sh ip int br).": "Multiple choice and IOS commands. You can type abbreviated commands (sh ip int br).",
  "Todo lo que fallas en el lab se guarda aquí y vuelve justo antes de que se te olvide (repaso espaciado).": "Everything you miss in the lab is saved here and comes back right before you forget it (spaced repetition).",
  "Un atacante juega contra ti y tú defiendes, con reloj, en CCNA, Wireshark o Linux. Todo es simulado: no toca tu PC ni tu red.": "An attacker plays against you and you defend, against the clock, in CCNA, Wireshark or Linux. Everything is simulated: it never touches your PC or network.",
  // botones y etiquetas
  "Generar práctica": "Generate practice", "Generar examen": "Generate exam", "Preparar simulacro": "Prepare mock exam", "Preparar lección": "Prepare lesson",
  "Diseñar topología": "Design topology", "Guardar": "Save", "Buscar": "Search", "Analizar": "Analyze", "Indexar lo nuevo": "Index new files",
  "Abrir la carpeta": "Open folder", "Liberar VRAM ahora": "Free VRAM now", "Cerrar la app": "Close the app", "Tema": "Topic", "Nivel": "Level",
  "Modo": "Mode", "Preguntas": "Questions", "Idioma": "Language", "Archivo": "File", "Comprobar": "Check", "Siguiente →": "Next →",
  "Empezar": "Start", "Empezar ronda": "Start round", "Otra ronda": "Another round", "Reiniciar": "Reset", "Ver resultado": "See result",
  "Calificar": "Grade", "Entregar": "Submit", "Probar": "Test", "Abrir en Wireshark": "Open in Wireshark", "Descargar .pcap": "Download .pcap",
  "Hacer una práctica": "Do a practice", "Hacer un examen": "Take an exam", "📖 Teoría": "📖 Theory", "Pelear": "Fight",
  "Guiado (te doy la config base)": "Guided (base config included)", "Desde cero": "From scratch", "Troubleshooting (encuentra las fallas)": "Troubleshooting (find the faults)",
  "Español": "Spanish", "Básico": "Basic", "Intermedio": "Intermediate", "Avanzado": "Advanced", "Superior": "Expert", "Experto": "Expert",
  "Sin intentos": "No attempts", "Sin intentar": "Not tried", "solo teoría": "theory only", "Mapa": "Map", "← Mapa": "← Map",
  "🖥️ Terminal libre": "🖥️ Free terminal", "📖 Teoría de Linux": "📖 Linux theory", "📝 Examen de Linux": "📝 Linux exam", "📝 Examen tipo WCA-101": "📝 WCA-101-style exam",
  "🏳️ Ver solución": "🏳️ Show solution", "⚔️ Empezar": "⚔️ Start", "Otra partida": "Another match", "Siguiente oleada →": "Next wave →",
  "🛡️ Aplicar defensa": "🛡️ Apply defense", "🏳️ Me rindo": "🏳️ I give up", "🛡️ Responder al incidente": "🛡️ Respond to incident",
  "Dificultad": "Difficulty", "Fácil": "Easy", "Normal": "Normal", "Difícil": "Hard", "Empezar repaso": "Start review", "Mostrar respuesta": "Show answer",
  "✓ La sabía": "✓ I knew it", "✗ No la sabía": "✗ I didn't know", "Siguiente": "Next", "Listo": "Done", "🔁 Repetir este examen": "🔁 Retake this exam",
  "🤖 Explícamelo": "🤖 Explain it to me", "💡 Pista": "💡 Hint", "Construir en Packet Tracer": "Build in Packet Tracer", "Revisar": "Review",
  "Captura en vivo": "Live capture", "Capturar": "Capture", "Interfaz": "Interface", "Segundos": "Seconds", "Empezar 5 ejercicios": "Start 5 exercises",
  "Retos por ronda": "Challenges per round", "Área": "Area", "Todo mezclado": "Everything mixed", "Aprende el método": "Learn the method",
  "Logros": "Achievements", "XP por área": "XP by area", "¿Estoy listo para el examen?": "Am I ready for the exam?", "Cómo se gana XP": "How to earn XP",
  "Nivel {n}": "Level {n}", "{n}/{n} misiones": "{n}/{n} missions", "{n}/{n} dominados": "{n}/{n} mastered", "{n}/{n} ★ en misiones": "{n}/{n} ★ in missions",
  "🖥️ Misiones ({n}/{n})": "🖥️ Missions ({n}/{n})", "📅 Misión del día": "📅 Daily mission", "Misión del día": "Daily mission", "listo para el examen": "ready for the exam",
  "{n}% listo para el examen": "{n}% ready for the exam", "{n}% dominio": "{n}% mastery", "{n}% de las ★": "{n}% of the ★", "Siguiente misión": "Next mission",
  "👹 Jefe final": "👹 Final boss", "Jefe final": "Final boss", "{n}/{n} · +{n} XP al completarla": "{n}/{n} · +{n} XP when completed",
  "Se abre al dominar la mitad del nivel anterior (8/10) o al vencer a su jefe final.": "Unlocks when you master half of the previous level (8/10) or beat its final boss.",
  "{n}/{n} misiones reales · cada partida cambia IPs, usuarios, puertos y rutas": "{n}/{n} real missions · every run changes IPs, users, ports and paths",
  "{n}/{n} ejercicios de Rustlings": "{n}/{n} Rustlings exercises", "{n} de {n} eventos": "{n} of {n} events", "Pregunta {n}/{n} · ✅ {n}": "Question {n}/{n} · ✅ {n}",
  "TryHackMe SAL1 · analista N1": "TryHackMe SAL1 · tier-1 analyst", "Logs de Windows, Sysmon y phishing": "Windows logs, Sysmon and phishing",
  "Ataque y defensa con reloj": "Attack and defense against the clock", "Práctica tipo SOC / THM SAL1": "SOC-style practice / THM SAL1",
  'CCNA: examen o práctica de "{q}"': 'CCNA: exam or practice on "{q}"', 'Linux: misión "{q}"': 'Linux: mission "{q}"',
  "Escenarios": "Scenarios", "Opción múltiple, solo de este mundo.": "Multiple choice, only about this world.",
  "Solo los temas de este mundo.": "Only this world's topics.", "Ver todos los mundos": "Show all worlds", "{n} XP en total": "{n} XP total", "faltan {n} para el nivel {n}": "{n} to go for level {n}",
  "racha de {n} día(s)": "{n}-day streak", "✅ hoy ya estudiaste": "✅ you studied today", "— ¡hoy todavía no!": "— not yet today!",
  "Vence al jefe de": "Beat the boss of", "{n} laboratorio(s) en": "{n} lab(s) in", ". Se abren en Packet Tracer con tu escala.": ". They open in Packet Tracer with your scale.",
  "No encontré la carpeta": "Folder not found:", "{n} retos que se califican con casos al azar.": "{n} challenges graded with random test cases.", "y entra directo.": "and jump straight in.",
  "Se abre al dominar la mitad del nivel anterior o al vencer a su jefe final. ¿Ya sabes esto?": "Unlocks when you master half of the previous level or beat its final boss. Already know this?",
  "tu mejor nota × {n}": "your best score × {n}", "nota × {n} (simulacro × {n})": "score × {n} (mock × {n})", "nota × {n}": "score × {n}",
  "{n} por estrella": "{n} per star", "Captura de Wireshark": "Wireshark capture", "Misión de Linux": "Linux mission", "Lección de teoría": "Theory lesson",
  "Academia (Rust, IA, Procesadores)": "Academy (Rust, AI, Processors)", "tus puntos ÷ {n} (más en Difícil).": "your points ÷ {n} (more on Hard).",
  "Academia": "Academy", "🏠 Inicio": "🏠 Home", "🗺️ Ruta CCNA": "🗺️ CCNA path", "Práctica Packet Tracer": "Packet Tracer practice",
  "Ciberseguridad": "Cybersecurity", "Estudio": "Study", "📝 Examen": "📝 Exam", "📝 Examen general": "📝 General exam",
  "🗺️ Todas las misiones": "🗺️ All missions", "← Ruta": "← Path", "🦈 Captura": "🦈 Capture", "🎯 Ejercicios BPF": "🎯 BPF exercises",
  "🧩 Práctica Packet Tracer": "🧩 Packet Tracer practice", "📝 Examen / simulacro": "📝 Exam / mock", "🧮 Subneteo": "🧮 Subnetting",
  "🧪 JITL": "🧪 JITL", "🏗️ Constructor": "🏗️ Builder", "🧲 Arrastrar y soltar": "🧲 Drag & drop", "🏁 Comparar modelos": "🏁 Compare models",
  "Elige tu mundo. Cada uno tiene ruta por niveles, jefes y medidor de \"¿estoy listo para la certificación?\".": "Pick your world. Each one has a level path, bosses and a \"am I ready for the certification?\" meter.", "🧠 IA": "🧠 AI", "🔧 Procesadores": "🔧 Processors", "🧠 Inteligencia Artificial": "🧠 Artificial Intelligence",
  "✅ Calificar": "✅ Grade", "▶ Ejecutar": "▶ Run", "↺ Código inicial": "↺ Starter code", "🧪 Laboratorio libre": "🧪 Free lab",
  "📖 Lección de este nivel": "📖 Lesson for this level", "🎯 Misión": "🎯 Mission", "🤖 Mentor": "🤖 Mentor", "Preguntar": "Ask",
  "🏳️ Ver solución": "🏳️ Show solution", "Siguiente misión →": "Next mission →", "🛠️ No compila": "🛠️ Doesn't compile",
  "Inteligencia Artificial": "Artificial Intelligence", "ML desde cero": "ML from scratch", "Procesadores": "Processors",
  "{n}% de las ★": "{n}% of stars earned", "listo para el examen": "exam ready", "{n}% listo para el examen": "{n}% exam ready",
  "{n}% dominio": "{n}% mastery", "Deep learning en tu GPU": "Deep learning on your GPU", "Diseño de chips": "Chip design",
  "Arquitectura y RISC-V": "Architecture and RISC-V", "Logs de Windows, Sysmon y phishing": "Windows logs, Sysmon and phishing",
  "Ataque y defensa con reloj": "Timed attack and defense", "Práctica tipo SOC / THM SAL1": "SOC-style practice / THM SAL1",
  "Rust Book + seguridad": "Rust Book + security", "Linux para SOC / LPIC-1": "Linux for SOC / LPIC-1",
  "TryHackMe SAL1 · analista N1": "TryHackMe SAL1 · Tier 1 analyst",
  "🛰️ SIEM": "🛰️ SIEM", "Elasticsearch + Kibana real": "Real Elasticsearch + Kibana", "Caza incidentes en Kibana real": "Hunt incidents in real Kibana",
  "SIEM instalado": "SIEM installed", "VM encendida": "VM running", "Elasticsearch": "Elasticsearch", "Kibana": "Kibana",
  "⚙️ Instalar el SIEM en la VM (una vez, 10-20 min)": "⚙️ Install the SIEM on the VM (once, 10-20 min)", "▶ Encender la VM": "▶ Start the VM",
  "🔍 Abrir Kibana": "🔍 Open Kibana", "🔍 Investigar en Kibana": "🔍 Investigate in Kibana", "💡 Pista": "💡 Hint", "🏳️ Ver respuesta": "🏳️ Show answer",
  "✅ Enviar mi análisis": "✅ Submit my analysis", "← Casos del SIEM": "← SIEM cases", "Casos para investigar": "Cases to investigate",
  "Fuerza bruta de credenciales": "Credential brute force", "Ataque al login web": "Web login attack", "Barrido de puertos": "Port scan",
  "Beacon C2": "C2 beacon", "Fuga de datos": "Data exfiltration",
  "🛠️ Proyectos Rust": "🛠️ Rust Projects", "Proyectos Rust": "Rust Projects", "Escáner, pcap y mini IDS con cargo": "Scanner, pcap and mini IDS with cargo",
  "🔌 Escáner de puertos": "🔌 Port scanner", "📦 Parser de .pcap": "📦 .pcap parser", "🛡️ Mini IDS": "🛡️ Mini IDS",
  "Sockets TCP y concurrencia con hilos": "TCP sockets and thread concurrency", "Parseo binario y little-endian": "Binary parsing and little-endian",
  "Reglas de detección con mapas y conjuntos": "Detection rules with maps and sets",
  "Parsear los puertos": "Parse the ports", "¿El puerto está abierto?": "Is the port open?", "👑 Escaneo concurrente": "👑 Concurrent scan",
  "Leer enteros little-endian": "Read little-endian integers", "Validar la cabecera": "Validate the header", "👑 Contar los paquetes": "👑 Count the packets",
  "¿IP interna o externa?": "Internal or external IP?", "Detectar un escaneo de puertos": "Detect a port scan", "👑 Detectar fuerza bruta": "👑 Detect brute force",
  "Velocidad": "Speed", "Voz": "Voice", "▶ Escuchar": "▶ Listen", "⏸ Pausa": "⏸ Pause", "⏹ Parar": "⏹ Stop",
};

// Traducción completa (la hace tu modelo una sola vez y queda en datos/i18n_en.json)
let EN_IA = IDIOMA_UI === "en" ? (_I18N?.en || {}) : {};
if (IDIOMA_UI === "en" && (!_I18N || _I18N._deCache)) {  // traer la versión fresca y retraducir lo que ya se pintó
  (async () => {
    for (let i = 0; i < 6; i++) {
      try {
        const r = await fetch("/api/i18n", { cache: "no-store" });
        if (r.ok) {
          const txt = await r.text(), d = JSON.parse(txt);
          try { localStorage.setItem("i18n_cache", txt); } catch {}
          EN_IA = d.en || {};
          if (document.body) traducirNodo(document.body);
          return;
        }
      } catch {}
      await new Promise((ok) => setTimeout(ok, 1500 * (i + 1)));
    }
  })();
}
const NO_TRADUCIR = "PRE, CODE, TEXTAREA, SCRIPT, STYLE, .lx-terminal, .ac-editor, [data-no-tr]";

function buscarEN(t) {
  if (EN[t]) return EN[t];
  if (EN_IA[t]) return EN_IA[t];
  if (t.length < 90 && !t.includes("`")) {  // con números: "3/44 misiones" → "{n}/{n} misiones"
    const nums = [];
    const k = t.replace(/\d+(?:[.,]\d+)?/g, (m) => { nums.push(m); return "{n}"; });
    if (nums.length) {
      const v = EN[k] || EN_IA[k];
      if (v) { let i = 0; return v.replace(/\{n\}/g, () => nums[i++] ?? ""); }
    }
  }
  const fin = t.match(/^(.*\p{L}.*?)(\s*[·:—–-]+)$/u);  // separador colgando al final: "Aún no: … con 8.25 ·"
  if (fin) { const r = buscarEN(fin[1].trim()); if (r) return r + fin[2]; }
  // antes que la regla del emoji: así "🔌 Escáner de puertos (…)" usa la clave con su emoji
  const par = t.match(/^(.+?) \((.+)\)$/);  // "Nombre (fuente)": "Ownership y préstamos (Rust Book cap. 4)"
  if (par) { const a = buscarEN(par[1].trim()), b = buscarEN(par[2].trim()); if (a || b) return `${a || par[1]} (${b || par[2]})`; }
  const m = t.match(/^([^\p{L}\p{N}¿¡"'(`]+)(.+)$/u);  // emoji o símbolo al inicio
  if (m) { const r = buscarEN(m[2].trim()); if (r) return m[1] + r; }
  const q = t.match(/^(.*?)"([^"]+)"(.*)$/);  // texto con un nombre entre comillas: 'Linux: misión "¿Dónde estoy?"'
  if (q) {
    const plantilla = EN[`${q[1]}"{q}"${q[3]}`] || EN_IA[`${q[1]}"{q}"${q[3]}`];
    if (plantilla) return plantilla.replace("{q}", buscarEN(q[2]) || q[2]);
  }
  for (const sep of [" · ", ": ", " — "]) {  // textos armados por partes: "Nivel 2 · Ownership y préstamos"
    if (!t.includes(sep)) continue;
    const partes = t.split(sep), trad = partes.map((p) => (p.trim() && buscarEN(p.trim())) || p);
    if (trad.some((x, i) => x !== partes[i])) return trad.join(sep);
  }
  return null;
}
/** Para contenido entero (lecciones, misiones…): devuelve la versión en inglés si existe. */
function tr(s) {
  if (IDIOMA_UI !== "en" || !s) return s;
  return EN[s.trim()] || EN_IA[s.trim()] || buscarEN(s.replace(/\s+/g, " ").trim()) || s;
}

function traducirNodo(raiz) {
  if (IDIOMA_UI !== "en" || !raiz) return;
  if (raiz.nodeType === 3) { traducirTexto(raiz); return; }
  if (raiz.closest?.(NO_TRADUCIR)) return;
  const w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, { acceptNode: (n) => n.parentElement?.closest(NO_TRADUCIR) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  let n;
  while ((n = w.nextNode())) traducirTexto(n);
  for (const at of ["placeholder", "title"]) {
    raiz.querySelectorAll?.(`[${at}]`).forEach((el) => { const v = buscarEN(el.getAttribute(at).trim()); if (v) el.setAttribute(at, v); });
  }
}
function traducirTexto(n) {
  if (n.parentElement?.closest(NO_TRADUCIR)) return;
  const t = n.nodeValue.replace(/\s+/g, " ").trim();
  if (!t || !/[a-záéíóúñ]{2}/i.test(t)) return;
  const v = buscarEN(t);
  if (v && v !== t) n.nodeValue = n.nodeValue.replace(n.nodeValue.trim(), v);
}

async function cambiarIdioma() {
  const nuevo = IDIOMA_UI === "en" ? "es" : "en";
  if (nuevo === "en") {
    try {
      const r = await api("/api/i18n");
      if (r.faltan > 0) {
        const capa = document.createElement("div");
        capa.className = "capa-idioma";
        capa.innerHTML = `<div class="tarjeta"><h2 style="margin-top:0">🌐 Preparing English…</h2>
          <p class="sub">Your model is translating NetLab (${r.faltan} texts). It only happens once (and again only for new texts).</p><div id="capaProg"></div></div>`;
        document.body.appendChild(capa);
        await trabajo("/api/i18n/traducir", {}, $("#capaProg"));
      }
    } catch (e) { aviso(e.message); }
  }
  try { localStorage.setItem("idioma_ui", nuevo); localStorage.setItem("teoria_idioma", nuevo); } catch {}
  api("/api/config", { idioma: nuevo }).catch(() => {}).finally(() => location.reload());
}

document.addEventListener("DOMContentLoaded", () => {
  const b = document.getElementById("btnIdioma");
  if (b) { b.textContent = IDIOMA_UI === "en" ? "🌐 English → Español" : "🌐 Español → English"; b.addEventListener("click", cambiarIdioma); }
  document.documentElement.lang = IDIOMA_UI;
  traducirNodo(document.body);
  if (IDIOMA_UI === "en") new MutationObserver((ms) => ms.forEach((m) => {
    if (m.type === "characterData") return;
    m.addedNodes.forEach((x) => { if (x.nodeType === 1 || x.nodeType === 3) traducirNodo(x); });
  })).observe(document.body, { childList: true, subtree: true });
});
