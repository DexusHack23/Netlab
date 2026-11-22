"use strict";
// ======================================================================
// NetLab — 🗺️ Ruta ofensiva (índice). NO genera ni enseña a ejecutar ataques: ordena las salas LEGALES de
// TryHackMe / Hack The Box y los labs oficiales que levantas en tu propia VM, guarda tu avance y tus notas,
// y a cada tema le pega la "Teoría a fondo" (por qué funciona + con qué se detecta) y una práctica de DEFENSA en NetLab.
// ======================================================================
const THM = (slug) => `https://tryhackme.com/room/${slug}`;
const HTB_SP = "https://app.hackthebox.com/starting-point";
const HTB_M = (n) => `https://app.hackthebox.com/machines/${n}`;

const INDICE = [
  { id: "fundamentos", icono: "🧭", nombre: "Fundamentos y metodología",
    porque: "Antes de tocar herramientas: qué es una prueba de penetración, las fases (reconocimiento, enumeración, explotación, post-explotación, reporte) y las reglas del juego (alcance y permiso por escrito).",
    detecta: "Cada fase deja rastro distinto: escaneos en el IDS, intentos de login en los logs, procesos raros en el EDR. Un buen analista piensa en la Kill Chain para saber en qué fase va el atacante.",
    practica: [["🚨 Triage en el SOC", () => ir("soc")]],
    items: [
      { id: "thm_presecurity", pl: "THM", nombre: "Pre Security (ruta)", url: "https://tryhackme.com/path/outline/presecurity", nivel: "Básico", que: "Redes, web, Linux y Windows desde cero: la base de todo lo demás." },
      { id: "thm_jrpentester", pl: "THM", nombre: "Jr Penetration Tester (ruta)", url: "https://tryhackme.com/path/outline/jrpenetrationtester", nivel: "Intermedio", que: "La ruta completa de pentester junior; muchas salas de este índice están dentro de ella." },
      { id: "htb_startingpoint", pl: "HTB", nombre: "Starting Point (tiers 0, 1 y 2)", url: HTB_SP, nivel: "Básico", que: "Las máquinas guiadas de HTB, con preguntas paso a paso. Hay gratis y VIP en cada tier." },
    ] },
  { id: "recon", icono: "🔭", nombre: "Reconocimiento y escaneo (Nmap)",
    porque: "Descubrir qué equipos están vivos y qué puertos/servicios tienen abiertos. Funciona porque cada protocolo contesta distinto (SYN/ACK = abierto, RST = cerrado, nada = filtrado).",
    detecta: "Muchos SYN a puertos distintos desde una IP, conexiones a medias (SYN sin ACK final), TTL raros. Filtros de Wireshark, alertas del IDS (Snort/Suricata) y logs del firewall.",
    practica: [["🦈 Red vs Blue · Wireshark (escaneos)", () => { RB.modo = "wireshark"; ir("rvb"); }], ["🦈 Captura de escaneo", () => ir("wireshark")]],
    items: [
      { id: "thm_nmap", pl: "THM", nombre: "Nmap: The Basics", url: THM("nmap"), nivel: "Básico", que: "Descubrir hosts, escanear puertos y detectar versiones." },
      { id: "thm_nmap01", pl: "THM", nombre: "Nmap Live Host Discovery", url: THM("nmap01"), nivel: "Básico", que: "ARP, ICMP y pings TCP/UDP para saber quién está vivo." },
      { id: "thm_nmap02", pl: "THM", nombre: "Nmap Basic Port Scans", url: THM("nmap02"), nivel: "Básico", que: "Connect, SYN y UDP scan: qué paquete manda cada uno." },
      { id: "thm_nmap03", pl: "THM", nombre: "Nmap Advanced Port Scans", url: THM("nmap03"), nivel: "Intermedio", que: "Escaneos NULL/FIN/Xmas, fragmentación y señuelos (y por qué los ve el IDS)." },
      { id: "thm_nmap04", pl: "THM", nombre: "Nmap Post Port Scans", url: THM("nmap04"), nivel: "Intermedio", que: "Detección de versión y SO, scripts NSE y guardar resultados." },
    ] },
  { id: "servicios", icono: "🔌", nombre: "Servicios de red expuestos",
    porque: "Servicios mal configurados (Telnet, FTP anónimo, SMB sin contraseña, Redis abierto) dejan entrar sin explotar nada: el error es de configuración, no de código.",
    detecta: "Inicios de sesión anónimos o sin contraseña en los logs del servicio, protocolos en texto claro en la red, puertos que no deberían estar expuestos en un escaneo propio.",
    practica: [["🌐 Red vs Blue · CCNA (Telnet, SNMP, CDP)", () => { RB.modo = "ccna"; ir("rvb"); }], ["🦈 Credenciales en texto claro (FTP)", () => ir("wireshark")]],
    items: [
      { id: "thm_networkservices", pl: "THM", nombre: "Network Services", url: THM("networkservices"), nivel: "Básico", que: "SMB, Telnet y FTP: enumerar y entender por qué son riesgosos." },
      { id: "htb_meow", pl: "HTB", nombre: "Meow (Starting Point 0)", url: HTB_SP, nivel: "Básico", que: "Telnet con una cuenta sin contraseña." },
      { id: "htb_fawn", pl: "HTB", nombre: "Fawn (Starting Point 0)", url: HTB_SP, nivel: "Básico", que: "FTP con acceso anónimo." },
      { id: "htb_dancing", pl: "HTB", nombre: "Dancing (Starting Point 0)", url: HTB_SP, nivel: "Básico", que: "Recursos SMB compartidos sin protección." },
      { id: "htb_redeemer", pl: "HTB", nombre: "Redeemer (Starting Point 0)", url: HTB_SP, nivel: "Básico", que: "Base de datos Redis expuesta sin autenticación." },
    ] },
  { id: "passwords", icono: "🔑", nombre: "Contraseñas y fuerza bruta",
    porque: "Las contraseñas débiles o repetidas caen con listas de palabras. En línea (contra el servicio) es ruidoso; fuera de línea (contra un hash robado) no deja rastro en el servidor.",
    detecta: "Ráfagas de 4625/4771 en Windows, 'Failed password' en auth.log, muchos POST al login con la misma respuesta, password spraying (un intento por cuenta). Se mitiga con MFA, bloqueo y contraseñas largas.",
    practica: [["🐧 Red vs Blue · Linux (fuerza bruta SSH)", () => { RB.modo = "linux"; ir("rvb"); }], ["🕸️ Red vs Blue · Web", () => { RB.modo = "web"; ir("rvb"); }], ["🏢 Red vs Blue · AD (spraying)", () => { RB.modo = "ad"; ir("rvb"); }]],
    items: [
      { id: "thm_hydra", pl: "THM", nombre: "Hydra", url: THM("hydra"), nivel: "Básico", que: "Ataques de contraseña en línea contra SSH y formularios web." },
      { id: "thm_passwordattacks", pl: "THM", nombre: "Password Attacks", url: THM("passwordattacks"), nivel: "Avanzado", que: "Listas de palabras a la medida, ataques en línea y password spraying." },
      { id: "thm_passwordcracking", pl: "THM", nombre: "Password Cracking", url: THM("passwordcracking"), nivel: "Intermedio", que: "Cómo se guardan las contraseñas, identificar hashes y crackearlos." },
      { id: "thm_bruteit", pl: "THM", nombre: "Brute It", url: THM("bruteit"), nivel: "Básico", que: "Reto corto de fuerza bruta, cracking de hashes y escalada." },
    ] },
  { id: "web", icono: "🕸️", nombre: "Aplicaciones web (OWASP Top 10:2025)",
    porque: "La app confía en lo que manda el usuario: si mezcla esa entrada con SQL, HTML, rutas de archivos o comandos, el atacante cambia lo que la app hace.",
    detecta: "En el access.log: comillas y UNION en parámetros, <script> codificado, ../ en rutas, ; o | en parámetros, cientos de 404 (fuzzing), .php en carpetas de subidas. Un WAF y el código bien hecho (consultas parametrizadas, codificar la salida, listas blancas) lo frenan.",
    practica: [["🕸️ Red vs Blue · Web", () => { RB.modo = "web"; ir("rvb"); }]],
    items: [
      { id: "thm_owasptop10", pl: "THM", nombre: "OWASP Top 10 - 2021", url: THM("owasptop102021"), nivel: "Básico", que: "Los 10 riesgos web, con un reto por cada uno. La sala es de 2021; la teoría de NetLab ya usa el Top 10:2025 (nuevos: cadena de suministro y manejo de condiciones excepcionales; SSRF pasó a control de acceso roto)." },
      { id: "thm_burp", pl: "THM", nombre: "Burp Suite: The Basics", url: THM("burpsuitebasics"), nivel: "Básico", que: "El proxy para ver y modificar las peticiones HTTP." },
      { id: "thm_contentdiscovery", pl: "THM", nombre: "Content Discovery", url: THM("contentdiscovery"), nivel: "Básico", que: "Encontrar rutas y archivos ocultos (lo que en los logs se ve como cientos de 404)." },
      { id: "thm_authbypass", pl: "THM", nombre: "Authentication Bypass", url: THM("authenticationbypass"), nivel: "Básico", que: "Lógica de login rota, enumeración de usuarios y cookies manipuladas." },
      { id: "thm_sqli", pl: "THM", nombre: "SQL Injection", url: THM("sqlinjectionlm"), nivel: "Intermedio", que: "Cómo una comilla rompe la consulta y cómo se lee otra tabla." },
      { id: "thm_xss", pl: "THM", nombre: "XSS", url: THM("axss"), nivel: "Básico", que: "Reflejado, almacenado y DOM: por qué el navegador ejecuta el script." },
      { id: "thm_fileinc", pl: "THM", nombre: "File Inclusion", url: THM("fileinc"), nivel: "Intermedio", que: "Path traversal, LFI y RFI." },
      { id: "thm_cmdi", pl: "THM", nombre: "Command Injection", url: THM("oscommandinjection"), nivel: "Básico", que: "Cuando la app pasa tu entrada a la shell." },
      { id: "thm_juiceshop", pl: "THM", nombre: "OWASP Juice Shop", url: THM("owaspjuiceshop"), nivel: "Básico", que: "La misma app que puedes levantar en tu VM (ver Labs locales)." },
      { id: "htb_appointment", pl: "HTB", nombre: "Appointment (Starting Point 1)", url: HTB_SP, nivel: "Básico", que: "Inyección SQL en un login." },
      { id: "htb_crocodile", pl: "HTB", nombre: "Crocodile (Starting Point 1)", url: HTB_SP, nivel: "Básico", que: "FTP anónimo que filtra credenciales de un panel web." },
    ] },
  { id: "api", icono: "🔗", nombre: "APIs (OWASP API Security Top 10)",
    porque: "Las APIs exponen objetos y funciones directamente: si el servidor no revisa que ESE usuario pueda ver ESE objeto (BOLA) o llamar ESA función, basta cambiar un id o un método en la petición. También fallan por aceptar campos de más (asignación masiva), no limitar el consumo y confiar en otras APIs.",
    detecta: "En los logs de la API: un mismo token pidiendo muchos ids distintos y seguidos (/api/orders/1001, 1002…), respuestas 200 a recursos de otro usuario, PUT/DELETE desde cuentas sin rol, ráfagas que rompen el límite de peticiones, endpoints viejos (/v1) aún en uso. Se mitiga revisando autorización por objeto y función, listas blancas de campos, rate limiting e inventario de APIs.",
    practica: [["🧪 Tu laboratorio (Juice Shop tiene API REST)", () => { IDX.abierto = "labs"; pintarIndice().then(() => $('[data-idx-tema="labs"]')?.scrollIntoView({ behavior: "smooth" })); }], ["🛰️ SIEM (buscarte en los logs)", () => ir("siem")]],
    items: [
      { id: "lab_crapi", pl: "LAB", nombre: "OWASP crAPI (completely ridiculous API)", url: "https://github.com/OWASP/crAPI", nivel: "Intermedio", que: "API vulnerable a propósito de OWASP para los 10 riesgos de API. Son varios microservicios (pesado): NetLab no lo instala solo; su README explica cómo correrlo con Docker." },
      { id: "lab_juiceshop_api", pl: "LAB", nombre: "Juice Shop: retos de su API REST", url: "http://127.0.0.1:4300/", nivel: "Básico", que: "Tu Juice Shop local (levántalo en Labs locales): varios retos son de autorización rota en su API (/api y /rest)." },
    ] },
  { id: "privesc_linux", icono: "🐧", nombre: "Escalada de privilegios en Linux",
    porque: "Una vez adentro como usuario normal, el atacante busca errores de configuración: binarios SUID, sudo mal dado, cron que corre scripts editables, kernel viejo, contraseñas en archivos.",
    detecta: "Binarios SUID nuevos (find / -perm -4000), cambios en /etc/crontab y /etc/sudoers, procesos de root lanzados por un usuario web, /etc/ld.so.preload. auditd y los logs de sudo ayudan.",
    practica: [["🐧 Red vs Blue · Linux (SUID, cron, LD_PRELOAD)", () => { RB.modo = "linux"; ir("rvb"); }], ["🐧 Misiones de Linux", () => ir("linux")]],
    items: [
      { id: "thm_linprivesc", pl: "THM", nombre: "Linux Privilege Escalation", url: THM("linprivesc"), nivel: "Intermedio", que: "Más de 8 vectores de escalada explicados uno por uno." },
      { id: "thm_linuxprivesc", pl: "THM", nombre: "Linux PrivEsc", url: THM("linuxprivesc"), nivel: "Intermedio", que: "Una VM Debian vulnerable a propósito para practicar cada técnica." },
      { id: "thm_commonlinuxprivesc", pl: "THM", nombre: "Common Linux Privesc", url: THM("commonlinuxprivesc"), nivel: "Intermedio", que: "Los errores más comunes: /etc/passwd editable, cron, PATH." },
    ] },
  { id: "privesc_win", icono: "🪟", nombre: "Escalada de privilegios en Windows",
    porque: "Servicios con permisos débiles, rutas sin comillas, credenciales guardadas, tokens con privilegios peligrosos (SeImpersonate)… cualquier cosa que deje a un usuario normal actuar como SYSTEM.",
    detecta: "Servicios nuevos o modificados (7045), procesos de SYSTEM con padre raro (4688/Sysmon 1), acceso a la memoria de LSASS (Sysmon 10), tareas programadas nuevas (4698).",
    practica: [["🚨 SOC · caso de Windows / Sysmon", () => { ir("soc"); }]],
    items: [
      { id: "thm_windowsprivesc", pl: "THM", nombre: "Windows Privilege Escalation", url: THM("windowsprivesc20"), nivel: "Intermedio", que: "Los vectores clásicos de escalada en Windows." },
    ] },
  { id: "ad", icono: "🏢", nombre: "Active Directory",
    porque: "AD centraliza identidades: con UNA cuenta del dominio ya puedes pedir tickets de Kerberos, enumerar usuarios y buscar cuentas débiles; con un admin, el dominio entero cae.",
    detecta: "4769 con cifrado 0x17 (Kerberoasting), 4768 con PreAuthType 0 (AS-REP), 4771 en muchas cuentas (spraying), 4624 NTLM tipo 3 entre servidores (Pass-the-Hash), 4662 con GUID de replicación (DCSync), 7045 PSEXESVC, 4728 a Domain Admins.",
    practica: [["🏢 Red vs Blue · Windows / AD", () => { RB.modo = "ad"; ir("rvb"); }]],
    items: [
      { id: "thm_winadbasics", pl: "THM", nombre: "Active Directory Basics", url: THM("winadbasics"), nivel: "Básico", que: "Dominios, OUs, GPOs, Kerberos y NTLM: cómo funciona AD." },
      { id: "thm_breachingad", pl: "THM", nombre: "Breaching Active Directory", url: THM("breachingad"), nivel: "Intermedio", que: "Cómo se consigue la primera cuenta del dominio." },
      { id: "thm_attacktive", pl: "THM", nombre: "Attacktive Directory", url: THM("attacktivedirectory"), nivel: "Intermedio", que: "Cadena completa contra un controlador de dominio vulnerable." },
      { id: "htb_forest", pl: "HTB", nombre: "Forest (retirada)", url: HTB_M("Forest"), nivel: "Intermedio", que: "AS-REP roasting y permisos de AD. Las retiradas suelen pedir VIP." },
      { id: "htb_active", pl: "HTB", nombre: "Active (retirada)", url: HTB_M("Active"), nivel: "Intermedio", que: "GPP en SYSVOL y Kerberoasting." },
      { id: "htb_sauna", pl: "HTB", nombre: "Sauna (retirada)", url: HTB_M("Sauna"), nivel: "Intermedio", que: "Usuarios desde una web, AS-REP y DCSync." },
    ] },
  { id: "cajas", icono: "🧩", nombre: "Máquinas completas (juntar todo)",
    porque: "Aquí se encadena todo: escaneo → servicio → acceso inicial → escalada. Es lo más parecido a un examen tipo OSCP/eJPT.",
    detecta: "Cada máquina es una cadena de técnicas: al terminarla, escribe en tus notas qué rastro dejó CADA paso y con qué Event ID, log o filtro lo habrías visto.",
    practica: [["⚔️ Red vs Blue (todos los modos)", () => ir("rvb")]],
    items: [
      { id: "thm_vulnversity", pl: "THM", nombre: "Vulnversity", url: THM("vulnversity"), nivel: "Básico", que: "Escaneo, subida de archivos y SUID." },
      { id: "thm_blue", pl: "THM", nombre: "Blue", url: THM("blue"), nivel: "Básico", que: "Windows sin parchear (MS17-010)." },
      { id: "thm_kenobi", pl: "THM", nombre: "Kenobi", url: THM("kenobi"), nivel: "Básico", que: "Samba, ProFTPD y una escalada por PATH." },
      { id: "thm_basicpentesting", pl: "THM", nombre: "Basic Pentesting", url: THM("basicpentestingjt"), nivel: "Básico", que: "Enumeración, fuerza bruta y llaves SSH." },
      { id: "thm_picklerick", pl: "THM", nombre: "Pickle Rick", url: THM("picklerick"), nivel: "Básico", que: "Reto web corto y divertido." },
      { id: "thm_rootme", pl: "THM", nombre: "RootMe", url: THM("rrootme"), nivel: "Básico", que: "Subida de archivos y SUID." },
      { id: "thm_simplectf", pl: "THM", nombre: "Simple CTF", url: THM("easyctf"), nivel: "Básico", que: "CMS vulnerable y sudo mal configurado." },
      { id: "thm_agentsudo", pl: "THM", nombre: "Agent Sudo", url: THM("agentsudoctf"), nivel: "Básico", que: "Enumeración, esteganografía y sudo." },
      { id: "thm_bountyhacker", pl: "THM", nombre: "Bounty Hacker", url: THM("cowboyhacker"), nivel: "Básico", que: "FTP, fuerza bruta y sudo." },
      { id: "thm_mrrobot", pl: "THM", nombre: "Mr Robot CTF", url: THM("mrrobot"), nivel: "Intermedio", que: "WordPress y escalada; un clásico." },
      { id: "thm_h4cked", pl: "THM", nombre: "h4cked (Purple)", url: THM("h4cked"), nivel: "Básico", que: "Primero analizas el .pcap del ataque como SOC y luego recuperas la máquina." },
      { id: "htb_sequel", pl: "HTB", nombre: "Sequel (Starting Point 1)", url: HTB_SP, nivel: "Básico", que: "MySQL expuesto." },
      { id: "htb_responder", pl: "HTB", nombre: "Responder (Starting Point 1)", url: HTB_SP, nivel: "Básico", que: "LFI y captura de hash NTLM." },
      { id: "htb_three", pl: "HTB", nombre: "Three (Starting Point 1)", url: HTB_SP, nivel: "Básico", que: "Bucket S3 mal configurado." },
      { id: "htb_archetype", pl: "HTB", nombre: "Archetype (Starting Point 2)", url: HTB_SP, nivel: "Básico", que: "MSSQL y escalada en Windows." },
      { id: "htb_oopsie", pl: "HTB", nombre: "Oopsie (Starting Point 2)", url: HTB_SP, nivel: "Básico", que: "Control de acceso roto (IDOR) y subida de archivos." },
      { id: "htb_vaccine", pl: "HTB", nombre: "Vaccine (Starting Point 2)", url: HTB_SP, nivel: "Básico", que: "Cracking de un zip, SQLi y sudo." },
      { id: "htb_unified", pl: "HTB", nombre: "Unified (Starting Point 2)", url: HTB_SP, nivel: "Básico", que: "Log4Shell en UniFi." },
      { id: "htb_lame", pl: "HTB", nombre: "Lame (retirada)", url: HTB_M("Lame"), nivel: "Básico", que: "Samba viejo: la primera máquina de HTB." },
      { id: "htb_legacy", pl: "HTB", nombre: "Legacy (retirada)", url: HTB_M("Legacy"), nivel: "Básico", que: "Windows XP con SMB vulnerable." },
      { id: "htb_jerry", pl: "HTB", nombre: "Jerry (retirada)", url: HTB_M("Jerry"), nivel: "Básico", que: "Tomcat con credenciales por defecto." },
      { id: "htb_netmon", pl: "HTB", nombre: "Netmon (retirada)", url: HTB_M("Netmon"), nivel: "Básico", que: "FTP anónimo y PRTG." },
      { id: "htb_cap", pl: "HTB", nombre: "Cap (retirada)", url: HTB_M("Cap"), nivel: "Básico", que: "IDOR que entrega un .pcap con credenciales y capabilities de Linux." },
    ] },
  { id: "labs", icono: "🧪", nombre: "Labs locales en tu Ubuntu de VirtualBox",
    porque: "Apps vulnerables A PROPÓSITO, oficiales, que corres tú en tu VM para practicar sin internet de por medio. Ideal para luego mirar sus logs desde el lado del defensor.",
    detecta: "Truco purple: ataca tu Juice Shop o DVWA siguiendo la sala de THM y luego revisa el access.log del contenedor (docker logs) o llévalo al SIEM de NetLab (carpeta siem_importar) para cazarte a ti mismo.",
    practica: [["🛰️ SIEM (importar tus logs)", () => ir("siem")], ["🕸️ Red vs Blue · Web", () => { RB.modo = "web"; ir("rvb"); }]],
    guia: true,
    items: [
      { id: "lab_dvwa", pl: "LAB", nombre: "DVWA (Damn Vulnerable Web Application)", url: "https://github.com/digininja/DVWA", nivel: "Básico", que: "SQLi, XSS, LFI, comandos y más, con niveles de seguridad bajo/medio/alto/imposible para comparar el código." },
      { id: "lab_juiceshop", pl: "LAB", nombre: "OWASP Juice Shop", url: "https://github.com/juice-shop/juice-shop", nivel: "Básico", que: "Tienda moderna (Node/Angular) con más de 100 retos del OWASP Top 10." },
      { id: "lab_vulhub", pl: "LAB", nombre: "Vulhub", url: "https://github.com/vulhub/vulhub", nivel: "Intermedio", que: "Cientos de entornos con CVEs reales (Log4Shell, Spring, Struts…), uno por carpeta, cada uno con su README." },
    ] },
];

