"use strict";
// ======================================================================
// NetLab (antes Lab CCNA) — interfaz
// ======================================================================
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let ESTADO = null;
let PRACTICA = null;   // práctica abierta
let EXAMEN = null;     // examen abierto

// ---------------------------------------------------------------- red
async function api(ruta, cuerpo) {
  let r;
  for (let i = 0; ; i++) {
    try {
      r = await fetch(ruta, cuerpo === undefined ? {} : {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
      });
      break;
    } catch (e) {  // fallo de red (conexión rechazada/agotada): los GET se reintentan; los POST no (podrían repetir una acción)
      if (cuerpo !== undefined || i >= 2) throw e;
      await new Promise((ok) => setTimeout(ok, 600 * (i + 1)));
    }
  }
  const d = await r.json();
  if (!r.ok || d.error) throw new Error(d.error || `Error ${r.status}`);
  if (cuerpo !== undefined && /\/(wireshark\/calificar|subneteo\/resultado|reto\/resultado|linux\/resultado|rvb\/resultado)$/.test(ruta)) setTimeout(() => { refrescarJugador(true); revisarMisionDia(); contarRepasos(); }, 300);
  return d;
}

/** Lanza un trabajo largo y va mostrando su progreso en `caja`. */
async function trabajo(ruta, cuerpo, caja) {
  const { trabajo: id } = await api(ruta, cuerpo);
  const t0 = Date.now();
  for (;;) {
    const t = await api(`/api/trabajo/${id}`);
    const seg = Math.round((Date.now() - t0) / 1000);
    if (caja) caja.innerHTML = `<div class="trabajo"><div class="girar"></div><div>${esc(t.mensajes.at(-1) || "Trabajando…")} <span class="sub">(${seg}s)</span></div></div>`;
    if (t.estado === "listo") {
      if (caja) caja.innerHTML = "";
      if (/\/(practica\/revisar|examen\/calificar|teoria\/generar)$/.test(ruta)) setTimeout(() => { refrescarJugador(true); if (typeof revisarMisionDia === "function") revisarMisionDia(); if (typeof contarRepasos === "function") contarRepasos(); }, 300);
      return t.resultado;
    }
    if (t.estado === "error") { if (caja) caja.innerHTML = ""; throw new Error(t.error); }
    await new Promise((r) => setTimeout(r, 1000));
  }
}

function aviso(txt) {
  const a = $("#aviso");
  a.textContent = txt;
  a.classList.add("ver");
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => a.classList.remove("ver"), 2600);
}

function copiar(txt) {
  navigator.clipboard.writeText(txt).then(() => aviso("Copiado al portapapeles"), () => aviso("No se pudo copiar"));
}

function notaClase(n) { return n == null ? "" : n >= 8 ? "alta" : n >= 6 ? "media" : "baja"; }

