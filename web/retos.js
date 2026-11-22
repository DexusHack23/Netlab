"use strict";
// ======================================================================
// NetLab — Retos de arrastrar y soltar (como las preguntas drag & drop del CCNA)
// Bancos escritos a mano y generadores con respuesta exacta: no usa IA.
// ======================================================================
const RETOS = (() => {
  const az = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const mezcla = (a) => { const b = [...a]; for (let i = b.length - 1; i > 0; i--) { const j = az(0, i); [b[i], b[j]] = [b[j], b[i]]; } return b; };
  const toma = (a, n) => mezcla(a).slice(0, n);
  const clasif = (titulo, instruccion, cubetas, pares, n, explicacion) => {
    const items = toma(pares, Math.min(n, pares.length)).map(([t, c]) => ({ t, c }));
    return { tipo: "clasificar", titulo, instruccion, cubetas: cubetas.filter((c) => items.some((i) => i.c === c) || cubetas.length <= 4), items, explicacion };
  };
  const emparejar = (titulo, instruccion, pares, n, explicacion) => {
    const p = toma(pares, n);
    return { tipo: "clasificar", titulo, instruccion, cubetas: p.map(([, c]) => c), items: p.map(([t, c]) => ({ t, c })), uno: true, explicacion };
  };
  const ordenar = (titulo, instruccion, pasos, explicacion) => ({ tipo: "ordenar", titulo, instruccion, items: pasos, explicacion });

  // ---------------------------------------------------------------- CCNA
  const ipPrivada = () => {
    const tipos = [
      () => [`10.${az(0, 255)}.${az(0, 255)}.${az(1, 254)}`, "Privada (RFC 1918)"],
      () => [`172.${az(16, 31)}.${az(0, 255)}.${az(1, 254)}`, "Privada (RFC 1918)"],
      () => [`192.168.${az(0, 255)}.${az(1, 254)}`, "Privada (RFC 1918)"],
      () => [`${[8, 23, 45, 66, 104, 151, 200, 201][az(0, 7)]}.${az(0, 255)}.${az(0, 255)}.${az(1, 254)}`, "Pública"],
      () => [`172.${[az(1, 15), az(32, 200)][az(0, 1)]}.${az(0, 255)}.${az(1, 254)}`, "Pública"],
      () => [`127.${az(0, 255)}.${az(0, 255)}.${az(1, 254)}`, "Especial (loopback / APIPA)"],
      () => [`169.254.${az(1, 254)}.${az(1, 254)}`, "Especial (loopback / APIPA)"],
    ];
    const items = []; const vistos = new Set();
    while (items.length < 7) { const [t, c] = tipos[az(0, tipos.length - 1)](); if (!vistos.has(t)) { vistos.add(t); items.push({ t, c }); } }
    return { tipo: "clasificar", titulo: "IPv4: privadas, públicas y especiales", instruccion: "Arrastra cada dirección a su tipo.",
      cubetas: ["Privada (RFC 1918)", "Pública", "Especial (loopback / APIPA)"], items,
      explicacion: "Privadas: 10.0.0.0/8, 172.16.0.0/12 (172.16 a 172.31) y 192.168.0.0/16. Loopback 127.0.0.0/8, APIPA 169.254.0.0/16. Todo lo demás de unicast es público." };
  };
  const CCNA = [
    () => clasif("Capas del modelo OSI", "Arrastra cada cosa a la capa donde trabaja.", ["Capa 1 · Física", "Capa 2 · Enlace", "Capa 3 · Red", "Capa 4 · Transporte", "Capa 7 · Aplicación"], [
      ["Hub", "Capa 1 · Física"], ["Bits en el cable", "Capa 1 · Física"], ["Repetidor", "Capa 1 · Física"], ["Switch", "Capa 2 · Enlace"], ["Dirección MAC", "Capa 2 · Enlace"], ["Trama", "Capa 2 · Enlace"],
      ["802.1Q (etiqueta de VLAN)", "Capa 2 · Enlace"], ["Router", "Capa 3 · Red"], ["Dirección IP", "Capa 3 · Red"], ["Paquete", "Capa 3 · Red"], ["OSPF", "Capa 3 · Red"],
      ["Número de puerto", "Capa 4 · Transporte"], ["Segmento", "Capa 4 · Transporte"], ["TCP", "Capa 4 · Transporte"], ["UDP", "Capa 4 · Transporte"],
      ["HTTP", "Capa 7 · Aplicación"], ["DNS", "Capa 7 · Aplicación"], ["SSH", "Capa 7 · Aplicación"]], 8,
      "PDU por capa: bits (1), trama (2), paquete (3), segmento (4). El switch decide por MAC (2), el router por IP (3)."),
    () => clasif("TCP o UDP", "Arrastra cada característica o protocolo a TCP o a UDP.", ["TCP", "UDP"], [
      ["Orientado a conexión", "TCP"], ["Handshake de 3 vías", "TCP"], ["Retransmite lo perdido", "TCP"], ["Control de flujo con ventana", "TCP"], ["Entrega en orden", "TCP"],
      ["HTTP / HTTPS", "TCP"], ["SSH", "TCP"], ["FTP", "TCP"], ["SMTP", "TCP"], ["Sin conexión", "UDP"], ["Cabecera de 8 bytes", "UDP"], ["Sin acuses de recibo", "UDP"],
      ["VoIP / video en vivo", "UDP"], ["DHCP", "UDP"], ["TFTP", "UDP"], ["SNMP", "UDP"], ["Syslog", "UDP"]], 8,
      "TCP es confiable (handshake, ACKs, retransmisión, ventana). UDP es rápido y ligero: lo usan protocolos de consulta corta o de tiempo real."),
    () => emparejar("Puertos bien conocidos", "Arrastra cada protocolo a su puerto.", [
      ["FTP (datos)", "20"], ["FTP (control)", "21"], ["SSH", "22"], ["Telnet", "23"], ["SMTP", "25"], ["DNS", "53"], ["DHCP servidor", "67"], ["TFTP", "69"],
      ["HTTP", "80"], ["POP3", "110"], ["NTP", "123"], ["SNMP", "161"], ["HTTPS", "443"], ["Syslog", "514"]], 6,
      "Memoriza los clásicos: 22 SSH, 23 Telnet, 53 DNS, 67/68 DHCP, 69 TFTP, 80 HTTP, 123 NTP, 161 SNMP, 443 HTTPS, 514 Syslog."),
    ipPrivada,
    () => clasif("Tipos de dirección IPv6", "Arrastra cada dirección a su tipo.", ["Global unicast", "Link-local", "Unique local", "Multicast", "Loopback"], [
      ["2001:db8:acad:1::10", "Global unicast"], ["2001:4860:4860::8888", "Global unicast"], ["3fff:12::1", "Global unicast"], ["fe80::1", "Link-local"], ["fe80::a8bb:ccff:fe00:100", "Link-local"],
      ["fd12:3456:789a::1", "Unique local"], ["fc00:10::5", "Unique local"], ["ff02::1", "Multicast"], ["ff02::2", "Multicast"], ["ff05::1:3", "Multicast"], ["::1", "Loopback"]], 7,
      "Global unicast 2000::/3 · link-local fe80::/10 (no se enruta) · unique local fc00::/7 (como las privadas) · multicast ff00::/8 · loopback ::1."),
    () => clasif("¿Cable directo o cruzado?", "Sin auto-MDIX: arrastra cada conexión al cable que necesita.", ["Directo", "Cruzado"], [
      ["PC → Switch", "Directo"], ["Switch → Router", "Directo"], ["Router → Hub", "Directo"], ["PC → Hub", "Directo"], ["Switch → Servidor", "Directo"],
      ["PC → Router", "Cruzado"], ["Switch → Switch", "Cruzado"], ["PC → PC", "Cruzado"], ["Router → Router", "Cruzado"], ["Hub → Switch", "Cruzado"]], 7,
      "Equipos de distinto grupo (PC/router vs switch/hub) van con directo; del mismo grupo, con cruzado. Con auto-MDIX cualquiera funciona."),
    () => emparejar("Ataque y su defensa", "Arrastra cada defensa al ataque que frena.", [
      ["DHCP snooping", "Servidor DHCP falso"], ["Dynamic ARP Inspection", "ARP spoofing"], ["Port security", "Inundación de MACs"], ["BPDU Guard", "Switch pirata en un puerto de acceso"],
      ["Root Guard", "Otro switch quiere ser root bridge"], ["Desactivar DTP (switchport nonegotiate)", "VLAN hopping por troncal falso"], ["SSH en vez de Telnet", "Contraseñas viajando en texto claro"],
      ["ACL en las líneas VTY", "Acceso de administración desde cualquier IP"]], 5,
      "Cada mecanismo de seguridad de capa 2 frena un ataque concreto: memoriza las parejas, en el examen salen así."),
    () => clasif("802.11: bandas de cada estándar", "Arrastra cada estándar a la banda en la que funciona.", ["Solo 2.4 GHz", "Solo 5 GHz", "2.4 y 5 GHz", "2.4, 5 y 6 GHz"], [
      ["802.11b", "Solo 2.4 GHz"], ["802.11g", "Solo 2.4 GHz"], ["802.11a", "Solo 5 GHz"], ["802.11ac (Wi-Fi 5)", "Solo 5 GHz"], ["802.11n (Wi-Fi 4)", "2.4 y 5 GHz"],
      ["802.11ax (Wi-Fi 6)", "2.4 y 5 GHz"], ["802.11ax (Wi-Fi 6E)", "2.4, 5 y 6 GHz"]], 6, "b/g = 2.4 · a/ac = 5 · n y ax = ambas · Wi-Fi 6E agrega 6 GHz."),
    () => ordenar("Distancia administrativa", "Ordena de la fuente MÁS confiable (arriba) a la menos confiable.", toma([
      "Conectada (0)", "Estática (1)", "eBGP (20)", "EIGRP interna (90)", "OSPF (110)", "RIP (120)", "EIGRP externa (170)", "iBGP (200)"], 6).sort((a, b) => +a.match(/\d+/)[0] - +b.match(/\d+/)[0]),
      "Menor distancia administrativa = más confiable. El router usa la ruta con menor AD cuando dos protocolos conocen la misma red."),
    () => ordenar("DHCP (DORA)", "Ordena los mensajes de DHCP.", ["Discover (cliente, broadcast)", "Offer (servidor)", "Request (cliente)", "Acknowledgment (servidor)"], "D-O-R-A: el cliente busca, el servidor ofrece, el cliente pide y el servidor confirma."),
    () => ordenar("Estados de vecino OSPF", "Ordena los estados desde que arranca hasta la adyacencia completa.", ["Down", "Init", "2-Way", "ExStart", "Exchange", "Loading", "Full"], "Down → Init (recibí su hello) → 2-Way (me ve en su hello; aquí se elige DR/BDR) → ExStart → Exchange (DBD) → Loading (LSR/LSU) → Full."),
    () => ordenar("Estados de puerto en STP (802.1D)", "Ordena los estados por los que pasa un puerto hasta reenviar.", ["Blocking", "Listening", "Learning", "Forwarding"], "Blocking (20 s max age) → Listening (15 s) → Learning (15 s, aprende MACs) → Forwarding. RSTP lo hace en discarding/learning/forwarding."),
    () => ordenar("Configurar SSH en un router", "Ordena los pasos.", ["hostname R1", "ip domain-name netlab.local", "crypto key generate rsa (1024 bits o más)", "username admin secret Cisco123", "line vty 0 4", "transport input ssh + login local"],
      "La llave RSA necesita hostname y dominio. Luego un usuario local y en las VTY: solo SSH y login con usuarios locales."),
    () => ordenar("Arranque de un router Cisco", "Ordena lo que pasa al encenderlo.", ["POST (prueba del hardware)", "Carga el bootstrap desde ROM", "Busca y carga el IOS (flash)", "Carga la startup-config (NVRAM) a la running-config"],
      "Si no hay IOS en flash, intenta TFTP o entra a ROMMON. Si no hay startup-config, aparece el diálogo de configuración inicial."),
  ];

  // ---------------------------------------------------------------- Wireshark
  const WS = [
    () => emparejar("Filtro → qué muestra", "Arrastra cada filtro de visualización a lo que muestra.", [
      ["tcp.flags.syn==1 && tcp.flags.ack==0", "Solo el primer paquete de cada handshake"], ["dns.flags.rcode != 0", "Respuestas DNS con error"], ["http.request", "Peticiones HTTP"],
      ["tcp.analysis.retransmission", "Retransmisiones TCP"], ["arp.opcode == 2", "Respuestas ARP"], ["icmp.type == 8", "Echo request (ping de ida)"], ["ip.addr == 10.0.0.5", "Todo lo que entra o sale de 10.0.0.5"],
      ["!(arp || dns)", "Todo menos ARP y DNS"], ["tcp.port == 443", "Tráfico TCP del puerto 443 (origen o destino)"], ["tls.handshake.type == 1", "TLS Client Hello"], ["tcp.analysis.zero_window", "Receptor sin espacio (ventana cero)"]], 6,
      "Los filtros de visualización usan campos (tcp.flags.syn, dns.flags.rcode…). Con && y || los combinas; ! niega."),
    () => clasif("¿Filtro de captura (BPF) o de visualización?", "Arrastra cada filtro a su tipo.", ["Captura (BPF)", "Visualización"], [
      ["host 192.168.1.10", "Captura (BPF)"], ["port 53", "Captura (BPF)"], ["tcp dst port 443", "Captura (BPF)"], ["net 10.0.0.0/8", "Captura (BPF)"], ["not arp", "Captura (BPF)"],
      ["ip.addr == 192.168.1.10", "Visualización"], ["dns", "Visualización"], ["tcp.dstport == 443", "Visualización"], ["http.request.method == \"POST\"", "Visualización"], ["!arp", "Visualización"]], 8,
      "Captura (BPF, antes de grabar): palabras como host, port, net, src/dst, and/or/not. Visualización (después): campos con punto y operadores ==, &&, ||, !."),
    () => ordenar("Handshake de TLS 1.2", "Ordena los mensajes.", ["Client Hello", "Server Hello", "Certificate", "Server Hello Done", "Client Key Exchange", "Change Cipher Spec + Finished (cliente)", "Change Cipher Spec + Finished (servidor)"],
      "En TLS 1.3 es más corto: Client Hello (con key share) → Server Hello y casi todo lo demás ya va cifrado."),
    () => ordenar("Handshake y cierre TCP", "Ordena los segmentos de una conexión completa.", ["SYN", "SYN, ACK", "ACK", "Datos (PSH, ACK)", "FIN, ACK", "ACK del FIN"],
      "3 vías para abrir. Para cerrar, cada lado manda su FIN y el otro lo confirma (a veces se juntan FIN y ACK)."),
    () => clasif("Capa de cada protocolo", "Arrastra cada protocolo a la capa que ves en el panel de detalles de Wireshark.", ["Enlace", "Red", "Transporte", "Aplicación"], [
      ["Ethernet II", "Enlace"], ["802.1Q", "Enlace"], ["ARP", "Enlace"], ["IPv4", "Red"], ["IPv6", "Red"], ["ICMP", "Red"], ["TCP", "Transporte"], ["UDP", "Transporte"],
      ["DNS", "Aplicación"], ["HTTP", "Aplicación"], ["DHCP", "Aplicación"], ["TLS", "Aplicación"]], 8, "Wireshark muestra las capas de arriba (más externa) a abajo: Frame, Ethernet, IP, TCP/UDP y la aplicación."),
    () => emparejar("Menú de estadísticas", "Arrastra cada pregunta a la herramienta de Wireshark que la responde.", [
      ["¿Qué protocolos hay y en qué proporción?", "Protocol Hierarchy"], ["¿Quién habla con quién y cuántos bytes?", "Conversations"], ["¿Qué hosts aparecen?", "Endpoints"],
      ["¿Cómo cambia el tráfico en el tiempo?", "I/O Graphs"], ["¿Hubo retransmisiones o errores?", "Expert Information"], ["Quiero leer toda la conversación TCP", "Follow TCP Stream"]], 5,
      "Statistics y Analyze son los menús que más se usan en el análisis (y en el WCA)."),
  ];

  // ---------------------------------------------------------------- Linux
  const permisos = () => {
    const rwx = (d) => ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"][d];
    const vistos = new Set(), p = [];
    for (const m of ["644", "600", "755", "700", "640", "750", "444", "777", "711", "664"].sort(() => Math.random() - 0.5)) {
      if (p.length >= 5) break; const s = [...m].map((d) => rwx(+d)).join(""); if (!vistos.has(s)) { vistos.add(s); p.push([s, m]); } }
    return { tipo: "clasificar", titulo: "Permisos: letras ↔ números", instruccion: "Arrastra cada permiso en letras a su número octal.", cubetas: p.map(([, m]) => m),
      items: p.map(([t, c]) => ({ t, c })), uno: true, explicacion: "r=4, w=2, x=1. Se suman por grupo: dueño, grupo, otros. rwxr-xr-x = 7,5,5 = 755." };
  };
  const LX = [
    () => emparejar("Comando → para qué sirve", "Arrastra cada comando a lo que hace.", [
      ["pwd", "Muestra la carpeta actual"], ["ls -la", "Lista todo, con ocultos y permisos"], ["grep -i error app.log", "Busca 'error' sin importar mayúsculas"], ["tail -f /var/log/syslog", "Sigue un log en vivo"],
      ["chmod 600 id_rsa", "Solo el dueño lee y escribe la llave"], ["ss -tulpn", "Puertos escuchando y su proceso"], ["ip a", "Direcciones IP de las interfaces"], ["sudo systemctl restart ssh", "Reinicia el servicio SSH"],
      ["find / -name '*.conf'", "Busca archivos .conf en todo el sistema"], ["ps aux", "Todos los procesos con su dueño"], ["sort | uniq -c", "Cuenta líneas repetidas"]], 6,
      "Los de navegación y búsqueda son la base de todo; ss, ip y systemctl son los de redes y servicios."),
    permisos,
    () => emparejar("¿Dónde está?", "Arrastra cada cosa al archivo o carpeta donde vive en Linux.", [
      ["Intentos de login y sudo", "/var/log/auth.log"], ["Usuarios del sistema", "/etc/passwd"], ["Hashes de contraseñas", "/etc/shadow"], ["Nombres a IP locales", "/etc/hosts"],
      ["Servidor DNS que usa el equipo", "/etc/resolv.conf"], ["Configuración del servidor SSH", "/etc/ssh/sshd_config"], ["Tareas programadas del sistema", "/etc/crontab"], ["Archivos de tu usuario", "/home/usuario"]], 6,
      "/etc = configuración, /var/log = registros, /home = usuarios. En un SOC, /var/log/auth.log es de los primeros que se revisan."),
    () => ordenar("Publicar un servicio web", "Ordena los pasos en un servidor Ubuntu.", ["sudo apt update", "sudo apt install apache2", "sudo systemctl enable --now apache2", "sudo ufw allow 80", "curl localhost (comprobar)"],
      "Actualizar la lista de paquetes, instalar, arrancar y habilitar, abrir el firewall y comprobar."),
    () => ordenar("Investigar un ataque de fuerza bruta por SSH", "Ordena la tubería para ver qué IP atacó más.", ["sudo grep \"Failed password\" /var/log/auth.log", "grep -oE '[0-9]+(\\.[0-9]+){3}'", "sort", "uniq -c", "sort -nr", "head"],
      "Filtrar las líneas, sacar las IPs, ordenar para que uniq junte repetidas, contar, ordenar por número y quedarte con las primeras."),
    () => clasif("¿Necesita sudo?", "Arrastra cada comando según necesite ser root o no (usuario normal en Ubuntu).", ["Necesita sudo", "Sin sudo"], [
      ["apt install nmap", "Necesita sudo"], ["systemctl restart nginx", "Necesita sudo"], ["cat /etc/shadow", "Necesita sudo"], ["ufw enable", "Necesita sudo"], ["useradd -m ana", "Necesita sudo"],
      ["ls /etc", "Sin sudo"], ["cat /etc/passwd", "Sin sudo"], ["ip a", "Sin sudo"], ["ping 8.8.8.8", "Sin sudo"], ["systemctl status ssh", "Sin sudo"], ["mkdir ~/proyectos", "Sin sudo"]], 8,
      "Leer suele ser libre; cambiar el sistema (paquetes, servicios, usuarios, firewall) o leer secretos (/etc/shadow) pide sudo."),
  ];

  const AREAS = { ccna: ["CCNA", CCNA], wireshark: ["Wireshark", WS], linux: ["Linux", LX] };
  return {
    AREAS,
    nuevo(area) { const [, banco] = AREAS[area]; const r = banco[az(0, banco.length - 1)](); r.area = area; r.items = r.tipo === "ordenar" ? r.items : mezcla(r.items); return r; },
    ronda(area, n = 5) {  // n retos distintos
      const fuentes = Object.entries(AREAS).filter(([k]) => area === "todo" || k === area).flatMap(([k, [, banco]]) => banco.map((f) => [f, k]));
      return toma(fuentes, Math.min(n, fuentes.length)).map(([f, k]) => { const r = f(); r.area = k; if (r.tipo !== "ordenar") r.items = mezcla(r.items); return r; });
    },
    mezcla,
  };
})();