// 🐳 Panel del laboratorio local: DVWA + Juice Shop YA instalados en la VM (POST /api/vm/lab, acciones fijas).
function panelLabHtml() {
  return `<div class="idx-lab" id="idxLab">
    <div><b>🐳 Tu laboratorio (DVWA + Juice Shop), ya instalado en tu VM</b></div>
    <p class="sub">Corre dentro de tu Ubuntu de VirtualBox, aislado: solo tu Windows lo alcanza. Levántalo, haz la sala de THM contra él y luego manda sus logs al SIEM para cazarte desde el lado defensivo.</p>
    <div class="acciones"><button class="primario" data-lab="levantar">▶️ Levantar</button><button data-lab="estado">🔎 Estado</button>
      <button data-lab="logs">📥 Logs al SIEM</button><button data-lab="analizar">🧠 Analizar con IA</button>
      <button data-lab="apagar">⏹️ Apagar (borra sus datos)</button></div>
    <div class="acciones"><button data-lab-abrir="http://127.0.0.1:4280/">🧪 Abrir DVWA ↗</button><button data-lab-abrir="http://127.0.0.1:4300/">🧃 Abrir Juice Shop ↗</button>
      <button data-lab-abrir="http://127.0.0.1:4290/WebGoat">🐐 Abrir WebGoat ↗</button><button data-lab-siem>🛰️ Ir al SIEM</button></div>
    <div class="sub">DVWA: usuario <code data-no-tr>admin</code>, contraseña <code data-no-tr>password</code>; la primera vez entra a <i>Setup</i> y dale <i>Create / Reset Database</i>.</div>
    <div id="idxLabProg"></div><pre class="idx-lab-salida" id="idxLabSalida" data-no-tr hidden></pre>
    <div class="idx-lab-analisis" id="idxLabAnalisis" hidden></div>
    <div class="idx-reto">
      <div><b>🟣 Reto morado: tú atacas, la IA defiende y te califica</b></div>
      <p class="sub">Elige la arena, atácala TÚ desde tu sala de THM/HTB o a mano (es tu app, es legal), y escribe cómo lo detectarías y mitigarías. La IA hace de equipo azul: lee los logs, verifica qué se ve y pone nota a tu defensa con base en OWASP. No ataca nada: solo defiende y evalúa.</p>
      <div class="acciones">
        <label class="sub" for="idxRetoArena">Arena:</label>
        <select id="idxRetoArena" data-no-tr><option value="dvwa">DVWA</option><option value="juice">Juice Shop</option><option value="webgoat">WebGoat</option></select>
      </div>
      <textarea id="idxRetoResp" rows="4" placeholder="¿Cómo detectarías y mitigarías lo que acabas de hacer? (reglas de SIEM, qué buscar en logs, cómo corregir el código/config). Puedes dejarlo vacío y la IA solo evalúa la detectabilidad de la sesión."></textarea>
      <div class="acciones"><button class="primario" data-lab-calificar>🟣 Calificar mi defensa</button></div>
      <div class="idx-lab-analisis" id="idxRetoSalida" hidden></div>
    </div>
    <div class="idx-reto">
      <div><b>🤖 La IA ataca (simulación): tú defiendes</b></div>
      <p class="sub">El otro sentido del reto morado. Eliges un CVE real del banco y la IA hace de equipo rojo <b>en simulación</b>: reconstruye el ataque a nivel conceptual y te genera los <b>logs sintéticos</b> que dejaría, para que TÚ lo caces. La IA no ejecuta exploits de verdad: es un ejercicio de detección. Varios de estos CVE también los puedes levantar de verdad en Vulhub.</p>
      <div class="acciones">
        <label class="sub" for="idxSimCve">CVE:</label>
        <select id="idxSimCve" data-no-tr><option value="log4shell">Log4Shell — CVE-2021-44228 (Log4j)</option><option value="spring4shell">Spring4Shell — CVE-2022-22965 (Spring)</option><option value="struts2_045">Struts2 S2-045 — CVE-2017-5638</option><option value="shellshock">Shellshock — CVE-2014-6271 (Bash/CGI)</option><option value="drupalgeddon2">Drupalgeddon2 — CVE-2018-7600 (Drupal)</option><option value="confluence_26134">Confluence OGNL — CVE-2022-26134</option><option value="gitlab_22205">GitLab ExifTool — CVE-2021-22205</option><option value="weblogic_10271">WebLogic WLS-WSAT — CVE-2017-10271</option></select>
        <button class="primario" data-lab-simular>🤖 Generar ataque</button>
      </div>
      <div class="idx-lab-analisis" id="idxSimSalida" hidden></div>
      <textarea id="idxCazaResp" rows="4" placeholder="¿Qué ataque ves en esos logs? ¿Qué CVE/categoría OWASP es, cómo lo detectarías (reglas de SIEM) y cómo lo mitigarías? Luego pulsa «Calificar mi caza»."></textarea>
      <div class="acciones"><button data-lab-caza>🔵 Calificar mi caza</button></div>
      <div class="idx-lab-analisis" id="idxCazaSalida" hidden></div>
    </div>
    <details class="idx-guia"><summary><b>➕ Más arenas: Vulhub (CVEs reales) y ampliar la VM</b></summary>
      <p class="sub">Vulhub trae decenas de entornos de CVEs reales (Log4Shell, Spring4Shell, Struts…). NetLab solo clona el repo oficial en tu VM; cada CVE lo levantas a mano desde la terminal porque cada uno usa sus propios puertos (lee el README de su carpeta).</p>
      <div class="acciones"><button data-lab-vulhub>📦 Clonar Vulhub en la VM</button></div>
      <pre class="idx-lab-salida" id="idxVulhubSalida" data-no-tr hidden></pre>
      <div class="sub">Ejemplos (dentro de la terminal de la VM, carpeta <code data-no-tr>~/vulhub</code>): <code data-no-tr>cd ~/vulhub/log4j/CVE-2021-44228 &amp;&amp; docker compose up -d</code> · al terminar <code data-no-tr>docker compose down -v</code>. Siempre <code data-no-tr>cat README.md</code> para ver el puerto y los pasos.</div>
      <hr>
      <p class="sub">Si quieres más músculo para correr varias arenas a la vez, puedes dejar la VM permanentemente en 16 GB de RAM y 6 núcleos. La apaga, la amplía y rehornea la base 'limpio' (tarda un poco).</p>
      <div class="acciones"><button data-lab-recursos>🧠 Ampliar la VM a 16 GB / 6 núcleos</button></div>
    </details>
    <details class="idx-guia"><summary><b>🤖 Claude Code con tu modelo local (0 tokens de Anthropic)</b></summary>
      <p class="sub">Dentro de la VM tienes Claude Code conectado a tu Qwen3-Coder de Ollama: todo corre en tu PC, no gasta tokens. Te ayuda a levantar, revisar configuraciones y leer logs del laboratorio (sus reglas están en <code data-no-tr>~/lab/CLAUDE.md</code>). No ve tus libros: para teoría usa NetLab.</p>
      <ol><li>Abre la terminal de la VM: <b>Linux → Ubuntu real</b> (botón de terminal).</li>
        <li>Escribe <code data-no-tr>~/lab/claude-lab.sh</code></li>
        <li>Al terminar, <b>⏹️ Apagar</b> aquí para no dejar basura.</li></ol></details>
  </div>`;
}