/** Markdown mínimo para las explicaciones del modelo. */
function md(texto) {
  const bloques = String(texto || "").split(/```[a-z]*\n?/);
  return bloques.map((b, i) => {
    if (i % 2) return `<pre>${esc(b.trim())}</pre>`;
    const lineas = esc(b).split("\n");
    let html = "", enLista = false;
    for (let l of lineas) {
      l = l.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/^#{1,4}\s*(.+)/, "<b>$1</b>");
      const li = l.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
      if (li) { if (!enLista) { html += "<ul>"; enLista = true; } html += `<li>${li[1]}</li>`; continue; }
      if (enLista) { html += "</ul>"; enLista = false; }
      if (l.trim()) html += `<p>${l}</p>`;
    }
    return html + (enLista ? "</ul>" : "");
  }).join("");
}

// ---------------------------------------------------------------- mundos
// Teoría y Examen son vistas compartidas: antes, entrar desde Linux o Rust mostraba los temas de TODOS los mundos y
// los exámenes se abrían en la pantalla de CCNA (con su formulario y su simulacro). Ahora saben de qué mundo vienes.
const MUNDOS = { ccna: "🌐 CCNA", linux: "🐧 Linux", wireshark: "🦈 Wireshark", rust: "🦀 Rust", ia: "🧠 Inteligencia Artificial",
  torch: "🔥 PyTorch", chisel: "🔩 Chisel", rustproj: "🛠️ Proyectos Rust", cpu: "🔧 Procesadores", sv: "📐 SystemVerilog", soc: "🚨 SOC", purple: "🗺️ Ruta ofensiva" };
const VISTA_MUNDO = { ccna: "ruta", linux: "linux", wireshark: "wireshark", rust: "rust", ia: "ia", torch: "torch", chisel: "chisel", rustproj: "rustproj", cpu: "cpu", sv: "sv", soc: "soc", purple: "indice" };
function mundoDeTema(id) {
  id = String(id || "");
  if (id === "linux" || /^(jefe_)?lx_/.test(id)) return "linux";
  if (id === "wireshark" || /^(jefe_)?ws_/.test(id)) return "wireshark";
  if (/^soc_|^jefe_soc/.test(id)) return "soc";
  if (/^(jefe_)?idx_/.test(id)) return "purple";
  if (/^(jefe_)?sv_/.test(id)) return "sv";
  const a = id.match(/^ac_(.+)_\d+$/) || id.match(/^jefe_ac_(.+)$/) || id.match(/^libre_(.+)$/);
  return a ? a[1] : "ccna";
}
const mundoExamen = (e) => (e?.dominio && e.dominio !== "ccna" ? e.dominio : mundoDeTema(e?.tema));
const marcarMundoEnNav = (m) => { const v = VISTA_MUNDO[m]; if (v) $$("nav button").forEach((b) => b.classList.toggle("activo", b.dataset.vista === v)); };
let TEORIA_MUNDO = null, TEORIA_SEL = null, _teoriaDesdeMundo = false, _examenDesdeMundo = false;
function irTeoria(mundo, temaId) { TEORIA_MUNDO = mundo || null; TEORIA_SEL = temaId || null; _teoriaDesdeMundo = true; ir("teoria"); }
function irExamenMundo(mundo) { _examenDesdeMundo = true; ir("examen"); modoExamen(mundo); }
function modoExamen(mundo) {
  const ccna = !mundo || mundo === "ccna";
  $("#formExamen").style.display = ccna ? "" : "none";
  $("#tarjetaSimulacro").style.display = ccna ? "" : "none";
  $("#eTitulo").textContent = ccna ? "Examen" : `${MUNDOS[mundo] || mundo} · Examen`;
  $("#eSub").textContent = ccna ? "Opción múltiple y comandos de IOS. Puedes escribir comandos abreviados (sh ip int br)." : "Opción múltiple, solo de este mundo.";
  $("#eVolver").innerHTML = ccna ? "" : `<div class="acciones" style="margin-bottom:10px"><button id="eVolverBtn">← ${esc(MUNDOS[mundo] || mundo)}</button></div>`;
  $("#eVolverBtn")?.addEventListener("click", () => ir(VISTA_MUNDO[mundo] || "inicio"));
  if (!ccna) marcarMundoEnNav(mundo);
  else if (EXAMEN && mundoExamen(EXAMEN) !== "ccna") { $("#examenVista").innerHTML = ""; EXAMEN = null; }  // no dejar un examen de Linux en CCNA
}

// ---------------------------------------------------------------- navegación
function ir(vista) {
  if (typeof RB !== "undefined" && RB.activo && vista !== "rvb") { aviso("Terminaste la partida de Red vs Blue al salir"); pararRvb(); $("#rvbVista").innerHTML = ""; }
  if (vista !== "teoria" && typeof pararLectura === "function" && LECTOR.activo) pararLectura();
  $$("nav button").forEach((b) => b.classList.toggle("activo", b.dataset.vista === vista));
  $$(".vista").forEach((v) => v.classList.toggle("visible", v.id === `v-${vista}`));
  if (vista === "historial") cargarHistorial();
  if (vista === "ruta") { cargarEstado(); pintarCcnaListo(); }
  if (vista === "inicio") { pintarInicio(); revisarMisionDia(); }
  if (vista === "repaso") cargarRepaso();
refrescarJugador(false);
  if (vista === "jitl") cargarJitl();
  if (vista === "wireshark") cargarWireshark();
  if (vista === "guias") cargarGuias();
  if (vista === "teoria") { if (!_teoriaDesdeMundo) { TEORIA_MUNDO = null; TEORIA_SEL = null; } _teoriaDesdeMundo = false; cargarTeoria(); }
  if (vista === "examen") { if (!_examenDesdeMundo) modoExamen("ccna"); _examenDesdeMundo = false; }
  if (vista === "linux") cargarLinux();
  if (["rust", "ia", "cpu", "torch", "chisel", "rustproj"].includes(vista)) cargarAcademia(vista);
  if (vista === "sv" && typeof pintarRutaSV === "function") pintarRutaSV();
  if (vista === "soc" && !SOC.caso) pintarSoc();
  if (vista === "siem" && typeof pintarSiem === "function") pintarSiem();
  if (vista === "salud" && typeof pintarSalud === "function") pintarSalud();
  if (vista === "logros") pintarLogros();
  if (vista === "ajustes" && typeof pintarAjustesVoz === "function") pintarAjustesVoz();
  if (vista === "retos" && !RET.ronda.length) pintarRetosInicio();
  if (vista === "rvb" && !RB.activo) pintarRvbInicio();
  if (vista === "indice" && typeof pintarIndice === "function") pintarIndice();
  if (vista === "subneteo" && !SUB.activo) pintarSubneteoInicio();
  window.scrollTo(0, 0);
}
$$("nav button").forEach((b) => b.addEventListener("click", () => ir(b.dataset.vista)));
$("#jugador").addEventListener("click", () => ir("logros"));

// ---------------------------------------------------------------- estado / ruta
async function cargarEstado() {
  try {
    ESTADO = await api("/api/estado");
  } catch (e) {
    $("#estadoOllama").textContent = "App sin conexión";
    return;
  }
  const eo = $("#estadoOllama");
  eo.className = "estado-ollama " + (ESTADO.ollama ? "ok" : "mal");
  eo.textContent = ESTADO.ollama ? `Ollama: ${ESTADO.modelos.length} modelos` : "Ollama no responde";
  llenarSelects();
  pintarRuta();
  pintarAjustes();
}

function llenarSelects() {
  for (const id of ["pTema", "eTema"]) {
    const sel = $("#" + id), previo = sel.value;
    const libre = id === "pTema" ? '<option value="">— Libre (usa la descripción) —</option>' : '<option value="">— Libre (usa el enfoque) —</option>';
    sel.innerHTML = libre + ESTADO.niveles.map((n) =>
      `<optgroup label="${n}">` + ESTADO.temas.filter((t) => t.nivel === n && (id === "eTema" || t.lab))
        .map((t) => `<option value="${t.id}">${esc(t.nombre)}</option>`).join("") + "</optgroup>").join("");
    if (previo !== undefined) sel.value = previo;
  }
  for (const id of ["pNivel", "eNivel"]) {
    const sel = $("#" + id), previo = sel.value;
    sel.innerHTML = ESTADO.niveles.map((n) => `<option>${n}</option>`).join("");
    sel.value = previo || "Intermedio";
  }
}

// Al elegir tema, el nivel se ajusta solo
["pTema", "eTema"].forEach((id) => $("#" + id).addEventListener("change", (e) => {
  const t = ESTADO.temas.find((x) => x.id === e.target.value);
  if (t) $("#" + (id[0] === "p" ? "pNivel" : "eNivel")).value = t.nivel;
}));

const estrellasTema = (n) => (n >= 9.5 ? 3 : n >= 8 ? 2 : n >= 6 ? 1 : 0);
const ICONO_NIVEL = { "Básico": "🌱", "Intermedio": "⚙️", "Avanzado": "🔥", "Superior": "👑" };
function nivelAbierto(i) {
  if (i === 0) return true;
  const prog = ESTADO.progreso, n = ESTADO.niveles[i - 1];
  const temas = ESTADO.temas.filter((t) => t.nivel === n);
  const dominados = temas.filter((t) => (prog[t.id]?.mejor || 0) >= 8).length;
  return (prog[`jefe_${n}`]?.mejor_examen || 0) >= 8 || dominados >= Math.ceil(temas.length / 2);
}
function pintarRuta() {
  const prog = ESTADO.progreso;
  const rec = ESTADO.temas.find((t) => t.id === ESTADO.recomendado);
  $("#siguiente").innerHTML = `
    <div class="sub" style="margin:0">Siguiente misión · ${rec.nivel}</div>
    <h2 style="margin:4px 0 10px">${esc(rec.nombre)}</h2>
    <div class="acciones">
      <button data-accion="teoria" data-tema="${rec.id}">📖 Teoría</button>
      ${rec.lab ? `<button class="primario" data-accion="practica" data-tema="${rec.id}">Hacer una práctica</button>` : ""}
      <button ${rec.lab ? "" : 'class="primario"'} data-accion="examen" data-tema="${rec.id}">Hacer un examen</button>
    </div>`;
  $("#niveles").innerHTML = ESTADO.niveles.map((n, i) => {
    const temas = ESTADO.temas.filter((t) => t.nivel === n);
    const dominados = temas.filter((t) => (prog[t.id]?.mejor || 0) >= 8).length;
    const abierto = nivelAbierto(i), jefe = prog[`jefe_${n}`]?.mejor_examen;
    const est = temas.reduce((s, t) => s + estrellasTema(prog[t.id]?.mejor || 0), 0);
    return `<div class="nivel ${abierto ? "" : "cerrado"}">
      <h2>${abierto ? ICONO_NIVEL[n] || "" : "🔒"} ${n} <span class="sub" style="margin:0;font-size:13px">${dominados}/${temas.length} dominados · ${est}/${temas.length * 3} ★</span>
        <span class="barra"><i style="width:${(100 * dominados) / temas.length}%"></i></span></h2>
      ${abierto ? "" : `<p class="sub"><span>Se abre al dominar la mitad del nivel anterior o al vencer a su jefe final. ¿Ya sabes esto?</span> <span>Vence al jefe de</span> <b>${esc(ESTADO.niveles[i - 1])}</b> <span>y entra directo.</span></p>`}
      <div class="temas">${temas.map((t) => {
        const p = prog[t.id], nota = p ? p.mejor : null, s = estrellasTema(nota || 0);
        return `<div class="tema ${t.id === ESTADO.recomendado ? "rec" : ""}">
          <div class="nombre">${esc(t.nombre)}</div>
          <div class="lx-estrellas">${"★".repeat(s)}<span class="vacia">${"★".repeat(3 - s)}</span></div>
          <div class="meta">${p ? `<span class="nota ${notaClase(nota)}">${nota}/10</span> · ${p.practicas} práctica(s) · ${p.examenes} examen(es)` : "Sin intentos"}${t.lab ? "" : " · solo teoría"}</div>
          <div class="acciones">
            <button class="chico" data-accion="teoria" data-tema="${t.id}" ${abierto ? "" : "disabled"}>Teoría</button>
            ${t.lab ? `<button class="chico" data-accion="practica" data-tema="${t.id}" ${abierto ? "" : "disabled"}>Práctica</button>` : ""}
            <button class="chico" data-accion="examen" data-tema="${t.id}" ${abierto ? "" : "disabled"}>Examen</button>
          </div></div>`;
      }).join("")}
        <div class="tema jefe">
          <div class="nombre">👹 Jefe final: ${n}</div>
          <div class="meta">${jefe != null ? `<span class="nota ${notaClase(jefe)}">${jefe}/10</span> · ${jefe >= 8 ? "¡vencido!" : "necesitas 8"}` : "15 preguntas de todo el nivel · necesitas 8"}</div>
          <div class="acciones"><button class="chico ${abierto ? "primario" : ""}" data-jefe="${esc(n)}">Pelear</button></div>
        </div></div></div>`;
  }).join("");
  $$("[data-jefe]").forEach((b) => b.addEventListener("click", () => pelearJefe(b.dataset.jefe)));
}
async function pelearJefe(nivel) {
  const temas = ESTADO.temas.filter((t) => t.nivel === nivel);
  ir("examen");
  const caja = $("#examenVista");
  try {
    const { id } = await trabajo("/api/examen/generar", { tema: `jefe_${nivel}`, nivel, n: 15,
      descripcion: `JEFE FINAL del nivel ${nivel}: preguntas variadas y exigentes que mezclen TODOS estos temas: ${temas.map((t) => t.nombre).join("; ")}.` }, caja);
    await abrirExamen(id);
  } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-accion]");
  if (!b) return;
  const t = ESTADO.temas.find((x) => x.id === b.dataset.tema);
  if (b.dataset.accion === "practica") {
    ir("practica");
    $("#pTema").value = t.id; $("#pNivel").value = t.nivel;
    $("#pDesc").focus();
  } else if (b.dataset.accion === "examen") {
    ir("examen");
    $("#eTema").value = t.id; $("#eNivel").value = t.nivel;
  } else if (b.dataset.accion === "teoria") {
    irTeoria("ccna", t.id);
  }
});

// ---------------------------------------------------------------- práctica
$("#btnGenPractica").addEventListener("click", async () => {
  const cuerpo = { tema: $("#pTema").value, nivel: $("#pNivel").value, modo: $("#pModo").value, descripcion: $("#pDesc").value };
  if (!cuerpo.tema && !cuerpo.descripcion.trim()) return aviso("Elige un tema o escribe una descripción");
  const btn = $("#btnGenPractica"), caja = $("#practicaVista");
  btn.disabled = true;
  try {
    const { id } = await trabajo("/api/practica/generar", cuerpo, caja);
    await abrirPractica(id);
  } catch (e) {
    caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
});

async function abrirPractica(id, conSolucion = false) {
  PRACTICA = await api(`/api/practica/${id}${conSolucion ? "?solucion=1" : ""}`);
  pintarPractica();
  ir("practica");
  $("#practicaVista").scrollIntoView({ behavior: "smooth" });
}

const ES_HOST = (tipo) => ["pc", "servidor", "laptop"].includes(tipo);
const corto = (i) => String(i || "").replace("GigabitEthernet", "Gi").replace("FastEthernet", "Fa").replace("Serial", "Se").replace("Ethernet", "Eth");

function pintarPractica() {
  const p = PRACTICA, v = p.validacion || { ok: true, problemas: [] };
  const tema = ESTADO?.temas.find((t) => t.id === p.tema);
  const cfgIni = (p.config_inicial || []).filter((c) => c.config.trim());
  const ts = p.modo === "troubleshooting";
  $("#practicaVista").innerHTML = `
  <div class="tarjeta">
    <div>${tema ? `<span class="pill">${esc(tema.nombre)}</span>` : ""}<span class="pill">${esc(p.nivel)}</span>
      <span class="pill">${ts ? "Troubleshooting" : p.modo === "desde_cero" ? "Desde cero" : "Guiado"}</span>
      ${v.ok ? '<span class="pill ok">✓ Autovalidada</span>' : '<span class="pill mal">⚠ Revisa: el modelo dejó inconsistencias</span>'}
      <span class="pill">${esc(p.modelo || "")}</span></div>
    <div class="acciones" style="margin-top:10px"><button class="primario btn-teofondo" id="ptTeoFondo">📖 Teoría a fondo</button>
      ${tema ? '<button id="ptTeoLec">📚 Lección y examen del tema</button>' : ""}</div>
    <div id="ptTeoFondoCaja" hidden></div>
    <h2 style="margin-top:10px">${esc(p.titulo)}</h2>
    <p><b>Objetivo:</b> ${esc(p.objetivo)}</p>
    <p class="sub">${esc(p.escenario)}</p>
    ${v.ok ? "" : `<details><summary class="sub">Inconsistencias detectadas (${v.problemas.length})</summary><ul>${v.problemas.map((x) => `<li class="sub">${esc(x)}</li>`).join("")}</ul></details>`}
    <div class="acciones">
      ${ESTADO?.packet_tracer ? '<button id="btnAbrirPT">Abrir Packet Tracer</button>' : ""}
      <a href="/api/practica/${p.id}/exportar"><button>Exportar enunciado (.md)</button></a>
    </div>
  </div>

  <div class="tarjeta">
    <h3 style="margin-top:0">Topología</h3>
    <div class="topologia">${svgTopologia(p)}</div>
    <h3>Equipos</h3>
    <p>${p.dispositivos.map((d) => `<span class="pill">${esc(d.nombre)} · ${esc(d.modelo)}</span>`).join(" ")}</p>
    <h3>Conexiones</h3>
    <table class="tabla"><tr><th>Desde</th><th>Puerto</th><th>Hacia</th><th>Puerto</th><th>Cable</th></tr>
      ${p.enlaces.map((e) => `<tr><td>${esc(e.a)}</td><td class="mono">${esc(e.puerto_a)}</td><td>${esc(e.b)}</td><td class="mono">${esc(e.puerto_b)}</td><td>${esc(e.cable)}</td></tr>`).join("")}
    </table>
    <h3>Direccionamiento</h3>
    <table class="tabla"><tr><th>Equipo</th><th>Interfaz</th><th>IP</th><th>Máscara</th><th>Gateway</th></tr>
      ${p.direccionamiento.map((a) => `<tr><td>${esc(a.dispositivo)}</td><td class="mono">${esc(a.interfaz)}</td><td class="mono">${esc(a.ip)}</td><td class="mono">${esc(a.mascara)}</td><td class="mono">${esc(a.gateway || "")}</td></tr>`).join("")}
    </table>
  </div>

  <div class="tarjeta" id="construir">
    <h3 style="margin-top:0">Construir en Packet Tracer</h3>
    <p class="sub">Copia el script y pégalo en Packet Tracer: <b>Extensions → Builder Code Editor</b> → <b>Run</b>.
      Packet Tracer crea los equipos, los cables y la configuración solo. Si un router pregunta por el "initial configuration dialog", contesta <code>no</code>.</p>
    <div class="acciones">
      ${ts ? `<button class="primario" data-ptb="inicial">Armar la red con las fallas</button>
              <button data-ptb="completa">Red ya arreglada (spoiler)</button>`
           : `<button data-ptb="topologia">Solo la topología</button>
              <button data-ptb="inicial">Topología + config inicial</button>
              <button data-ptb="completa">Práctica completa (resuelta)</button>`}
    </div>
    <div id="ptbScript"></div>
  </div>

  <div class="tarjeta">
    <h3 style="margin-top:0">Tareas</h3>
    <ol class="tareas">${p.tareas.map((t) => `<li>${esc(t)}</li>`).join("")}</ol>
    ${cfgIni.length && !ts ? `<h3>Configuración inicial</h3><p class="sub">Pégala en cada equipo (CLI) antes de empezar.</p>
      ${cfgIni.map((c) => bloqueConfig(c.dispositivo, "enable\nconfigure terminal\n" + c.config.trim() + "\nend")).join("")}` : ""}
    ${cfgIni.length && ts ? `<details><summary class="sub">Si no usas PTBuilder: configuración (averiada) para pegar en cada equipo</summary>
      ${cfgIni.map((c) => bloqueConfig(c.dispositivo, "enable\nconfigure terminal\n" + c.config.trim() + "\nend")).join("")}
      <p class="sub">Y pon a cada PC la IP de la tabla, con el gateway que se indica:
        ${(p.direccionamiento_inicial || []).filter((a) => a.gateway).map((a) => `${esc(a.dispositivo)} → gw ${esc(a.gateway)}`).join(" · ")}</p></details>` : ""}
    ${(p.pistas || []).length ? `<h3>Pistas</h3><div id="pistas"></div><button class="chico" id="btnPista">Ver una pista (${p.pistas.length})</button>` : ""}
  </div>

  <div class="tarjeta" id="revision">
    <h2>Revisar mi práctica</h2>
    <p class="sub">Pega de cada equipo su <code>show running-config</code> (o los comandos que tecleaste) y, abajo, las salidas de prueba. Lo que no pegues queda como "sin datos", no como error.</p>
    ${p.dispositivos.map((d) => cajaRevision(d)).join("")}
    <label class="check" style="margin-top:12px"><input type="checkbox" id="chkExplicar" checked> Que la IA me explique los errores</label>
    <div class="acciones"><button class="primario" id="btnRevisar">Revisar</button></div>
    <div id="resRevision"></div>
  </div>

  <div class="tarjeta">
    <h3 style="margin-top:0">Solución</h3>
    ${p.fallas ? `<h3>Las fallas eran</h3><ol>${p.fallas.map((f) => `<li>${esc(f.explicacion)}</li>`).join("")}</ol><h3>Configuración correcta</h3>` : ""}
    ${p.solucion ? p.solucion.map((c) => bloqueConfig(c.dispositivo, c.config.trim())).join("") :
      '<p class="sub">Está oculta. Inténtalo primero; si te atoras, usa las pistas.</p><button id="btnSolucion">Mostrar solución</button>'}
  </div>`;

  $("#btnAbrirPT")?.addEventListener("click", () => abrirEnPT());
  $("#ptTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#ptTeoFondoCaja"), {
    clave: `pt:${p.id}`, mundo: "ccna", titulo: p.titulo,
    contexto: `Práctica de Packet Tracer (${p.nivel}, ${ts ? "troubleshooting" : p.modo}). Tema: ${tema ? tema.nombre : ""}. Objetivo: ${p.objetivo}. Escenario: ${String(p.escenario || "").slice(0, 600)}` }));
  $("#ptTeoLec")?.addEventListener("click", () => irTeoria("ccna", p.tema));
  let pista = 0;
  $("#btnPista")?.addEventListener("click", (e) => {
    if (pista < p.pistas.length) $("#pistas").insertAdjacentHTML("beforeend", `<p class="pista">💡 ${esc(p.pistas[pista++])}</p>`);
    e.target.textContent = pista < p.pistas.length ? `Otra pista (${p.pistas.length - pista})` : "Sin más pistas";
    e.target.disabled = pista >= p.pistas.length;
  });
  $("#btnSolucion")?.addEventListener("click", () => {
    if (confirm("¿Seguro? Ver la solución antes de intentarlo le quita valor a la práctica.")) {
      const guardado = leerEvidencias();
      abrirPractica(p.id, true).then(() => { escribirEvidencias(guardado); $("#btnSolucion")?.scrollIntoView(); });
    }
  });
  $("#btnRevisar").addEventListener("click", revisar);
  $$("[data-ptb]").forEach((b) => b.addEventListener("click", async () => {
    const nivel = b.dataset.ptb;
    if (nivel === "completa" && !confirm("Esto arma la práctica ya resuelta (incluye la solución). ¿Continuar?")) return;
    const titulos = ts ? { inicial: "Script: red con fallas", completa: "Script: red arreglada" }
                       : { topologia: "Script: topología", inicial: "Script: topología + config inicial", completa: "Script: práctica completa" };
    try {
      const r = await api(`/api/practica/${p.id}/ptbuilder?nivel=${nivel}`);
      $("#ptbScript").innerHTML = bloqueConfig(titulos[nivel], r.script.trim());
      $("#ptbScript .copiar").addEventListener("click", (e) => copiar(e.target.dataset.texto));
      copiar(r.script);
    } catch (e) { aviso(e.message); }
  }));
  $$(".copiar").forEach((b) => b.addEventListener("click", () => copiar(b.dataset.texto)));
  // borrador de lo pegado (por si recargas la ventana)
  try { const g = JSON.parse(localStorage.getItem("ev_" + p.id) || "null"); if (g) escribirEvidencias(g); } catch {}
  $$("#revision textarea").forEach((t) => t.addEventListener("input", () => {
    try { localStorage.setItem("ev_" + p.id, JSON.stringify(leerEvidencias())); } catch {}
  }));
}

function bloqueConfig(titulo, texto) {
  return `<div class="bloque-config"><b>${esc(titulo)}</b>
    <button class="chico copiar" data-texto="${esc(texto)}">Copiar</button><pre>${esc(texto)}</pre></div>`;
}

function cajaRevision(d) {
  const checks = (PRACTICA.verificaciones || []).filter((c) => c.dispositivo === d.nombre);
  const pings = checks.filter((c) => c.tipo === "ping").map((c) => `ping ${c.ip}`);
  if (ES_HOST(d.tipo)) {
    const cmds = [...(checks.some((c) => c.tipo === "ip_pc") ? ["ipconfig"] : []), ...pings];
    if (!cmds.length) return "";
    return `<div class="equipo-revision" data-disp="${esc(d.nombre)}">
      <b>${esc(d.nombre)}</b> <span class="sub">(${esc(d.modelo)}, Desktop → Command Prompt)</span>
      <div class="ayuda">Pega la salida de: ${cmds.map((c) => `<code>${esc(c)}</code>`).join(", ")}
        · o pega una captura (Ctrl+V) <button class="chico" data-foto="salidas">📷</button></div>
      <textarea class="mono" data-campo="salidas" rows="4"></textarea></div>`;
  }
  const extra = [...(checks.some((c) => c.tipo === "vlan") ? ["show vlan brief"] : []), ...pings];
  return `<div class="equipo-revision" data-disp="${esc(d.nombre)}">
    <b>${esc(d.nombre)}</b> <span class="sub">(${esc(d.modelo)})</span>
    <div class="ayuda">Configuración: <code>show running-config</code> (o tus comandos) · o pega una captura (Ctrl+V)
      <button class="chico" data-foto="config">📷</button></div>
    <textarea class="mono" data-campo="config" rows="6"></textarea>
    ${extra.length ? `<div class="ayuda">Salidas de prueba: ${extra.map((c) => `<code>${esc(c)}</code>`).join(", ")}
      <button class="chico" data-foto="salidas">📷</button></div>
    <textarea class="mono" data-campo="salidas" rows="3"></textarea>` : ""}</div>`;
}

// ---- capturas: pegar (Ctrl+V) o elegir una imagen de la CLI y convertirla en texto con el modelo de visión
async function leerCaptura(area, archivo) {
  const aviso_ = area.parentElement.querySelector(".lectura") || area.insertAdjacentElement("afterend", Object.assign(document.createElement("div"), { className: "lectura sub" }));
  const datos = await new Promise((ok, mal) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = mal; r.readAsDataURL(archivo); });
  aviso_.textContent = "📷 Leyendo la captura…";
  try {
    const r = await trabajo("/api/leer_captura", { imagen: datos }, aviso_);
    area.value = (area.value.trim() ? area.value.trimEnd() + "\n" : "") + r.texto;
    area.dispatchEvent(new Event("input"));
    aviso_.innerHTML = `📷 Listo (${esc(r.modelo)}). <b>Revisa el texto</b>: si algo se leyó mal, corrígelo antes de revisar.`;
  } catch (e) { aviso_.innerHTML = `<span class="error">📷 ${esc(e.message)}</span>`; }
}
document.addEventListener("paste", (e) => {
  const area = e.target.closest?.("#revision textarea");
  if (!area) return;
  const img = [...(e.clipboardData?.items || [])].find((it) => it.type.startsWith("image/"));
  if (!img) return;
  e.preventDefault();
  leerCaptura(area, img.getAsFile());
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-foto]");
  if (!b) return;
  const area = b.closest(".equipo-revision").querySelector(`[data-campo="${b.dataset.foto}"]`);
  const inp = Object.assign(document.createElement("input"), { type: "file", accept: "image/*" });
  inp.onchange = () => inp.files[0] && leerCaptura(area, inp.files[0]);
  inp.click();
});

function leerEvidencias() {
  const ev = {};
  $$("#revision .equipo-revision").forEach((div) => {
    ev[div.dataset.disp] = {
      config: $('[data-campo="config"]', div)?.value || "",
      salidas: $('[data-campo="salidas"]', div)?.value || "",
    };
  });
  return ev;
}
function escribirEvidencias(ev) {
  $$("#revision .equipo-revision").forEach((div) => {
    const e = ev[div.dataset.disp]; if (!e) return;
    const c = $('[data-campo="config"]', div), s = $('[data-campo="salidas"]', div);
    if (c) c.value = e.config || ""; if (s) s.value = e.salidas || "";
  });
}

async function revisar() {
  const btn = $("#btnRevisar"), caja = $("#resRevision");
  btn.disabled = true;
  try {
    const r = await trabajo("/api/practica/revisar", { id: PRACTICA.id, evidencias: leerEvidencias(), explicar: $("#chkExplicar").checked }, caja);
    const ic = { ok: "✓", falla: "✗", sin_datos: "?" };
    caja.innerHTML = `<div class="resultado">
      <h3>Resultado</h3>
      <div><span class="calif nota ${notaClase(r.calificacion)}">${r.calificacion}</span><span class="sub"> / 10</span></div>
      <p class="sub">${r.ok} correctas · ${r.fallas} con error · ${r.sin_datos} sin datos (de ${r.total})</p>
      ${r.resultados.map((x) => `<div class="res-item ${x.estado}"><span class="ic">${ic[x.estado]}</span>
        <div><b>${esc(x.dispositivo)}</b> — ${esc(x.descripcion)}${x.detalle ? `<div class="det">${esc(x.detalle)}</div>` : ""}</div></div>`).join("")}
      ${r.explicacion ? `<h3>Explicación</h3><div class="md">${md(r.explicacion)}</div>` : ""}
    </div>`;
  } catch (e) {
    caja.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  } finally { btn.disabled = false; }
}

// ---- dibujo de la topología (SVG generado a partir de la práctica)
function svgTopologia(p) {
  const fila = (t) => ({ router: 0, switch_l3: 1, switch: 2 }[t] ?? 3);
  const nodos = p.dispositivos.map((d) => ({ ...d, f: fila(d.tipo) }));
  const porNombre = Object.fromEntries(nodos.map((n) => [n.nombre, n]));
  const vecinos = {};
  p.enlaces.forEach((e) => { (vecinos[e.a] ||= []).push(e.b); (vecinos[e.b] ||= []).push(e.a); });
  const filas = [0, 1, 2, 3].map((f) => nodos.filter((n) => n.f === f)).filter((f) => f.length);
  const zigzag = nodos.filter((n) => n.f === 0).length >= 3;
  const top = zigzag ? 110 : 60;
  const W = Math.max(720, Math.max(...filas.map((f) => f.length)) * 150), H = filas.length * 160 + 10 + (top - 60);
  filas.forEach((f, i) => {
    // ordenar por el promedio de posición de los vecinos ya colocados (menos cruces)
    f.forEach((n) => {
      const xs = (vecinos[n.nombre] || []).map((v) => porNombre[v]).filter((v) => v && v.x != null).map((v) => v.x);
      n.orden = xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 1e9;
    });
    f.sort((a, b) => a.orden - b.orden);
    f.forEach((n, j) => {
      n.x = (W / (f.length + 1)) * (j + 1) - 30;
      n.y = top + i * 160 - (zigzag && n.f === 0 && j % 2 === 1 ? 60 : 0);
    });
  });
  const icono = (n) => {
    const { x, y } = n;
    if (n.tipo === "router") return `<circle cx="${x}" cy="${y}" r="24" class="ic-r"/><path d="M${x - 12} ${y}h24M${x} ${y - 12}v24" class="ic-l"/>`;
    if (n.tipo === "switch" || n.tipo === "switch_l3") return `<rect x="${x - 30}" y="${y - 16}" width="60" height="32" rx="5" class="${n.tipo === "switch_l3" ? "ic-l3" : "ic-s"}"/><path d="M${x - 16} ${y - 5}h32M${x - 16} ${y + 5}h32" class="ic-l"/>`;
    return `<rect x="${x - 20}" y="${y - 16}" width="40" height="26" rx="3" class="ic-pc"/><path d="M${x - 10} ${y + 16}h20" class="ic-l"/>`;
  };
  const lineas = p.enlaces.map((e) => {
    const a = porNombre[e.a], b = porNombre[e.b];
    if (!a || !b) return "";
    const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1;
    // etiquetas de puerto sobre la línea, lejos del nombre del equipo y corridas a un lado
    const d = Math.min(56, L * 0.32), nx = (-dy / L) * 14, ny = (dx / L) * 14;
    const la = { x: a.x + (dx / L) * d + nx, y: a.y + (dy / L) * d + ny + 4 }, lb = { x: b.x - (dx / L) * d + nx, y: b.y - (dy / L) * d + ny + 4 };
    const dash = e.cable === "cruzado" ? ' stroke-dasharray="6 4"' : e.cable === "serial" ? ' stroke-dasharray="2 4"' : "";
    return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="enlace"${dash}/>
      <text x="${la.x}" y="${la.y}" class="puerto">${esc(corto(e.puerto_a))}</text>
      <text x="${lb.x}" y="${lb.y}" class="puerto">${esc(corto(e.puerto_b))}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" xmlns="http://www.w3.org/2000/svg">
    <style>
      .enlace{stroke:#5c6678;stroke-width:2}
      .puerto{fill:#4fb3ff;font:11px Consolas,monospace;text-anchor:middle;paint-order:stroke;stroke:#1e222b;stroke-width:4px}
      .ic-r{fill:#1b3b5c;stroke:#4fb3ff;stroke-width:2}.ic-s{fill:#1d3d33;stroke:#3ecf8e;stroke-width:2}
      .ic-l3{fill:#3a2f16;stroke:#f2b84b;stroke-width:2}.ic-pc{fill:#2a2f3a;stroke:#9aa3b2;stroke-width:2}
      .ic-l{stroke:#e6e8ec;stroke-width:2}.nom{fill:#e6e8ec;font:600 13px Segoe UI,sans-serif;text-anchor:start}
      .mod{fill:#9aa3b2;font:11px Segoe UI,sans-serif;text-anchor:start}
    </style>
    ${lineas}
    ${nodos.map((n) => `${icono(n)}<text x="${n.x + 38}" y="${n.y}" class="nom">${esc(n.nombre)}</text><text x="${n.x + 38}" y="${n.y + 14}" class="mod">${esc(n.modelo)}</text>`).join("")}
  </svg>`;
}

// ---------------------------------------------------------------- examen
$("#btnGenExamen").addEventListener("click", async () => {
  const cuerpo = { tema: $("#eTema").value, nivel: $("#eNivel").value, n: +$("#eN").value || 10, descripcion: $("#eDesc").value };
  if (!cuerpo.tema && !cuerpo.descripcion.trim()) return aviso("Elige un tema o escribe un enfoque");
  const btn = $("#btnGenExamen"), caja = $("#examenVista");
  btn.disabled = true;
  try {
    const { id } = await trabajo("/api/examen/generar", cuerpo, caja);
    await abrirExamen(id);
  } catch (e) {
    caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
});

async function abrirExamen(id) {
  EXAMEN = await api(`/api/examen/${id}`);
  if (EXAMEN.subneteo || (EXAMEN.titulo || "").startsWith("Subneteo")) return ir("subneteo");
  pintarExamen();
  irExamenMundo(mundoExamen(EXAMEN));
  if (EXAMEN.resultado) mostrarResultadoExamen(EXAMEN.resultado);
  else if (EXAMEN.simulacro) iniciarCronometro();
}

// ---- voz: lee la pregunta con las voces de Windows en español
const LETRAS = "ABCDEFGH";
function vozEspanol() {
  const voces = speechSynthesis.getVoices();
  return voces.find((v) => /es-MX/i.test(v.lang) && /natural/i.test(v.name))
    || voces.find((v) => /es-MX/i.test(v.lang)) || voces.find((v) => /^es/i.test(v.lang)) || null;
}
function leerPregunta(i) {
  const q = EXAMEN.preguntas[i];
  const en = idiomaDe(q.enunciado + " " + (q.opciones || []).join(" ")) === "en";
  let texto = `${en ? "Question" : "Pregunta"} ${i + 1}. ${q.enunciado}`;
  if (q.tipo === "opcion") texto += ". " + q.opciones.map((o, j) => `${en ? "Option" : "Opción"} ${LETRAS[j]}: ${o}.`).join(" ");
  else texto += en ? ". Type the command." : ". Escribe el comando.";
  hablarTexto(texto, en ? "en" : "es");
}
if ("speechSynthesis" in window) speechSynthesis.getVoices();

function pintarExamen() {
  const e = EXAMEN;
  $("#examenVista").innerHTML = `<div class="tarjeta">
    ${e.simulacro ? `<div class="cronometro" id="crono"></div>` : ""}
    <h2>${esc(e.titulo)}</h2><span class="pill">${esc(e.nivel)}</span><span class="pill">${e.preguntas.length} preguntas</span>
    ${e.simulacro ? `<span class="pill">${e.minutos} minutos</span><p class="sub">Como el examen real: sin explicaciones hasta que entregues. Al acabarse el tiempo se entrega solo.</p>` : ""}
    <div id="preguntas">${e.preguntas.map((q, i) => `
      <div class="pregunta" data-i="${i}">
        <div class="enun"><button class="chico voz" data-voz="${i}" title="Escuchar la pregunta">🔊</button>
          ${i + 1}. ${esc(q.enunciado)}${q.dudosa ? ' <span class="pill mal" title="El modelo no confirmó su propia respuesta">dudosa</span>' : ""}</div>
        ${q.tipo === "opcion"
          ? q.opciones.map((o, j) => `<label class="op"><input type="radio" name="q${i}" value="${j}"> <span><b>${LETRAS[j]}.</b> ${esc(o)}</span></label>`).join("")
          : `<input class="mono" data-cmd="${i}" placeholder="Escribe el comando (ej. R1(config-if)# ...)" autocomplete="off" spellcheck="false">`}
        <div class="expl"></div>
      </div>`).join("")}</div>
    <div class="acciones" style="margin-top:14px"><button class="primario" id="btnEntregar">Entregar y calificar</button></div>
    <div id="resExamen"></div></div>`;
  $("#btnEntregar").addEventListener("click", () => entregarExamen(false));
  $$("[data-voz]").forEach((b) => b.addEventListener("click", () => leerPregunta(+b.dataset.voz)));
}

// ---- cronómetro del simulacro (si recargas la ventana, sigue donde iba)
let RELOJ = null;
function iniciarCronometro() {
  clearInterval(RELOJ);
  const clave = "sim_" + EXAMEN.id;
  let inicio = Date.now();
  try { inicio = +localStorage.getItem(clave) || inicio; localStorage.setItem(clave, inicio); } catch {}
  const fin = inicio + EXAMEN.minutos * 60000;
  const tic = () => {
    const el = $("#crono");
    if (!el || !EXAMEN || EXAMEN.resultado) return clearInterval(RELOJ);
    const ms = Math.max(0, fin - Date.now());
    const m = Math.floor(ms / 60000), sg = Math.floor((ms % 60000) / 1000);
    el.textContent = `⏱ ${m}:${String(sg).padStart(2, "0")}`;
    el.classList.toggle("poco", ms < 5 * 60000);
    if (ms <= 0) { clearInterval(RELOJ); aviso("Se acabó el tiempo"); entregarExamen(true); }
  };
  tic();
  RELOJ = setInterval(tic, 1000);
}

async function entregarExamen(forzado) {
  const respuestas = EXAMEN.preguntas.map((q, i) => {
    if (q.tipo === "opcion") { const r = $(`input[name="q${i}"]:checked`); return r ? +r.value : null; }
    return $(`[data-cmd="${i}"]`).value;
  });
  const vacias = respuestas.filter((r) => r === null || r === "").length;
  if (!forzado && vacias && !confirm(`Te faltan ${vacias} pregunta(s). ¿Entregar así?`)) return;
  const btn = $("#btnEntregar");
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  speechSynthesis?.cancel();
  try {
    const r = await trabajo("/api/examen/calificar", { id: EXAMEN.id, respuestas }, $("#resExamen"));
    EXAMEN.resultado = r;
    clearInterval(RELOJ);
    mostrarResultadoExamen(r);
  } catch (e) { $("#resExamen").innerHTML = `<p class="error">${esc(e.message)}</p>`; btn.disabled = false; }
}

function mostrarResultadoExamen(r) {
  r.detalle.forEach((d, i) => {
    const div = $(`.pregunta[data-i="${i}"]`);
    div.classList.add(d.correcta ? "bien" : "mal");
    $$("input", div).forEach((x) => (x.disabled = true));
    const q = EXAMEN.preguntas[i];
    if (q.tipo === "comando") $(`[data-cmd="${i}"]`, div).value = d.tu_respuesta === "(sin responder)" ? "" : d.tu_respuesta;
    else $$("input", div).forEach((x) => { if (q.opciones[+x.value] === d.tu_respuesta) x.checked = true; });
    $(".expl", div).innerHTML = `${d.correcta ? "<b>Correcta.</b>" : `<b>Incorrecta.</b> Respuesta: <code>${esc(d.respuesta_correcta)}</code>`}
      ${d.motivo_juez ? `<br><i>${esc(d.motivo_juez)}</i>` : ""}<br>${esc(d.explicacion)}
      ${d.correcta ? "" : `<div><button class="chico" data-explica="${i}">🤖 Explícamelo</button><div class="tutor-caja"></div></div>`}`;
    $(`[data-explica="${i}"]`, div)?.addEventListener("click", (ev) => explicame(ev.target, (MUNDOS[mundoExamen(EXAMEN)] || "🌐 CCNA").replace(/^\S+\s/, ""),
      `Pregunta: ${q.enunciado}\n${(q.opciones || []).map((o, k) => `${LETRAS[k]}) ${o}`).join("\n")}\nMi respuesta: ${d.tu_respuesta}\nRespuesta correcta: ${d.respuesta_correcta}\nExplicación corta: ${d.explicacion}`,
      "No entiendo por qué mi respuesta está mal y la otra está bien. Explícamelo."));
  });
  $("#btnEntregar")?.remove();
  $("#crono")?.remove();
  setTimeout(() => {
    $("#resExamen").insertAdjacentHTML("beforeend", `<div class="acciones"><button id="btnRepetir">🔁 Repetir este examen</button></div>`);
    $("#btnRepetir").addEventListener("click", () => { EXAMEN.resultado = null; pintarExamen(); if (EXAMEN.simulacro) iniciarCronometro(); window.scrollTo(0, 0); });
  }, 0);
  revisarMisionDia(); contarRepasos();
  const dom = Object.entries(r.por_dominio || {}).map(([k, v]) => ({ k, ...v, pct: Math.round((100 * v.buenas) / v.total) }))
    .sort((a, b) => a.pct - b.pct);
  $("#resExamen").innerHTML = `<div class="resultado" style="margin-top:14px">
    <span class="calif nota ${notaClase(r.calificacion)}">${r.calificacion}</span><span class="sub"> / 10 · ${r.buenas} de ${r.total}</span>
    ${dom.length ? `<h3>Por dominio del CCNA</h3>
      <table class="tabla"><tr><th>Dominio</th><th>Aciertos</th><th></th></tr>
      ${dom.map((d) => `<tr><td>${esc(d.k)}</td><td class="nota ${notaClase(d.pct / 10)}">${d.buenas}/${d.total} (${d.pct}%)</td>
        <td><div class="barra-dom"><i style="width:${d.pct}%"></i></div></td></tr>`).join("")}</table>
      ${dom[0] && dom[0].pct < 80 ? `<p class="sub">Lo que más te conviene reforzar: <b>${esc(dom[0].k)}</b>.</p>` : ""}` : ""}
  </div>`;
  try { localStorage.removeItem("sim_" + EXAMEN.id); } catch {}
}

$("#btnSimulacro")?.addEventListener("click", async () => {
  const n = +$("#sN").value;
  const btn = $("#btnSimulacro"), caja = $("#examenVista");
  btn.disabled = true;
  try {
    const { id } = await trabajo("/api/simulacro/generar", { n }, caja);
    await abrirExamen(id);
  } catch (e) {
    caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
});

// ---------------------------------------------------------------- subneteo rápido (sin IA)
const SUB = { activo: false };
const ipNum = (s) => s.split(".").reduce((a, o) => a * 256 + +o, 0);
const ipStr = (n) => [24, 16, 8, 0].map((b) => Math.floor(n / 2 ** b) % 256).join(".");
const mascaraDe = (pre) => ipStr(pre ? (2 ** 32 - 2 ** (32 - pre)) : 0);
const wildcardDe = (pre) => ipStr(2 ** (32 - pre) - 1);
const azar = (a, b) => a + Math.floor(Math.random() * (b - a + 1));

function ipAzar() {
  const tipo = azar(0, 2);
  if (tipo === 0) return [10, azar(0, 255), azar(0, 255), azar(0, 255)].join(".");
  if (tipo === 1) return [172, azar(16, 31), azar(0, 255), azar(0, 255)].join(".");
  return [192, 168, azar(0, 255), azar(0, 255)].join(".");
}

function datosRed(ip, pre) {
  const tam = 2 ** (32 - pre), n = ipNum(ip);
  const red = n - (n % tam), bc = red + tam - 1;
  return { red: ipStr(red), bc: ipStr(bc), primero: ipStr(red + 1), ultimo: ipStr(bc - 1), hosts: tam - 2, tam };
}

// ---------- pasos "cómo se resuelve" (método del número mágico) ----------
const OCT = ["primer", "segundo", "tercer", "cuarto"];
function pasosRed(ip, pre) {
  const d = datosRed(ip, pre), m = mascaraDe(pre).split(".").map(Number), o = ip.split(".").map(Number);
  const P = [`<b>1. Máscara:</b> /${pre} = <code>${mascaraDe(pre)}</code> (${pre} bits en 1).`];
  if (pre % 8 === 0) {
    P.push(`<b>2.</b> El prefijo es múltiplo de 8: la red copia los primeros ${pre / 8} octeto(s) y pone 0 en el resto.`);
  } else {
    const k = Math.floor(pre / 8), B = 256 - m[k];
    const ini = Math.floor(o[k] / B) * B;
    P.push(`<b>2. Octeto interesante:</b> el ${OCT[k]} (donde la máscara no es 255 ni 0: vale ${m[k]}).`);
    P.push(`<b>3. Número mágico (tamaño del bloque):</b> 256 − ${m[k]} = <b>${B}</b>. Las redes van de ${B} en ${B}: 0, ${B}, ${2 * B}, ${3 * B}…`);
    P.push(`<b>4.</b> En la IP ese octeto vale ${o[k]}. El múltiplo de ${B} que queda justo abajo es <b>${ini}</b> (el siguiente es ${ini + B}).`);
  }
  P.push(`<b>Red:</b> <code>${d.red}</code> · <b>Broadcast:</b> <code>${d.bc}</code> (una antes de la siguiente red).`);
  P.push(`<b>Hosts:</b> <code>${d.primero}</code> a <code>${d.ultimo}</code> → 2^${32 - pre} − 2 = ${d.hosts} utilizables.`);
  return P;
}
const v6Expandir = (a) => {
  let [izq, der] = a.includes("::") ? a.split("::") : [a, null];
  const L = izq ? izq.split(":") : [], R = der ? der.split(":") : [];
  const medio = der === null ? [] : Array(8 - L.length - R.length).fill("0");
  return [...L, ...medio, ...R].map((g) => g.padStart(4, "0")).join(":");
};
function v6Abreviar(full) {
  const g = full.split(":").map((x) => x.replace(/^0+(?=.)/, ""));
  let mejor = [-1, 0];
  for (let i = 0; i < 8;) { if (g[i] === "0") { let j = i; while (j < 8 && g[j] === "0") j++; if (j - i > mejor[1]) mejor = [i, j - i]; i = j; } else i++; }
  if (mejor[1] < 2) return g.join(":");
  return (g.slice(0, mejor[0]).join(":") + "::" + g.slice(mejor[0] + mejor[1]).join(":"));
}
function v6Azar() {
  const h = () => azar(0, 65535).toString(16).padStart(4, "0");
  const g = ["2001", "0db8", h(), "0000", "0000", h(), "0000", h()];
  if (Math.random() < 0.5) [g[3], g[5]] = [h(), "0000"];
  return g.join(":");
}

// Cada generador: { cat, texto, campos: [{etiqueta, respuesta, prefijo?}], pasos: [html] }
const uno = (texto, respuesta, pasos, extra = {}) => ({ texto, campos: [{ etiqueta: "Respuesta", respuesta, ...extra }], pasos });
const GENERADORES = [
  ["red", () => { const ip = ipAzar(), pre = azar(17, 30), d = datosRed(ip, pre); return uno(`¿Dirección de red de ${ip}/${pre}?`, d.red, pasosRed(ip, pre)); }],
  ["red", () => { const ip = ipAzar(), pre = azar(17, 30), d = datosRed(ip, pre); return uno(`¿Broadcast de ${ip}/${pre}?`, d.bc, pasosRed(ip, pre)); }],
  ["red", () => { const ip = ipAzar(), pre = azar(18, 29), d = datosRed(ip, pre); return uno(`¿Primer host utilizable de ${ip}/${pre}?`, d.primero, pasosRed(ip, pre)); }],
  ["red", () => { const ip = ipAzar(), pre = azar(18, 29), d = datosRed(ip, pre); return uno(`¿Último host utilizable de ${ip}/${pre}?`, d.ultimo, pasosRed(ip, pre)); }],
  ["red", () => { const pre = azar(16, 30); return uno(`¿Cuántos hosts utilizables tiene un /${pre}?`, String(2 ** (32 - pre) - 2),
    [`Bits de host = 32 − ${pre} = ${32 - pre}.`, `2^${32 - pre} = ${2 ** (32 - pre)} direcciones, menos red y broadcast = <b>${2 ** (32 - pre) - 2}</b>.`]); }],
  ["red", () => { const pre = azar(20, 29), ip = ipAzar(), d = datosRed(ip, pre);
    const otro = Math.random() < 0.5 ? ipStr(ipNum(d.red) + azar(1, d.tam - 2)) : ipStr(ipNum(d.red) + d.tam + azar(1, Math.max(1, d.tam - 2)));
    const d2 = datosRed(otro, pre);
    return uno(`¿${ip} y ${otro} están en la misma subred con /${pre}? (si / no)`, d.red === d2.red ? "si" : "no",
      [...pasosRed(ip, pre).slice(0, -2), `${ip} → red <code>${d.red}</code>; ${otro} → red <code>${d2.red}</code>.`,
       d.red === d2.red ? "Misma red → <b>sí</b>." : "Redes distintas → <b>no</b> (necesitan un router)."]); }],
  ["mascara", () => { const pre = azar(8, 30); return uno(`Máscara decimal de /${pre}`, mascaraDe(pre),
    [`/${pre} = ${pre} unos y ${32 - pre} ceros.`, `Por octeto: ${mascaraDe(pre).split(".").map((x) => `${x} (${(+x).toString(2).padStart(8, "0")})`).join(" · ")}`,
     "Valores posibles en un octeto: 128, 192, 224, 240, 248, 252, 254, 255."]); }],
  ["mascara", () => { const pre = azar(8, 30); return uno(`¿Qué prefijo es la máscara ${mascaraDe(pre)}?`, String(pre),
    [`Cuenta los bits en 1 de cada octeto: ${mascaraDe(pre).split(".").map((x) => (+x).toString(2).split("1").length - 1).join(" + ")} = <b>/${pre}</b>.`], { prefijo: true }); }],
  ["mascara", () => { const pre = azar(8, 30); return uno(`Wildcard de /${pre} (para ACL u OSPF)`, wildcardDe(pre),
    [`Wildcard = 255.255.255.255 − máscara.`, `255.255.255.255 − ${mascaraDe(pre)} = <b>${wildcardDe(pre)}</b>.`,
     `Truco: cada octeto de la wildcard = número mágico − 1.`]); }],
  ["diseno", () => { const h = azar(5, 1000), b = Math.ceil(Math.log2(h + 2)); return uno(`¿Qué prefijo mínimo necesitas para ${h} hosts?`, String(32 - b),
    [`Busca la potencia de 2 tal que 2^n − 2 ≥ ${h}.`, `2^${b - 1} − 2 = ${2 ** (b - 1) - 2} (no alcanza) · 2^${b} − 2 = ${2 ** b - 2} (sí).`,
     `${b} bits de host → 32 − ${b} = <b>/${32 - b}</b>.`], { prefijo: true }); }],
  ["diseno", () => { const s = azar(3, 60), b = Math.ceil(Math.log2(s)), base = [8, 16, 24][azar(0, 2)];
    return uno(`Partiendo de un /${base}, ¿qué prefijo da al menos ${s} subredes?`, String(base + b),
      [`Busca la potencia de 2 tal que 2^n ≥ ${s}: 2^${b} = ${2 ** b}.`, `Pides ${b} bits prestados → ${base} + ${b} = <b>/${base + b}</b>.`], { prefijo: true }); }],
  ["completo", () => { const ip = ipAzar(), pre = azar(18, 30), d = datosRed(ip, pre);
    return { texto: `Problema completo: la PC tiene ${ip}/${pre}. Llena todo.`, pasos: pasosRed(ip, pre), campos: [
      { etiqueta: "Máscara", respuesta: mascaraDe(pre) }, { etiqueta: "Red", respuesta: d.red }, { etiqueta: "Broadcast", respuesta: d.bc },
      { etiqueta: "Primer host", respuesta: d.primero }, { etiqueta: "Último host", respuesta: d.ultimo }, { etiqueta: "Hosts utilizables", respuesta: String(d.hosts) }] }; }],
  ["vlsm", () => vlsmAzar()],
  ["ipv6", () => { const f = v6Azar(); return uno(`Abrevia al máximo la IPv6 ${f}`, v6Abreviar(f),
    ["Regla 1: quita los ceros a la izquierda de cada grupo (0db8 → db8, 0000 → 0).",
     "Regla 2: el grupo de ceros consecutivos MÁS LARGO se cambia por :: (solo una vez; si empatan, el primero).", `Resultado: <code>${v6Abreviar(f)}</code>`], { exacto: true }); }],
  ["ipv6", () => { const f = v6Azar(), a = v6Abreviar(f); return uno(`Escribe completa (8 grupos de 4) la IPv6 ${a}`, f,
    [`Cuenta los grupos que se ven y rellena con grupos 0000 donde está :: hasta tener 8.`, "Cada grupo lleva 4 dígitos: rellena con ceros a la izquierda.", `Resultado: <code>${f}</code>`]); }],
];

function vlsmAzar() {
  for (;;) {
    const basePre = [22, 23, 24][azar(0, 2)], tam = 2 ** (32 - basePre);
    const base = datosRed([10, azar(0, 255), azar(0, 255), 0].join(".") , basePre).red;
    const nombres = ["Ventas", "Contabilidad", "Ingeniería", "Recursos Humanos", "Gerencia", "Invitados", "Soporte"].sort(() => Math.random() - 0.5);
    const deps = Array.from({ length: azar(3, 4) }, (_, i) => ({ nombre: nombres[i], hosts: azar(5, Math.floor(tam / 3)) }));
    if (Math.random() < 0.7) deps.push({ nombre: "Enlace R1-R2", hosts: 2 });
    deps.forEach((x, i) => { x.orden = i; x.bits = Math.ceil(Math.log2(x.hosts + 2)); x.bloque = 2 ** x.bits; });
    if (deps.reduce((s, x) => s + x.bloque, 0) > tam) continue;
    const orden = [...deps].sort((a, b) => b.bloque - a.bloque || b.hosts - a.hosts || a.orden - b.orden);
    let sig = ipNum(base);
    const pasos = [`Ordena de mayor a menor bloque (si empatan, primero la que pide más hosts) y asigna en orden, sin huecos, empezando en ${base}.`];
    orden.forEach((x) => {
      x.red = ipStr(sig); x.pre = 32 - x.bits;
      pasos.push(`<b>${x.nombre}</b> (${x.hosts} hosts): 2^${x.bits} − 2 = ${x.bloque - 2} ≥ ${x.hosts} → /${x.pre}, bloque de ${x.bloque} → <code>${x.red}/${x.pre}</code> (hasta ${ipStr(sig + x.bloque - 1)}).`);
      sig += x.bloque;
    });
    return { texto: `VLSM: reparte ${base}/${basePre} entre: ${deps.map((x) => `${x.nombre} (${x.hosts} hosts)`).join(", ")}. ` +
      "Asigna de la más grande a la más chica, en orden y sin huecos. Escribe la red y el prefijo de cada una.",
      pasos, campos: orden.flatMap((x) => [{ etiqueta: `${x.nombre}: red`, respuesta: x.red }, { etiqueta: `${x.nombre}: prefijo`, respuesta: String(x.pre), prefijo: true }]) };
  }
}

const CATS = { todo: "Todo mezclado", red: "Red, broadcast y hosts", mascara: "Máscaras, prefijos y wildcards",
  diseno: "Diseño (prefijo para hosts o subredes)", completo: "Problemas completos", vlsm: "VLSM", ipv6: "IPv6" };
const genDe = (cat, rapido) => {
  const lista = GENERADORES.filter(([c]) => (cat === "todo" || c === cat) && (!rapido || (c !== "completo" && c !== "vlsm")));
  return (lista.length ? lista : GENERADORES.filter(([c]) => c !== "completo" && c !== "vlsm"))[azar(0, Math.max(0, lista.length - 1))][1];
};

function normalizaSub(v, prefijo, exacto) {
  let t = String(v || "").trim().toLowerCase().replace(/\s+/g, "").replace("sí", "si");
  if (prefijo) t = t.replace(/^\//, "");
  if (t.includes(":") && !exacto) { try { t = v6Expandir(t); } catch {} }   // IPv6: compara completas
  return t;
}
const pasosHtml = (q) => `<details class="pasos"><summary>¿Cómo se resuelve?</summary><ol>${q.pasos.map((p) => `<li>${p}</li>`).join("")}</ol></details>`;
const camposHtml = (q, pref) => `<div class="sub-campos">${q.campos.map((c, j) => `<label>${esc(c.etiqueta)}
  <input class="mono" data-campo="${pref}${j}" autocomplete="off" spellcheck="false"></label>`).join("")}</div>`;
function calificaCampos(q, pref) {
  let ok = 0;
  q.campos.forEach((c, j) => {
    const inp = $(`[data-campo="${pref}${j}"]`), bien = normalizaSub(inp.value, c.prefijo, c.exacto) === normalizaSub(c.respuesta, c.prefijo, c.exacto);
    ok += bien;
    inp.classList.add(bien ? "bien" : "mal");
    inp.disabled = true;
    if (!bien) inp.insertAdjacentHTML("afterend", `<span class="era">Era <code>${esc(c.prefijo ? "/" + c.respuesta : c.respuesta)}</code></span>`);
  });
  return ok;
}

function pintarSubneteoInicio() {
  $("#subneteoVista").innerHTML = `<div class="tarjeta">
    <p class="sub">Ejercicios infinitos: los genera el código al instante y siempre están bien calculados (no usa IA). Cada uno trae "¿Cómo se resuelve?" paso a paso.</p>
    <div class="fila">
      <label>Modo<select id="subModo">
        <option value="practica">Práctica (sin reloj, con solución paso a paso)</option>
        <option value="t120">Contra reloj 2 min</option><option value="t300">Contra reloj 5 min</option>
        <option value="e10">Examen de 10 ejercicios</option><option value="e20">Examen de 20 ejercicios</option></select></label>
      <label>Tipo<select id="subCat">${Object.entries(CATS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
    </div>
    <div class="acciones"><button class="primario" id="btnSubEmpezar">Empezar</button><button id="btnSubAprende">Aprende el método</button>
      <button class="primario btn-teofondo" id="subTeoFondo">📖 Teoría a fondo</button><button id="subTeoLec">📚 Lecciones y exámenes de CCNA</button></div>
    <div id="subTeoFondoCaja" hidden></div>
    ${SUB.ultimo ? `<p class="sub">Última ronda: ${SUB.ultimo}</p>` : ""}</div>`;
  $("#subTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#subTeoFondoCaja"), {
    clave: `subneteo:${$("#subCat").value}`, mundo: "ccna", titulo: `Subneteo IPv4: ${CATS[$("#subCat").value] || $("#subCat").value}`,
    contexto: "Subneteo IPv4 de cabeza para el CCNA: máscara y prefijo, octeto interesante, número mágico (256 − octeto), red, broadcast, rango de hosts, cantidad de hosts (2^n − 2), cantidad de subredes, VLSM y sumarización. Con ejemplos resueltos paso a paso y errores típicos." }));
  $("#subTeoLec").addEventListener("click", () => irTeoria("ccna", null));
  if (SUB.modo) { $("#subModo").value = SUB.modo; $("#subCat").value = SUB.cat; }
  $("#btnSubEmpezar").addEventListener("click", empezarSubneteo);
  $("#btnSubAprende").addEventListener("click", aprendeSubneteo);
}

function aprendeSubneteo() {
  const ip = ipAzar(), pre = [19, 21, 22, 26, 27, 28, 29][azar(0, 6)];
  $("#subneteoVista").innerHTML = `<div class="tarjeta">
    <h2>El método del número mágico</h2>
    <p>Sirve para sacar red, broadcast y rango de hosts de cabeza, sin pasar a binario:</p>
    <ol><li>Escribe la máscara del prefijo y busca el <b>octeto interesante</b>: el que no es 255 ni 0.</li>
      <li><b>Número mágico</b> = 256 − ese octeto de la máscara. Es el tamaño de cada subred en ese octeto.</li>
      <li>Las redes empiezan en los múltiplos del número mágico. Toma el múltiplo que queda <b>justo abajo</b> del valor de la IP: esa es la red.</li>
      <li><b>Broadcast</b> = la siguiente red − 1. Los octetos de la derecha van en 0 en la red y en 255 en el broadcast.</li>
      <li><b>Hosts</b> = de red + 1 a broadcast − 1. Cantidad = 2^(bits de host) − 2.</li></ol>
    <p class="sub">Valores de máscara por octeto: /1→128, /2→192, /3→224, /4→240, /5→248, /6→252, /7→254, /8→255 (y se repite en cada octeto).</p>
    <h3>Ejemplo: ${ip}/${pre}</h3>
    <ol>${pasosRed(ip, pre).map((p) => `<li>${p}</li>`).join("")}</ol>
    <h3>VLSM en una línea</h3>
    <p>Ordena las redes de la que necesita más hosts a la que menos, saca a cada una el prefijo mínimo (2^n − 2 ≥ hosts) y asígnalas una tras otra, sin dejar huecos.</p>
    <div class="acciones"><button id="btnOtroEj">Otro ejemplo</button><button class="primario" id="btnAPracticar">A practicar</button></div></div>`;
  $("#btnOtroEj").addEventListener("click", aprendeSubneteo);
  $("#btnAPracticar").addEventListener("click", pintarSubneteoInicio);
}

function empezarSubneteo() {
  const modo = $("#subModo").value, cat = $("#subCat").value;
  Object.assign(SUB, { activo: true, modo, cat, buenas: 0, total: 0, racha: 0, mejorRacha: 0, inicio: Date.now(),
    limite: modo.startsWith("t") ? +modo.slice(1) : 0 });
  clearInterval(SUB.reloj);
  if (modo.startsWith("e")) return examenSubneteo(+modo.slice(1), cat);
  $("#subneteoVista").innerHTML = `<div class="tarjeta">
    <div class="sub-marcador"><span id="subCuenta"></span><span id="subRacha"></span><span id="subReloj"></span></div>
    <div class="sub-pregunta" id="subTexto"></div>
    <div id="subZona"></div>
    <div class="acciones"><button class="primario" id="btnSubComprobar">Comprobar</button><button id="btnSubTerminar">Terminar</button></div>
    <div id="subFeedback"></div></div>`;
  $("#btnSubComprobar").addEventListener("click", responderSubneteo);
  $("#btnSubTerminar").addEventListener("click", terminarSubneteo);
  SUB.reloj = setInterval(relojSubneteo, 250);
  siguienteSubneteo();
}

function siguienteSubneteo() {
  SUB.actual = genDe(SUB.cat, !!SUB.limite)();
  SUB.revisada = false;
  $("#subTexto").textContent = SUB.actual.texto;
  $("#subZona").innerHTML = camposHtml(SUB.actual, "p");
  $$("#subZona input").forEach((x, j, arr) => x.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    if (j < arr.length - 1 && !SUB.revisada) arr[j + 1].focus(); else responderSubneteo();
  }));
  $("#btnSubComprobar").textContent = "Comprobar";
  $("#subZona input").focus();
  marcadorSubneteo();
}