// ---------------------------------------------------------------- interfaz (arrastrar con mouse o tocar con el dedo)
const RET = { ronda: [], i: 0, puntos: 0, max: 0, area: "ccna" };

function pintarRetosInicio() {
  $("#retosVista").innerHTML = `<div class="tarjeta">
    <p class="sub">Como las preguntas de arrastrar del examen real. Puedes arrastrar con el mouse o tocar una tarjeta y luego la caja.</p>
    <div class="fila"><label>Área<select id="rArea"><option value="ccna">CCNA</option><option value="wireshark">Wireshark</option><option value="linux">Linux</option><option value="todo">Todo mezclado</option></select></label>
      <label>Retos por ronda<select id="rN"><option>5</option><option>8</option><option>12</option></select></label></div>
    <div class="acciones"><button class="primario" id="rEmpezar">Empezar ronda</button>
      <button class="primario btn-teofondo" id="rTeoFondo">📖 Teoría a fondo del área</button><button id="rTeoLec">📚 Lecciones y exámenes</button></div>
    <div id="rTeoFondoCaja" hidden></div></div>`;
  $("#rArea").value = RET.area;
  const mundoRet = () => ($("#rArea").value === "todo" ? "ccna" : $("#rArea").value);
  $("#rTeoFondo").addEventListener("click", (ev) => {
    const caja = $("#rTeoFondoCaja"), a = $("#rArea").value;
    if (caja.dataset.area !== a) { caja.innerHTML = ""; delete caja.dataset.listo; caja.dataset.area = a; }  // si cambiaste de área, otra teoría
    teoriaAFondo(ev.target, caja, { clave: `retos:${a}`, mundo: mundoRet(), titulo: `Lo que hay que saber para clasificar y ordenar: ${RETOS.AREAS[a]?.[0] || a}`,
      contexto: "Preguntas de arrastrar y soltar del examen: ordenar pasos de procesos (DORA, handshake de TCP, arranque, elección de root bridge…) y clasificar conceptos en su categoría (capas del modelo OSI, puertos, tipos de direcciones, comandos). Explica cada proceso en orden y cómo distinguir las categorías." });
  });
  $("#rTeoLec").addEventListener("click", () => irTeoria(mundoRet(), null));
  $("#rEmpezar").addEventListener("click", () => {
    RET.area = $("#rArea").value;
    Object.assign(RET, { ronda: RETOS.ronda(RET.area, +$("#rN").value), i: 0, puntos: 0, max: 0, inicio: Date.now() });
    pintarReto();
  });
}