function pintarAnalisisLab(r) {
  const caja = $("#idxLabAnalisis");
  const li = (xs) => (xs || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const sev = { alta: "🔴", high: "🔴", media: "🟠", medium: "🟠", baja: "🟢", low: "🟢" };
  const etiq = (txt, cod) => cod ? `${txt}: <span data-no-tr>${esc(cod)}</span>` : "";
  const hallazgo = (h) => {
    const meta = [etiq("OWASP", h.owasp), etiq("ATT&CK", h.attack), etiq("WSTG", h.wstg)].filter(Boolean).join(" · ");
    const pasos = (h.pasos || []).map((p, i) => `<li><code data-no-tr>${esc(p.peticion)}</code><div>${esc(p.porque)}</div></li>`).join("");
    return `<details class="idx-lab-hallazgo" open><summary><b>${sev[String(h.severidad || "").toLowerCase()] || "⚪"} ${esc(h.que)}</b></summary>
      <div class="sub">${meta}</div>
      ${h.como_funciona ? `<div><b>⚙️ Cómo funciona</b><p>${esc(h.como_funciona)}</p></div>` : ""}
      ${h.evidencia ? `<div><b>📄 Evidencia en tu log</b><code data-no-tr>${esc(h.evidencia)}</code></div>` : ""}
      ${pasos ? `<div><b>🧭 Paso a paso (lo que pasó en tu laboratorio)</b><ol class="idx-lab-pasos">${pasos}</ol></div>` : ""}
      ${h.deteccion?.length ? `<div><b>🔍 Cómo detectarlo</b><ul>${li(h.deteccion)}</ul></div>` : ""}
      ${h.mitigacion?.length ? `<div><b>🛡️ Cómo mitigarlo</b><ul>${li(h.mitigacion)}</ul></div>` : ""}</details>`;
  };
  caja.innerHTML = `<div><b>🧠 Análisis de tus logs</b> <span class="sub">· ${r.lineas} líneas · <span data-no-tr>${esc(r.modelo || "")}</span></span></div>
    <p>${esc(r.resumen || "")}</p>
    ${(r.hallazgos || []).length ? r.hallazgos.map(hallazgo).join("") : `<p class="sub">No se vio actividad sospechosa en estos logs.</p>`}
    ${r.fuentes?.length ? `<div class="sub">📚 Fuentes de tu bibliografía: <span data-no-tr>${r.fuentes.map(esc).join(" · ")}</span></div>` : ""}`;
  caja.hidden = false;
}

function pintarSimLab(r) {
  const caja = $("#idxSimSalida");
  const li = (xs) => (xs || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const fase = (f) => `<li><b>${esc(f.fase)}</b><div>${esc(f.que_ocurre)}</div><div class="sub">🐾 ${tr("Huella")}: ${esc(f.huella)}</div></li>`;
  const meta = [r.owasp && `OWASP: <span data-no-tr>${esc(r.owasp)}</span>`, r.cwe && `<span data-no-tr>${esc(r.cwe)}</span>`,
    r.attack && `ATT&CK: <span data-no-tr>${esc(r.attack)}</span>`].filter(Boolean).join(" · ");
  const logs = (r.logs_sinteticos || []).map(esc).join("\n");
  caja.innerHTML = `<div><b>🤖 ${esc(r.nombre || "")}</b> <span class="sub">· <span data-no-tr>${esc(r.cve || "")}</span> · <span data-no-tr>${esc(r.producto || "")}</span> · <span data-no-tr>${esc(r.modelo || "")}</span></span></div>
    <div class="sub">${meta}</div>
    <p>${esc(r.escenario || "")}</p>
    ${(r.fases || []).length ? `<div><b>🧭 ${tr("Fases del ataque (conceptual)")}</b><ol class="idx-lab-pasos">${r.fases.map(fase).join("")}</ol></div>` : ""}
    ${logs ? `<div><b>📄 ${tr("Logs sintéticos para cazar")}</b><pre class="idx-lab-salida" data-no-tr>${logs}</pre></div>` : ""}
    ${(r.pistas_deteccion || []).length ? `<div><b>🔍 ${tr("Pistas de detección")}</b><ul>${li(r.pistas_deteccion)}</ul></div>` : ""}
    ${(r.mitigacion || []).length ? `<div><b>🛡️ ${tr("Mitigación")}</b><ul>${li(r.mitigacion)}</ul></div>` : ""}
    ${r.vulhub ? `<div class="sub">📦 ${tr("Para hacerlo de verdad en la VM")}: <code data-no-tr>cd ~/vulhub/${esc(r.vulhub)} && docker compose up -d</code></div>` : ""}
    ${r.fuentes?.length ? `<div class="sub">📚 ${tr("Fuentes de tu bibliografía")}: <span data-no-tr>${r.fuentes.map(esc).join(" · ")}</span></div>` : ""}`;
  caja.hidden = false;
}

function pintarRetoLab(r, sel) {
  const caja = $(sel || "#idxRetoSalida");
  const li = (xs) => (xs || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const sev = { alta: "🔴", high: "🔴", media: "🟠", medium: "🟠", baja: "🟢", low: "🟢" };
  const ataque = (x) => `<li><b>${sev[String(x.severidad || "").toLowerCase()] || "⚪"} ${esc(x.que)}</b>${x.owasp ? ` <span class="sub">(<span data-no-tr>${esc(x.owasp)}</span>)</span>` : ""}${x.evidencia ? `<div><code data-no-tr>${esc(x.evidencia)}</code></div>` : ""}</li>`;
  const p = Math.max(0, Math.min(100, parseInt(r.puntaje, 10) || 0));
  const color = p >= 80 ? "#16a34a" : p >= 50 ? "#d97706" : "#dc2626";
  caja.innerHTML = `<div class="idx-reto-nota"><div class="idx-reto-num" style="color:${color}" data-no-tr>${p}</div>
      <div><b>${esc(r.nivel || "")}</b><div class="sub">${tr("Postura defensiva")} · ${r.lineas} ${tr("líneas")} · <span data-no-tr>${esc(r.modelo || "")}</span></div></div></div>
    <p>${esc(r.resumen || "")}</p>
    ${(r.ataques || []).length ? `<div><b>🎯 ${tr("Lo que se ve en tus logs")}</b><ul>${r.ataques.map(ataque).join("")}</ul></div>` : ""}
    ${r.cobertura ? `<div><b>📡 ${tr("Cobertura de detección")}</b><p>${esc(r.cobertura)}</p></div>` : ""}
    ${(r.reglas_siem || []).length ? `<div><b>🛰️ ${tr("Reglas de SIEM sugeridas")}</b><ul>${li(r.reglas_siem)}</ul></div>` : ""}
    ${r.evaluacion_respuesta ? `<div><b>📝 ${tr("Evaluación de tu respuesta")}</b><p>${esc(r.evaluacion_respuesta)}</p></div>` : ""}
    ${(r.mejoras || []).length ? `<div><b>⬆️ ${tr("Para subir de nivel")}</b><ul>${li(r.mejoras)}</ul></div>` : ""}
    ${r.fuentes?.length ? `<div class="sub">📚 ${tr("Fuentes de tu bibliografía")}: <span data-no-tr>${r.fuentes.map(esc).join(" · ")}</span></div>` : ""}`;
  caja.hidden = false;
}

function activarPanelLab() {
  const caja = $("#idxLab");
  if (!caja) return;
  const salida = $("#idxLabSalida"), prog = $("#idxLabProg");
  const msj = { levantar: "Laboratorio arriba: DVWA en 127.0.0.1:4280 y Juice Shop en 127.0.0.1:4300", apagar: "Laboratorio apagado y limpio" };
  $$("[data-lab]", caja).forEach((b) => b.addEventListener("click", async () => {
    const accion = b.dataset.lab;
    $$("[data-lab]", caja).forEach((x) => (x.disabled = true));
    salida.hidden = true;
    try {
      const r = await trabajo("/api/vm/lab", { accion }, prog);
      if (accion === "analizar") { pintarAnalisisLab(r); aviso("Análisis listo"); $$("[data-lab]", caja).forEach((x) => (x.disabled = false)); return; }
      if (accion === "logs") {
        salida.textContent = tr(r.importado ? `${r.lineas} líneas cargadas al SIEM (índice importados). Búscalas en Kibana.`
          : `${r.lineas} líneas guardadas en siem_importar; el SIEM no está encendido.`);
      } else salida.textContent = r.salida || "";
      salida.hidden = !salida.textContent;
      aviso(msj[accion] || "Listo");
    } catch (e) { aviso(e.message); salida.textContent = e.message; salida.hidden = false; }
    $$("[data-lab]", caja).forEach((x) => (x.disabled = false));
  }));
  $$("[data-lab-abrir]", caja).forEach((b) => b.addEventListener("click", () => window.open(b.dataset.labAbrir, "_blank", "noopener")));
  $("[data-lab-siem]", caja)?.addEventListener("click", () => ir("siem"));

  // 🟣 Reto morado: califica la defensa (manda arena + tu respuesta)
  $("[data-lab-calificar]", caja)?.addEventListener("click", async () => {
    const arena = $("#idxRetoArena", caja)?.value || "lab";
    const respuesta = $("#idxRetoResp", caja)?.value || "";
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = true));
    try {
      const r = await trabajo("/api/vm/lab", { accion: "calificar", arena, respuesta }, prog);
      pintarRetoLab(r); aviso(tr("Reto calificado"));
    } catch (e) { aviso(e.message); }
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = false));
  });

  // 📦 Vulhub: clona el repo oficial en la VM
  const vhSal = $("#idxVulhubSalida", caja);
  $("[data-lab-vulhub]", caja)?.addEventListener("click", async () => {
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = true));
    try {
      const r = await trabajo("/api/vm/lab", { accion: "vulhub" }, prog);
      vhSal.textContent = tr(`Vulhub listo: ${r.entornos} entornos en ~/vulhub. Levanta el que quieras desde la terminal de la VM.`);
      vhSal.hidden = false; aviso(tr("Vulhub clonado"));
    } catch (e) { aviso(e.message); vhSal.textContent = e.message; vhSal.hidden = false; }
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = false));
  });

  // 🧠 Ampliar la VM (apaga + modifyvm + rehornea 'limpio'): pide confirmación
  $("[data-lab-recursos]", caja)?.addEventListener("click", async () => {
    if (!confirm(tr("Esto APAGA la VM, la deja en 16 GB de RAM y 6 núcleos y rehornea la base 'limpio'. Tarda unos minutos. ¿Continuar?"))) return;
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = true));
    try {
      const r = await trabajo("/api/vm/lab", { accion: "recursos" }, prog);
      aviso(tr(`VM ampliada: ${(r.ram_mb/1024)|0} GB de RAM y ${r.cpus} núcleos`));
    } catch (e) { aviso(e.message); }
    $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja).forEach((x) => (x.disabled = false));
  });

  const todos = () => $$("[data-lab],[data-lab-calificar],[data-lab-vulhub],[data-lab-recursos],[data-lab-simular],[data-lab-caza]", caja);
  // 🤖 La IA ataca (simulación): genera el ataque + logs sintéticos del CVE elegido
  $("[data-lab-simular]", caja)?.addEventListener("click", async () => {
    const cve = $("#idxSimCve", caja)?.value || "";
    todos().forEach((x) => (x.disabled = true));
    try {
      const r = await trabajo("/api/vm/lab", { accion: "simular", cve }, prog);
      pintarSimLab(r);
      $("#idxCazaSalida", caja).hidden = true;  // caza previa ya no aplica al nuevo ataque
      aviso(tr("Ataque simulado listo"));
    } catch (e) { aviso(e.message); }
    todos().forEach((x) => (x.disabled = false));
  });
  // 🔵 Califica la caza del alumno sobre la última simulación
  $("[data-lab-caza]", caja)?.addEventListener("click", async () => {
    const respuesta = $("#idxCazaResp", caja)?.value || "";
    todos().forEach((x) => (x.disabled = true));
    try {
      const r = await trabajo("/api/vm/lab", { accion: "calificar_caza", respuesta }, prog);
      pintarRetoLab(r, "#idxCazaSalida"); aviso(tr("Caza calificada"));
    } catch (e) { aviso(e.message); }
    todos().forEach((x) => (x.disabled = false));
  });
}

