"""Red vs Blue: el atacante hace una jugada y tú te defiendes.

CCNA: una alerta de un switch o router y tú tecleas la configuración de IOS que la frena; el código la revisa.
Wireshark: una oleada de tráfico con un ataque; identificas al atacante, la técnica y el filtro (con tshark).
Linux: corre en el navegador (web/rvb.js); aquí solo se elige la jugada del atacante con la IA.
"""
from __future__ import annotations

import random
import re

from .ios_parser import Config, norm_iface, parse_config

DIFICULTAD = {
    "facil": {"nombre": "Fácil", "oleadas": 4, "seg": 300, "pistas": 3},
    "normal": {"nombre": "Normal", "oleadas": 6, "seg": 180, "pistas": 1},
    "dificil": {"nombre": "Difícil", "oleadas": 8, "seg": 120, "pistas": 0},
    "pesadilla": {"nombre": "☠️ Pesadilla", "oleadas": 10, "seg": 75, "pistas": 0},
}


# ---------------------------------------------------------------- CCNA
def _iface(c: Config, nombre: str) -> list[str]:
    return [l.lower() for l in (c.iface(norm_iface(nombre)) or [])]


def _glob(c: Config) -> list[str]:
    return [l.lower() for l in c.global_lines]


def _vty(c: Config) -> list[str]:
    out = []
    for s in c.find_sections(r"line vty"):
        out += [l.lower() for l in s.children]
    return out


def _acl_niega(c: Config, ip: str) -> str | None:
    """Número/nombre de una ACL que niega esa IP (estándar numerada, extendida o con nombre)."""
    for l in _glob(c):
        m = re.match(rf"access-list (\S+) deny (?:ip )?(?:host {re.escape(ip)}|{re.escape(ip)} 0\.0\.0\.0)\b", l)
        if m:
            return m.group(1)
    for s in c.find_sections(r"ip access-list (standard|extended) "):
        nombre = s.header.split()[-1].lower()
        if any(re.match(rf"(?:\d+ )?deny (?:ip )?(?:host {re.escape(ip)}|{re.escape(ip)} 0\.0\.0\.0)\b", x.lower()) for x in s.children):
            return nombre
    return None


def _acl_tiene_permit(c: Config, acl: str) -> bool:
    if any(re.match(rf"access-list {re.escape(acl)} permit\b", l) for l in _glob(c)):
        return True
    for s in c.find_sections(r"ip access-list (standard|extended) "):
        if s.header.split()[-1].lower() == acl and any(re.match(r"(?:\d+ )?permit\b", x.lower()) for x in s.children):
            return True
    return False


