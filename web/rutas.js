"use strict";
// ======================================================================
// NetLab — Rutas de Linux y Wireshark con la misma mecánica que la de CCNA:
// temas con 📖 teoría · práctica · 📝 examen, estrellas, candados y 👹 jefe por nivel.
// ======================================================================
const RUTA_LX = [
  { nombre: "Básico", icono: "🌱", temas: [
    { id: "lx_fs", nombre: "Moverte por el sistema", mis: ["l1", "l2", "l3", "l4"] },
    { id: "lx_archivos", nombre: "Archivos y carpetas", mis: ["a1", "a2", "a3", "a4", "a5", "a6"] },
    { id: "lx_texto", nombre: "Ver y buscar texto", mis: ["b1", "b2", "b3", "b4", "b5"] },
  ] },
  { nombre: "Intermedio", icono: "⚙️", temas: [
    { id: "lx_tuberias", nombre: "Tuberías y redirecciones", mis: ["t1", "t2", "t3", "t4"] },
    { id: "lx_sedawk", nombre: "Texto pro: awk, sed, cut y base64", mis: ["x1", "x2", "x3", "x4", "x5"] },
    { id: "lx_permisos", nombre: "Permisos y dueños", mis: ["p1", "p2", "p3", "p4"] },
    { id: "lx_usuarios", nombre: "Usuarios y grupos", mis: [] },
  ] },
  { nombre: "Avanzado", icono: "🔥", temas: [
    { id: "lx_red", nombre: "Redes en Linux", mis: ["s1", "s2", "s3", "s4", "s5"] },
    { id: "lx_procesos", nombre: "Procesos y servicios", mis: ["s6"] },
    { id: "lx_paquetes", nombre: "Paquetes e instalación", mis: [] },
    { id: "lx_bash", nombre: "Scripts de bash y cron", mis: ["z1", "z2", "z3", "z4", "z5"] },
  ] },
  { nombre: "Experto SOC", icono: "👑", temas: [
    { id: "lx_logs", nombre: "Logs y detección", mis: ["c1", "c2"] },
    { id: "lx_ir", nombre: "Respuesta a incidentes y persistencia", mis: ["c3", "c4", "c5"] },
  ] },
];

const RUTAS = { claves: null };
const notaRuta = (partes) => { const v = partes.filter((x) => x != null); return v.length ? Math.round((10 * v.reduce((s, x) => s + x, 0)) / v.length) / 10 : null; };

async function clavesTeoria() {
  if (RUTAS.claves) return RUTAS.claves;
  try { RUTAS.claves = Object.fromEntries((await api("/api/teoria")).temas.map((t) => [t.id, t])); } catch { RUTAS.claves = {}; }
  return RUTAS.claves;
}
async function progresoGeneral() {
  try { ESTADO = await api("/api/estado"); } catch {}
  return ESTADO?.progreso || {};
}