const GUIA_LABS = `<details class="idx-guia"><summary><b>🛠️ Instalarlos a mano (Vulhub, crAPI u otros) sin exponerlos</b></summary>
  <p class="sub">Todo esto se teclea dentro de la VM de Ubuntu, no en Windows. Usa SOLO las fuentes oficiales: hubo imágenes de Docker Hub con puerta trasera, así que nada de copias de terceros.</p>
  <ol>
    <li><b>Red de la VM:</b> en VirtualBox deja la VM en <b>NAT</b> o <b>Solo anfitrión (host-only)</b>. Nunca en modo puente: estas apps son vulnerables a propósito y no deben quedar a la vista de tu red.</li>
    <li><b>Docker:</b> instálalo desde el repositorio oficial de Docker para Ubuntu (docs.docker.com/engine/install/ubuntu). Comprueba con <code>docker version</code> y <code>docker compose version</code>.</li>
    <li><b>DVWA</b> (fuente: github.com/digininja/DVWA · imagen oficial ghcr.io/digininja/dvwa + MariaDB; varios cientos de MB):
      <pre data-no-tr>git clone https://github.com/digininja/DVWA.git
cd DVWA
docker compose up -d        # queda en http://localhost:4280 (solo localhost)</pre></li>
    <li><b>Juice Shop</b> (fuente: OWASP, imagen oficial bkimminich/juice-shop; varios cientos de MB):
      <pre data-no-tr>docker run -d --name juice -p 127.0.0.1:3000:3000 bkimminich/juice-shop
# http://localhost:3000</pre></li>
    <li><b>Vulhub</b> (fuente: github.com/vulhub/vulhub; el repo pesa decenas de MB y cada entorno baja sus propias imágenes):
      <pre data-no-tr>git clone --depth 1 https://github.com/vulhub/vulhub.git
cd vulhub/&lt;app&gt;/&lt;CVE&gt;     # lee el README de esa carpeta
docker compose up -d</pre></li>
    <li><b>Limpieza al terminar</b> (para no dejar basura): <code>docker compose down -v</code> en la carpeta del lab, o <code>docker rm -f juice</code>.</li>
    <li><b>Lado defensor:</b> <code>docker logs juice</code> o <code>docker compose logs dvwa</code> te dan los logs de lo que hiciste. Copia el access.log a la carpeta <code>siem_importar</code> de NetLab y búscate en Kibana.</li>
  </ol></details>`;

