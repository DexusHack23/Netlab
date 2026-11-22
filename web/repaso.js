"use strict";
// ======================================================================
// NetLab — Cuaderno de errores (repaso espaciado) y misión del día
// ======================================================================
const REP = { cola: [], i: 0, bien: 0 };

function agregarRepaso(area, tipo, datos, clave) {
  api("/api/repaso/agregar", { area, tipo, datos, clave }).then(() => contarRepasos()).catch(() => {});
}

async function contarRepasos() {
  try {
    const r = await api("/api/repaso");
    const b = $("#badgeRepaso");
    if (b) { b.textContent = r.pendientes || ""; b.hidden = !r.pendientes; }
    return r;
  } catch { return null; }
}

async function cargarRepaso() {
  const r = await contarRepasos();
  if (!r) return;
  Object.assign(REP, { cola: r.cola, i: 0, bien: 0 });
  $("#repasoVista").innerHTML = `<div class="tarjeta lx-resumen">
      <div>📚 <b>${r.total}</b> en tu cuaderno · <b>${r.cola.length}</b> para hoy · <b>${r.dominadas}</b> dominadas</div>
      ${r.cola.length ? `<button class="primario" id="repEmpezar">Empezar repaso</button>` : ""}</div>
    ${r.cola.length ? "" : `<div class="tarjeta"><p>${r.total ? "🎉 Por hoy no tienes repasos. Vuelve mañana." : "Tu cuaderno está vacío. Cada pregunta que falles en exámenes, Wireshark, subneteo, arrastrar, Linux o Red vs Blue se guarda aquí sola."}</p>
      <p class="sub">Cómo funciona: lo que fallas vuelve mañana; si aciertas, regresa en 2, 4, 8, 16, 32 y 60 días. Si fallas, empieza otra vez. Así lo pasas a la memoria de largo plazo.</p></div>`}`;
  $("#repEmpezar")?.addEventListener("click", pintarTarjeta);
}

function pintarTarjeta() {
  if (REP.i >= REP.cola.length) {
    $("#repasoVista").innerHTML = `<div class="tarjeta"><div class="resultado"><span class="calif nota ${notaClase(10 * REP.bien / Math.max(1, REP.cola.length))}">${REP.bien}/${REP.cola.length}</span>
      <span class="sub"> repasos bien. Los que fallaste vuelven mañana.</span><div class="acciones"><button id="repVolver">Listo</button></div></div></div>`;
    $("#repVolver").addEventListener("click", cargarRepaso);
    refrescarJugador(true); revisarMisionDia();
    return;
  }
  const c = REP.cola[REP.i], d = c.datos;
  const cab = `<div class="sub-marcador"><span>${REP.i + 1} de ${REP.cola.length}</span><span>${esc(c.area)} · caja ${c.caja}</span><span>${esc(d.origen || "")}</span></div>`;
  let cuerpo = "";
  if (c.tipo === "opcion") cuerpo = `<div class="rep-ops">${d.opciones.map((o, k) => `<button class="rep-op" data-k="${k}">${esc(o)}</button>`).join("")}</div>`;
  else if (c.tipo === "flash") cuerpo = `<div class="acciones"><button class="primario" id="repVer">Mostrar respuesta</button></div>`;
  else cuerpo = `<input class="mono" id="repIn" autocomplete="off" placeholder="Tu respuesta y Enter"><div class="acciones"><button class="primario" id="repComprobar">Comprobar</button></div>`;
  $("#repasoVista").innerHTML = `<div class="tarjeta reto">${cab}<h2 class="rep-enun">${esc(d.enunciado)}</h2>${cuerpo}<div id="repFb"></div></div>`;
  const final = (bien, extra = "") => {
    $("#repFb").innerHTML = `<div class="${bien ? "rvb-ok" : "rvb-mal"}">${bien ? "✓ ¡Bien!" : "✗ A repasarla"}</div>${extra}
      ${d.explicacion ? `<p class="sub">💡 ${esc(d.explicacion)}</p>` : ""}${(d.pasos || []).length ? `<ol class="sub">${d.pasos.map((p) => `<li>${p}</li>`).join("")}</ol>` : ""}
      <div class="acciones"><button class="primario" id="repSig">Siguiente →</button>${bien ? "" : `<button class="chico" id="repExp">🤖 Explícamelo</button><div class="tutor-caja"></div>`}</div>`;
    REP.bien += bien;
    api("/api/repaso/responder", { id: c.id, bien }).catch(() => {});
    $("#repSig").addEventListener("click", () => { REP.i++; pintarTarjeta(); });
    $("#repSig").focus();
    $("#repExp")?.addEventListener("click", (ev) => explicame(ev.target, c.area, `Pregunta: ${d.enunciado}\nRespuesta correcta: ${respuestaTxt(d, c.tipo)}\n${d.explicacion || ""}`,
      "La vuelvo a fallar: explícamelo de otra forma, con un truco para recordarlo."));
  };
  if (c.tipo === "opcion") $$(".rep-op").forEach((b) => b.addEventListener("click", () => {
    const bien = +b.dataset.k === d.correcta;
    $$(".rep-op").forEach((x) => { x.disabled = true; if (+x.dataset.k === d.correcta) x.classList.add("bien"); });
    if (!bien) b.classList.add("mal");
    final(bien);
  }));
  if (c.tipo === "flash") $("#repVer").addEventListener("click", () => {
    $("#repVer").parentElement.outerHTML = `<pre class="rep-resp">${esc(respuestaTxt(d, c.tipo))}</pre>
      <div class="acciones"><button class="primario" id="repSi">✓ La sabía</button><button id="repNo">✗ No la sabía</button></div>`;
    $("#repSi").addEventListener("click", () => { $("#repSi").parentElement.remove(); final(true); });
    $("#repNo").addEventListener("click", () => { $("#repNo").parentElement.remove(); final(false); });
  });
  if (c.tipo === "texto" || c.tipo === "comando") {
    const norm = (s) => String(s).toLowerCase().replace(/\s+/g, " ").replace(/\s*([=!<>&|]+)\s*/g, "$1").trim();
    const comprobar = () => {
      const v = $("#repIn").value; if (!v.trim()) return;
      const bien = (d.respuestas || []).some((r) => norm(r) === norm(v));
      $("#repIn").disabled = true; $("#repComprobar").remove();
      final(bien, bien ? "" : `<p>Respuesta: <code>${esc(respuestaTxt(d, c.tipo))}</code> <button class="chico" id="repYaBien">Lo mío también era correcto</button></p>`);
      $("#repYaBien")?.addEventListener("click", () => { api("/api/repaso/responder", { id: c.id, bien: true }); REP.bien++; $("#repYaBien").replaceWith("✓ Marcada como bien"); });
    };
    $("#repComprobar").addEventListener("click", comprobar);
    $("#repIn").addEventListener("keydown", (e) => { if (e.key === "Enter") comprobar(); });
    $("#repIn").focus();
  }
}
const respuestaTxt = (d, tipo) => tipo === "opcion" ? d.opciones[d.correcta] : (d.respuestas || [d.respuesta || ""]).join("\n");