function marcadorSubneteo() {
  $("#subCuenta").textContent = `✓ ${SUB.buenas} / ${SUB.total}`;
  $("#subRacha").textContent = `🔥 racha ${SUB.racha}`;
}

function relojSubneteo() {
  if (!SUB.activo || !$("#subReloj")) return clearInterval(SUB.reloj);
  const seg = (Date.now() - SUB.inicio) / 1000;
  if (SUB.limite) {
    const resta = Math.max(0, SUB.limite - seg);
    $("#subReloj").textContent = `⏱ ${Math.floor(resta / 60)}:${String(Math.floor(resta % 60)).padStart(2, "0")}`;
    if (resta <= 0) terminarSubneteo();
  } else {
    $("#subReloj").textContent = `⏱ ${Math.floor(seg / 60)}:${String(Math.floor(seg % 60)).padStart(2, "0")}`;
  }
}

function responderSubneteo() {
  if (SUB.revisada) return siguienteSubneteo();
  const q = SUB.actual;
  if (!$$("#subZona input").some((x) => x.value.trim())) return;
  const ok = calificaCampos(q, "p") === q.campos.length;
  if (!ok && q.campos.length === 1) agregarRepaso("Subneteo", "texto", { enunciado: q.texto, respuestas: [q.campos[0].respuesta, q.campos[0].prefijo ? "/" + q.campos[0].respuesta : q.campos[0].respuesta], pasos: q.pasos, origen: "Subneteo" });
  SUB.total++;
  if (ok) { SUB.buenas++; SUB.racha++; SUB.mejorRacha = Math.max(SUB.mejorRacha, SUB.racha); } else SUB.racha = 0;
  marcadorSubneteo();
  if (SUB.limite) {  // contra reloj: sin pausa; la solución queda abajo por si la quieres ver
    $("#subFeedback").innerHTML = (ok ? `<p class="nota alta">✓ Correcto</p>` : `<p class="nota baja">✗ ${esc(q.texto)} → <code>${esc(q.campos[0].respuesta)}</code></p>`) + (ok ? "" : pasosHtml(q));
    return siguienteSubneteo();
  }
  SUB.revisada = true;
  $("#subFeedback").innerHTML = (ok ? `<p class="nota alta">✓ Correcto</p>` : `<p class="nota baja">✗ Revisa los campos en rojo</p>`) + pasosHtml(q);
  if (!ok) $("#subFeedback details").open = true;
  $("#btnSubComprobar").textContent = "Siguiente →";
  $("#btnSubComprobar").focus();
}