const IDX = { prog: {}, abierto: null, pestana: "salas" };
const ESTADOS_IDX = [["pendiente", "⬜ Pendiente"], ["en_curso", "🟨 En curso"], ["hecha", "✅ Hecha"]];

async function pintarIndice() {
  const caja = $("#indiceVista");
  if (!caja) return;
  try { IDX.prog = (await api("/api/indice")).progreso || {}; } catch { IDX.prog = {}; }
  const total = INDICE.reduce((s, t) => s + t.items.length, 0), hechas = Object.values(IDX.prog).filter((x) => x.estado === "hecha").length;
  caja.innerHTML = `<div class="idx-pestanas">${[["salas", "🗺️ Salas y labs"], ["ruta", "📚 Teoría, exámenes y jefes"], ["mitre", "🧩 Mapa de MITRE ATT&CK"]]
      .map(([k, n]) => `<button data-idx-pest="${k}" class="${IDX.pestana === k ? "primario" : ""}">${n}</button>`).join("")}</div>
    <div id="idxPestRuta" ${IDX.pestana === "ruta" ? "" : "hidden"}></div><div id="idxPestMitre" ${IDX.pestana === "mitre" ? "" : "hidden"}></div>
    <div id="idxPestSalas" ${IDX.pestana === "salas" ? "" : "hidden"}><div class="tarjeta">
      <div class="idx-cabeza"><div><b>${hechas} de ${total}</b> salas, máquinas y labs hechos</div><div class="j-barra grande"><i style="width:${Math.round(100 * hechas / total)}%"></i></div></div>
      <p class="sub">Aquí no se ataca nada: cada sala se hace en TryHackMe o Hack The Box (su infraestructura, legal) o en tu propia VM. NetLab te ordena el camino, guarda tu avance y tus notas, y en cada tema te explica <b>por qué funciona</b> la técnica y <b>con qué se detecta</b>, con una práctica de defensa aquí mismo. Algunas salas son Premium/VIP y las plataformas cambian eso seguido.</p>
      <div class="fila-filtro"><input id="idxQ" placeholder="Buscar sala, máquina o tema (ej. nmap, sqli, kerberos)…"><select id="idxEstado"><option value="">Todas</option>${ESTADOS_IDX.map(([k, n]) => `<option value="${k}">${n}</option>`).join("")}</select>
        <select id="idxPl"><option value="">THM + HTB + labs</option><option value="THM">TryHackMe</option><option value="HTB">Hack The Box</option><option value="LAB">Labs locales</option></select></div>
    </div>
    <div id="idxTemas"></div></div>`;
  $$("[data-idx-pest]").forEach((b) => b.addEventListener("click", () => { IDX.pestana = b.dataset.idxPest; pintarIndice(); }));
  if (IDX.pestana === "ruta") pintarRutaPurple();
  if (IDX.pestana === "mitre") pintarMapaMitre();
  const pinta = () => pintarTemasIndice($("#idxQ").value.trim().toLowerCase(), $("#idxEstado").value, $("#idxPl").value);
  $("#idxQ").addEventListener("input", pinta);
  $("#idxEstado").addEventListener("change", pinta);
  $("#idxPl").addEventListener("change", pinta);
  pinta();
}