// ---------------------------------------------------------------- misión del día
async function revisarMisionDia() {
  let m;
  try { m = await api("/api/mision_dia"); } catch { return; }
  const dia = new Date().getDay(), a = m.actividad;
  const lxSig = typeof MISIONES_LINUX !== "undefined" ? MISIONES_LINUX.find((x) => !m.misiones[x.id]) : null;
  const wsSig = Object.entries(m.escenarios).find(([id]) => (m.progreso_ws[id]?.mejor || 0) < 8);
  const rot = [
    { id: "subneteo", txt: "Subneteo contra reloj (2 min)", hecho: a.subneteo > 0, ir: "subneteo" },
    { id: "retos", txt: "Una ronda de arrastrar y soltar", hecho: a.retos > 0, ir: "retos" },
    { id: "wireshark", txt: wsSig ? `Wireshark: ${wsSig[1].nombre}` : "Wireshark: cualquier escenario", hecho: a.wireshark + (a.examenes_wireshark || 0) > 0, ir: "wireshark" },
    { id: "linux", txt: lxSig ? `Linux: misión "${lxSig.titulo}"` : "Linux: repite una misión por 3 ★", hecho: a.linux + (a.examenes_linux || 0) > 0, ir: "linux" },
    { id: "rvb", txt: "Una partida de Red vs Blue", hecho: a.rvb > 0, ir: "rvb" },
  ];
  const tareas = [
    m.repaso.total ? { txt: `Repasa tu cuaderno de errores (${m.repaso.pendientes} pendientes)`, hecho: m.repaso.pendientes === 0, ir: "repaso" }
      : { txt: "Teoría: escucha o lee una lección", hecho: a.lecciones > 0, ir: "teoria" },
    { txt: `CCNA: examen o práctica de "${m.recomendado.nombre}"`, hecho: a.examenes + a.practicas > 0, ir: "ruta" },
    rot[dia % rot.length], rot[(dia + 2) % rot.length],
  ];
  const hechas = tareas.filter((t) => t.hecho).length;
  const caja = $("#misionDia");
  if (caja) {
    caja.innerHTML = `<div class="mision-cab"><b>📅 Misión del día</b><span class="sub">${hechas}/${tareas.length} · +50 XP al completarla</span></div>
      <div class="mision-lista">${tareas.map((t) => `<button class="mision-t ${t.hecho ? "hecha" : ""}" data-ir="${t.ir}">${t.hecho ? "✅" : "⬜"} ${esc(t.txt)}</button>`).join("")}</div>`;
    $$("[data-ir]", caja).forEach((b) => b.addEventListener("click", () => ir(b.dataset.ir)));
  }
  if (hechas === tareas.length) {
    const r = await api("/api/mision_dia/completar", {}).catch(() => ({}));
    if (r.nueva) { celebrar("📅 ¡Misión del día completa! +50 XP", "nivel"); refrescarJugador(true); }
  }
}