function pintarReto() {
  const r = RET.ronda[RET.i];
  const cab = `<div class="sub-marcador"><span>Reto ${RET.i + 1} de ${RET.ronda.length}</span><span>✓ ${RET.puntos.toFixed(1)} / ${RET.max}</span><span>${esc(RETOS.AREAS[r.area || RET.area]?.[0] || "")}</span></div>`;
  if (r.tipo === "ordenar") {
    const orden = RETOS.mezcla(r.items.map((t, k) => ({ t, k })));
    $("#retosVista").innerHTML = `<div class="tarjeta reto">${cab}<h2>${esc(r.titulo)}</h2><p>${esc(r.instruccion)}</p>
      <ol class="orden" id="rOrden">${orden.map((x) => `<li draggable="true" data-k="${x.k}"><span class="asa">⠿</span>${esc(x.t)}<span class="mover"><button class="chico" data-sube>▲</button><button class="chico" data-baja>▼</button></span></li>`).join("")}</ol>
      <div class="acciones"><button class="primario" id="rComprobar">Comprobar</button></div><div id="rFeedback"></div></div>`;
    activarOrden($("#rOrden"));
  } else {
    $("#retosVista").innerHTML = `<div class="tarjeta reto">${cab}<h2>${esc(r.titulo)}</h2><p>${esc(r.instruccion)}</p>
      <div class="banco" id="rBanco">${r.items.map((it, k) => `<div class="ficha" draggable="true" data-k="${k}">${esc(it.t)}</div>`).join("")}</div>
      <div class="cubetas">${r.cubetas.map((c, j) => `<div class="cubeta" data-c="${j}"><div class="cubeta-t">${esc(c)}</div><div class="cubeta-z"></div></div>`).join("")}</div>
      <div class="acciones"><button class="primario" id="rComprobar">Comprobar</button><button id="rReiniciar">Reiniciar</button></div><div id="rFeedback"></div></div>`;
    activarClasificar(r);
  }
  // teoría a fondo de ESTE reto (se guarda por reto)
  $(".reto .acciones").insertAdjacentHTML("beforeend", '<button class="btn-teofondo" id="rTeoReto">📖 Teoría a fondo</button>');
  $(".reto .acciones").insertAdjacentHTML("afterend", '<div id="rTeoRetoCaja" hidden></div>');
  const areaR = r.area || RET.area;
  $("#rTeoReto").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#rTeoRetoCaja"), {
    clave: `reto:${areaR}:${r.titulo}`, mundo: areaR === "todo" ? "ccna" : areaR, titulo: r.titulo,
    contexto: `Reto de ${r.tipo === "ordenar" ? "ordenar pasos" : "clasificar en categorías"}. ${r.instruccion}${r.cubetas ? ` Categorías: ${r.cubetas.join(", ")}.` : ""}` }));
  $("#rComprobar").addEventListener("click", comprobarReto);
}