function pintarTemasIndice(q, est, pl) {
  const estDe = (it) => IDX.prog[it.id]?.estado || "pendiente";
  const html = INDICE.map((t) => {
    const items = t.items.filter((it) => (!q || `${it.nombre} ${it.que} ${t.nombre}`.toLowerCase().includes(q)) && (!est || estDe(it) === est) && (!pl || it.pl === pl));
    if (!items.length) return "";
    const h = t.items.filter((it) => estDe(it) === "hecha").length;
    const abierto = IDX.abierto === t.id || !!q;
    return `<div class="tarjeta idx-tema" data-idx-tema="${t.id}">
      <div class="idx-tema-cab" data-idx-abrir="${t.id}"><span class="icono">${t.icono}</span><b>${esc(t.nombre)}</b><span class="pill">${h}/${t.items.length}</span><span class="sub">${abierto ? "▲" : "▼"}</span></div>
      <div ${abierto ? "" : "hidden"}>
        <div class="acciones" style="margin:8px 0"><button class="primario btn-teofondo" data-idx-teo="${t.id}">📖 Teoría a fondo: por qué funciona y con qué se detecta</button>
          ${t.practica.map(([n], k) => `<button data-idx-prac="${t.id}:${k}">🛡️ ${esc(n)}</button>`).join("")}<button data-idx-lec>📚 Lecciones y exámenes de SOC</button></div>
        <div class="idx-teo-caja" id="idxTeo_${t.id}" hidden></div>
        <div class="idx-dos"><div><div class="sub"><b>Por qué funciona</b></div><p>${esc(t.porque)}</p></div><div><div class="sub"><b>Con qué se detecta</b></div><p>${esc(t.detecta)}</p></div></div>
        ${t.guia ? panelLabHtml() + GUIA_LABS : ""}
        <div class="idx-items">${items.map((it) => {
          const p = IDX.prog[it.id] || {};
          return `<div class="idx-item ${estDe(it)}">
            <div class="idx-item-cab"><span class="pill idx-pl-${it.pl}">${it.pl}</span><b>${esc(it.nombre)}</b><span class="sub">${esc(it.nivel)}</span>
              <a href="${it.url}" target="_blank" rel="noopener noreferrer" class="chico">Abrir ↗</a></div>
            <div class="sub">${esc(it.que)}</div>
            <div class="idx-item-pie"><select data-idx-est="${it.id}">${ESTADOS_IDX.map(([k, n]) => `<option value="${k}" ${estDe(it) === k ? "selected" : ""}>${n}</option>`).join("")}</select>
              <textarea data-idx-nota="${it.id}" rows="${p.notas ? 3 : 1}" placeholder="Tus notas: qué aprendiste y qué rastro dejaría cada paso (Event ID, log, filtro)…">${esc(p.notas || "")}</textarea></div></div>`;
        }).join("")}</div></div></div>`;
  }).join("");
  $("#idxTemas").innerHTML = html || `<p class="sub">Nada coincide con tu búsqueda.</p>`;
  $$("[data-idx-abrir]").forEach((b) => b.addEventListener("click", () => { IDX.abierto = IDX.abierto === b.dataset.idxAbrir ? null : b.dataset.idxAbrir; pintarTemasIndice(q, est, pl); }));
  activarPanelLab();
  $$("[data-idx-teo]").forEach((b) => b.addEventListener("click", (ev) => {
    const t = INDICE.find((x) => x.id === b.dataset.idxTeo);
    teoriaAFondo(ev.target, $(`#idxTeo_${t.id}`), { clave: `idx:${t.id}`, mundo: "indice", titulo: `Purple Team · ${t.nombre}`,
      contexto: `${t.porque} Detección: ${t.detecta} Explica el concepto, por qué funciona, qué rastro deja y cómo se detecta y mitiga; sin pasos de ataque.` });
  }));
  $$("[data-idx-lec]").forEach((b) => b.addEventListener("click", () => irTeoria("soc", null)));
  $$("[data-idx-prac]").forEach((b) => b.addEventListener("click", () => { const [tid, k] = b.dataset.idxPrac.split(":"); INDICE.find((x) => x.id === tid).practica[+k][1](); }));
  $$("[data-idx-est]").forEach((s) => s.addEventListener("change", async () => {
    const id = s.dataset.idxEst;
    try {
      const r = await api("/api/indice/marcar", { item: id, estado: s.value });
      IDX.prog[id] = { ...(IDX.prog[id] || {}), estado: r.estado, notas: r.notas };
      if (r.estado === "hecha") { celebrar("🗺️ +30 XP · Ruta ofensiva", "xp"); refrescarJugador(true); }
      s.closest(".idx-item").className = `idx-item ${r.estado}`;
      const total = INDICE.reduce((a, t) => a + t.items.length, 0), hechas = Object.values(IDX.prog).filter((x) => x.estado === "hecha").length;
      $(".idx-cabeza b").textContent = `${hechas} de ${total}`;
      $(".idx-cabeza i").style.width = `${Math.round(100 * hechas / total)}%`;
    } catch (e) { aviso(e.message); }
  }));
  $$("[data-idx-nota]").forEach((t) => t.addEventListener("change", async () => {
    try { const r = await api("/api/indice/marcar", { item: t.dataset.idxNota, notas: t.value }); IDX.prog[t.dataset.idxNota] = { ...(IDX.prog[t.dataset.idxNota] || {}), estado: r.estado, notas: r.notas }; aviso("Notas guardadas"); }
    catch (e) { aviso(e.message); }
  }));
}


