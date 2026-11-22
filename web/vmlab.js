"use strict";
// ======================================================================
// NetLab — Laboratorio Linux REAL: Ubuntu Server en VirtualBox.
// NetLab prepara cada misión dentro de la VM por SSH y la califica con un script.
// ======================================================================
const VML = { est: null, mision: null, pistas: 0, vioSol: false };

async function abrirVmLab() {
  const caja = $("#linuxVista");
  caja.innerHTML = `<div class="tarjeta"><div class="trabajo"><div class="girar"></div><div>Revisando VirtualBox…</div></div></div>`;
  try { VML.est = await api("/api/vm/estado"); } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  pintarVmLab();
}

function pintarVmLab() {
  const e = VML.est, caja = $("#linuxVista");
  const listo = e.existe && e.snapshot;
  const niveles = [...new Set(e.misiones.map((m) => m.nivel))];
  const hechas = e.misiones.filter((m) => e.progreso[m.id]).length;
  caja.innerHTML = `
    <div class="acciones" style="margin-bottom:10px"><button id="vmVolver">← Ruta de Linux</button></div>
    <div class="tarjeta vm-estado">
      <h2 style="margin-top:0">🖥️ Laboratorio real · Ubuntu Server 24.04</h2>
      <p class="sub">Una máquina Linux de verdad en VirtualBox. NetLab arma el escenario adentro (usuarios, servicios, backdoors, logs…), tú lo resuelves en una terminal real y NetLab lo revisa. Si rompes algo, "Reiniciar máquina" la deja como nueva.</p>
      <div class="vm-chips">
        ${chip(e.vbox, "VirtualBox")}${chip(e.ova, "Imagen de Ubuntu")}${chip(e.existe, "Máquina creada")}${chip(e.snapshot, "Instantánea limpia")}
        ${chip(e.corriendo, "Encendida")}${chip(e.ssh, "SSH listo")}
      </div>
      ${e.error ? `<p class="error">${esc(e.error)}</p>` : ""}
      <div class="acciones">
        ${!e.vbox ? '<span class="error">Instala VirtualBox para usar el laboratorio real.</span>' : ""}
        ${e.vbox && !e.ova ? '<span class="error">Falta la imagen de Ubuntu: bájala desde Guías.</span>' : ""}
        ${e.vbox && e.ova && !listo ? '<button class="primario" id="vmCrear">⚙️ Crear la máquina (una sola vez, ~3 min)</button>' : ""}
        ${listo && !e.corriendo ? `<button class="primario" id="vmEncender">${e.vmstate === "saved" ? "▶️ Reanudar VM" : "▶ Encender"}</button>` : ""}
        ${listo && e.corriendo ? '<button class="primario" id="vmTerm">🖥️ Abrir terminal</button><button id="vmPausar">⏸️ Pausar VM</button><button id="vmApagar">⏻ Apagar</button>' : ""}
        ${listo ? '<button id="vmReset">♻️ Reiniciar máquina (borrar todo)</button>' : ""}
        ${e.existe ? '<button class="chico" id="vmRecrear">🛠️ Recrear desde cero</button>' : ""}
      </div>
      <div id="vmTrabajo"></div>
      <p class="sub">Acceso manual: <code>ssh -p ${e.puerto} ${esc(e.usuario)}@127.0.0.1</code> · contraseña <code>${esc(e.clave)}</code> (tiene sudo). La VM se apaga sola al cerrar NetLab.</p>
    </div>
    <div class="tarjeta lx-resumen"><div><b>${hechas}/${e.misiones.length}</b> misiones reales · cada partida cambia IPs, usuarios, puertos y rutas</div></div>
    ${niveles.map((n) => `<div class="tarjeta"><h3 style="margin-top:0">${esc(n)}</h3><div class="ws-grid">
      ${e.misiones.filter((m) => m.nivel === n).map((m) => { const s = e.progreso[m.id] || 0;
        return `<button class="ws-esc lx-mision ${s ? "hecha" : ""}" data-vm="${m.id}" ${listo ? "" : "disabled"}><b>${esc(m.titulo)}</b>
          <span class="sub">${esc(m.historia)}</span><span class="lx-estrellas">${"★".repeat(s)}<span class="vacia">${"★".repeat(3 - s)}</span></span></button>`; }).join("")}
      </div></div>`).join("")}`;
  $("#vmVolver").addEventListener("click", () => { LX.mision = null; cargarLinux(); });
  $("#vmCrear")?.addEventListener("click", () => trabajoVm("/api/vm/crear"));
  $("#vmEncender")?.addEventListener("click", () => trabajoVm("/api/vm/encender"));
  $("#vmPausar")?.addEventListener("click", () => trabajoVm("/api/vm/suspender"));
  $("#vmReset")?.addEventListener("click", () => { if (window.confirm("Se borra todo lo que hiciste dentro de la máquina. ¿Seguro?")) trabajoVm("/api/vm/reiniciar"); });
  $("#vmRecrear")?.addEventListener("click", () => { if (window.confirm("Borro la máquina de VirtualBox y la vuelvo a crear (unos 3 min). ¿Seguro?")) trabajoVm("/api/vm/recrear"); });
  $("#vmApagar")?.addEventListener("click", async () => { VML.est = { ...VML.est, ...(await api("/api/vm/apagar", {})) }; pintarVmLab(); });
  $("#vmTerm")?.addEventListener("click", () => api("/api/vm/terminal", {}).then(() => aviso("Abriendo la terminal…")));
  $$("[data-vm]").forEach((b) => b.addEventListener("click", () => empezarVm(b.dataset.vm)));
}
// traduce la plantilla y luego rellena {{IP}}, {{USR}}… (así la traducción sirve para cualquier partida)
const rellenarVm = (t, vars) => tr(t).replace(/\{\{(\w+)\}\}/g, (_, k) => vars?.[k] ?? _);
const chip = (ok, txt) => `<span class="vm-chip ${ok ? "ok" : ""}">${ok ? "✓" : "○"} ${txt}</span>`;