def ataques_ccna(rnd: random.Random) -> dict:
    vlan = rnd.choice([10, 20, 30, 99])
    p = lambda: f"FastEthernet0/{rnd.randint(2, 20)}"  # noqa: E731
    atacante = f"{rnd.choice([45, 103, 185, 203])}.{rnd.randint(1, 250)}.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}"
    up = "GigabitEthernet0/1"
    A = {}

    pd = p()
    def dhcp(c, pd=pd):
        g, falt = _glob(c), []
        if "ip dhcp snooping" not in g:
            falt.append("activar DHCP snooping (ip dhcp snooping)")
        if not any(re.match(rf"ip dhcp snooping vlan .*\b{vlan}\b", l) for l in g):
            falt.append(f"activarlo en la VLAN {vlan}")
        if "ip dhcp snooping trust" not in _iface(c, up):
            falt.append(f"confiar en el uplink {up} (ip dhcp snooping trust)")
        if "ip dhcp snooping trust" in _iface(c, pd):
            falt.append(f"NO confiar en {pd}: ahí está el servidor falso")
        return falt
    A["dhcp_falso"] = {"titulo": "Servidor DHCP falso", "dispositivo": "SW1", "tecnica": "DHCP spoofing (rogue DHCP)",
        "alerta": f"SW1: equipos de la VLAN {vlan} reciben gateway 192.168.{vlan}.66 de un servidor DHCP conectado en {pd}. El DHCP legítimo está detrás de {up}.",
        "pistas": ["La defensa es DHCP snooping: global, por VLAN, y solo los puertos de confianza pueden responder DHCP.",
                   f"El puerto hacia el servidor legítimo ({up}) es el único 'trust'."],
        "solucion": [f"ip dhcp snooping", f"ip dhcp snooping vlan {vlan}", f"interface {up}", " ip dhcp snooping trust"], "check": dhcp}

    pm = p()
    def macflood(c, pm=pm):
        i, falt = _iface(c, pm), []
        if "switchport mode access" not in i:
            falt.append(f"{pm} en modo acceso (port-security lo exige)")
        if "switchport port-security" not in i:
            falt.append(f"activar port-security en {pm}")
        if not any(l.startswith("switchport port-security maximum") for l in i) and "switchport port-security" in i:
            pass  # el máximo por defecto es 1: también vale
        return falt
    A["mac_flood"] = {"titulo": "Inundación de MACs", "dispositivo": "SW1", "tecnica": "MAC flooding",
        "alerta": f"SW1: la tabla MAC se llenó; {pm} aprendió 8,000 MACs en 10 segundos y el switch empezó a inundar tráfico por todos los puertos.",
        "pistas": ["Port security limita cuántas MACs puede aprender un puerto.", "El puerto debe estar en modo acceso antes de activar port-security."],
        "solucion": [f"interface {pm}", " switchport mode access", " switchport port-security", " switchport port-security maximum 2",
                     " switchport port-security violation shutdown"], "check": macflood}

    pb = p()
    def bpdu(c, pb=pb):
        i, g = _iface(c, pb), _glob(c)
        if "spanning-tree bpduguard enable" in i or ("spanning-tree portfast bpduguard default" in g and "spanning-tree portfast" in i):
            return []
        return [f"BPDU Guard en {pb} (spanning-tree bpduguard enable)"]
    A["switch_pirata"] = {"titulo": "Switch pirata", "dispositivo": "SW1", "tecnica": "Ataque a STP (BPDU falsas)",
        "alerta": f"SW1: llegan BPDUs con prioridad 0 por {pb} (puerto de una PC). Alguien quiere convertirse en root bridge.",
        "pistas": ["En un puerto de usuario nunca deberían llegar BPDUs.", "BPDU Guard apaga el puerto (err-disabled) si llega una."],
        "solucion": [f"interface {pb}", " spanning-tree portfast", " spanning-tree bpduguard enable"], "check": bpdu}

    def bruta(c, ip=atacante):
        falt = []
        acl = _acl_niega(c, ip)
        v = _vty(c)
        if not any(l.startswith("login block-for") for l in _glob(c)):
            if not acl:
                falt.append(f"una ACL que niegue a {ip} (o login block-for)")
            elif not _acl_tiene_permit(c, acl):
                falt.append("la ACL necesita un permit al final (si no, el deny implícito te deja fuera a ti también)")
            if acl and f"access-class {acl} in" not in v:
                falt.append(f"aplicarla a las VTY con access-class {acl} in")
        return falt
    A["fuerza_bruta"] = {"titulo": "Fuerza bruta a las VTY", "dispositivo": "R1", "tecnica": "Fuerza bruta por SSH/Telnet",
        "alerta": f"R1: %SEC_LOGIN-4-LOGIN_FAILED x 120 en 2 minutos desde {atacante}.",
        "pistas": ["Una ACL estándar que niegue esa IP y permita lo demás, aplicada en line vty con access-class.",
                   "Otra opción: login block-for 120 attempts 3 within 60."],
        "solucion": [f"access-list 10 deny host {atacante}", "access-list 10 permit any", "line vty 0 4", " access-class 10 in"], "check": bruta}

    def telnet(c):
        v, g, falt = _vty(c), _glob(c), []
        if "transport input ssh" not in v:
            falt.append("solo SSH en las VTY (transport input ssh)")
        if "login local" not in v:
            falt.append("login local en las VTY")
        if not any(l.startswith("username ") for l in g):
            falt.append("un usuario local (username ... secret ...)")
        if not any(l.startswith("ip domain-name") for l in g):
            falt.append("ip domain-name (necesario para la llave RSA)")
        return falt
    A["telnet"] = {"titulo": "Telnet en texto claro", "dispositivo": "R1", "tecnica": "Robo de credenciales por sniffing (Telnet)",
        "alerta": "R1: un sniffer en la red de administración capturó la contraseña de las VTY: viaja en texto claro por Telnet.",
        "pistas": ["Hay que pasar a SSH: dominio, llave RSA, usuario local y transport input ssh.", "crypto key generate rsa modulus 2048"],
        "solucion": ["ip domain-name netlab.local", "crypto key generate rsa modulus 2048", "username admin secret Cisco123!", "line vty 0 4",
                     " login local", " transport input ssh"], "check": telnet}

    ph = p()
    def hopping(c, ph=ph):
        i, falt = _iface(c, ph), []
        if "switchport mode access" not in i:
            falt.append(f"{ph} fijo en modo acceso (switchport mode access)")
        if "switchport nonegotiate" not in i and "switchport mode access" not in i:
            falt.append("desactivar DTP (switchport nonegotiate)")
        return falt
    A["vlan_hopping"] = {"titulo": "VLAN hopping", "dispositivo": "SW1", "tecnica": "VLAN hopping (DTP)",
        "alerta": f"SW1: {ph} negoció un troncal con una laptop (DTP dynamic desirable). Ahora esa laptop ve todas las VLANs.",
        "pistas": ["Los puertos de usuario deben ser de acceso, nunca 'dynamic'.", "switchport nonegotiate apaga DTP."],
        "solucion": [f"interface {ph}", " switchport mode access", " switchport nonegotiate"], "check": hopping}

    def arpdai(c):
        g, falt = _glob(c), []
        if not any(re.match(rf"ip arp inspection vlan .*\b{vlan}\b", l) for l in g):
            falt.append(f"Dynamic ARP Inspection en la VLAN {vlan}")
        if "ip arp inspection trust" not in _iface(c, up):
            falt.append(f"confiar en el uplink {up} (ip arp inspection trust)")
        if "ip dhcp snooping" not in g:
            falt.append("DAI usa la tabla de DHCP snooping: actívalo también")
        return falt
    A["arp_spoof"] = {"titulo": "ARP spoofing", "dispositivo": "SW1", "tecnica": "ARP spoofing / man-in-the-middle",
        "alerta": f"SW1: en la VLAN {vlan} una MAC está anunciando ser el gateway 192.168.{vlan}.1 cada segundo (ARP gratuito).",
        "pistas": ["Dynamic ARP Inspection revisa cada ARP contra la tabla de DHCP snooping.", "El uplink al router es de confianza."],
        "solucion": ["ip dhcp snooping", f"ip dhcp snooping vlan {vlan}", f"ip arp inspection vlan {vlan}", f"interface {up}",
                     " ip dhcp snooping trust", " ip arp inspection trust"], "check": arpdai}

    def escaneo(c, ip=atacante):
        acl = _acl_niega(c, ip)
        falt = []
        if not acl:
            return [f"una ACL que niegue a {ip}"]
        if not _acl_tiene_permit(c, acl):
            falt.append("un permit al final de la ACL (si no, cortas todo internet)")
        if f"ip access-group {acl} in" not in _iface(c, up):
            falt.append(f"aplicarla de entrada en la interfaz a internet {up} (ip access-group {acl} in)")
        return falt
    A["escaneo"] = {"titulo": "Escaneo desde internet", "dispositivo": "R1", "tecnica": "Escaneo de puertos",
        "alerta": f"R1: {atacante} está escaneando todos los puertos de la red interna a través de {up} (la interfaz hacia internet).",
        "pistas": ["Una ACL que niegue esa IP y permita lo demás.", f"Aplícala lo más cerca del origen: de entrada (in) en {up}."],
        "solucion": [f"access-list 110 deny ip host {atacante} any", "access-list 110 permit ip any any", f"interface {up}", " ip access-group 110 in"],
        "check": escaneo}

    def claves(c):
        g, falt = _glob(c), []
        if "service password-encryption" not in g:
            falt.append("service password-encryption")
        if not any(l.startswith("enable secret") for l in g):
            falt.append("enable secret (en vez de enable password)")
        return falt
    A["claves_claro"] = {"titulo": "Contraseñas en la config", "dispositivo": "R1", "tecnica": "Exposición de contraseñas en la configuración",
        "alerta": "R1: un respaldo de la running-config se filtró y trae 'enable password cisco' y las contraseñas de línea legibles.",
        "pistas": ["enable secret guarda un hash; enable password no.", "service password-encryption oculta las demás contraseñas (tipo 7)."],
        "solucion": ["enable secret N3tL@b2026", "no enable password", "service password-encryption"], "check": claves}
    ps = p()
    def starvation(c, ps=ps):
        g, i, falt = _glob(c), _iface(c, ps), []
        if "ip dhcp snooping" not in g:
            falt.append("activar DHCP snooping (ip dhcp snooping)")
        if not any(re.match(rf"ip dhcp snooping vlan .*\b{vlan}\b", l) for l in g):
            falt.append(f"activarlo en la VLAN {vlan}")
        lim = next((int(m.group(1)) for l in i for m in [re.match(r"ip dhcp snooping limit rate (\d+)", l)] if m), None)
        if lim is None:
            falt.append(f"limitar los paquetes DHCP por segundo en {ps} (ip dhcp snooping limit rate 10)")
        elif lim > 20:
            falt.append(f"un límite más bajo en {ps}: {lim} paquetes/s sigue dejando agotar el pool (usa 10-15)")
        return falt
    A["dhcp_starvation"] = {"titulo": "DHCP starvation", "dispositivo": "SW1", "tecnica": "DHCP starvation (agotar el pool)",
        "alerta": f"SW1: {ps} manda 900 DHCP Discover por segundo, cada uno con una MAC distinta. El pool de la VLAN {vlan} quedó en 0 IPs libres.",
        "pistas": ["DHCP snooping, además de bloquear servidores falsos, puede limitar cuántos mensajes DHCP manda un puerto.",
                   f"En la interfaz {ps}: ip dhcp snooping limit rate <n>; si se pasa, el puerto queda err-disabled."],
        "solucion": ["ip dhcp snooping", f"ip dhcp snooping vlan {vlan}", f"interface {ps}", " ip dhcp snooping limit rate 10"],
        "check": starvation}

    dist = "GigabitEthernet0/2"
    def rootguard(c, dist=dist):
        i, falt = _iface(c, dist), []
        if "spanning-tree guard root" not in i:
            falt.append(f"Root Guard en {dist} (spanning-tree guard root)")
        if "spanning-tree bpduguard enable" in i:
            falt.append(f"NO uses BPDU Guard en {dist}: es un enlace legítimo a otro switch y lo apagarías siempre")
        return falt
    A["root_pirata"] = {"titulo": "Root bridge usurpado por el enlace de distribución", "dispositivo": "SW1", "tecnica": "Ataque a STP (BPDU superiores)",
        "alerta": f"SW1: por {dist} (troncal hacia el switch del área de Ventas) llegan BPDUs con prioridad 4096, mejor que la del root actual. "
                  "Alguien conectó un switch casero detrás de ese piso y quiere ser root.",
        "pistas": ["Ese puerto SÍ debe recibir BPDUs (hay otro switch legítimo), así que BPDU Guard no sirve.",
                   "Root Guard acepta BPDUs pero pone el puerto en root-inconsistent si alguien anuncia ser mejor root."],
        "solucion": [f"interface {dist}", " spanning-tree guard root"], "check": rootguard}

    pc = p()
    def cdp(c, pc=pc):
        g, i = _glob(c), _iface(c, pc)
        return [] if ("no cdp run" in g or "no cdp enable" in i) else [f"apagar CDP en {pc} (no cdp enable) o en todo el switch (no cdp run)"]
    A["cdp_recon"] = {"titulo": "Reconocimiento con CDP", "dispositivo": "SW1", "tecnica": "Reconocimiento por CDP (fuga de información)",
        "alerta": f"SW1: una laptop en {pc} está capturando los anuncios CDP: ya sabe el modelo del switch, la versión de IOS, la VLAN nativa y la IP de administración.",
        "pistas": ["CDP es útil entre equipos Cisco, pero en puertos de usuario solo regala información.",
                   "Se apaga por interfaz (no cdp enable) o en todo el equipo (no cdp run)."],
        "solucion": [f"interface {pc}", " no cdp enable"], "check": cdp}

    def snmp(c):
        g, falt = _glob(c), []
        if "no snmp-server community public" not in g:
            falt.append("quitar la community 'public' (no snmp-server community public)")
        for l in g:
            m = re.match(r"snmp-server community (\S+)(?: (ro|rw))?", l)
            if m and not l.startswith("no "):
                if m.group(1) in ("public", "private"):
                    falt.append(f"'{m.group(1)}' es la primera community que prueba cualquier escáner: usa otra")
                if m.group(2) == "rw":
                    falt.append("no dejes una community RW: con ella se puede cambiar la configuración")
        return falt
    A["snmp_publico"] = {"titulo": "SNMP con community por defecto", "dispositivo": "R1", "tecnica": "Abuso de SNMP (community por defecto)",
        "alerta": f"R1: {atacante} hizo un snmpwalk con la community 'public' (configurada RW) y descargó la tabla de rutas y la running-config.",
        "pistas": ["Quita la community débil con 'no snmp-server community public'.",
                   "Si necesitas SNMP, usa una community difícil, solo RO y con una ACL (o mejor SNMPv3)."],
        "solucion": ["no snmp-server community public", "access-list 20 permit host 10.0.0.50",
                     "snmp-server community Mon1t0r-2026 RO 20"], "check": snmp}

    a = rnd.randint(16, 20)
    libres = [f"FastEthernet0/{k}" for k in range(a, 25)]
    def libres_chk(c, libres=libres):
        falt = []
        apag = [x for x in libres if "shutdown" not in _iface(c, x)]
        if apag:
            falt.append(f"apagar los puertos sin uso (shutdown): faltan {', '.join(x.replace('FastEthernet', 'Fa') for x in apag[:4])}{'…' if len(apag) > 4 else ''}")
        vl = [x for x in libres if not any(re.match(r"switchport access vlan (\d+)", l) and l.split()[-1] != "1" for l in _iface(c, x))]
        if vl:
            falt.append("moverlos a una VLAN sin uso (switchport access vlan 999), no dejarlos en la VLAN 1")
        return falt
    A["puertos_libres"] = {"titulo": "Puerto libre en la sala de juntas", "dispositivo": "SW1",
        "tecnica": "Acceso físico no autorizado (puerto sin uso activo)",
        "alerta": f"SW1: alguien conectó una laptop en Fa0/{a + 1}, un puerto que nadie usa y que sigue encendido en la VLAN 1. Los puertos Fa0/{a} a Fa0/24 no tienen ningún equipo asignado.",
        "pistas": ["Los puertos sin uso se apagan y se mandan a una VLAN 'agujero negro' que no se enruta.",
                   f"interface range fa0/{a} - 24 te deja configurarlos todos juntos."],
        "solucion": [f"interface range fa0/{a} - 24", " switchport mode access", " switchport access vlan 999", " shutdown"],
        "check": libres_chk}
    return A