// ====================================================================== 📚 Teoría, exámenes y jefes (Purple Team)
// Lecciones, examen por tema y jefe por nivel con la misma mecánica de las demás rutas. Las preguntas son SOLO de concepto,
// rastro, detección, mitigación e ID de ATT&CK (el servidor lo exige con el dominio "purple"); el ataque se practica en las salas.
const RUTA_PURPLE = [
  { nombre: "Básico", icono: "🌱", temas: ["fundamentos", "recon", "servicios"] },
  { nombre: "Intermedio", icono: "⚙️", temas: ["passwords", "web", "privesc_linux"] },
  { nombre: "Avanzado", icono: "🔥", temas: ["api", "privesc_win", "ad"] },
];
async function pintarRutaPurple() {
  const caja = $("#idxPestRuta");
  if (!caja) return;
  const prog = await progresoGeneral();
  const niveles = RUTA_PURPLE.map((n) => ({ ...n, temas: n.temas.map((tid) => {
    const t = INDICE.find((x) => x.id === tid), h = t.items.filter((it) => IDX.prog[it.id]?.estado === "hecha").length;
    return { id: `idx_${tid}`, tid, nombre: t.nombre, nota_practica: h ? Math.round((100 * h) / t.items.length) / 10 : null,
      practica_txt: `🗺️ Salas (${h}/${t.items.length})`, detalle: `${h}/${t.items.length} salas hechas · teoría + examen` };
  }) }));
  caja.innerHTML = `<div class="tarjeta"><p class="sub">Aquí se estudia la TEORÍA de cada tema y se presenta su examen: por qué funciona la técnica, qué rastro deja, con qué se detecta, cómo se mitiga y su ID de ATT&CK. Las preguntas nunca piden comandos de ataque. La nota de práctica sale de las salas que marcas como hechas.</p></div><div id="idxRuta2"></div>`;
  pintarRuta2({ caja: $("#idxRuta2"), pref: "idx", dominio: "purple", titulo: "Ruta ofensiva (Purple Team): teoría y detección", cert: "eJPT / OSCP (parte teórica) y SAL1",
    niveles, onPractica: (t) => { IDX.pestana = "salas"; IDX.abierto = t.tid; pintarIndice().then(() => $(`[data-idx-tema="${t.tid}"]`)?.scrollIntoView({ behavior: "smooth" })); } }, prog);
}