function examenSubneteo(n, cat) {
  SUB.examen = Array.from({ length: n }, (_, i) => (i % 5 === 4 && cat === "todo" ? (i % 10 === 9 ? vlsmAzar : GENERADORES.find(([c]) => c === "completo")[1]) : genDe(cat, false))());
  $("#subneteoVista").innerHTML = `<div class="tarjeta">
    <div class="sub-marcador"><span>Examen de subneteo · ${n} ejercicios · ${CATS[cat]}</span><span id="subReloj"></span></div>
    <p class="sub">No ves si vas bien hasta entregar. Al final te dice la nota y cómo se resolvía cada uno.</p>
    ${SUB.examen.map((q, i) => `<div class="pregunta" data-sx="${i}"><div class="enun">${i + 1}. ${esc(q.texto)}</div>${camposHtml(q, `x${i}_`)}<div class="expl"></div></div>`).join("")}
    <div class="acciones"><button class="primario" id="btnSubEntregar">Entregar</button></div><div id="subFeedback"></div></div>`;
  SUB.reloj = setInterval(relojSubneteo, 250);
  $("#btnSubEntregar").addEventListener("click", () => {
    let puntos = 0, max = 0;
    SUB.examen.forEach((q, i) => {
      const ok = calificaCampos(q, `x${i}_`);
      puntos += ok / q.campos.length; max += 1;
      const div = $(`[data-sx="${i}"]`);
      div.classList.add(ok === q.campos.length ? "bien" : "mal");
      $(".expl", div).innerHTML = pasosHtml(q);
    });
    SUB.buenas = Math.round(puntos * 10) / 10; SUB.total = max;
    $("#btnSubEntregar").remove();
    terminarSubneteo(true);
  });
}

async function terminarSubneteo(esExamen) {
  if (!SUB.activo) return;
  SUB.activo = false;
  clearInterval(SUB.reloj);
  const seg = Math.round((Date.now() - SUB.inicio) / 1000);
  const nota = SUB.total ? Math.round((100 * SUB.buenas) / SUB.total) : 0;
  SUB.ultimo = `${SUB.buenas}/${SUB.total} (${nota}%) en ${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}` + (esExamen === true ? "" : `, mejor racha ${SUB.mejorRacha}`);
  if (SUB.total) api("/api/subneteo/resultado", { buenas: SUB.buenas, total: SUB.total, segundos: seg,
    titulo: esExamen === true ? `Examen de subneteo (${CATS[SUB.cat]})` : `Subneteo: ${CATS[SUB.cat]}` }).catch(() => {});
  const res = `<div class="tarjeta"><div class="resultado"><span class="calif nota ${notaClase(nota / 10)}">${nota}%</span>
    <span class="sub"> · ${SUB.buenas} de ${SUB.total} · ${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}</span>
    <div class="acciones"><button id="btnSubOtra">Otra ronda</button></div></div></div>`;
  if (esExamen === true) {  // deja el examen calificado a la vista para repasar
    $("#subFeedback").innerHTML = res;
    $("#btnSubOtra").addEventListener("click", pintarSubneteoInicio);
    return;
  }
  pintarSubneteoInicio();
  $("#subneteoVista").insertAdjacentHTML("afterbegin", res);
  $("#btnSubOtra").addEventListener("click", empezarSubneteo.bind(null));
}

// ---------------------------------------------------------------- historial
async function cargarHistorial() {
  const filas = await api("/api/historial");
  const nombreTema = (id) => id === "constructor" ? "Constructor" : id === "simulacro" ? "Todos (simulacro)"
    : id === "wireshark" ? "Análisis de tráfico" : id === "linux" ? "Linux" : id === "retos" ? "Arrastrar y soltar" : id === "rvb" ? "Red vs Blue"
    : String(id).startsWith("jefe_") ? `Jefe final ${id.slice(5)}`
    : ESTADO?.temas.find((t) => t.id === id)?.nombre
      || (String(id).startsWith("lx_") ? `Linux · ${id.slice(3)}` : String(id).startsWith("ws_") ? `Wireshark · ${id.slice(3)}` : "Libre");
  const mundoTxt = (f) => f.mundo && f.mundo !== "ccna" && MUNDOS[f.mundo] ? ` <span data-no-tr>${MUNDOS[f.mundo].split(" ")[0]}</span>` : "";
  $("#tablaHist").innerHTML = filas.length ? `<tr><th>Fecha</th><th>Tipo</th><th>Título</th><th>Tema</th><th>Nota</th><th></th></tr>` +
    filas.map((f) => `<tr class="clic" data-clase="${f.clase}" data-tema="${esc(f.tema)}" data-id="${f.id}">
      <td>${esc(f.fecha)}</td><td>${f.clase === "examen" ? "Examen" + mundoTxt(f) : f.clase === "rvb" ? "Red vs Blue" : f.clase === "wireshark" ? "Wireshark" : f.tema === "constructor" ? "Topología" : "Práctica"}</td><td>${esc(f.titulo)}</td>
      <td>${esc(nombreTema(f.tema))}</td>
      <td class="nota ${notaClase(f.calificacion)}">${f.calificacion == null ? "—" : f.calificacion}</td>
      <td>${f.clase === "practica" ? `<span class="sub">${f.intentos} intento(s)</span>` : ""}</td></tr>`).join("")
    : '<tr><td class="sub">Aún no hay nada. Empieza por la ruta de temas.</td></tr>';
  $$("#tablaHist tr.clic").forEach((tr) => tr.addEventListener("click", () =>
    tr.dataset.clase === "examen" ? abrirExamen(+tr.dataset.id)
      : tr.dataset.clase === "wireshark" ? (ir("wireshark"), abrirCapturaWs(+tr.dataset.id))
      : tr.dataset.clase === "rvb" ? ir("rvb")
      : tr.dataset.tema === "constructor" ? abrirTopologia(+tr.dataset.id) : abrirPractica(+tr.dataset.id)));
}

// ---------------------------------------------------------------- teoría (lecciones + lector de voz)
let TEORIA = null, LECCION = null;
const LECTOR = { cola: [], i: 0, activo: false, pausado: false };
const lsGet = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch {} };

function vocesDe(idioma) {
  const pre = idioma === "en" ? /^en/i : /^es/i;
  const v = speechSynthesis.getVoices().filter((x) => pre.test(x.lang));
  const pref = idioma === "en" ? /en-US/i : /es-MX/i;
  return v.sort((a, b) => (pref.test(b.lang) + /natural/i.test(b.name) * 2) - (pref.test(a.lang) + /natural/i.test(a.name) * 2));
}

async function cargarTeoria() {
  TEORIA = await api("/api/teoria");
  const mundo = TEORIA_MUNDO;
  const temas = TEORIA.temas.filter((t) => !mundo || mundoDeTema(t.id) === mundo);
  const grupos = {};
  temas.forEach((t) => (grupos[t.grupo] ||= []).push(t));
  const previo = $("#tTema").value;
  $("#tTema").innerHTML = '<option value="">— Libre (usa el enfoque) —</option>' + Object.entries(grupos).map(([g, ts]) =>
    `<optgroup label="${esc(g)}">${ts.map((t) => `<option value="${t.id}">${esc(t.nombre)}</option>`).join("")}</optgroup>`).join("");
  const sel = TEORIA_SEL || previo;
  if (sel && temas.some((t) => t.id === sel)) $("#tTema").value = sel;
  TEORIA_SEL = null;
  if (!$("#tIdioma").dataset.listo) { $("#tIdioma").value = lsGet("teoria_idioma", IDIOMA_UI); $("#tIdioma").dataset.listo = "1"; }
  $("#tMundo").innerHTML = mundo ? `<span class="pill">${esc(MUNDOS[mundo] || mundo)}</span> <span class="sub">Solo los temas de este mundo.</span> <a href="#" id="tTodos">Ver todos los mundos</a>` : "";
  $("#tTodos")?.addEventListener("click", (ev) => { ev.preventDefault(); TEORIA_MUNDO = null; cargarTeoria(); });
  if (mundo) marcarMundoEnNav(mundo);
  const lecciones = TEORIA.lecciones.filter((l) => !mundo || mundoDeTema(l.tema) === mundo);
  const viejas = TEORIA.lecciones.filter((l) => (l.version || 1) < 2).length;
  const nombre = (id) => TEORIA.temas.find((t) => t.id === id)?.nombre || "Libre";
  $("#tGuardadas").innerHTML = `<h3 style="margin-top:0">Tus lecciones</h3>`
    + (viejas ? `<div class="aviso-idioma"><span>Tienes ${viejas} lección(es) en el formato viejo (sin ejemplos resueltos, práctica ni quiz).</span>
        <button class="chico primario" id="tActualizar">✨ Pasarlas al formato nuevo</button></div><div id="tActualizarCaja"></div>` : "")
    + (lecciones.length
    ? `<table class="tabla"><tr><th>Fecha</th><th>Lección</th><th>Tema</th><th>Idioma</th><th></th></tr>${lecciones.map((l) => `
      <tr class="clic" data-lec="${l.id}"><td>${esc(l.fecha)}</td><td>${l.leida ? "✅ " : "📖 "}${esc(l.titulo)}</td><td class="sub">${esc(nombre(l.tema))}</td>
      <td>${l.idioma === "en" ? "English" : "Español"}</td><td><button class="chico peligro" data-lec-borrar="${l.id}">Borrar</button></td></tr>`).join("")}</table>`
    : '<p class="sub">Aún no tienes lecciones. Elige un tema y prepara la primera.</p>');
  $$("[data-lec]").forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.dataset.lecBorrar) abrirLeccion(+tr.dataset.lec); }));
  $("#tActualizar")?.addEventListener("click", async (ev) => {
    if (!window.confirm(`Voy a regenerar ${viejas} lección(es) con el formato nuevo. Tarda unos 3-4 min por lección y usa la GPU. ¿Empezamos?`)) return;
    ev.target.disabled = true;
    try { const r = await trabajo("/api/teoria/actualizar", {}, $("#tActualizarCaja")); aviso(`${r.actualizadas} lecciones actualizadas`); }
    catch (e) { aviso(e.message); }
    cargarTeoria();
  });
  $$("[data-lec-borrar]").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/teoria/borrar", { id: +b.dataset.lecBorrar });
    if (LECCION?.id === +b.dataset.lecBorrar) { pararLectura(); $("#teoriaVista").innerHTML = ""; LECCION = null; }
    cargarTeoria();
  }));
}