def revisar_ccna(ataque: dict, texto: str) -> dict:
    c = parse_config(texto)
    faltan = ataque["check"](c)
    return {"ok": not faltan, "faltan": faltan}


# ---------------------------------------------------------------- Wireshark
OLEADAS_WS = {  # escenario: (técnica, id de pregunta clave, id de filtro)
    "escaneo": ("Escaneo de puertos", "p1", "f3"),
    "arp_spoof": ("ARP spoofing / man-in-the-middle", "p2", "f1"),
    "syn_flood": ("SYN flood (DoS)", "p2", "f1"),
    "dns_tunel": ("Exfiltración por DNS", "p1", "f2"),
    "dhcp_starvation": ("DHCP starvation", "p3", "f1"),
    "ftp_claro": ("Robo de credenciales en texto claro (FTP)", "p2", "f1"),
    "http_basic": ("Credenciales en Base64 (HTTP Basic)", "p3", "f1"),
    "beaconing": ("Beaconing de malware (comando y control)", "p1", "f1"),
    "ssh_bruta": ("Fuerza bruta a SSH", "p1", "f1"),
    "icmp_tunel": ("Exfiltración por túnel ICMP", "p1", "f1"),
}
TECNICAS = sorted({v[0] for v in OLEADAS_WS.values()} | {"Retransmisiones por red saturada", "Escaneo de vulnerabilidades web", "Ping de barrido (descubrimiento de hosts)"})

# ---------------------------------------------------------------- Linux (las jugadas existen en web/rvb.js)
JUGADAS_LINUX = ["fuerza_bruta", "cambiar_ip", "usuario_root", "cron", "minero", "llave_ssh", "borrar_huellas",
                 "suid", "shell_inversa", "webshell", "ld_preload"]

ESQUEMA_JUGADA = {"type": "object", "properties": {"accion": {"type": "string"}, "mensaje": {"type": "string"}},
                  "required": ["accion", "mensaje"]}