function activarClasificar(r) {
  let sel = null;
  const ponEn = (ficha, destino) => {
    const zona = destino.classList.contains("banco") ? destino : $(".cubeta-z", destino);
    if (r.uno && !destino.classList.contains("banco") && zona.children.length) $("#rBanco").appendChild(zona.firstElementChild);
    zona.appendChild(ficha);
    ficha.classList.remove("sel"); sel = null;
  };
  $$(".ficha").forEach((f) => {
    f.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", f.dataset.k); f.classList.add("arrastrando"); });
    f.addEventListener("dragend", () => f.classList.remove("arrastrando"));
    f.addEventListener("click", (e) => { e.stopPropagation(); if (sel === f) { f.classList.remove("sel"); sel = null; return; } $$(".ficha.sel").forEach((x) => x.classList.remove("sel")); sel = f; f.classList.add("sel"); });
  });
  [...$$(".cubeta"), $("#rBanco")].forEach((z) => {
    z.addEventListener("dragover", (e) => { e.preventDefault(); z.classList.add("encima"); });
    z.addEventListener("dragleave", () => z.classList.remove("encima"));
    z.addEventListener("drop", (e) => { e.preventDefault(); z.classList.remove("encima"); const f = $(`.ficha[data-k="${e.dataTransfer.getData("text/plain")}"]`); if (f) ponEn(f, z); });
    z.addEventListener("click", () => { if (sel) ponEn(sel, z); });
  });
  $("#rReiniciar").addEventListener("click", () => $$(".ficha").forEach((f) => $("#rBanco").appendChild(f)));
}

