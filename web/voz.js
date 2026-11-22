"use strict";
// ======================================================================
// NetLab — Voz en todo el lab: 🔊 en cada texto, leer lo que selecciones,
// voces elegibles en español e inglés (prefiere las "Natural" de Edge).
// ======================================================================
const VOZ = { token: 0 };
const lsG = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const lsS = (k, v) => { try { localStorage.setItem(k, v); } catch {} };

function idiomaDe(texto) {
  const p = (texto.toLowerCase().match(/[a-záéíóúñ]+/g) || []);
  const en = new Set(["the", "and", "is", "of", "to", "with", "that", "for", "this", "are", "it", "you", "your", "what"]);
  const es = new Set(["el", "la", "los", "las", "que", "y", "con", "para", "una", "es", "del", "por", "se", "como", "qué"]);
  let a = 0, b = 0;
  for (const w of p) { if (en.has(w)) a++; if (es.has(w)) b++; }
  return a > b ? "en" : "es";
}

function vocesIdioma(idioma) {
  const pre = idioma === "en" ? /^en/i : /^es/i, pref = idioma === "en" ? /en-US/i : /es-MX/i;
  const puntos = (v) => (/natural|neural|online/i.test(v.name) ? 4 : 0) + (pref.test(v.lang) ? 2 : 0);
  return speechSynthesis.getVoices().filter((v) => pre.test(v.lang)).sort((x, y) => puntos(y) - puntos(x));
}
function vozElegida(idioma) {
  const nombre = lsG(`voz_${idioma}`, ""), vs = vocesIdioma(idioma);
  return vs.find((v) => v.name === nombre) || vs[0] || null;
}