/** Pinta una ruta. cfg: { caja, pref, dominio, niveles: [{nombre, icono, temas: [{id, nombre, nota_practica, practica_txt, detalle}]}], onPractica } */
function pintarRuta2(cfg, prog) {
  const nota = (t) => notaRuta([t.nota_practica, prog[t.id]?.mejor_examen ?? null]);
  const abierto = (i) => {
    if (i === 0) return true;
    const prev = cfg.niveles[i - 1];
    return (prog[`jefe_${cfg.pref}_${i - 1}`]?.mejor_examen || 0) >= 8
      || prev.temas.filter((t) => (nota(t) || 0) >= 8).length >= Math.ceil(prev.temas.length / 2);
  };
  const todos = cfg.niveles.flatMap((n, i) => n.temas.map((t) => ({ ...t, i })));
  const sig = todos.find((t) => abierto(t.i) && (nota(t) || 0) < 8);
  cfg.caja.innerHTML = (sig ? `<div class="tarjeta destacada">
      <div class="sub" style="margin:0">Siguiente misión · ${esc(cfg.niveles[sig.i].nombre)}</div>
      <h2 style="margin:4px 0 10px">${esc(sig.nombre)}</h2>
      <div class="acciones"><button data-r-teo="${sig.id}">📖 Teoría</button>
        ${sig.practica_txt ? `<button class="primario" data-r-prac="${sig.id}">${sig.practica_txt}</button>` : ""}
        <button ${sig.practica_txt ? "" : 'class="primario"'} data-r-ex="${sig.id}">📝 Examen</button></div></div>` : "")
    + cfg.niveles.map((n, i) => {
      const ok = abierto(i), dom = n.temas.filter((t) => (nota(t) || 0) >= 8).length;
      const est = n.temas.reduce((s, t) => s + estrellasTema(nota(t) || 0), 0), jefe = prog[`jefe_${cfg.pref}_${i}`]?.mejor_examen;
      return `<div class="nivel ${ok ? "" : "cerrado"}">
        <h2>${ok ? n.icono : "🔒"} ${esc(n.nombre)} <span class="sub" style="margin:0;font-size:13px">${dom}/${n.temas.length} dominados · ${est}/${n.temas.length * 3} ★</span>
          <span class="barra"><i style="width:${(100 * dom) / n.temas.length}%"></i></span></h2>
        ${ok ? "" : `<p class="sub">Se abre al dominar la mitad del nivel anterior (8/10) o al vencer a su jefe final.</p>`}
        <div class="temas">${n.temas.map((t) => {
          const v = nota(t), s = estrellasTema(v || 0), ex = prog[t.id]?.mejor_examen;
          return `<div class="tema ${sig && t.id === sig.id ? "rec" : ""}">
            <div class="nombre">${esc(t.nombre)}</div>
            <div class="lx-estrellas">${"★".repeat(s)}<span class="vacia">${"★".repeat(3 - s)}</span></div>
            <div class="meta">${v != null ? `<span class="nota ${notaClase(v)}">${v}/10</span> · ` : ""}${esc(t.detalle || "")}${ex != null ? ` · examen ${ex}` : ""}</div>
            <div class="acciones">
              <button class="chico" data-r-teo="${t.id}" ${ok ? "" : "disabled"}>Teoría</button>
              ${t.practica_txt ? `<button class="chico" data-r-prac="${t.id}" ${ok ? "" : "disabled"}>${t.practica_txt}</button>` : ""}
              <button class="chico" data-r-ex="${t.id}" ${ok ? "" : "disabled"}>Examen</button>
            </div><div class="r-extra" data-r-extra="${t.id}"></div></div>`;
        }).join("")}
          <div class="tema jefe"><div class="nombre">👹 Jefe final: ${esc(n.nombre)}</div>
            <div class="meta">${jefe != null ? `<span class="nota ${notaClase(jefe)}">${jefe}/10</span> · ${jefe >= 8 ? "¡vencido!" : "necesitas 8"}` : "15 preguntas de todo el nivel · necesitas 8"}</div>
            <div class="acciones"><button class="chico ${ok ? "primario" : ""}" data-r-jefe="${i}" ${ok ? "" : "disabled"}>Pelear</button></div></div>
        </div></div>`;
    }).join("");
  const tema = (id) => todos.find((t) => t.id === id);
  $$("[data-r-teo]", cfg.caja).forEach((b) => b.addEventListener("click", () => irTeoria(cfg.dominio, b.dataset.rTeo)));
  $$("[data-r-prac]", cfg.caja).forEach((b) => b.addEventListener("click", () => cfg.onPractica(tema(b.dataset.rPrac), b)));
  $$("[data-r-ex]", cfg.caja).forEach((b) => b.addEventListener("click", () => {
    const t = tema(b.dataset.rEx), caja = $(`[data-r-extra="${t.id}"]`, cfg.caja);
    antesDelExamen(caja, { tema: t.id, hayPractica: t.nota_practica != null || (prog[t.id]?.examenes || 0) > 0,
      alLeccion: () => irTeoria(cfg.dominio, t.id),
      alPractica: t.practica_txt ? () => cfg.onPractica(t, b) : null,
      alExamen: () => examenDeTema(cfg, t) });
  }));
  $$("[data-r-jefe]", cfg.caja).forEach((b) => b.addEventListener("click", () => jefeDeRuta(cfg, +b.dataset.rJefe)));
}

async function examenDeTema(cfg, t) {
  const claves = await clavesTeoria();
  irExamenMundo(cfg.dominio);
  const caja = $("#examenVista");
  try {
    const { id } = await trabajo("/api/examen/generar", { dominio: cfg.dominio, tema: t.id, n: 10, nivel: cfg.niveles[t.i].nombre.split(" ")[0],
      descripcion: `${cfg.titulo}. Tema: ${t.nombre}. Conceptos: ${claves[t.id]?.clave || t.nombre}. Nivel de certificación (${cfg.cert}).` }, caja);
    await abrirExamen(id);
  } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
}

async function jefeDeRuta(cfg, i) {
  const claves = await clavesTeoria(), n = cfg.niveles[i];
  irExamenMundo(cfg.dominio);
  const caja = $("#examenVista");
  try {
    const { id } = await trabajo("/api/examen/generar", { dominio: cfg.dominio, tema: `jefe_${cfg.pref}_${i}`, n: 15, nivel: n.nombre.split(" ")[0],
      descripcion: `JEFE FINAL del nivel ${n.nombre} de ${cfg.titulo} (${cfg.cert}): preguntas variadas y exigentes, tipo escenario, que mezclen TODOS estos temas: `
        + n.temas.map((t) => `${t.nombre} (${claves[t.id]?.clave || ""})`).join("; ") }, caja);
    await abrirExamen(id);
  } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
}