$("#btnLeccion").addEventListener("click", async () => {
  const btn = $("#btnLeccion"), tema = $("#tTema").value, enfoque = $("#tEnfoque").value.trim();
  if (!tema && !enfoque) return aviso("Elige un tema o escribe el enfoque");
  lsSet("teoria_idioma", $("#tIdioma").value);
  btn.disabled = true;
  pararLectura();
  try {
    const { id } = await trabajo("/api/teoria/generar", { tema, idioma: $("#tIdioma").value, enfoque, mundo: TEORIA_MUNDO || "" }, $("#teoriaVista"));
    await abrirLeccion(id);
    cargarTeoria();
  } catch (e) { $("#teoriaVista").innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
  finally { btn.disabled = false; }
});

// ---- lecciones v2 (mini-curso): ejemplos resueltos, práctica con solución, quiz y laboratorio
const inlLec = (t) => esc(t).replace(/`([^`]+)`/g, '<code data-no-tr>$1</code>').replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
const parrafosLec = (t) => String(t || "").split(/\n+/).filter((x) => x.trim()).map((p) => `<p>${inlLec(p)}</p>`).join("");

function bloquesLeccionV2(l, T) {
  const b = [];
  b.push({ html: `<p class="lec-intro">${inlLec(l.intro)}</p>`
    + (l.objetivos?.length ? `<div class="lec-caja lec-objetivos"><div class="lec-caja-tit">🎯 ${T.objetivos}</div><ul class="lec-check">${l.objetivos.map((o) => `<li>${inlLec(o)}</li>`).join("")}</ul></div>` : "")
    + (l.metodos_clave?.length ? `<div class="lec-caja lec-metodos"><div class="lec-caja-tit">🧰 ${T.metodos}</div><ul>${l.metodos_clave.map((o) => `<li>${inlLec(o)}</li>`).join("")}</ul></div>` : ""),
    voz: [l.intro, ...(l.objetivos || [])].join(". ") });
  l.secciones.forEach((s, i) => {
    const ej = s.ejemplo || {}, pr = s.practica || {};
    const h = htmlSeccionV2(s, i, T);
    const vozEj = ej.pasos?.length ? `${T.ejemplo}. ${ej.titulo || ""}. ${ej.pasos.map((p) => `${p.paso}. ${p.detalle}`).join(". ")}. ${ej.resultado || ""}` : "";
    b.push({ html: h, voz: [s.titulo, s.texto, s.analogia, vozEj, pr.enunciado ? `${T.pruebalo}. ${pr.enunciado}` : ""].filter(Boolean).join(". ") });
  });
  return bloquesCierreV2(l, T, b);
}

const TXT_SEC = {
  en: { analogia: "Think of it like this:", ejemplo: "Worked example", codigo: "Code", copiar: "Copy", pruebalo: "Try it yourself", pista: "Hint", solucion: "Solution",
    fondo: "📖 In-depth theory", ocultar: "Hide in-depth theory", nota: "Generated once with your model and saved: next time it opens instantly." },
  es: { analogia: "Piénsalo así:", ejemplo: "Ejemplo resuelto", codigo: "Código", copiar: "Copiar", pruebalo: "Pruébalo tú", pista: "Pista", solucion: "Solución",
    fondo: "📖 Teoría a fondo", ocultar: "Ocultar teoría a fondo", nota: "Se genera una vez con tu modelo y queda guardada: la próxima vez abre al instante." },
};

/** Primero la base: si vas a un examen sin haber leído la lección ni practicado ese tema, en vez de generarlo de golpe
 *  te ofrece ir a la lección o a la práctica (o hacerlo de todos modos, para saltarte lo que ya dominas). */
async function antesDelExamen(caja, { tema, hayPractica, alLeccion, alPractica, alExamen }) {
  let leida = false;
  try { leida = (await api("/api/teoria")).lecciones.some((l) => l.tema === tema && l.leida); } catch {}
  if (leida || hayPractica || !caja) return alExamen();
  caja.innerHTML = `<div class="aviso-base"><b>📚 Primero la base</b>
    <p class="sub">Aún no has leído la lección ni hecho la práctica de este tema. El examen es para comprobar lo que ya aprendiste, o para saltarte el tema si ya lo dominas.</p>
    <div class="acciones"><button class="primario" data-b-lec>📖 Ver la lección</button>${alPractica ? "<button data-b-prac>🎯 Ir a la práctica</button>" : ""}
      <button data-b-ex>📝 Ya lo sé: examen de todos modos</button><button class="chico" data-b-no>✕</button></div></div>`;
  caja.hidden = false;
  caja.scrollIntoView({ block: "nearest" });
  $("[data-b-lec]", caja).addEventListener("click", () => { caja.innerHTML = ""; alLeccion(); });
  $("[data-b-prac]", caja)?.addEventListener("click", () => { caja.innerHTML = ""; alPractica(); });
  $("[data-b-ex]", caja).addEventListener("click", () => { caja.innerHTML = ""; alExamen(); });
  $("[data-b-no]", caja).addEventListener("click", () => { caja.innerHTML = ""; });
}

/** 📖 Teoría a fondo de una misión: explicación completa con ejemplo resuelto (distinto al reto), código y calentamiento.
 *  Antes cada misión solo traía 30-50 palabras de teoría. Se genera una vez y queda en caché. */
async function teoriaAFondo(boton, caja, { clave, mundo, titulo, contexto }) {
  const idioma = IDIOMA_UI === "en" ? "en" : "es", T = TXT_SEC[idioma];
  if (caja.dataset.listo) { caja.hidden = !caja.hidden; boton.textContent = caja.hidden ? T.fondo : T.ocultar; return; }
  caja.hidden = false;
  boton.disabled = true;
  try {
    const r = await trabajo("/api/teoria/mision", { clave, mundo, titulo, contexto, idioma }, caja);
    const d = r.datos;
    caja.innerHTML = `<div class="leccion lec2 lec-mision">${htmlSeccionV2({ ...d, titulo: d.titulo || titulo }, 0, T)}<p class="sub">${T.nota}</p></div>`;
    $$("[data-copiar]", caja).forEach((b) => b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(b.closest(".lec-codigo").querySelector("pre").innerText); aviso(T.copiar + " ✓"); } catch {}
    }));
    caja.dataset.listo = "1";
    boton.textContent = T.ocultar;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  boton.disabled = false;
}

/** Una sección de lección v2 (también la usa la "Teoría a fondo" de las misiones). */
function htmlSeccionV2(s, i, T) {
    const ej = s.ejemplo || {}, cod = s.codigo || {}, pr = s.practica || {};
    let h = `<section class="lec-sec" id="lec-s${i}"><div class="lec-sec-cab"><span class="lec-num">${i + 1}</span><h3>${esc(s.titulo)}</h3></div>${parrafosLec(s.texto)}`;
    if (s.analogia) h += `<div class="lec-callout lec-analogia"><b>💡 ${T.analogia}</b> ${inlLec(s.analogia)}</div>`;
    if (ej.pasos?.length) h += `<div class="lec-ejemplo"><div class="lec-caja-tit">🧮 ${T.ejemplo}${ej.titulo ? `: ${inlLec(ej.titulo)}` : ""}</div>
      <ol class="lec-pasos">${ej.pasos.map((p) => `<li><div class="lec-paso">${inlLec(p.paso)}</div><div class="lec-detalle">${inlLec(p.detalle)}</div></li>`).join("")}</ol>
      ${ej.resultado ? `<div class="lec-resultado">✅ ${inlLec(ej.resultado)}</div>` : ""}</div>`;
    if ((cod.contenido || "").trim()) h += `<div class="lec-codigo"><div class="lec-cod-cab"><span data-no-tr>${esc(cod.lenguaje || T.codigo)}</span><button class="chico" data-copiar>📋 ${T.copiar}</button></div>
      <pre data-no-tr><code>${esc(cod.contenido)}</code></pre>${cod.explicacion ? `<div class="lec-cod-exp">${inlLec(cod.explicacion)}</div>` : ""}</div>`;
    if (pr.enunciado) h += `<div class="lec-practica"><div class="lec-caja-tit">🧪 ${T.pruebalo}</div><p>${inlLec(pr.enunciado)}</p>
      ${pr.pista ? `<details><summary>💡 ${T.pista}</summary>${parrafosLec(pr.pista)}</details>` : ""}
      ${pr.solucion ? `<details><summary>✅ ${T.solucion}</summary>${parrafosLec(pr.solucion)}</details>` : ""}</div>`;
    return h + "</section>";
}

function bloquesCierreV2(l, T, b) {
  if (l.comandos?.length) b.push({ html: `<div class="lec-caja"><div class="lec-caja-tit">⌨️ ${T.cmds}</div><table class="tabla lec-cmds">${l.comandos.map((c) =>
    `<tr><td><code data-no-tr>${esc(c.comando)}</code></td><td>${inlLec(c.que_hace)}</td></tr>`).join("")}</table></div>`,
    voz: `${T.cmds}. ` + l.comandos.map((c) => `${c.comando}: ${c.que_hace}`).join(". ") });
  if (l.puntos_clave?.length || l.errores_comunes?.length) b.push({ html: `<div class="lec-dos">
    ${l.puntos_clave?.length ? `<div class="lec-caja lec-clave"><div class="lec-caja-tit">⭐ ${T.clave}</div><ul class="lec-check">${l.puntos_clave.map((p) => `<li>${inlLec(p)}</li>`).join("")}</ul></div>` : ""}
    ${l.errores_comunes?.length ? `<div class="lec-caja lec-errores"><div class="lec-caja-tit">⚠️ ${T.errores}</div><ul>${l.errores_comunes.map((p) => `<li>${inlLec(p)}</li>`).join("")}</ul></div>` : ""}</div>`,
    voz: `${T.clave}. ${(l.puntos_clave || []).join(". ")}. ${T.errores}. ${(l.errores_comunes || []).join(". ")}` });
  const lab = l.laboratorio || {};
  if (lab.pasos?.length) b.push({ html: `<div class="lec-lab"><div class="lec-caja-tit">🛠️ ${T.lab}${lab.titulo ? `: ${inlLec(lab.titulo)}` : ""}</div>
    ${lab.objetivo ? `<p><b>${T.objetivo}:</b> ${inlLec(lab.objetivo)}</p>` : ""}
    <ol class="lec-lab-pasos">${lab.pasos.map((p) => `<li><label><input type="checkbox"> <span>${inlLec(p)}</span></label></li>`).join("")}</ol>
    ${lab.verificacion ? `<div class="lec-callout lec-verif"><b>🔍 ${T.verifica}</b> ${inlLec(lab.verificacion)}</div>` : ""}</div>`,
    voz: `${T.lab}. ${lab.titulo || ""}. ${lab.objetivo || ""}. ${lab.pasos.join(". ")}. ${lab.verificacion || ""}` });
  return b;
}

function quizLeccionV2(l, T) {
  if (!l.quiz?.length) return "";
  return `<div class="lec-quiz"><div class="lec-caja-tit">📝 ${T.quiz}</div>${l.quiz.map((q, i) => `<div class="lec-q" data-q="${i}">
    <div class="lec-q-preg"><b>${i + 1}.</b> ${inlLec(q.pregunta)}</div>
    <div class="lec-ops">${q.opciones.map((o, j) => `<button class="lec-op" data-op="${j}"><b>${"ABCD"[j]}</b> ${inlLec(o)}</button>`).join("")}</div>
    <div class="lec-q-exp"></div></div>`).join("")}<div class="lec-q-total" id="lecQuizTotal"></div></div>`;
}

function activarLeccionV2(l, T) {
  $$("[data-ir-sec]").forEach((a) => a.addEventListener("click", (ev) => { ev.preventDefault(); $(`#lec-s${a.dataset.irSec}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }));
  $$("[data-copiar]").forEach((b) => b.addEventListener("click", async () => {
    const txt = b.closest(".lec-codigo").querySelector("pre").innerText;
    try { await navigator.clipboard.writeText(txt); aviso(T.copiar + " ✓"); } catch { aviso("No se pudo copiar"); }
  }));
  let bien = 0, hechas = 0;
  $$(".lec-q").forEach((qd) => {
    const q = l.quiz[+qd.dataset.q];
    $$(".lec-op", qd).forEach((b) => b.addEventListener("click", () => {
      if (qd.dataset.listo) return;
      qd.dataset.listo = "1"; hechas++;
      const j = +b.dataset.op, ok = j === q.correcta;
      if (ok) bien++;
      $$(".lec-op", qd).forEach((x) => { x.disabled = true; if (+x.dataset.op === q.correcta) x.classList.add("ok"); });
      if (!ok) b.classList.add("mal");
      $(".lec-q-exp", qd).innerHTML = `<div class="${ok ? "ac-ok" : "ac-error"}">${ok ? "✓" : "✗"} ${inlLec(q.explicacion || "")}</div>`;
      $("#lecQuizTotal").innerHTML = `<b>${bien}/${hechas}</b> ${T.correctas}${hechas === l.quiz.length ? (bien === hechas ? " 🎉" : "") : ""}`;
    }));
  });
}

async function abrirLeccion(id) {
  pararLectura();
  LECCION = await api(`/api/teoria/${id}`);
  pintarLeccion();
  window.scrollTo(0, 0);
}