// lee un texto largo frase por frase (Edge corta los textos muy largos) con un mini reproductor
function hablarTexto(texto, idioma) {
  if (!("speechSynthesis" in window)) return aviso("Este navegador no tiene voz");
  texto = String(texto || "").replace(/[*`#_>|]/g, " ").replace(/\s+/g, " ").trim();
  if (!texto) return;
  idioma = idioma || idiomaDe(texto);
  speechSynthesis.cancel();
  if (typeof pararLectura === "function" && typeof LECTOR !== "undefined" && LECTOR.activo) pararLectura();
  const token = ++VOZ.token;
  const frases = texto.match(/[^.!?;:]+[.!?;:]*/g) || [texto];
  const v = vozElegida(idioma), rate = +lsG("voz_vel", "1");
  reproductor(true);
  const decir = (i) => {
    if (token !== VOZ.token) return;
    if (i >= frases.length) return reproductor(false);
    const u = new SpeechSynthesisUtterance(frases[i].trim().replace(/(\d)\/(\d)/g, idioma === "en" ? "$1 slash $2" : "$1 diagonal $2"));
    if (v) u.voice = v;
    u.lang = v ? v.lang : (idioma === "en" ? "en-US" : "es-MX");
    u.rate = rate;
    u.onend = () => decir(i + 1);
    u.onerror = (e) => { if (e.error !== "interrupted" && e.error !== "canceled") decir(i + 1); };
    speechSynthesis.speak(u);
  };
  decir(0);
}
function callarVoz() { VOZ.token++; speechSynthesis.cancel(); reproductor(false); }

function reproductor(ver) {
  let r = document.getElementById("vozPlayer");
  if (!r) {
    r = document.createElement("div");
    r.id = "vozPlayer";
    r.innerHTML = `<span>🔊 Leyendo…</span><button class="chico" id="vozPausa">⏸</button><button class="chico" id="vozParar">⏹</button>`;
    document.body.appendChild(r);
    r.querySelector("#vozPausa").addEventListener("click", (e) => {
      if (speechSynthesis.paused) { speechSynthesis.resume(); e.target.textContent = "⏸"; } else { speechSynthesis.pause(); e.target.textContent = "▶"; }
    });
    r.querySelector("#vozParar").addEventListener("click", callarVoz);
  }
  r.classList.toggle("visible", ver);
}

// 🔊 automático en los textos para leer de todo el lab
const LEIBLES = [".respuesta-tutor", ".explicacion", ".rvb-alerta", ".lx-panel > p", ".lx-objetivo", ".rep-enun", ".reto > p",
  ".pregunta > div:first-child", "#practicaVista .tareas", "#practicaVista .descripcion", ".tarjeta.destacada > h2 + p", ".sub-pregunta"];
function ponerBotonesVoz(raiz = document) {
  for (const sel of LEIBLES) {
    raiz.querySelectorAll?.(sel).forEach((el) => {
      if (el.dataset.conVoz || el.closest(".leccion .bloque") || el.querySelector("[data-voz]") || !el.textContent.trim()) return;
      el.dataset.conVoz = "1";
      const b = document.createElement("button");
      b.className = "chico voz-auto";
      b.type = "button";
      b.title = "Escuchar";
      b.textContent = "🔊";
      b.addEventListener("click", (e) => { e.stopPropagation(); hablarTexto(el.innerText.replace(/🔊/g, "")); });
      el.appendChild(b);
    });
  }
}
new MutationObserver((ms) => { for (const m of ms) m.addedNodes.forEach((n) => n.nodeType === 1 && ponerBotonesVoz(n.parentElement || n)); })
  .observe(document.body, { childList: true, subtree: true });

// leer lo que selecciones
document.addEventListener("mouseup", (e) => {
  const burbuja = document.getElementById("vozSel");
  if (burbuja && e.target === burbuja) return;
  burbuja?.remove();
  const sel = window.getSelection().toString().trim();
  if (sel.length < 12 || e.target.closest("input, textarea, .lx-terminal")) return;
  const b = document.createElement("button");
  b.id = "vozSel"; b.className = "chico"; b.textContent = "🔊 Leer selección";
  b.style.left = `${Math.min(window.innerWidth - 160, e.clientX + 8)}px`; b.style.top = `${e.clientY + 12}px`;
  b.addEventListener("click", () => { hablarTexto(sel); b.remove(); });
  document.body.appendChild(b);
});

// Ajustes de voz
function pintarAjustesVoz() {
  const caja = document.getElementById("ajustesVoz");
  if (!caja) return;
  const opts = (idioma) => vocesIdioma(idioma).map((v) => `<option value="${esc(v.name)}" ${vozElegida(idioma)?.name === v.name ? "selected" : ""}>${esc(v.name.replace(/^Microsoft /, ""))}${/natural|online/i.test(v.name) ? " ★" : ""}</option>`).join("")
    || `<option value="">No hay voces de ${idioma === "en" ? "inglés" : "español"}</option>`;
  caja.innerHTML = `<div class="fila">
      <label>Voz en español<select id="vozEs">${opts("es")}</select></label>
      <label>Voz en inglés<select id="vozEn">${opts("en")}</select></label>
      <label>Velocidad<select id="vozVel">${[0.8, 0.9, 1, 1.1, 1.2, 1.35, 1.5].map((x) => `<option ${+lsG("voz_vel", 1) === x ? "selected" : ""}>${x}</option>`).join("")}</select></label></div>
    <div class="acciones"><button id="vozProbarEs">▶ Probar español</button><button id="vozProbarEn">▶ Try English</button></div>
    <p class="sub">★ = voces "Natural" de Microsoft (las mejores; necesitan internet). Si no aparecen, NetLab usa las voces de Windows. Para agregar más: Configuración de Windows → Hora e idioma → Voz → Agregar voces.</p>`;
  $("#vozEs").addEventListener("change", (e) => lsS("voz_es", e.target.value));
  $("#vozEn").addEventListener("change", (e) => lsS("voz_en", e.target.value));
  $("#vozVel").addEventListener("change", (e) => lsS("voz_vel", e.target.value));
  $("#vozProbarEs").addEventListener("click", () => hablarTexto("Hola, soy la voz de NetLab. Vamos a configurar OSPF en el router uno.", "es"));
  $("#vozProbarEn").addEventListener("click", () => hablarTexto("Hi, I'm the NetLab voice. Let's analyze this capture in Wireshark.", "en"));
}
if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => pintarAjustesVoz();