async function trabajoVm(ruta) {
  $$("#linuxVista button").forEach((b) => { b.disabled = true; });
  try { await trabajo(ruta, {}, $("#vmTrabajo")); } catch (e) { aviso(e.message); }
  abrirVmLab();
}

async function empezarVm(id) {
  const caja = $("#linuxVista");
  VML.pistas = 0; VML.vioSol = false;
  caja.innerHTML = `<div class="tarjeta"><div id="vmPrep"></div></div>`;
  try { VML.mision = await trabajo("/api/vm/mision", { id }, $("#vmPrep")); } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; return; }
  const m = VML.mision;
  caja.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button id="vmLab">← Laboratorio real</button>
      <button class="primario btn-teofondo" id="vmTeoFondo">📖 Teoría a fondo</button>
      <button id="vmTeoLinux">📚 Lecciones y exámenes de Linux</button></div>
    <div id="vmTeoFondoCaja" class="tarjeta" hidden></div>
    <div class="tarjeta destacada">
      <div class="sub">Ubuntu real · ${esc(m.nivel)}</div><h2 style="margin:4px 0">${esc(m.titulo)}</h2>
      <p class="explicacion">${esc(m.historia)}</p>
      <div class="lx-objetivo">🎯 ${esc(IDIOMA_UI === "en" ? rellenarVm(m.objetivo_t, m.vars) : m.objetivo)}</div>
      <div class="acciones">
        <button class="primario" id="vmTerm2">🖥️ Abrir terminal</button>
        <button class="primario" id="vmCheck">✅ Verificar</button>
        <button id="vmPista">💡 Pista (${m.n_pistas})</button>
        <button id="vmSol">🏳️ Ver solución</button>
      </div>
      <div id="vmPistas"></div><div id="vmRes"></div>
    </div>`;
  $("#vmLab").addEventListener("click", abrirVmLab);
  $("#vmTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#vmTeoFondoCaja"), {
    clave: `vm:${m.id}`, mundo: "linux", titulo: m.titulo,
    contexto: `Ubuntu real (servidor), nivel ${m.nivel}. ${m.historia} Objetivo: ${m.objetivo}` }));
  $("#vmTeoLinux").addEventListener("click", () => irTeoria("linux", null));
  $("#vmTerm2").addEventListener("click", () => api("/api/vm/terminal", {}).then(() => aviso("Abriendo la terminal…")));
  $("#vmPista").addEventListener("click", async () => {
    if (VML.pistas >= m.n_pistas) return aviso("Ya viste todas las pistas");
    VML.pistas++;
    const r = await api("/api/vm/pista", { id: m.id, n: VML.pistas });
    const ps = IDIOMA_UI === "en" ? r.pistas_t.map((p) => rellenarVm(p, r.vars)) : r.pistas;
    $("#vmPistas").innerHTML = ps.map((p, i) => `<div class="ac-pista">💡 ${i + 1}. ${md(p)}</div>`).join("");
  });
  $("#vmSol").addEventListener("click", async () => {
    if (!window.confirm("Si ves la solución, esta misión vale 1 ★. ¿Verla?")) return;
    VML.vioSol = true;
    const r = await api("/api/vm/solucion", { id: m.id });
    $("#vmPistas").insertAdjacentHTML("beforeend", `<div class="ac-pista"><b>Solución</b> (escríbela tú en la terminal)<pre>${esc(r.solucion)}</pre></div>`);
  });
  $("#vmCheck").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    $("#vmRes").innerHTML = `<div class="trabajo"><div class="girar"></div><div>Revisando dentro de la máquina…</div></div>`;
    try {
      const r = await api("/api/vm/revisar", { id: m.id });
      if (r.ok) {
        const est = VML.vioSol ? 1 : VML.pistas ? 2 : 3;
        await api("/api/vm/resultado", { id: m.id, estrellas: est });
        celebrar(`✅ ¡Misión real cumplida! ${"★".repeat(est)}`, "logro");
        setTimeout(() => refrescarJugador(true), 300);
      }
      $("#vmRes").innerHTML = `<div class="tarjeta ${r.ok ? "ac-ok" : "ac-error"}"><b>${r.ok ? "✅ ¡Lo lograste!" : "✗ Todavía no"}</b><pre class="ac-pre">${esc(r.salida)}</pre></div>`;
    } catch (e) { $("#vmRes").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
    ev.target.disabled = false;
  });
}
