"use strict";
// ======================================================================
// NetLab — Academia: 🦀 Rust · 🧠 IA · 🔧 Procesadores
// Tu código se compila con el rustc de tu PC y se califica con pruebas ocultas.
// ======================================================================
const AC = { datos: null, curso: "rust", mision: null, pistas: 0, vioSolucion: false, ultimo: null };
const lsAc = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

async function cargarAcademia(curso) {
  AC.curso = curso;
  try { AC.datos = await api("/api/academia"); } catch (e) { $(`#acVista_${curso}`).innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  AC.prog = await progresoGeneral();  // mejores notas de exámenes por tema (ac_<curso>_<nivel>, jefe_ac_<curso>)
  if (!AC.mision || AC.mision.curso !== curso) pintarMapaAcademia(curso);
}

const estrellasAc = (id) => AC.datos.progreso[id]?.estrellas || 0;

function nivelAbiertoAc(curso, i) {
  if (i === 0) return true;
  // atajo como en la ruta CCNA: si ya sabes el nivel anterior (8+ en su examen), entras directo sin hacer sus misiones
  if ((AC.prog?.[`ac_${curso}_${i - 1}`]?.mejor_examen || 0) >= 8) return true;
  if ((AC.prog?.[`ac_${curso}_${i}`]?.mejor_examen || 0) >= 8) return true;  // ya aprobaste el examen de ESTE nivel
  const prev = AC.datos.cursos[curso].niveles[i - 1].misiones;
  const jefe = prev.find((m) => m.jefe);
  return jefe ? estrellasAc(jefe.id) > 0 : prev.every((m) => estrellasAc(m.id) > 0);
}

function pintarMapaAcademia(curso) {
  AC.mision = null;
  const c = AC.datos.cursos[curso], todas = c.niveles.flatMap((n) => n.misiones);
  const hechas = todas.filter((m) => estrellasAc(m.id)).length, est = todas.reduce((s, m) => s + estrellasAc(m.id), 0);
  const jefes = todas.filter((m) => m.jefe), jefesHechos = jefes.filter((m) => estrellasAc(m.id)).length;
  $(`#acVista_${curso}`).innerHTML = `
    <div class="tarjeta lx-resumen">
      <div><b>${hechas}/${todas.length}</b> misiones · <b>${est}/${todas.length * 3}</b> ★ · 👑 jefes ${jefesHechos}/${jefes.length}
        <div class="sub">${curso === "torch" ? "Python + PyTorch (CUDA) en ia_env" : curso === "chisel" ? "Chisel 3.6 + chiseltest con tu Java y sbt (la primera vez baja ~200 MB y tarda unos minutos)" : AC.datos.rustc ? `Compilador: ${esc(AC.datos.rustc)}` : "⚠️ No encontré <code>rustc</code>: instala Rust con rustup.rs y reinicia NetLab."}
        · Mentor: ${esc(AC.datos.modelo_codigo || "")}</div></div>
      <div class="acciones">
        ${["torch", "chisel", "rustproj"].includes(curso) ? "" : "<button data-ac-libre>🧪 Laboratorio libre</button>"}
        <button data-ac-teoria>📖 Teoría</button>
      </div>
    </div>
    ${c.niveles.map((n, i) => {
      const abierto = nivelAbiertoAc(curso, i);
      const ok = n.misiones.filter((m) => estrellasAc(m.id)).length;
      return `<div class="tarjeta ac-nivel ${abierto ? "" : "cerrado"}">
        <div class="ac-nivel-cab"><h3>${abierto ? "" : "🔒 "}Nivel ${i + 1} · ${esc(n.nombre)}</h3><span class="sub">${esc(n.cap)} · ${ok}/${n.misiones.length}</span></div>
        ${abierto ? "" : '<p class="sub">Vence al jefe del nivel anterior para abrirlo.</p>'}
        <div class="ws-grid">${n.misiones.map((m) => {
          const e = estrellasAc(m.id);
          return `<button class="ws-esc lx-mision ${e ? "hecha" : ""} ${m.jefe ? "ac-jefe" : ""}" data-ac="${m.id}" ${abierto ? "" : "disabled"}>
            <b>${m.jefe ? "👑 " : ""}${esc(tr(m.titulo).replace(/^(JEFE|BOSS): /i, "").replace(/^./, (c) => c.toUpperCase()))}</b>
            <span class="lx-estrellas">${"★".repeat(e)}<span class="vacia">${"★".repeat(3 - e)}</span></span></button>`;
        }).join("")}</div>
        <div class="ac-camino">
          <button class="chico" data-ac-teonivel="${i}"><b>①</b> 📖 Lección</button><span class="flecha">→</span>
          <span class="sub"><b>②</b> 🎯 Misiones (arriba)</span><span class="flecha">→</span>
          <button class="chico" data-ac-exnivel="${i}" ${abierto ? "" : 'title="Si ya dominas este nivel, apruébalo con 8 y se abre"'}><b>③</b> 📝 Examen del nivel</button>
          ${notaAc(`ac_${curso}_${i}`)}</div>
        <div data-ac-base="${i}"></div></div>`;
    }).join("")}
    ${tarjetaJefeAc(curso, c)}
    ${curso === "torch" ? `<div class="tarjeta"><h3 style="margin-top:0">🧪 nanoGPT: entrena tu propio GPT</h3>
      <p class="sub">El nanoGPT de Andrej Karpathy entrenado en tu RTX con las obras de Shakespeare, carácter por carácter. Ves bajar la pérdida y al final tu modelo escribe texto nuevo. Mientras entrena, el resto de la IA de NetLab espera.</p>
      <div class="fila"><label>Iteraciones<select data-ng-it><option>500</option><option selected>1500</option><option>3000</option><option>5000</option></select></label></div>
      <div class="acciones"><button class="primario" data-ng>🚀 Entrenar</button><button class="primario btn-teofondo" data-ng-teo>📖 Teoría a fondo</button></div>
      <div data-ng-teocaja hidden></div><div data-ng-caja></div></div>` : ""}
    <div class="tarjeta ac-infinito" ${["torch", "chisel", "rustproj"].includes(curso) ? "hidden" : ""}>
      <h3 style="margin-top:0">♾️ Retos infinitos</h3>
      <p class="sub"><b data-no-tr>${esc(AC.datos.modelo_codigo || "")}</b> <span>inventa un reto nuevo del nivel que elijas. NetLab compila su solución contra sus pruebas en tu Rust y solo te lo da si funciona (y si el código inicial falla).</span></p>
      <div class="fila">
        <label>Nivel<select data-g-nivel>${c.niveles.map((n, i) => `<option value="${i}" ${nivelAbiertoAc(curso, i) ? "" : "disabled"}>${i + 1} · ${esc(n.nombre)}</option>`).join("")}</select></label>
        <label>Dificultad<select data-g-dif><option value="normal">Normal</option><option value="dificil">Difícil (tipo jefe)</option></select></label>
      </div>
      <div class="acciones"><button class="primario" data-g-gen>✨ Generar reto</button></div>
      <div data-g-caja></div><div data-g-lista></div>
    </div>
    ${curso === "cpu" ? `<div class="tarjeta"><h3 style="margin-top:0">🧮 Entrenador infinito de bits y RISC-V</h3>
      <p class="sub">Binario, hex, complemento a dos, banderas, bits, codificar/decodificar RISC-V, endianness y caché. Respuesta exacta y explicación paso a paso.</p>
      <div class="acciones"><button data-cpu-ent>Entrenar</button></div></div>
      <div class="tarjeta"><h3 style="margin-top:0">🖥️ Simulador de ensamblador RISC-V</h3>
      <p class="sub"><span>Escribe ensamblador de verdad, ejecútalo y mira los registros.</span> <span>${RETOS_RV.length} retos que se califican con casos al azar.</span></p>
      <div class="acciones"><button data-cpu-sim>Abrir simulador</button></div></div>` : ""}
    ${curso === "rust" ? `<div class="tarjeta"><h3 style="margin-top:0">🏋️ Rustlings oficiales</h3>
      <p class="sub">Los ~90 ejercicios oficiales de la comunidad de Rust (los mismos de rustlings), con sus pistas y soluciones, calificados aquí mismo.</p>
      <div class="acciones"><button data-rl-abrir>Abrir Rustlings</button></div></div>` : ""}`;
  const v = $(`#acVista_${curso}`);
  $$("[data-ac]", v).forEach((b) => b.addEventListener("click", () => abrirMisionAc(b.dataset.ac)));
  $("[data-ac-libre]", v)?.addEventListener("click", () => abrirMisionAc(null));
  $("[data-ac-teoria]", v).addEventListener("click", () => irTeoriaAc(curso, 0));
  $$("[data-ac-teonivel]", v).forEach((b) => b.addEventListener("click", () => irTeoriaAc(curso, +b.dataset.acTeonivel)));
  $$("[data-ac-exnivel]", v).forEach((b) => b.addEventListener("click", () => {
    const i = +b.dataset.acExnivel, n = c.niveles[i];
    const pendiente = n.misiones.find((m) => !estrellasAc(m.id));
    antesDelExamen($(`[data-ac-base="${i}"]`, v), {
      tema: `ac_${curso}_${i}`, hayPractica: n.misiones.some((m) => estrellasAc(m.id) > 0),
      alLeccion: () => irTeoriaAc(curso, i),
      alPractica: nivelAbiertoAc(curso, i) && pendiente ? () => abrirMisionAc(pendiente.id) : null,
      alExamen: () => examenAc(curso, i) });
  }));
  $$("[data-ac-jefe]", v).forEach((b) => b.addEventListener("click", () => examenAc(curso, null)));
  $("[data-rl-abrir]", v)?.addEventListener("click", pintarRustlings);
  $("[data-ng]", v)?.addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    const caja = $("[data-ng-caja]", v);
    try {
      const r = await trabajo("/api/academia/nanogpt", { iteraciones: +$("[data-ng-it]", v).value }, caja);
      caja.innerHTML = `<div class="tarjeta ac-ok"><b>✅ Tu GPT terminó de entrenar</b>
        <div class="sub">${r.perdidas.map((p) => `paso ${p.paso}: val ${p.val}`).join(" · ")}</div>
        <h4>Texto que escribió tu modelo:</h4><pre class="ac-pre" data-no-tr>${esc(r.muestra)}</pre></div>`;
    } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
    ev.target.disabled = false;
  });
  $("[data-cpu-ent]", v)?.addEventListener("click", pintarEntrenadorCpu);
  $("[data-ng-teo]", v)?.addEventListener("click", (ev) => teoriaAFondo(ev.target, $("[data-ng-teocaja]", v), {
    clave: "torch:nanogpt", mundo: "torch", titulo: "nanoGPT: cómo funciona y cómo se entrena un GPT pequeño",
    contexto: "nanoGPT de Andrej Karpathy entrenado carácter por carácter con Shakespeare: tokenización por caracteres, embeddings y posiciones, self-attention con máscara causal, multi-head attention, bloques Transformer (LayerNorm, MLP, conexiones residuales), pérdida de entropía cruzada, AdamW y tasa de aprendizaje, train/val y sobreajuste, y muestreo con temperatura. Relaciona cada parte con el código en PyTorch." }));
  $("[data-cpu-sim]", v)?.addEventListener("click", () => pintarSimuladorRv("suma"));
  $("[data-g-gen]", v).addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try {
      const { id } = await trabajo("/api/academia/generar", { curso, nivel: +$("[data-g-nivel]", v).value, dificultad: $("[data-g-dif]", v).value }, $("[data-g-caja]", v));
      abrirGeneradoAc(id);
    } catch (e) { $("[data-g-caja]", v).innerHTML = `<p class="error">${esc(e.message)}</p>`; ev.target.disabled = false; }
  });
  api(`/api/academia/retos?curso=${curso}`).then(({ retos }) => {
    if (!retos.length) return;
    $("[data-g-lista]", v).innerHTML = `<div class="sub" style="margin-top:8px">Tus retos generados:</div><div class="r-misiones">${retos.map((r) => { const e = estrellasAc(r.id);
      return `<button class="chico" data-g="${r.id}">${esc(r.titulo)} <span class="lx-estrellas">${"★".repeat(e)}<span class="vacia">${"★".repeat(3 - e)}</span></span></button>`; }).join("")}</div>`;
    $$("[data-g]", v).forEach((b) => b.addEventListener("click", () => abrirGeneradoAc(b.dataset.g)));
  }).catch(() => {});
}