// ---------------------------------------------------------------- Linux
async function pintarRutaLinux() {
  LX.mision = null;
  const prog = await progresoGeneral();
  const misT = (t) => t.mis.map((id) => MISIONES_LINUX.find((m) => m.id === id)).filter(Boolean);
  const niveles = RUTA_LX.map((n) => ({ ...n, temas: n.temas.map((t) => {
    const ms = misT(t), est = ms.reduce((s, m) => s + (LX.estrellas[m.id] || 0), 0), hechas = ms.filter((m) => LX.estrellas[m.id]).length;
    return { ...t, nota_practica: ms.length && hechas ? Math.round((100 * est) / (3 * ms.length)) / 10 : null,
      practica_txt: ms.length ? `🖥️ Misiones (${hechas}/${ms.length})` : "", detalle: ms.length ? `${est}/${ms.length * 3} ★ en misiones` : "teoría + examen" };
  }) }));
  const total = MISIONES_LINUX.length, hechas = MISIONES_LINUX.filter((m) => LX.estrellas[m.id]).length;
  $("#linuxVista").innerHTML = `<div class="tarjeta lx-resumen">
      <div><b>${hechas}/${total}</b> misiones · <b>${Object.values(LX.estrellas).reduce((s, x) => s + x, 0)}/${total * 3}</b> ★</div>
      <div class="acciones"><button class="primario" id="lxReal">🐧 Ubuntu real (VirtualBox)</button><button id="lxLibre">🖥️ Terminal libre</button><button id="lxTodas">🗺️ Todas las misiones</button>
        <button id="lxExamen">📝 Examen general</button></div></div><div id="lxRuta"></div>`;
  $("#lxLibre").addEventListener("click", () => abrirMision(null));
  $("#lxReal").addEventListener("click", abrirVmLab);
  $("#lxTodas").addEventListener("click", pintarMisionesLinux);
  $("#lxExamen").addEventListener("click", examenLinux);
  pintarRuta2({ caja: $("#lxRuta"), pref: "lx", dominio: "linux", titulo: "Linux para redes y SOC", cert: "Linux Essentials / LPIC-1 y SOC nivel 1",
    niveles, onPractica: (t, b) => {
      const caja = $(`[data-r-extra="${t.id}"]`);
      // el botón de "Siguiente misión" (arriba) abre la lista que vive más abajo, en su tema: antes se abría fuera de la
      // pantalla y parecía que no pasaba nada (y un segundo clic la cerraba). Ahora se queda abierta y te lleva ahí.
      const lejos = !caja.parentElement.contains(b);  // el clic vino del botón de arriba, no del de su tema
      if (caja.innerHTML && !lejos) { caja.innerHTML = ""; return; }
      if (caja.innerHTML) { caja.scrollIntoView({ block: "nearest" }); return; }
      caja.innerHTML = `<div class="r-misiones">${misT(t).map((m) => { const e = LX.estrellas[m.id] || 0;
        return `<button class="chico" data-lx="${m.id}">${esc(m.titulo)} <span class="lx-estrellas">${"★".repeat(e)}<span class="vacia">${"★".repeat(3 - e)}</span></span></button>`; }).join("")}</div>`;
      $$("[data-lx]", caja).forEach((x) => x.addEventListener("click", () => abrirMision(x.dataset.lx)));
      caja.scrollIntoView({ block: "nearest" });  // que siempre se vea la lista recién abierta (sin animación: es instantáneo y fiable)
    } }, prog);
}

// ---------------------------------------------------------------- Wireshark
async function pintarRutaWireshark(r) {
  const prog = await progresoGeneral();
  const extra = { Básico: [{ id: "ws_filtros", nombre: "Filtros de captura y de visualización", bpf: true }],
    Intermedio: [{ id: "ws_estadisticas", nombre: "Estadísticas y Expert Info" }] };
  const niveles = r.niveles.map((n, i) => ({ nombre: n, icono: ["🌱", "⚙️", "🔥", "👑"][i] || "⭐",
    temas: [...(extra[n] || []).map((t) => ({ ...t, practica_txt: t.bpf ? "🎯 Ejercicios BPF" : "", detalle: t.bpf ? "filtros que se compilan con dumpcap" : "teoría + examen" })),
      ...Object.entries(r.escenarios).filter(([, e]) => e.nivel === n).map(([id, e]) => {
        const p = r.progreso[id];
        return { id: `ws_${id}`, esc: id, nombre: e.nombre, nota_practica: p ? p.mejor : null, practica_txt: "🦈 Captura",
          detalle: p ? `captura ${p.mejor} · ${p.intentos} intento(s)` : e.temas };
      })] }));
  pintarRuta2({ caja: $("#wsEscenarios"), pref: "ws", dominio: "wireshark", titulo: "Wireshark y análisis de tráfico", cert: "Wireshark Certified Analyst WCA-101",
    niveles, onPractica: (t, b) => {
      if (t.bpf) { $("#wsBpf").scrollIntoView({ behavior: "smooth" }); $("#wsBpf").click(); return; }
      nuevoWs(t.esc, b).then(() => $("#wsVista").scrollIntoView({ behavior: "smooth" }));
    } }, prog);
}