function pintarLeccion() {
  const l = LECCION, en = IDIOMA_UI === "en";  // los botones van en el idioma de la interfaz; la voz, en el de la lección
  const T = en ? { escuchar: "▶ Listen", pausa: "⏸ Pause", parar: "⏹ Stop", vel: "Speed", voz: "Voice", cmds: "Commands",
    clave: "Key points", errores: "Common mistakes", duda: "Ask the tutor", preguntar: "Ask", ph: "Type or dictate your question…",
    examen: "Exam on this topic", practica: "Practice on this topic" }
    : { escuchar: "▶ Escuchar", pausa: "⏸ Pausa", parar: "⏹ Parar", vel: "Velocidad", voz: "Voz", cmds: "Comandos",
    clave: "Puntos clave", errores: "Errores comunes", duda: "Pregúntale al tutor", preguntar: "Preguntar", ph: "Escribe o dicta tu pregunta…",
    examen: "Examen de este tema", practica: "Práctica de este tema" };
  const v2 = l.version === 2, mundoL = mundoDeTema(l.tema);
  Object.assign(T, en
    ? { objetivos: "By the end you will be able to", metodos: "Key methods", analogia: "Think of it like this:", ejemplo: "Worked example", codigo: "Code",
      copiar: "Copy", pruebalo: "Try it yourself", pista: "Hint", solucion: "Solution", quiz: "Check what you learned", lab: "Final lab",
      objetivo: "Goal", verifica: "How to verify:", secciones: "sections", ejercicios: "exercises", min: "min", indice: "Contents", preguntas: "questions",
      correctas: "correct", examenMundo: "📝 Exam on this topic" }
    : { objetivos: "Al terminar podrás", metodos: "Métodos clave", analogia: "Piénsalo así:", ejemplo: "Ejemplo resuelto", codigo: "Código",
      copiar: "Copiar", pruebalo: "Pruébalo tú", pista: "Pista", solucion: "Solución", quiz: "Comprueba lo que aprendiste", lab: "Laboratorio final",
      objetivo: "Objetivo", verifica: "Cómo verificarlo:", secciones: "secciones", ejercicios: "ejercicios", min: "min", indice: "Contenido", preguntas: "preguntas",
      correctas: "correctas", examenMundo: "📝 Examen de este tema" });
  const bloques = v2 ? bloquesLeccionV2(l, T) : [{ html: `<p>${esc(l.intro)}</p>`, voz: l.intro }];
  if (!v2) {
    l.secciones.forEach((s) => bloques.push({ html: `<h3>${esc(s.titulo)}</h3>${s.texto.split(/\n+/).map((p) => `<p>${esc(p)}</p>`).join("")}`, voz: `${s.titulo}. ${s.texto}` }));
    if (l.comandos.length) bloques.push({ html: `<h3>${T.cmds}</h3>${l.comandos.map((c) => `<div class="cmd-lec"><code>${esc(c.comando)}</code><span>${esc(c.que_hace)}</span></div>`).join("")}`,
      voz: `${T.cmds}. ` + l.comandos.map((c) => `${c.comando}: ${c.que_hace}`).join(". ") });
    if (l.puntos_clave.length) bloques.push({ html: `<h3>${T.clave}</h3><ul>${l.puntos_clave.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`, voz: `${T.clave}. ` + l.puntos_clave.join(". ") });
    if (l.errores_comunes.length) bloques.push({ html: `<h3>${T.errores}</h3><ul>${l.errores_comunes.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`, voz: `${T.errores}. ` + l.errores_comunes.join(". ") });
  }
  LECCION.bloques = bloques;
  const enTemario = ESTADO?.temas.find((t) => t.id === l.tema);
  const palabras = bloques.reduce((n, b) => n + String(b.voz || "").split(/\s+/).length, 0);
  const nPrac = v2 ? l.secciones.filter((s) => s.practica?.enunciado).length : 0;
  $("#teoriaVista").innerHTML = `<div class="tarjeta destacada leccion ${v2 ? "lec2" : ""}">
    ${v2 ? `<div class="lec-hero">
      <div class="lec-hero-top"><span class="pill">${esc(MUNDOS[mundoL] || "")}</span><span class="pill">${l.idioma === "en" ? "English" : "Español"}</span>${l.con_guias ? '<span class="pill ok">Con tus guías</span>' : ""}</div>
      <h2>${esc(l.titulo)}</h2>
      <div class="lec-meta">⏱ ~${Math.max(5, Math.round(palabras / 170))} ${T.min} · 📚 ${l.secciones.length} ${T.secciones} · 🧪 ${nPrac} ${T.ejercicios}${l.quiz?.length ? ` · 📝 ${l.quiz.length} ${T.preguntas}` : ""}</div>
      <nav class="lec-indice"><b>${T.indice}</b>${l.secciones.map((s, i) => `<a href="#" data-ir-sec="${i}">${i + 1}. ${esc(s.titulo)}</a>`).join("")}</nav>
    </div>`
    : `<h2>${esc(l.titulo)} <span class="pill">${l.idioma === "en" ? "English" : "Español"}</span>${l.con_guias ? '<span class="pill ok">Con tus guías</span>' : ""}</h2>`}
    <div class="lector">
      <button class="primario" id="lPlay">${T.escuchar}</button><button id="lPausa">${T.pausa}</button><button id="lParar">${T.parar}</button>
      <label>${T.vel}<select id="lVel">${[0.8, 0.9, 1, 1.1, 1.25, 1.5].map((v) => `<option ${+lsGet("teoria_vel", 1) === v ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label>${T.voz}<select id="lVoz"></select></label>
    </div>
    <p class="sub">${en ? "Tip: click any paragraph to start reading from there. Keys: Space = pause/resume · ←/→ = previous/next paragraph · Esc = stop." : "Tip: haz clic en cualquier párrafo para leer desde ahí. Teclas: Espacio = pausa/sigue · ←/→ = párrafo anterior/siguiente · Esc = parar."}</p>
    ${IDIOMA_UI !== l.idioma ? `<div class="aviso-idioma">${IDIOMA_UI === "en" ? "🌐 This lesson was made in Spanish." : "🌐 Esta lección está en inglés."}
      <button class="chico primario" id="lTraducir">${IDIOMA_UI === "en" ? "Translate it to English" : "Traducirla al español"}</button></div>` : ""}
    ${bloques.map((b, i) => `<div class="bloque" data-b="${i}">${b.html}</div>`).join("")}
    ${v2 ? quizLeccionV2(l, T) : ""}
    <div class="acciones">${enTemario ? `<button id="lExamen">${T.examen}</button><button id="lPractica">${T.practica}</button>` : ""}
      ${!enTemario && mundoL !== "ccna" && !/^libre/.test(l.tema) ? `<button id="lExamenMundo">${T.examenMundo}</button>` : ""}
      ${l.tema.startsWith("ws_") ? `<button id="lWs">Wireshark</button>` : ""}</div>
    <div class="tarjeta sigue" id="lSigue"></div>
    <div class="acciones" id="lLeidaCaja">${l.leida ? `<span class="pill ok">✓ ${en ? "Read" : "Leída"}</span>` : `<button class="primario" id="lLeida">✅ ${en ? "I finished it (+15 XP)" : "Terminé de leerla (+15 XP)"}</button>`}</div>
    <h3>${T.duda}</h3>
    <div class="fila-filtro"><input id="lDuda" placeholder="${T.ph}"><button id="lMic" title="Dictar">🎤</button><button class="primario" id="lPreguntar">${T.preguntar}</button></div>
    <div id="lRespuesta"></div>
  </div>`;
  const llenarVoces = () => {
    const vs = vocesDe(l.idioma), guardada = lsGet("teoria_voz_" + l.idioma, "") || lsGet("voz_" + l.idioma, "");
    $("#lVoz").innerHTML = vs.length ? vs.map((v) => `<option value="${esc(v.name)}" ${v.name === guardada ? "selected" : ""}>${esc(v.name.replace(/^Microsoft /, ""))}</option>`).join("")
      : `<option value="">${l.idioma === "en" ? "No English voice installed" : "No hay voz en español"}</option>`;
  };
  llenarVoces();
  speechSynthesis.addEventListener("voiceschanged", () => { if ($("#lVoz")) llenarVoces(); });
  $("#lVoz").addEventListener("change", () => lsSet("teoria_voz_" + l.idioma, $("#lVoz").value));
  $("#lVel").addEventListener("change", () => lsSet("teoria_vel", $("#lVel").value));
  $("#lPlay").addEventListener("click", () => leerDesde(LECTOR.activo ? LECTOR.bloque || 0 : 0));
  $("#lPausa").addEventListener("click", () => {
    if (!LECTOR.activo) return;
    if (LECTOR.pausado) { speechSynthesis.resume(); LECTOR.pausado = false; } else { speechSynthesis.pause(); LECTOR.pausado = true; }
  });
  $("#lParar").addEventListener("click", pararLectura);
  // clic en un párrafo = leer desde ahí (pero no al abrir una pista, copiar código, marcar el lab o contestar el quiz)
  $$(".bloque").forEach((b) => b.addEventListener("click", (ev) => { if (!ev.target.closest("details,summary,button,input,label,a,pre,.lec-codigo")) leerDesde(+b.dataset.b); }));
  if (v2) activarLeccionV2(l, T);
  $("#lExamenMundo")?.addEventListener("click", async () => {
    pararLectura();
    irExamenMundo(mundoL);
    const caja = $("#examenVista");
    try {
      const { id } = await trabajo("/api/examen/generar", { dominio: mundoL, tema: l.tema, n: 10, nivel: "Intermedio",
        descripcion: `${l.titulo}. ${(l.objetivos || []).join("; ")}` }, caja);
      await abrirExamen(id);
    } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
  });
  $("#lExamen")?.addEventListener("click", () => { pararLectura(); ir("examen"); $("#eTema").value = enTemario.id; $("#eNivel").value = enTemario.nivel; });
  $("#lPractica")?.addEventListener("click", () => { pararLectura(); ir("practica"); $("#pTema").value = enTemario.id; $("#pNivel").value = enTemario.nivel; });
  $("#lWs")?.addEventListener("click", () => { pararLectura(); ir("wireshark"); });
  $("#lPreguntar").addEventListener("click", preguntarTutor);
  $("#lLeida")?.addEventListener("click", marcarLeida);
  $("#lTraducir")?.addEventListener("click", async (ev) => {
    ev.target.disabled = true; pararLectura();
    try { const { id } = await trabajo("/api/teoria/traducir", { id: l.id, idioma: IDIOMA_UI }, $("#lSigue")); await abrirLeccion(id); cargarTeoria(); }
    catch (e) { aviso(e.message); ev.target.disabled = false; }
  });
  pintarSiguePaso();
  $("#lDuda").addEventListener("keydown", (e) => { if (e.key === "Enter") preguntarTutor(); });
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) $("#lMic").remove();
  else $("#lMic").addEventListener("click", () => {
    const r = new SR();
    r.lang = en ? "en-US" : "es-MX";
    r.interimResults = true;
    $("#lMic").classList.add("hablando");
    r.onresult = (e) => { $("#lDuda").value = [...e.results].map((x) => x[0].transcript).join(""); };
    r.onerror = (e) => aviso(e.error === "not-allowed" ? "Da permiso al micrófono" : "No pude oírte: " + e.error);
    r.onend = () => { $("#lMic")?.classList.remove("hablando"); if ($("#lDuda").value.trim()) preguntarTutor(); };
    r.start();
  });
}

// ---- al terminar una lección: siguiente tema, practicar y volver a la ruta
async function pintarSiguePaso() {
  const l = LECCION, en = IDIOMA_UI === "en", caja = $("#lSigue");
  if (!caja) return;
  if (!TEORIA) { try { TEORIA = await api("/api/teoria"); } catch { return; } }
  const temas = TEORIA.temas, i = temas.findIndex((t) => t.id === l.tema), t = temas[i];
  const sig = i >= 0 ? temas.slice(i + 1).find((x) => x.grupo === t.grupo) : null;
  const pref = l.tema.split("_")[0];
  const practica = l.tema.startsWith("ws_") ? (en ? "🦈 Practice this in Wireshark" : "🦈 Practicarlo en Wireshark")
    : l.tema.startsWith("lx_") ? (en ? "🖥️ Linux missions for this topic" : "🖥️ Misiones de Linux de este tema")
    : l.tema.startsWith("ac_") ? (en ? "🎯 Missions of this level" : "🎯 Misiones de este nivel") : "";
  const volver = pref === "ws" ? "wireshark" : pref === "lx" ? "linux" : pref === "ac" ? l.tema.split("_")[1] : "ruta";
  caja.innerHTML = `<b>${en ? "What next?" : "¿Qué sigue?"}</b><div class="acciones">
    ${sig ? `<button class="primario" id="lSig">📚 ${en ? "Next lesson" : "Siguiente lección"}: ${esc(tr(sig.nombre))}</button>` : ""}
    ${practica ? `<button id="lPrac2">${practica}</button>` : ""}
    <button id="lVolver">← ${en ? "Back to the path" : "Volver a la ruta"}</button></div>`;
  $("#lSig")?.addEventListener("click", async (ev) => {
    pararLectura(); ev.target.disabled = true;
    const ya = TEORIA.lecciones.find((x) => x.tema === sig.id && x.idioma === IDIOMA_UI);
    if (ya) return abrirLeccion(ya.id);
    $("#tTema").value = sig.id; $("#tIdioma").value = IDIOMA_UI;
    window.scrollTo(0, 0);
    $("#btnLeccion").click();
  });
  $("#lPrac2")?.addEventListener("click", () => {
    pararLectura();
    if (l.tema.startsWith("ws_")) {
      ir("wireshark");
      const esc_ = l.tema.slice(3);
      setTimeout(() => { const b = document.querySelector(`[data-r-prac="ws_${esc_}"]`); if (b) b.click(); }, 1500);
    } else if (l.tema.startsWith("lx_")) {
      ir("linux");
      setTimeout(() => { const b = document.querySelector(`[data-r-prac="${l.tema}"]`); if (b) { b.click(); b.scrollIntoView({ block: "center" }); } }, 1500);
    } else ir(volver);
  });
  $("#lVolver").addEventListener("click", () => { pararLectura(); ir(volver); });
}

// atajos de teclado del lector (solo en Teoría y si no estás escribiendo)
document.addEventListener("keydown", (e) => {
  if (!$("#v-teoria")?.classList.contains("visible") || !LECCION?.bloques) return;
  if (e.target.closest("input, textarea, select") || e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.code === "Space") {
    e.preventDefault();
    if (!LECTOR.activo) return leerDesde(LECTOR.bloque || 0);
    if (LECTOR.pausado) { speechSynthesis.resume(); LECTOR.pausado = false; } else { speechSynthesis.pause(); LECTOR.pausado = true; }
  } else if (e.key === "Escape") pararLectura();
  else if (e.key === "ArrowRight" && LECTOR.activo) { e.preventDefault(); leerDesde(Math.min((LECTOR.bloque || 0) + 1, LECCION.bloques.length - 1)); }
  else if (e.key === "ArrowLeft" && LECTOR.activo) { e.preventDefault(); leerDesde(Math.max((LECTOR.bloque || 0) - 1, 0)); }
});

function frasesDe(texto) {
  return String(texto).replace(/\s+/g, " ").match(/[^.!?;:]+[.!?;:]*/g)?.map((s) => s.trim()).filter(Boolean) || [];
}

function hablar(texto, idioma, alTerminar) {
  const u = new SpeechSynthesisUtterance(texto.replace(/(\d)\/(\d)/g, idioma === "en" ? "$1 slash $2" : "$1 diagonal $2"));
  const v = speechSynthesis.getVoices().find((x) => x.name === $("#lVoz")?.value) || vocesDe(idioma)[0];
  if (v) u.voice = v;
  u.lang = v ? v.lang : (idioma === "en" ? "en-US" : "es-MX");
  u.rate = +($("#lVel")?.value || 1);
  u.onend = alTerminar;
  u.onerror = (e) => { if (e.error !== "interrupted" && e.error !== "canceled") alTerminar(); };
  speechSynthesis.speak(u);
}

function leerDesde(b) {
  if (!("speechSynthesis" in window)) return aviso("Este navegador no tiene voz");
  speechSynthesis.cancel();
  const token = (LECTOR.token = (LECTOR.token || 0) + 1);
  Object.assign(LECTOR, { activo: true, pausado: false, bloque: b });
  const siguienteBloque = (k) => {
    if (token !== LECTOR.token) return;
    $$(".bloque").forEach((x) => x.classList.toggle("leyendo", +x.dataset.b === k));
    if (k >= LECCION.bloques.length) { marcarLeida(); pararLectura(); $("#lSigue")?.scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    LECTOR.bloque = k;
    $(`.bloque[data-b="${k}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    const frases = frasesDe(LECCION.bloques[k].voz);
    const decir = (f) => {
      if (token !== LECTOR.token) return;
      if (f >= frases.length) return siguienteBloque(k + 1);
      hablar(frases[f], LECCION.idioma, () => decir(f + 1));  // frase por frase: Edge corta los textos largos
    };
    decir(0);
  };
  siguienteBloque(b);
}

function pararLectura() {
  LECTOR.token = (LECTOR.token || 0) + 1;
  Object.assign(LECTOR, { activo: false, pausado: false, bloque: 0 });
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  $$(".bloque").forEach((x) => x.classList.remove("leyendo"));
}

async function marcarLeida() {
  if (!LECCION || LECCION.leida) return;
  LECCION.leida = true;
  const r = await api("/api/teoria/leida", { id: LECCION.id }).catch(() => ({}));
  if ($("#lLeidaCaja")) $("#lLeidaCaja").innerHTML = `<span class="pill ok">✓ ${LECCION.idioma === "en" ? "Read" : "Leída"}</span>`;
  if (r.nueva) { refrescarJugador(true); revisarMisionDia(); cargarTeoria(); }
}

async function preguntarTutor() {
  const q = $("#lDuda").value.trim(), caja = $("#lRespuesta");
  if (!q) return;
  try {
    const r = await trabajo("/api/teoria/duda", { id: LECCION.id, pregunta: q }, caja);
    caja.innerHTML = `<div class="respuesta-tutor"><b>${esc(q)}</b>${md(r.respuesta)}<button class="chico voz" id="lOirResp">🔊</button></div>`;
    $("#lOirResp").addEventListener("click", () => {
      pararLectura();
      const token = LECTOR.token, fr = frasesDe(r.respuesta.replace(/[*`#_]/g, ""));
      const decir = (i) => { if (i < fr.length && token === LECTOR.token) hablar(fr[i], LECCION.idioma, () => decir(i + 1)); };
      decir(0);
    });
    $("#lDuda").value = "";
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}

// ---------------------------------------------------------------- tutor (en cualquier parte)
async function explicame(boton, area, contexto, pregunta) {
  const caja = boton.nextElementSibling;
  boton.disabled = true;
  try {
    const r = await trabajo("/api/tutor", { area, contexto, pregunta }, caja);
    caja.innerHTML = `<div class="respuesta-tutor">${md(r.respuesta)}</div>`;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; boton.disabled = false; }
}

// ---------------------------------------------------------------- modo juego
let JUGADOR = null;
async function refrescarJugador(anunciar) {
  let j;
  try { j = await api(`/api/jugador?misiones=${typeof MISIONES_LINUX !== "undefined" ? MISIONES_LINUX.length : 44}`); } catch { return; }
  const antes = JUGADOR;
  JUGADOR = j;
  $("#jNivel").textContent = j.nivel;
  $("#jTitulo").textContent = j.titulo;
  $("#jRacha").textContent = j.racha ? `🔥${j.racha}` : "";
  $("#jRacha").title = j.estudio_hoy ? "Racha de días estudiando" : "¡Estudia hoy para no perder la racha!";
  $("#jBarra").style.width = `${Math.round((100 * j.xp_nivel) / j.xp_para_subir)}%`;
  $("#jXp").textContent = `${j.xp_nivel} / ${j.xp_para_subir} XP`;
  if (!anunciar || !antes) return;
  const ganado = j.xp - antes.xp;
  if (ganado > 0) celebrar(`+${ganado} XP`, "xp");
  if (j.nivel > antes.nivel) setTimeout(() => celebrar(`⬆ ¡Nivel ${j.nivel}! ${j.titulo}`, "nivel"), 900);
  const nuevos = j.logros.filter((l) => l.ok && !antes.logros.find((x) => x.id === l.id)?.ok);
  nuevos.forEach((l, k) => setTimeout(() => celebrar(`${l.icono} Logro: ${l.nombre}`, "logro"), 1800 + k * 1200));
}
function celebrar(texto, clase) {
  const d = document.createElement("div");
  d.className = `celebra ${clase}`;
  d.textContent = texto;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 2600);
}
async function pintarLogros() {
  await refrescarJugador(false);
  const j = JUGADOR;
  if (!j) return;
  const areas = Object.entries(j.por_area), max = Math.max(1, ...areas.map(([, v]) => v));
  $("#logrosVista").innerHTML = `<div class="tarjeta jugador-grande">
      <div class="j-nivel grande">${j.nivel}</div>
      <div style="flex:1"><h2 style="margin:0">${esc(j.titulo)}</h2>
        <div class="j-barra grande"><i style="width:${Math.round((100 * j.xp_nivel) / j.xp_para_subir)}%"></i></div>
        <div class="sub"><span>${j.xp} XP en total</span> · <span>faltan ${j.xp_para_subir - j.xp_nivel} para el nivel ${j.nivel + 1}</span> · <span>racha de ${j.racha} día(s)</span> <span>${j.estudio_hoy ? "✅ hoy ya estudiaste" : "— ¡hoy todavía no!"}</span></div></div>
    </div>
    <div class="tarjeta"><h3 style="margin-top:0">¿Estoy listo para el examen?</h3>
      <div class="listos">${[["ccna", "CCNA 200-301"], ["wca", "Wireshark WCA-101"], ["linux", "Linux"]].map(([k, n]) => { const L = j.listo[k];
        return `<div class="listo"><div class="listo-cab"><b>${n}</b><span class="nota ${notaClase(L.total / 10)}">${L.total}%</span></div>
          ${L.dominios.map((d) => `<div class="j-area"><span title="${esc(d.dominio)}">${esc(d.dominio)}${d.peso ? ` <i class="sub">(${d.peso}%)</i>` : ""}</span>
            <div class="barra-dom"><i style="width:${d.pct}%;background:${d.pct >= 80 ? "var(--ok)" : d.pct >= 60 ? "var(--nodata)" : "var(--falla)"}"></i></div><b>${d.pct}%</b></div>`).join("")}
          ${k === "ccna" ? `<div class="sub">Mejor simulacro: ${L.simulacro ?? "—"}</div>` : ""}
          <div class="veredicto ${L.total >= 80 ? "ok-txt" : ""}">${esc(L.veredicto)}</div></div>`; }).join("")}</div></div>
    <div class="tarjeta"><h3 style="margin-top:0">XP por área</h3>
      ${areas.map(([k, v]) => `<div class="j-area"><span>${esc(k)}</span><div class="barra-dom"><i style="width:${Math.round((100 * v) / max)}%"></i></div><b>${v}</b></div>`).join("")}</div>
    <div class="tarjeta"><h3 style="margin-top:0">Logros (${j.logros.filter((l) => l.ok).length}/${j.logros.length})</h3>
      <div class="logros">${j.logros.map((l) => `<div class="logro ${l.ok ? "ok" : ""}"><span class="icono">${l.ok ? l.icono : "🔒"}</span>
        <b>${esc(l.nombre)}</b><span class="sub">${esc(l.desc)}</span></div>`).join("")}</div></div>
    <div class="tarjeta"><h3 style="margin-top:0">Cómo se gana XP</h3><ul class="sub">
      <li>Práctica de Packet Tracer: tu mejor nota × 10 · Examen: nota × 10 (simulacro × 20) · Subneteo: nota × 5</li>
      <li>Captura de Wireshark: nota × 10 · Misión de Linux: 20 por estrella · Lección de teoría: 15</li>
      <li>Academia (Rust, IA, Procesadores): 25 por estrella</li>
      <li>Red vs Blue: tus puntos ÷ 5 (más en Difícil).</li>
      <li>Cada nivel pide 100 XP más que el anterior. Estudia todos los días para mantener la racha 🔥.</li></ul></div>`;
}

// ---------------------------------------------------------------- guías
async function cargarGuias() {
  const g = await api("/api/guias");
  const avisos = [];
  if (!g.modelo) avisos.push('<span class="error">No tienes modelo de embeddings: <code>ollama pull qwen3-embedding:0.6b</code></span>');
  if (!g.pypdf) avisos.push('<span class="error">Falta pypdf en el Python de NetLab: los PDFs no se pueden leer.</span>');
  $("#gEstado").innerHTML = `Carpeta: <code>${esc(g.carpeta)}</code> · modelo: <b>${esc(g.modelo || "ninguno")}</b>` +
    (g.campos ? ` · ${g.campos} campos de Wireshark para revisar filtros` : "") + (avisos.length ? "<br>" + avisos.join("<br>") : "") +
    (g.pendientes ? `<br><b>${g.pendientes} archivo(s) sin indexar.</b>` : "");
  $("#tablaGuias").innerHTML = g.archivos.length
    ? `<tr><th>Archivo</th><th>MB</th><th>Estado</th></tr>` + g.archivos.map((a) => `<tr><td>${esc(a.nombre)}</td><td>${a.mb}</td>
        <td>${a.especial ? '<span class="pill ok">Lista de campos (no se indexa)</span>' : a.indexado
          ? `<span class="pill ok">✓ ${a.trozos} fragmentos</span>` : '<span class="pill mal">Sin indexar</span>'}</td></tr>`).join("")
    : '<tr><td class="sub">La carpeta está vacía. Echa ahí tus PDFs, .txt o .md.</td></tr>';
  $("#btnIndexar").disabled = !g.pendientes || !g.modelo;
}
$("#btnIndexar").addEventListener("click", async () => {
  const b = $("#btnIndexar");
  b.disabled = true;
  try {
    const r = await trabajo("/api/guias/indexar", {}, $("#gTrabajo"));
    $("#gTrabajo").innerHTML = `<p class="sub">Listo: ${r.indexados} archivo(s) con ${esc(r.modelo)}.</p>` +
      (r.errores.length ? `<p class="error">${r.errores.map(esc).join("<br>")}</p>` : "");
  } catch (e) { $("#gTrabajo").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  cargarGuias();
});
$("#btnBajarGuias").addEventListener("click", async () => {
  const b = $("#btnBajarGuias");
  b.disabled = true;
  try {
    const r = await trabajo("/api/guias/bajar_cisco", {}, $("#gTrabajo"));
    const nuevas = r.resultados.filter((x) => x.ok && !x.ya), malas = r.resultados.filter((x) => !x.ok);
    $("#gTrabajo").innerHTML = `<p class="sub">${nuevas.length ? `Bajé ${nuevas.length} guía(s). Dale "Indexar lo nuevo".` : "Ya tenías todas."}</p>` +
      (malas.length ? `<p class="error">${malas.map((x) => `${esc(x.nombre)}: ${esc(x.error)}`).join("<br>")}</p>` : "");
  } catch (e) { $("#gTrabajo").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  b.disabled = false;
  cargarGuias();
});
$("#btnAbrirGuias").addEventListener("click", () => api("/api/guias/abrir", {}).catch((e) => aviso(e.message)));
async function buscarGuias() {
  const q = $("#gQ").value.trim();
  if (!q) return;
  $("#gResultados").innerHTML = '<div class="trabajo"><div class="girar"></div><div>Buscando…</div></div>';
  try {
    const { resultados } = await api("/api/guias/buscar", { q });
    $("#gResultados").innerHTML = resultados.length ? resultados.map((r) => `<div class="pregunta">
      <div><b>${esc(r.archivo)}</b>${r.pagina ? ` · p. ${r.pagina}` : ""} <span class="pill">${Math.round(r.similitud * 100)}%</span></div>
      <pre class="fragmento">${esc(r.texto)}</pre></div>`).join("") : '<p class="sub">Nada parecido en tus guías (o aún no están indexadas).</p>';
  } catch (e) { $("#gResultados").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}
$("#btnBuscarGuias").addEventListener("click", buscarGuias);
$("#gQ").addEventListener("keydown", (e) => { if (e.key === "Enter") buscarGuias(); });

// ---------------------------------------------------------------- Wireshark
let WS = null;  // ejercicio abierto
const estrellasWs = (n) => (n >= 10 ? 3 : n >= 8 ? 2 : n >= 6 ? 1 : 0);
async function cargarWireshark() {
  const r = await api("/api/wireshark");
  $("#wsEstado").innerHTML = r.tshark
    ? "Escenarios con su clave: contestas leyendo los paquetes y tus filtros se prueban con tshark de verdad. ★ con 6, ★★ con 8, ★★★ con 10."
    : '<span class="error">No encontré tshark (viene con Wireshark). Puedes descargar las capturas, pero los filtros no se pueden calificar.</span>';
  pintarRutaWireshark(r);
  $("#wsExtras").innerHTML = `<div class="tarjeta"><h3 style="margin-top:0">🔴 Captura en vivo</h3>
      <p class="sub">Graba unos segundos de TU tráfico real y te hago preguntas exactas sobre él (respuestas sacadas con tshark). La captura se borra al cerrar NetLab.</p>
      <div class="fila"><label>Interfaz<select id="wsIf"><option value="">Cargando…</option></select></label>
        <label>Segundos<select id="wsSeg"><option>10</option><option selected>20</option><option>45</option><option>90</option></select></label></div>
      <div class="acciones"><button class="primario" id="wsCapturar">Capturar</button></div><div id="wsCapCaja"></div></div>
    <div class="tarjeta"><h3 style="margin-top:0">🎯 Filtros de captura (BPF)</h3>
      <p class="sub">Los que se ponen ANTES de capturar (host, port, net…). Se compilan con dumpcap y se comparan con el correcto: si filtran lo mismo, cuenta aunque lo escribas distinto.</p>
      <div class="acciones"><button id="wsBpf">Empezar 5 ejercicios</button></div><div id="wsBpfCaja"></div></div>`;
  $("#wsCapturar").addEventListener("click", capturarWs);
  $("#wsBpf").addEventListener("click", ejerciciosBpf);
  api("/api/wireshark/interfaces").then(({ interfaces }) => {
    const pref = interfaces.find((x) => x.principal) || interfaces.find((x) => /wi-?fi|ethernet/i.test(x.nombre) && !/virtual|vmware|loopback|bluetooth/i.test(x.nombre));
    $("#wsIf").innerHTML = interfaces.length ? interfaces.map((x) => `<option value="${esc(x.id)}" ${x === pref ? "selected" : ""}>${esc(x.nombre)}</option>`).join("")
      : '<option value="">No hay interfaces (¿Npcap instalado?)</option>';
  }).catch(() => { $("#wsIf").innerHTML = '<option value="">No pude listar las interfaces</option>'; });
}

async function capturarWs() {
  const b = $("#wsCapturar");
  if (!$("#wsIf").value) return aviso("Elige una interfaz");
  b.disabled = true;
  try {
    WS = await trabajo("/api/wireshark/capturar", { interfaz: $("#wsIf").value, segundos: +$("#wsSeg").value }, $("#wsCapCaja"));
    pintarWs();
    $("#wsVista").scrollIntoView({ behavior: "smooth" });
  } catch (e) { $("#wsCapCaja").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  b.disabled = false;
}

function retosBpf() {
  const az = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const ipr = () => `192.168.${az(0, 50)}.${az(2, 250)}`, ipp = () => `${[8, 23, 104, 142, 151][az(0, 4)]}.${az(1, 250)}.${az(1, 250)}.${az(2, 250)}`;
  const g = [
    () => { const x = ipr(); return { texto: `Solo el tráfico de o hacia ${x}.`, refs: [`host ${x}`] }; },
    () => { const x = ipp(); return { texto: `Solo lo que ENVÍA ${x}.`, refs: [`src host ${x}`, `src ${x}`] }; },
    () => ({ texto: "Solo DNS (puerto 53, UDP o TCP).", refs: ["port 53"] }),
    () => ({ texto: "Solo DNS por UDP.", refs: ["udp port 53"] }),
    () => { const p = [22, 23, 80, 443, 3389][az(0, 4)]; return { texto: `Todo menos el puerto ${p}.`, refs: [`not port ${p}`, `!port ${p}`] }; },
    () => { const o = az(1, 200); return { texto: `Solo la red 10.${o}.0.0/16.`, refs: [`net 10.${o}.0.0/16`, `net 10.${o}.0.0 mask 255.255.0.0`] }; },
    () => { const x = ipp(); return { texto: `Solo HTTPS (TCP 443) hacia el servidor ${x}.`, refs: [`tcp dst port 443 and dst host ${x}`, `dst host ${x} and tcp dst port 443`] }; },
    () => ({ texto: "Solo ARP.", refs: ["arp"] }),
    () => ({ texto: "Solo ICMP (pings y errores).", refs: ["icmp"] }),
    () => ({ texto: "Solo TCP que no sea SSH.", refs: ["tcp and not port 22", "tcp and not tcp port 22"] }),
    () => ({ texto: "Solo los puertos bien conocidos (1 a 1023).", refs: ["portrange 1-1023"] }),
    () => ({ texto: "Solo paquetes TCP con la bandera SYN encendida.", refs: ["tcp[tcpflags] & tcp-syn != 0", "tcp[13] & 2 != 0"] }),
    () => ({ texto: "Solo tráfico broadcast.", refs: ["broadcast", "ether broadcast"] }),
  ];
  return g.sort(() => Math.random() - 0.5).slice(0, 5).map((f) => f());
}

function ejerciciosBpf() {
  const lista = retosBpf();
  let buenas = 0, hechas = 0;
  $("#wsBpfCaja").innerHTML = lista.map((x, i) => `<div class="pregunta" data-bpf="${i}"><div><b>${i + 1}.</b> ${esc(x.texto)}</div>
    <div class="fila-filtro"><input class="mono" data-bpf-in="${i}" placeholder="ej. host 10.0.0.1 and port 80" autocomplete="off"><button class="chico" data-bpf-ok="${i}">Comprobar</button></div><div class="expl"></div></div>`).join("");
  $$("[data-bpf-ok]").forEach((b) => b.addEventListener("click", async () => {
    const i = +b.dataset.bpfOk, caja = $(`[data-bpf="${i}"] .expl`), x = lista[i];
    b.disabled = true;
    try {
      const r = await api("/api/wireshark/bpf", { filtro: $(`[data-bpf-in="${i}"]`).value, refs: x.refs });
      if (r.correcto) { caja.innerHTML = '<b class="ok-txt">✓ Exacto.</b>'; if (!x.hecho) { buenas++; } $(`[data-bpf="${i}"]`).classList.add("bien"); }
      else { caja.innerHTML = `<span class="error">${esc(r.error)}</span> <button class="chico" data-bpf-sol="${i}">Ver respuesta</button>`; b.disabled = false;
        $(`[data-bpf-sol="${i}"]`, caja).addEventListener("click", () => { caja.insertAdjacentHTML("beforeend", `<div>Una respuesta: <code>${esc(x.refs[0])}</code></div>`); x.visto = true; }); return; }
    } catch (e) { caja.textContent = e.message; b.disabled = false; return; }
    if (!x.hecho) { x.hecho = true; hechas++; }
    if (hechas === lista.length) api("/api/reto/resultado", { area: "wireshark", buenas: lista.filter((y) => y.hecho && !y.visto).length, total: lista.length }).catch(() => {});
  }));
  $$("[data-bpf-in]").forEach((x) => x.addEventListener("keydown", (e) => { if (e.key === "Enter") $(`[data-bpf-ok="${x.dataset.bpfIn}"]`).click(); }));
}

async function nuevoWs(escenario, btn) {
  btn.disabled = true;
  $("#wsVista").innerHTML = '<div class="tarjeta"><div class="trabajo"><div class="girar"></div><div>Armando la captura y comprobando la clave con tshark…</div></div></div>';
  try {
    WS = await api("/api/wireshark/generar", { escenario });
    pintarWs();
  } catch (e) { $("#wsVista").innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
  finally { btn.disabled = false; }
}

async function abrirCapturaWs(id) {
  WS = await api(`/api/wireshark/${id}`);
  pintarWs();
}

function pintarWs() {
  const c = WS;
  $("#wsVista").innerHTML = `<div class="tarjeta destacada">
    <h2>${esc(c.titulo)} <span class="pill">${esc(c.nivel)}</span><span class="pill">${c.paquetes} paquetes</span>
      ${c.validada ? '<span class="pill ok">✓ Clave comprobada con tshark</span>' : ""}</h2>
    <div class="acciones">
      <button class="primario" id="wsAbrir">Abrir en Wireshark</button>
      <a href="/api/wireshark/${c.id}/pcap" download><button>Descargar .pcap</button></a>
      <button class="primario btn-teofondo" id="wsTeoFondo">📖 Teoría a fondo</button>
      <button id="wsTeoLec">${c.escenario && c.escenario !== "vivo" ? "📚 Lección y examen de este tema" : "📚 Lecciones y exámenes de Wireshark"}</button>
    </div>
    <div id="wsTeoFondoCaja" hidden></div>
    <h3>Preguntas</h3>
    ${c.preguntas.map((p, i) => `<div class="pregunta" data-p="${p.id}"><div><b>${i + 1}.</b> ${esc(p.texto)}
      ${p.pista ? `<button class="chico" data-ws-pista="${i}">💡</button>` : ""}</div><div class="sub ws-pista" hidden>💡 ${esc(p.pista)}</div>
      <input class="mono" data-resp="${p.id}" autocomplete="off"><div class="expl"></div></div>`).join("")}
    <h3>Filtros de visualización</h3>
    <p class="sub">Escribe el filtro como en la barra de Wireshark. "Probar" lo corre con tshark y te dice si muestra exactamente los paquetes correctos.</p>
    ${c.filtros.map((f, i) => `<div class="pregunta" data-f="${f.id}"><div><b>F${i + 1}.</b> ${esc(f.texto)}
        ${f.pista ? `<span class="sub"> (pista: ${esc(f.pista)})</span>` : ""}</div>
      <div class="fila-filtro"><input class="mono" data-filtro="${f.id}" autocomplete="off" placeholder="ej. ip.addr == 10.0.0.1">
        <button class="chico" data-probar="${f.id}">Probar</button></div><div class="expl"></div></div>`).join("")}
    <div class="acciones"><button class="primario" id="wsCalificar">Calificar</button></div>
    <div id="wsRes"></div>
  </div>`;
  $$("[data-ws-pista]").forEach((b) => b.addEventListener("click", () => { b.parentElement.nextElementSibling.hidden = false; b.remove(); }));
  // teoría a fondo del TIPO de captura (se guarda por escenario, no por captura: las IPs cambian pero el tema no)
  $("#wsTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#wsTeoFondoCaja"), {
    clave: `ws:${c.escenario || c.titulo}`, mundo: "wireshark", titulo: c.titulo,
    contexto: `Ejercicio de análisis de una captura (.pcap) en Wireshark, nivel ${c.nivel}. Lo que hay que saber responder, por ejemplo: `
      + c.preguntas.slice(0, 4).map((p) => p.texto).join(" | ") + ". También se escriben filtros de visualización." }));
  $("#wsTeoLec").addEventListener("click", () => irTeoria("wireshark", c.escenario && c.escenario !== "vivo" ? `ws_${c.escenario}` : null));
  $("#wsAbrir").addEventListener("click", async () => {
    const r = await api("/api/wireshark/abrir", { id: c.id }).catch((e) => ({ error: e.message }));
    aviso(r.ok ? "Abriendo Wireshark…" : r.error);
  });
  $$("[data-probar]").forEach((b) => b.addEventListener("click", async () => {
    const fid = b.dataset.probar, caja = $(`[data-f="${fid}"] .expl`);
    b.disabled = true;
    try {
      const r = await api("/api/wireshark/filtro", { id: c.id, filtro_id: fid, filtro: $(`[data-filtro="${fid}"]`).value });
      caja.innerHTML = r.correcto ? '<b class="ok-txt">✓ Exacto.</b>'
        : r.error ? `<span class="error">${esc(r.error)}</span>`
        : `Muestra ${r.mostrados} paquete(s); deberían ser ${r.esperados}.` +
          (r.sobran.length ? ` Sobran: ${r.sobran.join(", ")}.` : "") + (r.faltan.length ? ` Faltan: ${r.faltan.join(", ")}.` : "");
    } catch (e) { caja.textContent = e.message; } finally { b.disabled = false; }
  }));
  $$("[data-filtro]").forEach((x) => x.addEventListener("keydown", (ev) => { if (ev.key === "Enter") $(`[data-probar="${x.dataset.filtro}"]`).click(); }));
  $("#wsCalificar").addEventListener("click", calificarWs);
  if (c.resultado) mostrarResultadoWs(c.resultado);
}

async function calificarWs() {
  const btn = $("#wsCalificar");
  btn.disabled = true;
  const respuestas = Object.fromEntries($$("[data-resp]").map((x) => [x.dataset.resp, x.value]));
  const filtros = Object.fromEntries($$("[data-filtro]").map((x) => [x.dataset.filtro, x.value]));
  $("#wsRes").innerHTML = '<div class="trabajo"><div class="girar"></div><div>Calificando con tshark…</div></div>';
  try { mostrarResultadoWs(await api("/api/wireshark/calificar", { id: WS.id, respuestas, filtros })); }
  catch (e) { $("#wsRes").innerHTML = `<p class="error">${esc(e.message)}</p>`; btn.disabled = false; }
}

function mostrarResultadoWs(r) {
  r.detalle.forEach((d) => {
    const div = $(d.clase === "filtro" ? `[data-f="${d.id}"]` : `[data-p="${d.id}"]`);
    if (!div) return;
    div.classList.add(d.ok ? "bien" : "mal");
    const inp = $("input", div);
    if (!inp.value) inp.value = d.tuya;
    $(".expl", div).innerHTML = `${d.ok ? "<b>Correcta.</b>" : `<b>Incorrecta.</b> ${d.clase === "filtro" ? "Un filtro que funciona" : "Respuesta"}: <code>${esc(d.correcta)}</code>`}
      ${d.explicacion ? `<br>${esc(d.explicacion)}` : ""}
      ${d.ok ? "" : `<div><button class="chico" data-ws-exp="${d.id}">🤖 Explícamelo</button><div class="tutor-caja"></div></div>`}`;
    $(`[data-ws-exp="${d.id}"]`, div)?.addEventListener("click", (ev) => explicame(ev.target, "Wireshark",
      `Ejercicio de Wireshark (${WS.titulo}). ${d.clase === "filtro" ? "Filtro pedido" : "Pregunta"}: ${d.texto}\nLo que escribí: ${d.tuya || "(nada)"}\nRespuesta correcta: ${d.correcta}\n${d.explicacion}`,
      d.clase === "filtro" ? "¿Por qué mi filtro no da los mismos paquetes? Explícame la sintaxis del correcto y cómo pensar el filtro." : "¿Cómo encuentro esto en Wireshark paso a paso (qué columna, qué panel, qué campo)?"));
  });
  $("#wsRes").innerHTML = `<div class="resultado" style="margin-top:14px">
    <span class="calif nota ${notaClase(r.calificacion)}">${r.calificacion}</span><span class="sub"> / 10 · ${r.buenas} de ${r.total}</span>
    <div class="acciones"><button id="wsOtra">Otra captura del mismo tipo</button></div></div>`;
  $("#wsOtra").addEventListener("click", (ev) => WS.escenario === "vivo" ? $("#wsCapturar").scrollIntoView({ behavior: "smooth" }) : nuevoWs(WS.escenario, ev.target));
  $("#wsCalificar").disabled = false;
}

$("#btnWsExamen").addEventListener("click", async () => {
  irExamenMundo("wireshark");
  const caja = $("#examenVista");
  try {
    const { id } = await trabajo("/api/examen/generar", { dominio: "wireshark", n: 10, nivel: "Intermedio",
      descripcion: "Wireshark para el WCA-101: captura, filtros de captura y de visualización, protocolos (Ethernet, ARP, IP, TCP, UDP, DNS, DHCP, HTTP, TLS), análisis TCP, estadísticas y Expert Info" }, caja);
    await abrirExamen(id);
  } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
});
$("#btnWsAnalizar").addEventListener("click", async () => {
  const f = $("#wsArchivo").files[0], caja = $("#wsAnalisis"), btn = $("#btnWsAnalizar");
  if (!f) return aviso("Elige un archivo .pcap o .pcapng");
  if (f.size > 40 * 1024 * 1024) return aviso("Máximo 40 MB; recorta la captura en Wireshark (File → Export Specified Packets).");
  btn.disabled = true;
  try {
    const datos = await new Promise((ok, mal) => { const lr = new FileReader(); lr.onload = () => ok(lr.result); lr.onerror = mal; lr.readAsDataURL(f); });
    const r = await trabajo("/api/wireshark/analizar", { datos, pregunta: $("#wsPregunta").value }, caja);
    caja.innerHTML = `<div class="explicacion">${md(r.texto)}</div>
      <details><summary class="sub">Estadísticas de tshark</summary><pre>${esc(r.resumen)}</pre></details>`;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  finally { btn.disabled = false; $("#wsArchivo").value = ""; }
});

// ---------------------------------------------------------------- laboratorios JITL
async function abrirEnPT(archivo) {
  try {
    const r = await api("/api/abrir_pt", archivo ? { archivo } : {});
    aviso(r.ok ? `Abriendo Packet Tracer al ${Math.round(r.escala * 100)}%…` : r.error);
  } catch (e) { aviso(e.message); }
}

async function cargarJitl() {
  const r = await api("/api/jitl");
  // la ruta va en su propio nodo (sin traducir) para que el resto de la frase sí se traduzca
  $("#jitlCarpeta").innerHTML = r.existe
    ? `<span>${r.labs.length} laboratorio(s) en</span> <code data-no-tr>${esc(r.carpeta)}</code><span>. Se abren en Packet Tracer con tu escala.</span>`
    : `<span>No encontré la carpeta</span> <code data-no-tr>${esc(r.carpeta)}</code>`;
  const nombreTema = (id) => ESTADO?.temas.find((t) => t.id === id)?.nombre;
  $("#tablaJitl").innerHTML = r.labs.length
    ? `<tr><th>Día</th><th>Laboratorio</th><th>Tema</th><th></th></tr>` + r.labs.map((l, i) => `<tr>
        <td>${l.dia ?? "—"}</td><td>${esc(l.titulo)}</td>
        <td class="sub">${esc(nombreTema(l.tema) || "—")}</td>
        <td><div class="acciones">
          <button class="chico primario" data-jitl-abrir="${i}">Abrir</button>
          <button class="chico btn-teofondo" data-jitl-teo="${i}">📖 Teoría a fondo</button>
          <button class="chico" data-jitl-examen="${i}">Examen</button>
          <button class="chico" data-jitl-practica="${i}">Práctica extra</button>
        </div></td></tr>`).join("")
    : '<tr><td class="sub">No hay archivos .pkt en esa carpeta.</td></tr>';
  $$("[data-jitl-abrir]").forEach((b) => b.addEventListener("click", () => abrirEnPT(r.labs[b.dataset.jitlAbrir].archivo)));
  // la teoría sale en una fila justo debajo del laboratorio
  $$("[data-jitl-teo]").forEach((b) => b.addEventListener("click", (ev) => {
    const l = r.labs[b.dataset.jitlTeo], tr = b.closest("tr");
    let fila = tr.nextElementSibling;
    if (!fila || !fila.classList.contains("jitl-teo")) {
      tr.insertAdjacentHTML("afterend", `<tr class="jitl-teo"><td colspan="4"><div data-jitl-caja hidden></div></td></tr>`);
      fila = tr.nextElementSibling;
    }
    teoriaAFondo(ev.target, $("[data-jitl-caja]", fila), {
      clave: `jitl:${l.titulo}`, mundo: "ccna", titulo: l.titulo,
      contexto: `Laboratorio de Jeremy's IT Lab (curso CCNA)${l.dia != null ? `, día ${l.dia}` : ""}. Tema: ${nombreTema(l.tema) || "—"}. Explica la teoría y los comandos de IOS que se practican en este laboratorio.` });
  }));
  $$("[data-jitl-examen]").forEach((b) => b.addEventListener("click", () => {
    const l = r.labs[b.dataset.jitlExamen], t = ESTADO.temas.find((x) => x.id === l.tema);
    ir("examen");
    $("#eTema").value = t ? t.id : "";
    if (t) $("#eNivel").value = t.nivel;
    $("#eDesc").value = `Lo del laboratorio de JITL: ${l.titulo}`;
  }));
  $$("[data-jitl-practica]").forEach((b) => b.addEventListener("click", () => {
    const l = r.labs[b.dataset.jitlPractica], t = ESTADO.temas.find((x) => x.id === l.tema && x.lab);
    ir("practica");
    $("#pTema").value = t ? t.id : "";
    if (t) $("#pNivel").value = t.nivel;
    $("#pDesc").value = `Una práctica parecida al laboratorio de JITL "${l.titulo}", pero con otro escenario y otras direcciones.`;
  }));
}

// ---------------------------------------------------------------- constructor
const EJEMPLOS_CONSTRUCTOR = [
  "3 routers en triángulo con OSPF área 0, cada uno con un switch y 2 PCs",
  "Oficina con 3 VLANs (Ventas, RRHH, TI), router-on-a-stick y DHCP en el router",
  "2 sucursales unidas por un enlace /30 con rutas estáticas y un servidor web en la sede",
  "Switch multicapa 3560 con SVIs para 2 VLANs y salida a internet con PAT",
];
$("#cEjemplos").innerHTML = EJEMPLOS_CONSTRUCTOR.map((e, i) => `<button data-ej="${i}">${esc(e)}</button>`).join("");
$$("[data-ej]").forEach((b) => b.addEventListener("click", () => { $("#cDesc").value = EJEMPLOS_CONSTRUCTOR[b.dataset.ej]; }));

$("#btnConstruir").addEventListener("click", async () => {
  const descripcion = $("#cDesc").value.trim();
  if (descripcion.length < 8) return aviso("Describe la red que quieres armar");
  const btn = $("#btnConstruir"), caja = $("#constructorVista");
  btn.disabled = true;
  try {
    const { id } = await trabajo("/api/constructor/generar", { descripcion }, caja);
    await abrirTopologia(id);
  } catch (e) {
    caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
});

async function abrirTopologia(id) {
  const t = await api(`/api/practica/${id}`);
  const v = t.validacion || { ok: true, problemas: [] };
  ir("constructor");
  $("#constructorVista").innerHTML = `
  <div class="tarjeta">
    <div>${v.ok ? '<span class="pill ok">✓ Revisada: puertos, IPs y subredes cuadran</span>' : '<span class="pill mal">⚠ Quedaron detalles por revisar</span>'}
      <span class="pill">${esc(t.modelo || "")}</span></div>
    <h2 style="margin-top:10px">${esc(t.titulo)}</h2>
    <p class="sub">${esc(t.descripcion || t.objetivo || "")}</p>
    ${v.ok ? "" : `<details><summary class="sub">Detalles (${v.problemas.length})</summary><ul>${v.problemas.map((x) => `<li class="sub">${esc(x)}</li>`).join("")}</ul></details>`}
    <h3>Construir en Packet Tracer</h3>
    <p class="sub">Se copia solo. En Packet Tracer: <b>Extensions → Builder Code Editor → Clear → Paste → Run</b>.</p>
    <div class="acciones">
      <button class="primario" data-tptb="topologia">Solo cables</button>
      <button data-tptb="completa">Ya configurada</button>
      ${ESTADO?.packet_tracer ? '<button id="btnAbrirPT2">Abrir Packet Tracer</button>' : ""}
    </div>
    <div id="tptbScript"></div>
  </div>
  <div class="tarjeta">
    <div class="topologia">${svgTopologia(t)}</div>
    <h3>Conexiones</h3>
    <table class="tabla"><tr><th>Desde</th><th>Puerto</th><th>Hacia</th><th>Puerto</th><th>Cable</th></tr>
      ${t.enlaces.map((e) => `<tr><td>${esc(e.a)}</td><td class="mono">${esc(e.puerto_a)}</td><td>${esc(e.b)}</td><td class="mono">${esc(e.puerto_b)}</td><td>${esc(e.cable)}</td></tr>`).join("")}
    </table>
    <h3>Direccionamiento</h3>
    <table class="tabla"><tr><th>Equipo</th><th>Interfaz</th><th>IP</th><th>Máscara</th><th>Gateway</th></tr>
      ${t.direccionamiento.map((a) => `<tr><td>${esc(a.dispositivo)}</td><td class="mono">${esc(a.interfaz)}</td><td class="mono">${esc(a.ip)}</td><td class="mono">${esc(a.mascara)}</td><td class="mono">${esc(a.gateway || "")}</td></tr>`).join("")}
    </table>
    ${(t.notas || []).length ? `<h3>Para probarla</h3><ul>${t.notas.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
  </div>
  <div class="tarjeta">
    <h3 style="margin-top:0">Configuración de cada equipo</h3>
    ${(t.solucion || []).map((c) => bloqueConfig(c.dispositivo, c.config.trim())).join("") || '<p class="sub">Sin configuración.</p>'}
  </div>`;
  $$("#constructorVista .copiar").forEach((b) => b.addEventListener("click", () => copiar(b.dataset.texto)));
  $("#btnAbrirPT2")?.addEventListener("click", () => abrirEnPT());
  $$("[data-tptb]").forEach((b) => b.addEventListener("click", async () => {
    const r = await api(`/api/practica/${id}/ptbuilder?nivel=${b.dataset.tptb}`);
    $("#tptbScript").innerHTML = bloqueConfig(b.dataset.tptb === "completa" ? "Script: ya configurada" : "Script: solo cables", r.script.trim());
    $("#tptbScript .copiar").addEventListener("click", (e) => copiar(e.target.dataset.texto));
    copiar(r.script);
  }));
  $("#constructorVista").scrollIntoView({ behavior: "smooth" });
}

// ---------------------------------------------------------------- ajustes
function pintarAjustes() {
  const c = ESTADO.config;
  if ((c.idioma || "es") !== IDIOMA_UI) api("/api/config", { idioma: IDIOMA_UI }).catch(() => {});
  for (const [id, k] of [["cPesado", "modelo_pesado"], ["cLigero", "modelo_ligero"]]) {
    const lista = ESTADO.modelos.includes(c[k]) ? ESTADO.modelos : [c[k], ...ESTADO.modelos];
    $("#" + id).innerHTML = lista.filter((m) => !/embed/.test(m)).map((m) => `<option ${m === c[k] ? "selected" : ""}>${esc(m)}</option>`).join("");
  }
  $("#cVerificar").checked = !!c.verificar_examenes;
  $("#cExplicarPesado").checked = !!c.explicar_con_pesado;
  $("#cEscala").value = c.escala_pt || "1.25";
  $("#cUsarGuias").checked = c.usar_guias !== false;
  const emb = ESTADO.modelos.filter((m) => /embed|bge/i.test(m));
  $("#cEmbed").innerHTML = `<option value="" ${!c.modelo_embed ? "selected" : ""}>Automático (el mejor que tengas)</option>` +
    emb.map((m) => `<option ${m === c.modelo_embed ? "selected" : ""}>${esc(m)}</option>`).join("");
  const vis = ESTADO.modelos.filter((m) => /vl|vision|gemma[34]/i.test(m));
  $("#cVision").innerHTML = (vis.includes(c.modelo_vision) ? vis : [c.modelo_vision, ...vis])
    .map((m) => `<option ${m === c.modelo_vision ? "selected" : ""}>${esc(m)}</option>`).join("");
  const chat = ESTADO.modelos.filter((m) => !/embed|bge|nomic/i.test(m));
  $("#cSeguridad").innerHTML = `<option value="" ${!c.modelo_seguridad ? "selected" : ""}>El ligero (sin modelo especial)</option>` +
    chat.map((m) => `<option ${m === c.modelo_seguridad ? "selected" : ""}>${esc(m)}</option>`).join("");
  $("#cCodigo").innerHTML = (chat.includes(c.modelo_codigo) ? chat : [c.modelo_codigo, ...chat])
    .map((m) => `<option ${m === c.modelo_codigo ? "selected" : ""}>${esc(m)}</option>`).join("");
  $("#vramInfo").textContent = ESTADO.cargados.length ? "Cargados ahora: " + ESTADO.cargados.join(", ") : "No hay modelos cargados en la GPU.";
}
$("#btnGuardarCfg").addEventListener("click", async () => {
  await api("/api/config", {
    modelo_pesado: $("#cPesado").value, modelo_ligero: $("#cLigero").value,
    verificar_examenes: $("#cVerificar").checked, explicar_con_pesado: $("#cExplicarPesado").checked,
    modelo_vision: $("#cVision").value, modelo_embed: $("#cEmbed").value, usar_guias: $("#cUsarGuias").checked,
    modelo_seguridad: $("#cSeguridad").value, modelo_codigo: $("#cCodigo").value,
    escala_pt: String(Math.min(2.5, Math.max(0.8, parseFloat($("#cEscala").value) || 1.25))),
  });
  aviso("Ajustes guardados");
  cargarEstado();
pintarInicio();
setTimeout(() => { revisarMisionDia(); contarRepasos(); }, 300);
});
$("#btnCompararSeg").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  try {
    const r = await trabajo("/api/seguridad/comparar", {}, $("#compSeg"));
    $("#compSeg").innerHTML = `<table class="tabla"><tr><th>Modelo</th><th>Aciertos</th><th>Seg/respuesta</th><th>Falló en</th></tr>
      ${r.resultados.map((x, i) => `<tr><td>${i === 0 ? "🏆 " : ""}${esc(x.modelo)}</td><td><b>${x.aciertos}/${x.total}</b></td><td>${x.seg_por_respuesta}</td>
        <td class="sub">${x.fallas.map(esc).join("<br>") || "—"}</td></tr>`).join("")}</table>
      <p class="sub">Quedó como modelo de seguridad: <b>${esc(r.elegido)}</b> (lo puedes cambiar arriba).</p>`;
    cargarEstado();
  } catch (e) { $("#compSeg").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  ev.target.disabled = false;
});
$("#btnLiberar").addEventListener("click", async () => {
  const r = await api("/api/liberar", {});
  $("#vramInfo").textContent = r.cargados.length ? "Siguen cargados: " + r.cargados.join(", ") : "VRAM liberada.";
});
$("#btnCerrar").addEventListener("click", async () => {
  await api("/api/cerrar", {}).catch(() => {});
  document.body.innerHTML = '<main><h1>NetLab cerrado</h1><p class="sub">VRAM liberada. Ya puedes cerrar esta ventana.</p></main>';
  setTimeout(() => window.close(), 800);
});

// ---------------------------------------------------------------- inicio (los mundos)
document.addEventListener("click", (e) => { const b = e.target.closest("[data-ir-a]"); if (b) { e.preventDefault(); ir(b.dataset.irA); } });

function barraListo(L) {
  return `<div class="j-barra"><i style="width:${L}%"></i></div>`;
}
async function pintarCcnaListo() {
  await refrescarJugador(false);
  const L = JUGADOR?.listo?.ccna, caja = $("#ccnaListo");
  if (!L || !caja) return;
  caja.innerHTML = `<div class="listo-cab"><b>🎓 ¿Listo para el CCNA 200-301?</b><span class="nota ${notaClase(L.total / 10)}">${L.total}%</span></div>
    ${barraListo(L.total)}<div class="sub" style="margin-top:6px">${esc(L.veredicto)} · <a href="#" data-ir-a="logros">ver por dominio</a></div>`;
}
async function pintarInicio() {
  await refrescarJugador(false);
  const j = JUGADOR, caja = $("#inicioMundos");
  if (!j || !caja) return;
  let ac = null;
  try { ac = await api("/api/academia"); } catch {}
  const acPct = (c) => { if (!ac) return 0; const ms = ac.cursos[c].niveles.flatMap((n) => n.misiones);
    return Math.round((100 * ms.reduce((s, m) => s + (ac.progreso[m.id]?.estrellas || 0), 0)) / (3 * ms.length)); };
  const x = j.por_area;
  const mundos = [
    { v: "ruta", ic: "🌐", n: "CCNA 200-301", cert: "Cisco CCNA", pct: j.listo.ccna.total, et: "listo para el examen", xp: x["Prácticas"] + x["Exámenes"] + x["Subneteo"] },
    { v: "wireshark", ic: "🦈", n: "Wireshark", cert: "WCA-101", pct: j.listo.wca.total, et: "listo para el examen", xp: x["Wireshark"] },
    { v: "linux", ic: "🐧", n: "Linux", cert: "Linux para SOC / LPIC-1", pct: j.listo.linux.total, et: "dominio", xp: x["Linux"] },
    { v: "soc", ic: "🚨", n: "SOC", cert: "TryHackMe SAL1 · analista N1", pct: null, xp: x["SOC"] },
    { v: "siem", ic: "🛰️", n: "SIEM", cert: "Elasticsearch + Kibana real", pct: null, xp: x["SIEM"] || 0 },
    { v: "rvb", ic: "⚔️", n: "Red vs Blue", cert: "Práctica tipo SOC / THM SAL1", pct: null, xp: x["Red vs Blue"] },
    { v: "indice", ic: "🗺️", n: "Ruta ofensiva", cert: "Purple Team · eJPT / OSCP (teoría) y SAL1", pct: null, xp: x["Ruta ofensiva"] || 0 },
    { v: "rust", ic: "🦀", n: "Rust", cert: "Rust Book + seguridad", pct: acPct("rust"), et: "de las ★", xp: x["Rust"] },
    { v: "ia", ic: "🧠", n: "Inteligencia Artificial", cert: "ML desde cero", pct: acPct("ia"), et: "de las ★", xp: x["IA"] },
    { v: "torch", ic: "🔥", n: "PyTorch", cert: "Deep learning en tu GPU", pct: acPct("torch"), et: "de las ★", xp: x["PyTorch"] || 0 },
    { v: "chisel", ic: "🔩", n: "Chisel", cert: "Diseño de chips", pct: acPct("chisel"), et: "de las ★", xp: x["Chisel"] || 0 },
    { v: "rustproj", ic: "🛠️", n: "Proyectos Rust", cert: "Escáner, pcap y mini IDS con cargo", pct: acPct("rustproj"), et: "de las ★", xp: x["Proyectos Rust"] || 0 },
    { v: "cpu", ic: "🔧", n: "Procesadores", cert: "Arquitectura y RISC-V", pct: acPct("cpu"), et: "de las ★", xp: x["Procesadores"] },
    { v: "sv", ic: "📐", n: "SystemVerilog", cert: "IEEE 1800 · diseño y verificación", pct: null, xp: x["SystemVerilog"] || 0 },
  ];
  caja.innerHTML = mundos.map((m) => `<button class="mundo" data-ir-a="${m.v}">
      <div class="mundo-ic">${m.ic}</div><div class="mundo-n">${esc(m.n)}</div><div class="sub">${esc(m.cert)}</div>
      ${m.pct != null ? `${barraListo(m.pct)}<div class="sub">${m.pct}% ${esc(m.et)}</div>` : `<div class="sub">${esc({ soc: "Logs de Windows, Sysmon y phishing", siem: "Caza incidentes en Kibana real", sv: "Diseño RTL y verificación de hardware", indice: "Teoría, labs, banco de CVEs y reto morado" }[m.v] || "Ataque y defensa con reloj")}</div>`}
      <div class="mundo-xp">${m.xp || 0} XP</div></button>`).join("");
}

// ---------------------------------------------------------------- arranque
// Si NetLab se reinicia o cambia la interfaz, esta ventana lo nota en el siguiente latido y se recarga sola
// (antes seguía con el código viejo en memoria hasta que dabas F5). Si estás a la mitad de algo, solo avisa.
let VER_WEB = null;
const latido = () => fetch("/api/latido", { method: "POST" }).then((r) => r.json()).then((d) => {
  if (!d?.ver) return;
  if (VER_WEB === null) VER_WEB = d.ver;
  else if (d.ver !== VER_WEB) avisoVersionNueva();
}).catch(() => {});
function avisoVersionNueva() {
  const ocupado = (typeof LECTOR !== "undefined" && LECTOR.activo) || $(".trabajo .girar")
    || ($("#v-examen.visible #preguntas") && !EXAMEN?.resultado) || (typeof SIE !== "undefined" && SIE.esc);
  if (!ocupado) { location.reload(); return; }
  if ($("#avisoVersion")) return;
  const d = document.createElement("div");
  d.id = "avisoVersion";
  d.className = "aviso-version";
  d.innerHTML = `🔄 <span>NetLab se actualizó.</span> <button class="chico primario">Recargar ahora</button>`;
  d.querySelector("button").addEventListener("click", () => location.reload());
  document.body.appendChild(d);
}
latido();
setInterval(latido, 20000);
cargarEstado();
pintarInicio();
// repaso.js carga después de app.js: esperar a que existan (antes tronaba "revisarMisionDia is not defined")
(function arrancarMisionDia(n = 0) {
  if (typeof revisarMisionDia === "function" && typeof contarRepasos === "function") { revisarMisionDia(); contarRepasos(); }
  else if (n < 40) setTimeout(() => arrancarMisionDia(n + 1), 150);
})();