async function abrirGeneradoAc(id) {
  const r = await api(`/api/academia/reto/${id}`);
  const n = AC.datos.cursos[r.curso].niveles[r.nivel];
  abrirMisionAc(id, { ...r, nombreNivel: `${n?.nombre || ""} · ♾️ reto generado` });
}

// ---------------------------------------------------------------- Rustlings
async function pintarRustlings() {
  const v = $("#acVista_rust");
  v.innerHTML = '<div class="tarjeta"><div class="trabajo"><div class="girar"></div><div>Cargando Rustlings…</div></div></div>';
  let r;
  try { r = await api("/api/rustlings"); } catch (e) { v.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  if (!r.ejercicios.length) {
    v.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button data-ac-mapa>← Mapa</button></div>
      <div class="tarjeta"><h3 style="margin-top:0">🏋️ Rustlings</h3><p class="sub">Aún no están en tu PC. Se bajan del repositorio oficial (github.com/rust-lang/rustlings, ~1 MB).</p>
      <div class="acciones"><button class="primario" data-rl-bajar>⬇️ Bajarlos</button></div><div data-rl-caja></div></div>`;
    $("[data-ac-mapa]", v).addEventListener("click", () => cargarAcademia("rust"));
    $("[data-rl-bajar]", v).addEventListener("click", async () => {
      try { await trabajo("/api/guias/bajar_paquetes", { paquetes: ["rustlings"] }, $("[data-rl-caja]", v)); pintarRustlings(); }
      catch (e) { $("[data-rl-caja]", v).innerHTML = `<p class="error">${esc(e.message)}</p>`; }
    });
    return;
  }
  const temas = [...new Set(r.ejercicios.map((e) => e.tema))];
  const hechos = r.ejercicios.filter((e) => e.estrellas).length;
  v.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button data-ac-mapa>← Mapa</button></div>
    <div class="tarjeta lx-resumen"><div><b>${hechos}/${r.ejercicios.length}</b> ejercicios de Rustlings</div></div>
    ${temas.map((t) => `<div class="tarjeta"><h3 style="margin-top:0">${esc(t)}</h3><div class="r-misiones">${r.ejercicios.filter((e) => e.tema === t).map((e) =>
      `<button class="chico" data-rl="${e.nombre}">${esc(e.nombre)} <span class="lx-estrellas">${"★".repeat(e.estrellas)}<span class="vacia">${"★".repeat(3 - e.estrellas)}</span></span></button>`).join("")}</div></div>`).join("")}`;
  $("[data-ac-mapa]", v).addEventListener("click", () => cargarAcademia("rust"));
  $$("[data-rl]", v).forEach((b) => b.addEventListener("click", async () => {
    const e = await api(`/api/rustlings/${b.dataset.rl}`);
    abrirMisionAc(`rl_${e.nombre}`, { id: `rl_${e.nombre}`, curso: "rust", nivel: 0, nombreNivel: `Rustlings · ${e.tema}`, titulo: e.nombre,
      teoria: "Ejercicio oficial de **rustlings**. Lee los comentarios `// TODO` del código: ahí dice qué hacer. " + (e.test ? "Se califica con sus pruebas (`#[test]`)." : "Basta con que compile y corra sin errores."),
      enunciado: "Haz que el código compile" + (e.test ? " y pasen todas sus pruebas." : " y corra."), inicial: e.guardado || e.codigo, pistas: [e.pista], volver: pintarRustlings });
  }));
}

/** Mejor nota de examen de un tema, como pastilla (o nada si aún no lo hace). */
function notaAc(tema) {
  const n = AC.prog?.[tema]?.mejor_examen;
  return n == null ? "" : `<span class="nota ${notaClase(n)}">${n}/10${n >= 8 ? " ✓" : ""}</span>`;
}

/** Tarjeta del jefe final del curso: 20 preguntas de todos los niveles, se vence con 8. */
function tarjetaJefeAc(curso, c) {
  const jf = AC.prog?.[`jefe_ac_${curso}`]?.mejor_examen;
  const listos = c.niveles.filter((_, i) => (AC.prog?.[`ac_${curso}_${i}`]?.mejor_examen || 0) >= 8).length;
  return `<div class="tarjeta ac-nivel ac-jefe-final ${jf >= 8 ? "vencido" : ""}">
    <div class="ac-nivel-cab"><h3>👹 Jefe final del curso</h3><span class="sub">${listos}/${c.niveles.length} exámenes de nivel aprobados</span></div>
    <p class="sub">20 preguntas difíciles, tipo escenario, de TODOS los niveles. Necesitas 8 para vencerlo.</p>
    <div class="acciones"><button class="${jf >= 8 ? "" : "primario"}" data-ac-jefe>👹 Pelear</button>${notaAc(`jefe_ac_${curso}`)}</div></div>`;
}

/** Examen de un nivel (10 preguntas) o jefe final del curso (nivel = null: 20 preguntas de todos los niveles). */
async function examenAc(curso, nivel) {
  const c = AC.datos.cursos[curso];
  const titulos = (n) => n.misiones.map((m) => m.titulo.replace(/^(JEFE|BOSS): /i, "")).join("; ");
  const cuerpo = nivel == null
    ? { dominio: curso, tema: `jefe_ac_${curso}`, n: 20, nivel: "Avanzado",
        descripcion: `JEFE FINAL del curso ${c.nombre}: preguntas difíciles, tipo escenario y de razonamiento, que mezclen TODOS los niveles: `
          + c.niveles.map((n, i) => `Nivel ${i + 1} ${n.nombre} (${n.cap}): ${titulos(n)}`).join(" | ") }
    : { dominio: curso, tema: `ac_${curso}_${nivel}`, n: 10, nivel: ["Básico", "Intermedio", "Avanzado", "Superior"][Math.min(nivel, 3)],
        descripcion: `${c.nombre}. Nivel ${nivel + 1}: ${c.niveles[nivel].nombre} (${c.niveles[nivel].cap}). Temas: ${titulos(c.niveles[nivel])}.` };
  irExamenMundo(curso);
  const caja = $("#examenVista");
  try { const { id } = await trabajo("/api/examen/generar", cuerpo, caja); await abrirExamen(id); }
  catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
}

function irTeoriaAc(curso, nivel) {
  irTeoria(curso, `ac_${curso}_${nivel}`);  // solo los temas de este curso, no los de todos los mundos
}

function buscarMisionAc(id) {
  for (const [cid, c] of Object.entries(AC.datos.cursos)) {
    for (const [n, nivel] of c.niveles.entries()) {
      const m = nivel.misiones.find((x) => x.id === id);
      if (m) return { ...m, curso: cid, nivel: n, nombreNivel: nivel.nombre };
    }
  }
  return null;
}

const LIBRE_AC = `use std::io::{self, Read};

fn main() {
    // Laboratorio libre: escribe lo que quieras y dale ▶ Ejecutar.
    let mut entrada = String::new();
    io::stdin().read_to_string(&mut entrada).unwrap();
    println!("Hola desde Rust 🦀. Me llegaron {} bytes por stdin.", entrada.len());
}
`;

function abrirMisionAc(id, obj) {
  const curso = AC.curso;
  const m = obj || (id ? buscarMisionAc(id) : null);
  AC.mision = m ? m : { id: null, curso };
  AC.pistas = 0; AC.vioSolucion = false; AC.ultimo = null;
  const clave = `ac_borrador_${id || "libre_" + curso}`;
  const codigo = lsAc.get(clave) || AC.datos.progreso[id]?.codigo || (m ? m.inicial : LIBRE_AC);
  const e = m ? estrellasAc(m.id) : 0;
  $(`#acVista_${curso}`).innerHTML = `
    <div class="acciones" style="margin-bottom:10px"><button data-ac-mapa>← Mapa</button>
      ${m ? '<button class="primario btn-teofondo" data-ac-teofondo>📖 Teoría a fondo</button>' : ""}
      ${m ? `<span class="sub">Nivel ${m.nivel + 1} · ${esc(m.nombreNivel)} ${e ? `· tu mejor: ${"★".repeat(e)}` : ""}</span>` : ""}</div>
    <div class="ac-layout">
      <div class="ac-izq">
        ${m ? `<div class="tarjeta ${m.jefe ? "ac-jefe-tarjeta" : ""}">
            <h2 style="margin-top:0">${m.jefe ? "👑 " : ""}${esc(m.titulo)}</h2>
            <div class="explicacion ac-teoria">${md(tr(m.teoria))}</div>
            <div data-ac-teofondo-caja hidden></div>
          </div>
          <div class="tarjeta"><h3 style="margin-top:0">🎯 Misión</h3><div class="explicacion">${md(tr(m.enunciado))}</div>
            <div class="acciones"><button class="chico" data-ac-pista>💡 Pista (${m.pistas.length})</button>
              <button class="chico" data-ac-solucion>🏳️ Ver solución</button></div>
            <div data-ac-pistas></div></div>`
        : `<div class="tarjeta"><h2 style="margin-top:0">🧪 Laboratorio libre</h2>
            <p class="sub">Programa lo que quieras con el Rust de tu PC. Lo que pongas en <b>Entrada</b> le llega a tu programa por stdin.</p>
            <label>Entrada (stdin)<textarea data-ac-stdin rows="4" spellcheck="false"></textarea></label></div>`}
        <div class="tarjeta"><h3 style="margin-top:0">🤖 Mentor</h3>
          <p class="sub">Le paso tu código, el error y la misión. Te guía sin darte la respuesta completa.</p>
          <div class="fila"><input data-ac-preg placeholder="¿Qué no entiendes? (vacío = explícame mi error)"><button data-ac-mentor>Preguntar</button></div>
          <div data-ac-mentor-caja></div></div>
      </div>
      <div class="ac-der">
        <div class="tarjeta ac-editor-tarjeta">
          <div class="ac-editor-cab"><b>${curso === "torch" ? "main.py" : curso === "chisel" ? "Ejercicio.scala" : curso === "rustproj" ? "src/lib.rs" : "main.rs"}</b><span class="sub">Tab = 4 espacios · Ctrl+Enter = ${m ? "calificar" : "ejecutar"}</span></div>
          <textarea class="ac-editor" data-ac-codigo spellcheck="false" autocomplete="off">${esc(codigo)}</textarea>
          <div class="acciones">
            ${m ? '<button class="primario" data-ac-calificar>✅ Calificar</button>' : ""}
            <button ${m ? "" : 'class="primario"'} data-ac-correr>${curso === "chisel" ? "🔍 Ver Verilog generado" : "▶ Ejecutar"}</button>
            <button data-ac-reiniciar>↺ Código inicial</button>
          </div>
        </div>
        <div data-ac-salida></div>
      </div>
    </div>`;
  const v = $(`#acVista_${curso}`), ed = $("[data-ac-codigo]", v);
  $("[data-ac-mapa]", v).addEventListener("click", () => { AC.mision = null; if (m?.volver) m.volver(); else cargarAcademia(curso); });
  $("[data-ac-teofondo]", v)?.addEventListener("click", (ev) => teoriaAFondo(ev.target, $("[data-ac-teofondo-caja]", v), {
    clave: `ac:${m.id}`, mundo: curso, titulo: tr(m.titulo).replace(/^(JEFE|BOSS): /i, ""),
    contexto: `${m.nombreNivel || ""}. ${m.teoria}\n${m.enunciado}` }));
  ed.addEventListener("input", () => lsAc.set(clave, ed.value));
  ed.addEventListener("keydown", (ev) => {
    if (ev.key === "Tab") { ev.preventDefault(); const s = ed.selectionStart; ed.setRangeText("    ", s, ed.selectionEnd, "end"); lsAc.set(clave, ed.value); }
    if (ev.key === "Enter" && ev.ctrlKey) { ev.preventDefault(); (m ? calificarAc : correrAc)(); }
    if (ev.key === "Enter" && !ev.ctrlKey) {  // mantener la sangría
      const s = ed.selectionStart, linea = ed.value.slice(0, s).split("\n").pop();
      let sang = linea.match(/^\s*/)[0];
      if (/[{(\[]\s*$/.test(linea)) sang += "    ";
      ev.preventDefault(); ed.setRangeText("\n" + sang, s, ed.selectionEnd, "end"); lsAc.set(clave, ed.value);
    }
  });
  $("[data-ac-correr]", v).addEventListener("click", correrAc);
  $("[data-ac-calificar]", v)?.addEventListener("click", calificarAc);
  $("[data-ac-reiniciar]", v).addEventListener("click", () => {
    if (!confirmarAc("¿Regresar al código inicial? Se pierde lo que escribiste.")) return;
    ed.value = m ? m.inicial : LIBRE_AC; lsAc.set(clave, ed.value);
  });
  $("[data-ac-pista]", v)?.addEventListener("click", (ev) => {
    if (AC.pistas >= m.pistas.length) return aviso("Ya viste todas las pistas");
    AC.pistas++;
    $("[data-ac-pistas]", v).innerHTML = m.pistas.slice(0, AC.pistas).map((p, i) => `<div class="ac-pista">💡 ${i + 1}. ${md(tr(p))}</div>`).join("");
    ev.target.textContent = `💡 Pista (${m.pistas.length - AC.pistas} más)`;
  });
  $("[data-ac-solucion]", v)?.addEventListener("click", async () => {
    if (!confirmarAc("Si ves la solución, esta misión vale máximo 1 ★. ¿Verla?")) return;
    AC.vioSolucion = true;
    const r = await api("/api/academia/solucion", { id: m.id });
    $("[data-ac-pistas]", v).innerHTML = `<div class="ac-pista"><b>Solución de referencia</b> (escríbela tú, no la copies: así se aprende)<pre>${esc(r.solucion)}</pre></div>`;
  });
  $("[data-ac-mentor]", v).addEventListener("click", mentorAc);
  $("[data-ac-preg]", v).addEventListener("keydown", (ev) => { if (ev.key === "Enter") mentorAc(); });
}

function confirmarAc(texto) { return window.confirm(texto); }

function cajaSalidaAc() { return $(`#acVista_${AC.curso} [data-ac-salida]`); }
function codigoAc() { return $(`#acVista_${AC.curso} [data-ac-codigo]`).value; }

function pintarCompilacionAc(r) {
  if (r.fase === "compilar") return `<div class="tarjeta ac-error"><h3 style="margin-top:0">🛠️ No compila</h3>
      <p class="sub">El compilador de Rust es tu aliado: lee la primera línea <code>error[E…]</code> y la flecha <code>--></code> que dice la línea.</p>
      <pre class="ac-pre">${esc(r.fallo)}</pre></div>`;
  return `<div class="tarjeta ac-error"><h3 style="margin-top:0">⚠️ ${r.fase === "rustc" ? "Falta Rust" : "Error al correr"}</h3><pre class="ac-pre">${esc(r.fallo)}</pre></div>`;
}

async function correrAc() {
  const caja = cajaSalidaAc();
  if (AC.curso === "chisel") {
    caja.innerHTML = `<div class="trabajo"><div class="girar"></div><div>Generando Verilog con sbt (tarda ~30 s)…</div></div>`;
    try {
      const r = await api("/api/academia/verilog", { codigo: codigoAc(), modulo: AC.mision?.modulo || "" });
      AC.ultimo = r.ok ? "" : r.fallo;
      caja.innerHTML = r.ok ? `<div class="tarjeta"><h3 style="margin-top:0">🔍 Verilog que genera tu diseño</h3>
        <p class="sub">Esto es lo que entienden las herramientas de chips y FPGAs (SystemVerilog). Compáralo con tu Chisel.</p><pre class="ac-pre" data-no-tr>${esc(r.verilog)}</pre></div>`
        : `<div class="tarjeta ac-error"><h3 style="margin-top:0">🛠️ No compila</h3><pre class="ac-pre">${esc(r.fallo)}</pre></div>`;
    } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
    return;
  }
  caja.innerHTML = `<div class="trabajo"><div class="girar"></div><div>Compilando con rustc…</div></div>`;
  try {
    const r = await api("/api/academia/correr", { lenguaje: AC.curso === "torch" ? "python" : "rust", codigo: codigoAc(), entrada: $(`#acVista_${AC.curso} [data-ac-stdin]`)?.value || "" });
    AC.ultimo = r.ok ? `Salida:\n${r.stdout}\n${r.stderr}` : r.fallo;
    caja.innerHTML = r.ok ? `<div class="tarjeta"><h3 style="margin-top:0">▶ Salida ${r.codigo_salida ? `<span class="nota baja">código ${r.codigo_salida}</span>` : ""}</h3>
        <pre class="ac-pre">${esc(r.stdout || "(sin salida)")}</pre>${r.stderr ? `<pre class="ac-pre err">${esc(r.stderr)}</pre>` : ""}</div>` : pintarCompilacionAc(r);
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}

async function calificarAc() {
  const m = AC.mision, caja = cajaSalidaAc(), codigo = codigoAc();
  caja.innerHTML = `<div class="trabajo"><div class="girar"></div><div>Compilando y corriendo las pruebas ocultas…</div></div>`;
  let r;
  try { r = await api("/api/academia/calificar", { id: m.id, codigo }); } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  if (r.fase) { AC.ultimo = r.fallo; caja.innerHTML = pintarCompilacionAc(r) + reglasAc(r.reglas); return; }
  const pr = r.pruebas || [], ok = pr.filter((p) => p.ok).length;
  AC.ultimo = pr.filter((p) => !p.ok).map((p) => `Falló "${p.prueba}": ${p.detalle || ""}`).join("\n") + (r.reglas?.length ? `\nReglas: ${r.reglas.join("; ")}` : "");
  let premio = "";
  if (r.aprobado) {
    const est = AC.vioSolucion ? 1 : AC.pistas === 0 ? 3 : 2;
    try {
      const g = await api("/api/academia/resultado", { id: m.id, estrellas: est, codigo });
      AC.datos.progreso[m.id] = { estrellas: g.ahora, codigo };
      setTimeout(() => { refrescarJugador(true); if (typeof revisarMisionDia === "function") revisarMisionDia(); }, 300);
    } catch {}
    celebrar(m.jefe ? `👑 ¡Jefe vencido! ${"★".repeat(est)}` : `✅ ¡Misión cumplida! ${"★".repeat(est)}`, m.jefe ? "nivel" : "logro");
    premio = `<div class="tarjeta ac-ok"><h3 style="margin-top:0">${m.jefe ? "👑 ¡Venciste al jefe!" : "✅ ¡Misión cumplida!"} ${"★".repeat(est)}<span class="vacia">${"★".repeat(3 - est)}</span></h3>
      <p class="sub">${est === 3 ? "Sin ayuda: perfecto." : est === 2 ? "Usaste pistas: vuelve a hacerla sin ayuda para las 3 ★." : "Viste la solución: inténtala de nuevo sin verla."}</p>
      <div class="acciones"><button class="primario" data-ac-sig>Siguiente misión →</button><button data-ac-volver>← Mapa</button></div></div>`;
  }
  caja.innerHTML = premio + `<div class="tarjeta"><h3 style="margin-top:0">🧪 Pruebas: ${ok}/${pr.length}</h3>
      ${pr.map((p) => `<div class="ac-prueba ${p.ok ? "ok" : "mal"}">${p.ok ? "✓" : "✗"} ${esc(p.prueba)}${p.detalle ? `<pre class="ac-pre">${esc(p.detalle)}</pre>` : ""}</div>`).join("")}
      ${reglasAc(r.reglas)}
      ${r.avisos && /warning/.test(r.avisos) ? `<details><summary class="sub">Avisos del compilador</summary><pre class="ac-pre">${esc(r.avisos)}</pre></details>` : ""}</div>`;
  $("[data-ac-sig]", caja)?.addEventListener("click", () => siguienteAc(m));
  $("[data-ac-volver]", caja)?.addEventListener("click", () => { AC.mision = null; if (m.volver) m.volver(); else cargarAcademia(AC.curso); });
}

function reglasAc(reglas) {
  return reglas?.length ? `<div class="ac-reglas">${reglas.map((x) => `<div class="ac-prueba mal">✗ ${md(x)}</div>`).join("")}</div>` : "";
}

function siguienteAc(m) {
  if (m.volver) return m.volver();
  if (String(m.id).startsWith("g")) { AC.mision = null; return cargarAcademia(m.curso); }
  const lista = AC.datos.cursos[m.curso].niveles.flatMap((n) => n.misiones);
  const i = lista.findIndex((x) => x.id === m.id);
  const sig = lista.slice(i + 1).find((x) => !estrellasAc(x.id)) || lista[i + 1];
  if (sig) abrirMisionAc(sig.id); else { AC.mision = null; cargarAcademia(m.curso); celebrar("🏆 ¡Terminaste el curso!", "nivel"); }
}

async function mentorAc() {
  const v = $(`#acVista_${AC.curso}`), m = AC.mision, caja = $("[data-ac-mentor-caja]", v);
  const preg = $("[data-ac-preg]", v).value.trim() || "Explícame qué está mal en mi código y cómo lo arreglo, sin darme la solución completa.";
  const contexto = `${m.id ? `Misión: ${m.titulo}\n${m.enunciado}` : "Laboratorio libre de Rust"}\n\nCódigo del alumno:\n\`\`\`rust\n${codigoAc().slice(0, 6000)}\n\`\`\`\n\n`
    + (AC.ultimo ? `Último resultado / error:\n${String(AC.ultimo).slice(0, 2500)}` : "Aún no lo ha compilado.");
  const cursoN = AC.datos.cursos[AC.curso].nombre;
  try {
    const r = await trabajo("/api/tutor", { area: AC.curso === "rust" ? "Rust" : AC.curso === "chisel" ? "Chisel (Scala) y diseño digital" : AC.curso === "torch" ? "PyTorch y deep learning (Python)" : `${cursoN} (programando en Rust)`, contexto, pregunta: preg, codigo: true }, caja);
    caja.innerHTML = `<div class="respuesta-tutor">${md(r.respuesta)}</div><div class="sub">Mentor: ${esc(r.modelo || "")}</div>`;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}