function activarOrden(lista) {
  let arr = null;
  lista.addEventListener("dragstart", (e) => { arr = e.target.closest("li"); arr?.classList.add("arrastrando"); });
  lista.addEventListener("dragend", () => { arr?.classList.remove("arrastrando"); arr = null; });
  lista.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (!arr) return;
    const despues = [...lista.querySelectorAll("li:not(.arrastrando)")].find((li) => e.clientY < li.getBoundingClientRect().top + li.offsetHeight / 2);
    despues ? lista.insertBefore(arr, despues) : lista.appendChild(arr);
  });
  lista.addEventListener("click", (e) => {
    const li = e.target.closest("li");
    if (e.target.matches("[data-sube]") && li.previousElementSibling) lista.insertBefore(li, li.previousElementSibling);
    if (e.target.matches("[data-baja]") && li.nextElementSibling) lista.insertBefore(li.nextElementSibling, li);
  });
}

function comprobarReto() {
  const r = RET.ronda[RET.i];
  let buenas = 0, total;
  if (r.tipo === "ordenar") {
    const lis = $$("#rOrden li");
    total = lis.length;
    lis.forEach((li, pos) => { const ok = +li.dataset.k === pos; buenas += ok; li.classList.add(ok ? "bien" : "mal"); li.draggable = false; });
    $("#rFeedback").innerHTML = `<p><b>Orden correcto:</b></p><ol>${r.items.map((t) => `<li>${esc(t)}</li>`).join("")}</ol>`;
  } else {
    total = r.items.length;
    $$(".ficha").forEach((f) => {
      const it = r.items[+f.dataset.k], cub = f.closest(".cubeta");
      const ok = cub && r.cubetas[+cub.dataset.c] === it.c;
      buenas += ok; f.classList.add(ok ? "bien" : "mal"); f.draggable = false;
      if (!ok) f.title = `Va en: ${it.c}`;
      if (!ok) f.insertAdjacentHTML("beforeend", `<span class="va">→ ${esc(it.c)}</span>`);
    });
  }
  const pts = buenas / total;
  RET.puntos += pts; RET.max += 1;
  const area = RETOS.AREAS[r.area || RET.area]?.[0] || "CCNA";
  if (pts < 1 && typeof agregarRepaso === "function") {
    if (r.tipo === "ordenar") agregarRepaso(area, "flash", { enunciado: `${r.titulo}: ${r.instruccion}`, respuestas: [r.items.map((t, k) => `${k + 1}. ${t}`).join("\n")], explicacion: r.explicacion, origen: "Arrastrar y soltar" }, "ord:" + r.titulo + r.items.join());
    else $$(".ficha.mal").forEach((f) => { const it = r.items[+f.dataset.k];
      agregarRepaso(area, "opcion", { enunciado: `${r.titulo}: ¿dónde va "${it.t}"?`, opciones: r.cubetas, correcta: r.cubetas.indexOf(it.c), explicacion: r.explicacion, origen: "Arrastrar y soltar" }, "ret:" + r.titulo + it.t); });
  }
  $("#rFeedback").insertAdjacentHTML("afterbegin", `<p class="nota ${notaClase(pts * 10)}">${buenas} de ${total} bien</p>`);
  $("#rFeedback").insertAdjacentHTML("beforeend", `<p class="sub">💡 ${esc(r.explicacion)}</p>
    ${pts < 1 ? `<div><button class="chico" id="rExplica">🤖 Explícamelo</button><div class="tutor-caja"></div></div>` : ""}`);
  $("#rExplica")?.addEventListener("click", (ev) => explicame(ev.target, RETOS.AREAS[r.area || RET.area]?.[0] || "redes",
    `Reto de arrastrar: ${r.titulo}. ${r.instruccion}\nRespuesta correcta: ${r.tipo === "ordenar" ? r.items.join(" → ") : r.items.map((i) => `${i.t} → ${i.c}`).join("; ")}`,
    "Explícame la lógica para que no se me olvide (con un truco para memorizarlo)."));
  const b = $("#rComprobar");
  b.textContent = RET.i < RET.ronda.length - 1 ? "Siguiente →" : "Ver resultado";
  b.removeEventListener("click", comprobarReto);
  b.addEventListener("click", siguienteReto);
  $("#rReiniciar")?.remove();
}

function siguienteReto() {
  RET.i++;
  if (RET.i < RET.ronda.length) return pintarReto();
  const nota = Math.round((100 * RET.puntos) / RET.max);
  api("/api/reto/resultado", { area: RET.area, buenas: Math.round(RET.puntos * 10) / 10, total: RET.max }).catch(() => {});
  $("#retosVista").innerHTML = `<div class="tarjeta"><div class="resultado"><span class="calif nota ${notaClase(nota / 10)}">${nota}%</span>
    <span class="sub"> · ${RET.puntos.toFixed(1)} de ${RET.max} retos</span>
    <div class="acciones"><button class="primario" id="rOtra">Otra ronda</button></div></div></div>`;
  $("#rOtra").addEventListener("click", pintarRetosInicio);
}
