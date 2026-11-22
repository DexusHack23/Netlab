"use strict";
// ======================================================================
// NetLab — Mundo SIEM: Elasticsearch + Kibana REALES dentro de la VM de Ubuntu.
// NetLab siembra un incidente con verdad de fondo, el alumno lo caza en Kibana
// y NetLab lo califica. Ejercicios de detección infinitos (estilo TryHackMe SAL1).
// ======================================================================
const SIE = { est: null, esc: null, pistas: 0, vioSol: false, calienta: null };

async function pintarSiem() {
  const caja = $("#siemVista");
  if (!SIE.esc) caja.innerHTML = `<div class="tarjeta"><div class="trabajo"><div class="girar"></div><div>Revisando el SIEM…</div></div></div>`;
  try { SIE.est = await api("/api/siem/estado"); } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  if (SIE.esc) return;  // hay un escenario abierto; no repintar el panel
  const e = SIE.est;
  const cal = e.calor || {};
  const calentando = ["arrancando", "ssh", "elastic", "kibana"].includes(cal.fase) || (e.instalado && e.corriendo && e.es && !e.kibana);
  // repintar solo mientras calienta (el indicador avanza por fases)
  if (calentando && !SIE.calienta) {
    SIE.calienta = setInterval(() => { if ($("#v-siem")?.classList.contains("visible") && !SIE.esc) pintarSiem(); else { clearInterval(SIE.calienta); SIE.calienta = null; } }, 4000);
  }
  if (!calentando && SIE.calienta) { clearInterval(SIE.calienta); SIE.calienta = null; }

  const hechos = Object.keys(e.progreso || {}).length;
  const pausada = e.vmstate === "saved";
  const esp = e.espacio || {};
  const modoTxt = e.modo === "rapido" ? "⚡ Fast mode (Hyper-V off)" : e.modo === "nem" ? "🐢 Hyper-V mode (NEM)" : "";
  caja.innerHTML = `
    <div class="tarjeta vm-estado">
      <h2 style="margin-top:0">🛰️ SIEM real · Elasticsearch + Kibana</h2>
      <p class="sub">Un SIEM profesional corriendo en tu VM de Ubuntu. NetLab te inyecta un incidente real en los logs (fuerza bruta, escaneos, beacons C2, fugas de datos…), tú lo investigas en <b>Kibana</b> como un analista N1, y NetLab te califica. Cada caso cambia IPs, usuarios y cantidades: son infinitos. Esto es justo lo que mide TryHackMe SAL1.</p>
      <div class="vm-chips">
        ${chip(e.instalado, "SIEM instalado")}${chip(e.corriendo, "VM encendida")}${chip(e.es, "Elasticsearch")}${chip(e.kibana, "Kibana")}
        ${e.instalado ? chip(e.caliente, "Instantánea en caliente") : ""}
      </div>
      ${e.instalado && modoTxt ? `<p class="sub"><span data-no-tr>${esc(modoTxt)}</span> · ${e.cpus || "?"} CPU</p>` : ""}
      ${e.instalado ? pasosCalor(e, cal) : ""}
      <div class="acciones">
        ${!e.instalado ? '<button class="primario" id="siemInstalar">⚙️ Instalar el SIEM en la VM (una vez, 10-20 min)</button>' : ""}
        ${e.instalado && !e.corriendo && !calentando ? `<button class="primario" id="siemEncender">${pausada ? "▶️ Reanudar VM" : "▶ Encender la VM"}</button>` : ""}
        ${e.instalado && e.corriendo && e.kibana ? `<button class="primario" id="siemKibana">🔍 Abrir Kibana</button>` : ""}
        ${e.instalado && e.corriendo && !calentando ? '<button id="siemPausar">⏸️ Pausar VM</button>' : ""}
      </div>
      <div id="siemTrabajo"></div>
      ${e.instalado ? `<label class="sub" style="display:block;margin-top:6px"><input type="checkbox" id="siemAuto" ${e.auto ? "checked" : ""}> Calentar el SIEM solo al abrir NetLab</label>` : ""}
      ${e.instalado ? `<p class="sub">Kibana manual: <code>${esc(e.kibana_url)}</code> · En Kibana ve a <b>Discover</b>, elige la vista <b>lab-logs</b> y pon el rango de tiempo en <b>Last 1 day</b>.</p>` : ""}
      ${!e.instalado ? '<p class="sub">Al instalar, la VM pasa a 8 GB de RAM y queda con Elastic+Kibana horneados en la instantánea limpia. Solo se hace una vez; no descargas nada en Windows.</p>' : ""}
    </div>
    ${e.instalado ? `
      <details class="tarjeta"><summary><b>💾 Disco y arranque rápido</b>${esp.poco ? ' <span class="ac-error">· poco espacio</span>' : ""}</summary>
        <p class="sub">Libre en disco: <b>${esp.libre_gb ?? "?"} GB</b> · Memoria guardada (.sav de la pausa + instantánea en caliente): <b>${esp.sav_gb ?? 0} GB</b> · Discos de instantáneas: <b>${esp.snaps_gb ?? 0} GB</b></p>
        <p class="sub">Al cerrar NetLab la VM se pausa (su RAM va a disco, ~8 GB) y al abrir reanuda en segundos. La instantánea en caliente guarda el SIEM ya calentado: si el estado guardado se pierde (p. ej. cambiaste el modo de Hyper-V), NetLab vuelve a ella en lugar de arrancar en frío.</p>
        ${esp.poco ? '<p class="ac-error">Hay poco espacio: al cerrar NetLab la VM se apagará en vez de pausarse.</p>' : ""}
        <div class="acciones">
          ${e.corriendo && e.kibana ? `<button id="siemSnap">📸 ${e.caliente ? "Rehacer" : "Tomar"} instantánea en caliente</button>` : ""}
          ${e.caliente ? '<button id="siemSnapB">🗑️ Borrar instantánea en caliente</button>' : ""}
          ${pausada ? '<button id="siemDescartar">🗑️ Descartar estado guardado</button>' : ""}
        </div>
      </details>` : ""}
    ${e.instalado && e.corriendo && e.kibana ? `
      <div class="tarjeta lx-resumen"><div><b>${hechos}</b> tipos de incidente resueltos · cada partida es un caso nuevo con otra verdad</div></div>
      <div class="tarjeta"><div class="ac-nivel-cab"><h3 style="margin:0">📚 Teoría y exámenes</h3></div>
        <p class="sub">La teoría, los exámenes y los jefes de búsquedas en SIEM, tráfico sospechoso y respuesta a incidentes están en la ruta del mundo SOC.</p>
        <div class="acciones"><button data-siem-ruta>🚨 Ir a la ruta SOC</button><button data-siem-teoria>📖 Teoría: Búsquedas en un SIEM</button></div></div>
      <div class="tarjeta"><h3 style="margin-top:0">Casos para investigar</h3><div class="ws-grid">
        ${e.catalogo.map((c) => { const s = e.progreso?.[c.id] || 0;
          return `<button class="ws-esc lx-mision ${s ? "hecha" : ""}" data-siem="${c.id}"><b>${c.ic} ${esc(c.titulo)}</b>
            <span class="sub">${esc(c.nivel)}</span><span class="lx-estrellas">${"★".repeat(s)}<span class="vacia">${"★".repeat(3 - s)}</span></span></button>`; }).join("")}
      </div></div>
      <div class="tarjeta"><h3 style="margin-top:0">📥 Importar tus datos reales</h3>
        <p class="sub">Pon capturas (.pcap/.pcapng) o logs (.log, .txt, .json, .csv) en la carpeta <code>${esc(e.importar?.carpeta || "")}</code>. NetLab los carga en Elasticsearch en la vista <b>importados</b> (las capturas se leen con tshark). Los casos del SIEM no los borran.</p>
        <div class="acciones"><button id="siemImpCarpeta">📂 Abrir la carpeta</button><button id="siemImpRefrescar">🔄 Actualizar lista</button>
          ${(e.importar?.archivos || []).length ? '<button class="primario" id="siemImpCargar">📥 Cargar seleccionados</button><button id="siemImpBorrar">🗑️ Vaciar importados</button>' : ""}</div>
        ${(e.importar?.archivos || []).length ? `<div class="siem-imp">${e.importar.archivos.map((f) => `<label style="display:block"><input type="checkbox" data-imp="${esc(f.nombre)}" checked> <span data-no-tr>${esc(f.nombre)}</span> <span class="sub">(${f.mb} MB)</span></label>`).join("")}</div>`
          : '<p class="sub">La carpeta está vacía.</p>'}
        <div id="siemImpRes"></div>
      </div>` : ""}`;

  $("#siemInstalar")?.addEventListener("click", () => {
    if (!window.confirm("Voy a instalar Elasticsearch + Kibana dentro de tu VM de Ubuntu. Descarga ~1 GB y puede tardar 10-20 min. No cierres NetLab mientras tanto. ¿Empezamos?")) return;
    trabajoSiem("/api/vm/siem");
  });
  $("#siemEncender")?.addEventListener("click", () => trabajoSiem("/api/vm/calentar"));
  $("#siemPausar")?.addEventListener("click", () => trabajoSiem("/api/vm/suspender"));
  $("#siemKibana")?.addEventListener("click", () => { window.open(SIE.est.kibana_url, "_blank"); aviso("Abriendo Kibana en tu navegador…"); });
  $("#siemAuto")?.addEventListener("change", async (ev) => { await api("/api/vm/auto", { auto: ev.target.checked }); aviso(ev.target.checked ? "El SIEM se calentará solo al abrir NetLab" : "Calentado automático desactivado"); });
  $("#siemSnap")?.addEventListener("click", () => trabajoSiem("/api/vm/caliente"));
  $("#siemSnapB")?.addEventListener("click", () => { if (window.confirm("¿Borrar la instantánea en caliente? Libera espacio, pero el próximo arranque en frío será lento.")) trabajoSiem("/api/vm/caliente_borrar"); });
  $("#siemDescartar")?.addEventListener("click", async () => {
    if (!window.confirm("¿Descartar el estado guardado de la VM? Libera ~8 GB; la próxima vez arranca desde la instantánea en caliente o en frío.")) return;
    await api("/api/vm/descartar_estado", {}); pintarSiem();
  });
  $("#siemImpCarpeta")?.addEventListener("click", async () => { await api("/api/siem/importar_carpeta", {}); aviso("Abriendo la carpeta de importación…"); });
  $("#siemImpRefrescar")?.addEventListener("click", () => pintarSiem());
  $("#siemImpBorrar")?.addEventListener("click", async () => { if (!window.confirm("¿Vaciar el índice 'importados' en Elasticsearch? Tus archivos no se tocan.")) return; await api("/api/siem/importados_borrar", {}); aviso("Índice 'importados' vaciado"); });
  $("#siemImpCargar")?.addEventListener("click", async (ev) => {
    const archivos = $$("[data-imp]").filter((c) => c.checked).map((c) => c.dataset.imp);
    if (!archivos.length) return aviso("Elige al menos un archivo");
    ev.target.disabled = true;
    try {
      const r = await trabajo("/api/siem/importar", { archivos }, $("#siemImpRes"));
      $("#siemImpRes").innerHTML = `<div class="tarjeta">${r.reporte.map((x) => `<div class="${x.fallo ? "ac-error" : "ac-ok"}"><span data-no-tr>${esc(x.archivo)}</span>: ${x.fallo ? esc(x.fallo) : `${x.eventos} eventos${x.errores ? ` · ${x.errores} con error` : ""}`}</div>`).join("")}
        <p class="sub">En Kibana → Discover elige la vista <b>importados</b>.</p></div>`;
    } catch (err) { $("#siemImpRes").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    ev.target.disabled = false;
  });
  $$("[data-siem]").forEach((b) => b.addEventListener("click", () => empezarSiem(b.dataset.siem)));
  $("[data-siem-ruta]")?.addEventListener("click", () => { ir("soc"); setTimeout(() => $("#socRuta")?.scrollIntoView({ behavior: "smooth" }), 600); });
  $("[data-siem-teoria]")?.addEventListener("click", () => irTeoria("soc", "soc_siem"));
}

/** Indicador de calentado por fases: VM → Elasticsearch → Kibana → listo. */
function pasosCalor(e, cal) {
  const pasos = [["arrancando", "VM"], ["elastic", "Elasticsearch"], ["kibana", "Kibana"], ["lista", "Listo"]];
  let actual = ["arrancando", "ssh"].includes(cal.fase) ? 0 : cal.fase === "elastic" ? 1 : cal.fase === "kibana" ? 2 : cal.fase === "lista" ? 3 : -1;
  if (actual < 0) actual = !e.corriendo ? -1 : !e.es ? 1 : !e.kibana ? 2 : 3;  // sin calentado en marcha: deducir de lo que responde
  if (actual < 0 && cal.fase !== "error") return "";
  const seg = cal.desde ? Math.max(0, Math.round(Date.now() / 1000 - cal.desde)) : 0;
  const barra = pasos.map(([, n], i) => `<span class="calor-paso" style="${i === actual && actual < 3 ? "font-weight:700" : i > actual ? "opacity:.55" : ""}">${i < actual || actual === 3 ? "✅" : i === actual ? "⏳" : "⬜"} ${esc(n)}</span>`).join(" → ");
  return `<div class="calor" style="margin:8px 0;padding:8px 10px;border-radius:8px;background:rgba(127,127,127,.08)">${barra}
    ${cal.fase === "error" ? `<div class="ac-error">⚠️ <span>${esc(cal.error || "")}</span></div>`
      : actual < 3 && actual >= 0 ? `<div class="sub">${cal.msg ? `<span>${esc(cal.msg)}</span>` : "Calentando…"}${seg ? ` · ${seg} s` : ""}</div>` : ""}</div>`;
}

async function trabajoSiem(ruta) {
  $$("#siemVista button").forEach((b) => { b.disabled = true; });
  try { await trabajo(ruta, {}, $("#siemTrabajo")); } catch (e) { aviso(e.message); }
  pintarSiem();
}

async function empezarSiem(id) {
  const caja = $("#siemVista");
  SIE.pistas = 0; SIE.vioSol = false;
  caja.innerHTML = `<div class="tarjeta"><div id="siemPrep"></div></div>`;
  let d;
  try { d = await trabajo("/api/siem/mision", { escenario: id }, $("#siemPrep")); }
  catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; SIE.esc = null; return; }
  SIE.esc = d;
  caja.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button id="siemVolver">← Casos del SIEM</button>
      <button class="primario btn-teofondo" id="siemTeoFondo">📖 Teoría a fondo</button>
      <button id="siemTeoLec">📚 Lecciones y exámenes de SOC</button></div>
    <div id="siemTeoFondoCaja" hidden></div>
    <div class="tarjeta destacada">
      <div class="sub">Incidente · ${d.n} eventos cargados en Elasticsearch</div><h2 style="margin:4px 0">${esc(d.titulo)}</h2>
      <p class="explicacion">${md(d.info)}</p>
      <div class="acciones">
        <button class="primario" id="siemKib2">🔍 Investigar en Kibana</button>
        <button id="siemPista">💡 Pista</button>
        <button id="siemSol">🏳️ Ver respuesta</button>
      </div>
      <div class="siem-preguntas">
        ${d.preguntas.map((p) => `<label class="siem-q"><span>${esc(p.q)}</span>
          <input data-k="${p.k}" placeholder="${p.tipo === "ip" ? "ej. 203.0.113.45" : p.tipo === "num" ? "número" : "respuesta"}"></label>`).join("")}
      </div>
      <div class="acciones"><button class="primario" id="siemCheck">✅ Enviar mi análisis</button></div>
      <div id="siemPistas"></div><div id="siemRes"></div>
    </div>`;
  $("#siemVolver").addEventListener("click", () => { SIE.esc = null; pintarSiem(); });
  $("#siemTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#siemTeoFondoCaja"), {
    clave: `siem:${id}`, mundo: "soc", titulo: d.titulo,
    contexto: `Caso de SIEM (Elasticsearch + Kibana) para analista SOC nivel 1. ${String(d.info || "").slice(0, 600)} `
      + `Hay que responder: ${d.preguntas.map((p) => p.q).join(" | ")}. Se investiga con consultas KQL, filtros por campo y línea de tiempo.` }));
  $("#siemTeoLec").addEventListener("click", () => irTeoria("soc", null));
  $("#siemKib2").addEventListener("click", () => { window.open(SIE.est.kibana_url, "_blank"); aviso("Abriendo Kibana…"); });
  $("#siemPista").addEventListener("click", async () => {
    SIE.pistas++;
    const r = await api("/api/siem/pista", { id: d.id, n: SIE.pistas });
    if (r.error) return aviso(r.error);
    $("#siemPistas").innerHTML = r.pistas.map((p, i) => `<div class="ac-pista">💡 ${i + 1}. ${md(p)}</div>`).join("");
    if (SIE.pistas >= r.pistas.length) aviso("Esa fue la última pista");
  });
  $("#siemSol").addEventListener("click", async () => {
    if (!window.confirm("Si ves la respuesta, el caso vale 1 ★. ¿Verla?")) return;
    SIE.vioSol = true;
    const r = await api("/api/siem/solucion", { id: d.id });
    if (r.error) return aviso(r.error);
    $("#siemPistas").insertAdjacentHTML("beforeend", `<div class="ac-pista"><b>Respuesta</b><pre>${esc(JSON.stringify(r.verdad, null, 2))}</pre></div>`);
  });
  $("#siemCheck").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    const respuestas = {};
    $$("#siemVista .siem-q input").forEach((i) => { respuestas[i.dataset.k] = i.value.trim(); });
    $("#siemRes").innerHTML = `<div class="trabajo"><div class="girar"></div><div>Comparando con la verdad del incidente…</div></div>`;
    try {
      const r = await api("/api/siem/revisar", { id: d.id, respuestas });
      if (r.error) { $("#siemRes").innerHTML = `<p class="error">${esc(r.error)}</p>`; ev.target.disabled = false; return; }
      const filas = r.detalle.map((x) => { const p = d.preguntas.find((q) => q.k === x.k);
        return `<div class="${x.ok ? "ac-ok" : "ac-error"}" style="padding:4px 0">${x.ok ? "✓" : "✗"} ${esc(p.q)}${x.ok ? "" : ` — era <code>${esc(String(x.esperado))}</code>`}</div>`; }).join("");
      if (r.ok) {
        const est = SIE.vioSol ? 1 : SIE.pistas ? 2 : 3;
        await api("/api/siem/resultado", { id: d.id, estrellas: est });
        celebrar(`✅ ¡Incidente resuelto! ${"★".repeat(est)}`, "logro");
        setTimeout(() => refrescarJugador(true), 300);
      }
      $("#siemRes").innerHTML = `<div class="tarjeta ${r.ok ? "ac-ok" : "ac-error"}"><b>${r.ok ? "✅ Análisis correcto" : `Llevas ${r.bien}/${r.total}`}</b>${filas}
        ${r.ok ? "" : '<p class="sub">Revisa en Kibana y vuelve a enviar. Usa las pistas si te atoras.</p>'}</div>`;
    } catch (e) { $("#siemRes").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
    ev.target.disabled = false;
  });
}
