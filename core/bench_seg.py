"""Examen corto de ciberseguridad (respuestas conocidas) para comparar qué modelo local sabe más de SOC/blue team."""
from __future__ import annotations

PREGUNTAS = [
    ("En MITRE ATT&CK, la técnica T1110 es:", ["Phishing", "Brute Force", "Valid Accounts", "Command and Scripting Interpreter"], "B"),
    ("Filtro de Wireshark para ver solo el primer paquete del handshake TCP (SYN sin ACK):",
     ["tcp.flags.syn==1 && tcp.flags.ack==0", "tcp.flags==0x12", "tcp.syn && tcp.ack", "tcp.port==syn"], "A"),
    ("En Windows, el Event ID de un inicio de sesión FALLIDO es:", ["4624", "4688", "4625", "4672"], "C"),
    ("¿Qué indicador apunta más a túnel DNS?",
     ["Muchas consultas A a google.com", "Subdominios muy largos y aleatorios hacia un mismo dominio, muchos TXT",
      "Respuestas DNS con TTL de 300", "Consultas PTR de la red interna"], "B"),
    ("Pass-the-Hash abusa de:", ["Tickets Kerberos TGT falsificados", "El hash NTLM de la contraseña", "Certificados TLS robados", "Cookies de sesión web"], "B"),
    ("En Linux, los hashes de las contraseñas de los usuarios están en:", ["/etc/passwd", "/etc/shadow", "/etc/group", "/var/log/auth.log"], "B"),
    ("Kerberoasting ataca principalmente:", ["Tickets de servicio (TGS) de cuentas con SPN", "El hash de krbtgt", "LLMNR/NBT-NS", "La caché ARP"], "A"),
    ("Un Golden Ticket es:", ["Un TGS falsificado para un servicio", "Un TGT falsificado con el hash de krbtgt", "Una cookie de administrador", "Un token OAuth robado"], "B"),
    ("¿Qué función de un switch Cisco mitiga un servidor DHCP falso?", ["Port security", "DHCP snooping", "BPDU guard", "Storm control"], "B"),
    ("Event ID de Windows (Security) para la creación de un proceso:", ["4688", "4720", "7045", "1102"], "A"),
    ("Una IP que hace miles de peticiones a rutas distintas que dan 404 en segundos suele ser:",
     ["Un CDN", "Fuerza bruta de directorios (gobuster/dirb)", "Un health check", "Un ataque de amplificación DNS"], "B"),
    ("¿Qué comando de Linux muestra los puertos en escucha con el proceso que los abrió?", ["ip a", "ss -tulpn", "ps aux", "netstat -r"], "B"),
    ("El Event ID 1102 de Windows indica:", ["Se borró el log de seguridad", "Falló un login", "Se creó un servicio", "Se agregó un usuario a un grupo"], "A"),
    ("En una captura, muchos SYN a distintos puertos de un host, respondidos con RST, indican:",
     ["Un SYN flood", "Un escaneo de puertos SYN", "Una transferencia de zona", "Retransmisiones normales"], "B"),
    ("Para detectar ARP spoofing en Wireshark, el aviso/campo útil es:",
     ["arp.duplicate-address-detected", "icmp.type==3", "tcp.analysis.retransmission", "dns.flags.rcode==3"], "A"),
    ("¿Qué táctica de ATT&CK agrupa técnicas como dumping de LSASS?", ["Persistence", "Credential Access", "Discovery", "Exfiltration"], "B"),
    # más difíciles, para que sí se note la diferencia entre modelos
    ("Event ID de Windows que registra la solicitud de un ticket de servicio Kerberos (clave para cazar Kerberoasting):", ["4768", "4769", "4771", "4776"], "B"),
    ("En Sysmon, el Event ID 3 corresponde a:", ["Creación de proceso", "Conexión de red", "Consulta DNS", "Creación de archivo"], "B"),
    ("Campo de Wireshark para ver el nombre del servidor (SNI) en un Client Hello:",
     ["tls.handshake.extensions_server_name", "ssl.server", "http.host", "tls.sni.name"], "A"),
    ("La sub-técnica ATT&CK T1059.001 es:", ["Windows Command Shell", "Unix Shell", "PowerShell", "Visual Basic"], "C"),
    ("Recibes paquetes de un host de tu misma LAN con TTL 128. Lo más probable es que sea:", ["Linux", "Windows", "Un router Cisco", "macOS"], "B"),
    ("El beaconing de un implante C2 se detecta típicamente por:",
     ["Conexiones salientes a intervalos casi regulares con tamaños parecidos", "Muchos RST entrantes", "Tráfico solo por ICMP", "Picos de ARP"], "A"),
    ("DCSync abusa principalmente de:", ["El permiso de replicación de directorio (Replicating Directory Changes)", "SMBv1", "La caché DNS", "NTLM relay a LDAP"], "A"),
    ("En una captura, 'tcp.analysis.zero_window' indica que:", ["El servidor cerró la conexión", "El receptor no puede aceptar más datos", "Se perdió un paquete", "El handshake falló"], "B"),
]

ESQUEMA = {"type": "object", "properties": {"respuesta": {"type": "string", "enum": ["A", "B", "C", "D"]}}, "required": ["respuesta"]}


def mensajes(i: int) -> list[dict]:
    q, ops, _ = PREGUNTAS[i]
    texto = q + "\n" + "\n".join(f"{l}) {o}" for l, o in zip("ABCD", ops))
    return [{"role": "system", "content": "Eres un analista SOC experto. Responde la pregunta de opción múltiple. Devuelve solo el JSON con la letra."},
            {"role": "user", "content": texto}]