// ====================================================================== 🧩 Mapa de MITRE ATT&CK
// ⚔️ = hiciste una sala que la practica · 🛡️ = la detectaste/contuviste en NetLab · 🟣 = las dos (purple).
const MITRE_MAPA = [
  ["Reconocimiento", "TA0043", [
    ["T1595", "Active Scanning", ["thm_nmap", "thm_nmap01", "thm_nmap02", "thm_nmap03", "thm_nmap04"], ["rvb:wireshark:escaneo", "ws:escaneo"]],
    ["T1595.003", "Wordlist Scanning", ["thm_contentdiscovery"], ["rvb:web:dirbust"]]]],
  ["Acceso inicial", "TA0001", [
    ["T1190", "Exploit Public-Facing Application", ["thm_owasptop10", "thm_sqli", "thm_fileinc", "thm_cmdi", "thm_juiceshop", "htb_appointment", "lab_dvwa", "lab_juiceshop", "lab_vulhub", "lab_crapi", "lab_juiceshop_api"],
      ["rvb:web:sqli", "rvb:web:traversal", "rvb:web:cmdi", "rvb:web:ssrf", "rvb:web:idor", "rvb:web:xxe"]],
    ["T1566.001", "Spearphishing Attachment", [], ["soc:phishing", "soc:ransomware"]],
    ["T1078", "Valid Accounts", ["htb_meow", "htb_fawn", "htb_jerry"], ["soc:nube", "rvb:ad:spray"]]]],
  ["Ejecución", "TA0002", [
    ["T1059.001", "PowerShell", [], ["soc:ransomware", "soc:windows"]],
    ["T1059.004", "Unix Shell", ["thm_cmdi"], ["rvb:web:cmdi", "rvb:linux:shell_inversa"]],
    ["T1569.002", "Service Execution", [], ["rvb:ad:psexec"]]]],
  ["Persistencia", "TA0003", [
    ["T1505.003", "Web Shell", ["thm_rootme", "thm_vulnversity"], ["rvb:web:webshell", "rvb:linux:webshell"]],
    ["T1136", "Create Account", [], ["rvb:ad:nuevo_admin", "rvb:linux:usuario_root", "soc:windows"]],
    ["T1053.003", "Cron", ["thm_linprivesc", "thm_commonlinuxprivesc"], ["rvb:linux:cron"]],
    ["T1098.004", "SSH Authorized Keys", ["thm_basicpentesting"], ["rvb:linux:llave_ssh"]],
    ["T1574.006", "Dynamic Linker Hijacking", ["thm_linuxprivesc"], ["rvb:linux:ld_preload"]]]],
  ["Escalada de privilegios", "TA0004", [
    ["T1548.001", "Setuid and Setgid", ["thm_linprivesc", "thm_linuxprivesc", "thm_rootme", "thm_vulnversity"], ["rvb:linux:suid"]],
    ["T1548.003", "Sudo and Sudo Caching", ["thm_simplectf", "thm_agentsudo", "thm_bountyhacker", "htb_vaccine"], []],
    ["T1068", "Exploitation for Privilege Escalation", ["thm_windowsprivesc", "thm_blue", "htb_legacy", "htb_lame"], []],
    ["T1543.003", "Windows Service", ["thm_windowsprivesc"], ["rvb:ad:psexec"]]]],
  ["Evasión de defensas", "TA0005", [
    ["T1070.001", "Clear Windows Event Logs", [], ["soc:windows", "soc:insider"]],
    ["T1070.002", "Clear Linux or Mac System Logs", [], ["rvb:linux:borrar_huellas"]],
    ["T1564.008", "Email Hiding Rules", [], ["soc:nube"]]]],
  ["Acceso a credenciales", "TA0006", [
    ["T1110.001", "Password Guessing", ["thm_hydra", "thm_bruteit", "thm_basicpentesting"],
      ["rvb:linux:fuerza_bruta", "rvb:web:bruta", "rvb:wireshark:ssh_bruta", "rvb:ccna:fuerza_bruta", "ws:ssh_bruta"]],
    ["T1110.002", "Password Cracking", ["thm_passwordcracking", "thm_bruteit", "htb_vaccine"], []],
    ["T1110.003", "Password Spraying", ["thm_passwordattacks"], ["rvb:ad:spray"]],
    ["T1558.003", "Kerberoasting", ["thm_attacktive", "htb_active"], ["rvb:ad:kerberoasting"]],
    ["T1558.004", "AS-REP Roasting", ["thm_attacktive", "htb_forest", "htb_sauna"], ["rvb:ad:asrep"]],
    ["T1003.006", "DCSync", ["htb_sauna", "thm_attacktive"], ["rvb:ad:dcsync"]],
    ["T1621", "MFA Request Generation", [], ["soc:nube"]],
    ["T1040", "Network Sniffing", ["htb_cap"], ["ws:ftp_claro", "ws:http_basic", "rvb:wireshark:ftp_claro", "rvb:ccna:telnet"]],
    ["T1557.002", "ARP Cache Poisoning", [], ["rvb:ccna:arp_spoof", "rvb:wireshark:arp_spoof", "ws:arp_spoof"]],
    ["T1557.003", "DHCP Spoofing", [], ["rvb:ccna:dhcp_falso"]]]],
  ["Descubrimiento", "TA0007", [
    ["T1046", "Network Service Discovery", ["thm_nmap02", "thm_nmap03", "thm_nmap04", "thm_networkservices"], ["rvb:wireshark:escaneo", "rvb:ccna:escaneo"]],
    ["T1087.002", "Domain Account", ["thm_winadbasics", "thm_breachingad"], []]]],
  ["Movimiento lateral", "TA0008", [
    ["T1021.002", "SMB/Windows Admin Shares", ["htb_dancing"], ["rvb:ad:psexec"]],
    ["T1550.002", "Pass the Hash", ["htb_responder"], ["rvb:ad:pth"]]]],
  ["Recolección", "TA0009", [
    ["T1560.001", "Archive via Utility", [], ["soc:insider"]]]],
  ["Comando y control", "TA0011", [
    ["T1071.001", "Web Protocols", [], ["soc:c2", "ws:beaconing", "rvb:wireshark:beaconing"]],
    ["T1071.004", "DNS", [], ["ws:dns_tunel", "rvb:wireshark:dns_tunel"]],
    ["T1095", "Non-Application Layer Protocol", [], ["ws:icmp_tunel", "rvb:wireshark:icmp_tunel"]]]],
  ["Exfiltración", "TA0010", [
    ["T1041", "Exfiltration Over C2 Channel", [], ["soc:c2"]],
    ["T1048", "Exfiltration Over Alternative Protocol", [], ["ws:dns_tunel", "ws:icmp_tunel"]],
    ["T1052.001", "Exfiltration over USB", [], ["soc:insider"]],
    ["T1567.002", "Exfiltration to Cloud Storage", ["htb_three"], ["soc:insider"]]]],
  ["Impacto", "TA0040", [
    ["T1486", "Data Encrypted for Impact", [], ["soc:ransomware"]],
    ["T1490", "Inhibit System Recovery", [], ["soc:ransomware"]],
    ["T1496", "Resource Hijacking", [], ["rvb:linux:minero"]],
    ["T1499.001", "OS Exhaustion Flood", [], ["ws:syn_flood", "rvb:wireshark:syn_flood"]]]],
];
const MODO_RVB_TXT = { ccna: "Red vs Blue CCNA", wireshark: "Red vs Blue Wireshark", linux: "Red vs Blue Linux", web: "Red vs Blue Web", ad: "Red vs Blue AD" };
const SOC_TXT = { windows: "Caso SOC de Windows", phishing: "Caso SOC de phishing", ransomware: "Caso SOC de ransomware", c2: "Caso SOC de C2",
  insider: "Caso SOC de amenaza interna", nube: "Caso SOC de Microsoft 365" };
function etiquetaDefensa(k) {
  const [t, a, b] = k.split(":");
  if (t === "rvb") return `${MODO_RVB_TXT[a] || a} · ${b.replace(/_/g, " ")}`;
  if (t === "soc") return SOC_TXT[a] || a;
  return `Captura de Wireshark · ${a.replace(/_/g, " ")}`;
}
function irDefensa(k) {
  const [t, a] = k.split(":");
  if (t === "rvb") { RB.modo = a; return ir("rvb"); }
  if (t === "soc") { ir("soc"); setTimeout(() => { SOC.caso = SOC_CASOS[a](); pintarCasoSoc(); $("#socCaso")?.scrollIntoView({ behavior: "smooth" }); }, 300); return; }
  ir("wireshark");
}

async function pintarMapaMitre() {
  const caja = $("#idxPestMitre");
  if (!caja) return;
  let ev = { rvb: [], soc: [], ws: [] };
  try { ev = await api("/api/mitre"); } catch {}
  const def = new Set([...ev.rvb.map((x) => `rvb:${x}`), ...ev.soc.map((x) => `soc:${x}`), ...ev.ws.map((x) => `ws:${x}`)]);
  const hecha = (id) => IDX.prog[id]?.estado === "hecha";
  const nombreSala = (id) => INDICE.flatMap((t) => t.items).find((it) => it.id === id)?.nombre || id;
  let total = 0, conAtq = 0, conDef = 0, purple = 0;
  const tacs = MITRE_MAPA.map(([tac, taid, tecs]) => `<div class="tarjeta mitre-tac"><h3>${esc(tac)} <span class="sub" data-no-tr>${taid}</span></h3>
    <div class="mitre-tecs">${tecs.map(([tid, nom, salas, defs]) => {
      const a = salas.some(hecha), d = defs.some((k) => def.has(k));
      total++; conAtq += a; conDef += d; purple += a && d;
      const cls = a && d ? "purple" : a ? "atq" : d ? "def" : "";
      return `<details class="mitre-tec ${cls}"><summary><span class="mitre-ic">${a && d ? "🟣" : a ? "⚔️" : d ? "🛡️" : "⬜"}</span> <b data-no-tr>${tid}</b> <span data-no-tr>${esc(nom)}</span></summary>
        ${salas.length ? `<div class="sub">⚔️ Salas que la practican:</div><div class="mitre-lista">${salas.map((id) => `<span class="pill ${hecha(id) ? "ok" : ""}">${hecha(id) ? "✓ " : ""}${esc(nombreSala(id))}</span>`).join("")}</div>` : `<div class="sub">⚔️ Sin sala en el índice todavía: apréndela desde la defensa.</div>`}
        ${defs.length ? `<div class="sub">🛡️ Dónde la detectas en NetLab:</div><div class="mitre-lista">${defs.map((k) => `<button class="chico ${def.has(k) ? "primario" : ""}" data-mitre-def="${k}">${def.has(k) ? "✓ " : ""}${esc(etiquetaDefensa(k))}</button>`).join("")}</div>` : `<div class="sub">🛡️ Aún no hay práctica de detección en NetLab.</div>`}
        <div class="acciones"><a class="chico" href="https://attack.mitre.org/techniques/${tid.replace(".", "/")}/" target="_blank" rel="noopener noreferrer">ATT&CK ↗</a></div></details>`;
    }).join("")}</div></div>`).join("");
  caja.innerHTML = `<div class="tarjeta"><div class="mitre-resumen">
      <div><b>${purple}</b>/<span>${total}</span> <span>🟣 purple (practicada y detectada)</span></div>
      <div><b>${conAtq}</b>/<span>${total}</span> <span>⚔️ con sala hecha</span></div>
      <div><b>${conDef}</b>/<span>${total}</span> <span>🛡️ detectada en NetLab</span></div></div>
    <p class="sub">Cada técnica se marca ⚔️ cuando haces una sala que la practica, 🛡️ cuando la detectas o contienes en NetLab (Red vs Blue bloqueado, caso SOC con 2★ o más, captura con 7 o más) y 🟣 cuando tienes las dos. Lo gris es tu siguiente hueco. Haz clic en una técnica para ver dónde practicarla.</p></div>
    <div class="mitre-grid">${tacs}</div>`;
  $$("[data-mitre-def]", caja).forEach((b) => b.addEventListener("click", () => irDefensa(b.dataset.mitreDef)));
}
