"""Laboratorio de Wireshark: escenarios generados por código con su clave de respuestas.

Cada escenario arma una captura .pcap a partir de una semilla (así se puede regenerar igual
desde el historial sin guardar archivos) y devuelve:
  - preguntas cuya respuesta sale de los propios paquetes (no de la IA)
  - ejercicios de filtro: tu filtro se corre con tshark y se compara contra el de referencia
"""
from __future__ import annotations

import ipaddress
import os
import random
import re
import shutil
import subprocess

import struct

from .pcap import (ACK, RST, SYN, Captura, SesionTCP, _checksum, arp, dhcp, dns_consulta, dns_respuesta, ethernet,
                   icmp_eco, ip, ipv4, mac, mac_azar, tcp, udp)
from .pcap import leer as leer_pcap

TSHARK_CANDIDATOS = [r"C:\Program Files\Wireshark\tshark.exe", r"C:\Program Files (x86)\Wireshark\tshark.exe"]


def tshark() -> str | None:
    return next((p for p in TSHARK_CANDIDATOS if os.path.isfile(p)), None) or shutil.which("tshark")


def wireshark_exe() -> str | None:
    t = tshark()
    if t:
        w = os.path.join(os.path.dirname(t), "Wireshark.exe")
        if os.path.isfile(w):
            return w
    return shutil.which("wireshark")


def correr_filtro(archivo: str, filtro: str) -> dict:
    """Corre un filtro de visualización con tshark y regresa los números de frame que muestra."""
    t = tshark()
    if not t:
        return {"ok": False, "error": "No encontré tshark (viene con Wireshark)."}
    if "\n" in filtro or len(filtro) > 500:
        return {"ok": False, "error": "El filtro debe ser de una sola línea."}
    try:
        r = subprocess.run([t, "-n", "-r", archivo, "-Y", filtro, "-T", "fields", "-e", "frame.number"],
                           capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "tshark tardó demasiado."}
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        return {"ok": False, "error": "Filtro inválido: " + (msg[0] if msg else "error de tshark")}
    return {"ok": True, "frames": sorted(int(x) for x in r.stdout.split() if x.strip().isdigit())}


def resumen_tshark(archivo: str) -> str:
    """Estadísticas de una captura (para que la IA te la explique)."""
    t = tshark()
    if not t:
        return ""
    partes = []
    for nombre, args in (("Protocolos", ["-z", "io,phs"]), ("Conversaciones IP", ["-z", "conv,ip"]),
                         ("Información experta", ["-z", "expert,note"])):
        try:
            r = subprocess.run([t, "-n", "-q", "-r", archivo, *args], capture_output=True, text=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            partes.append(f"### {nombre}\n{r.stdout.strip()[:5000]}")
        except subprocess.TimeoutExpired:
            partes.append(f"### {nombre}\n(tardó demasiado)")
    return "\n\n".join(partes)


# ---------------------------------------------------------------- escenarios

ESCENARIOS = {
    "handshake_http": {"nombre": "Conexión TCP y petición HTTP", "nivel": "Básico",
                       "temas": "handshake de 3 vías, puertos, HTTP GET, códigos de estado, cierre FIN"},
    "dns": {"nombre": "Consultas DNS", "nivel": "Básico",
            "temas": "consultas y respuestas DNS, registros A, NXDOMAIN, IDs de transacción"},
    "dhcp": {"nombre": "DHCP (DORA)", "nivel": "Básico",
             "temas": "Discover, Offer, Request, ACK, IP asignada, servidor, gateway, lease"},
    "arp_icmp": {"nombre": "ARP y ping", "nivel": "Básico",
                 "temas": "ARP request/reply, eco ICMP, TTL, hosts que no responden"},
    "retransmisiones": {"nombre": "Retransmisiones TCP", "nivel": "Intermedio",
                        "temas": "análisis TCP, retransmisiones, tiempos, calidad del enlace"},
    "escaneo": {"nombre": "Escaneo de puertos", "nivel": "Intermedio",
                "temas": "SYN scan, puertos abiertos (SYN/ACK) y cerrados (RST), identificar al atacante"},
    "ftp_claro": {"nombre": "Credenciales en texto claro (FTP)", "nivel": "Intermedio",
                  "temas": "protocolos inseguros, USER/PASS, seguir flujo TCP"},
    "arp_spoof": {"nombre": "ARP spoofing", "nivel": "Avanzado",
                  "temas": "ARP gratuito, MAC duplicada, suplantación del gateway, man-in-the-middle"},
    "traceroute": {"nombre": "Traceroute e ICMP de error", "nivel": "Intermedio",
                   "temas": "TTL, ICMP time exceeded, port unreachable, saltos, mensajes ICMP que llevan el paquete original"},
    "http_basic": {"nombre": "HTTP con autenticación básica", "nivel": "Intermedio",
                   "temas": "401 Unauthorized, encabezado Authorization, Base64 no es cifrado, credenciales"},
    "vlan": {"nombre": "Troncal con VLANs (802.1Q)", "nivel": "Intermedio",
             "temas": "etiqueta 802.1Q, VLAN ID, prioridad (PCP/CoS), tráfico por VLAN"},
    "tls": {"nombre": "Handshake TLS y SNI", "nivel": "Avanzado",
            "temas": "Client Hello, Server Hello, SNI, versión negociada, cipher suite, datos cifrados"},
    "zero_window": {"nombre": "Ventana TCP en cero", "nivel": "Avanzado",
                    "temas": "control de flujo, window size, zero window, window update, receptor lento"},
    "syn_flood": {"nombre": "SYN flood (DoS)", "nivel": "Avanzado",
                  "temas": "medias conexiones, IPs falsas, SYN sin ACK, servidor saturado"},
    "dns_tunel": {"nombre": "Exfiltración por DNS (túnel)", "nivel": "Experto",
                  "temas": "subdominios largos codificados, consultas TXT, un solo dominio, volumen anormal"},
    "dhcp_starvation": {"nombre": "DHCP starvation", "nivel": "Experto",
                        "temas": "muchos Discover con MACs falsas, pool agotado, servidor que deja de ofrecer"},
    "beaconing": {"nombre": "Beaconing de malware (C2)", "nivel": "Experto",
                  "temas": "conexiones periódicas, intervalo fijo, mismo Host y URI, comando y control"},
    "ssh_bruta": {"nombre": "Fuerza bruta a SSH", "nivel": "Avanzado",
                  "temas": "muchas conexiones cortas al puerto 22, banner del cliente (libssh), una sola IP de origen"},
    "icmp_tunel": {"nombre": "Túnel ICMP (exfiltración por ping)", "nivel": "Experto",
                   "temas": "echo request con datos grandes, Base64 dentro del ping, tamaño normal vs anormal"},
}

NIVELES_WS = ["Básico", "Intermedio", "Avanzado", "Experto"]


def _red(rnd):
    tercer = rnd.randint(1, 250)
    base = rnd.choice(["192.168", "10.10", "172.16"])
    return f"{base}.{tercer}"


def _host(red, n):
    return f"{red}.{n}"


def _p(id_, texto, respuesta, tipo="texto", explicacion="", alternativas=None, conteo=None):
    """conteo: filtro cuya cantidad de paquetes en tshark debe ser igual a la respuesta (doble verificación)."""
    d = {"id": id_, "texto": texto, "respuesta": str(respuesta), "tipo": tipo, "explicacion": explicacion,
         "alternativas": [str(a) for a in (alternativas or [])]}
    if conteo:
        d["conteo"] = conteo
    return d


def _f(id_, texto, referencia, pista=""):
    return {"id": id_, "texto": texto, "referencia": referencia, "pista": pista}


def _e_handshake_http(rnd):
    cap, red = Captura(), _red(rnd)
    cli = (mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90)), rnd.randint(49152, 65000))
    srv_ip = f"{rnd.randint(23, 200)}.{rnd.randint(1, 250)}.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}"
    gw = mac_azar(rnd, "00:1e:bd")
    host = rnd.choice(["intranet.empresa.mx", "portal.universidad.edu", "tienda.ejemplo.com", "api.labredes.net"])
    uri = rnd.choice(["/login", "/index.html", "/productos?id=17", "/api/v1/estado", "/descargas/manual.pdf"])
    codigo, texto = rnd.choice([(200, "OK"), (404, "Not Found"), (302, "Found"), (500, "Internal Server Error")])
    rtt = rnd.choice([0.012, 0.035, 0.08, 0.15])
    s = SesionTCP(cap, cli, (gw, srv_ip, 80), rnd, rtt=rtt)
    hs = s.handshake()
    req = f"GET {uri} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nAccept: */*\r\n\r\n".encode()
    f_req = s.datos(True, req, dt=0.002)
    s.ack(False, dt=rtt / 2)
    cuerpo = f"<html><body>{texto}</body></html>".encode()
    resp = (f"HTTP/1.1 {codigo} {texto}\r\nServer: nginx\r\nContent-Type: text/html\r\n"
            f"Content-Length: {len(cuerpo)}\r\n\r\n").encode() + cuerpo
    f_resp = s.datos(False, resp, dt=0.01)
    s.ack(True)
    s.cierre()
    preguntas = [
        _p("p1", "¿Qué IP inició la conexión TCP (envió el primer SYN)?", cli[1], "ip",
           "El primer paquete con solo SYN lo manda el cliente."),
        _p("p2", "¿Qué puerto de origen usó el cliente?", cli[2], "num", "Puerto efímero del cliente en el SYN."),
        _p("p3", "¿En qué número de frame termina el handshake de 3 vías (el ACK final)?", hs[2], "num",
           "SYN → SYN/ACK → ACK: el tercero completa el handshake."),
        _p("p4", "¿A qué Host (encabezado HTTP) se hizo la petición?", host, "texto",
           "Está en el encabezado 'Host:' del GET."),
        _p("p5", "¿Qué código de estado HTTP respondió el servidor?", codigo, "num",
           f"La respuesta fue 'HTTP/1.1 {codigo} {texto}'."),
        _p("p6", "¿Cuántos milisegundos tardó el servidor en contestar el SYN (aprox., redondeado)?",
           round(rtt * 500), "num", "Diferencia de tiempo entre el SYN y el SYN/ACK (columna Time o tcp.time_delta).",
           alternativas=[round(rtt * 500) - 1, round(rtt * 500) + 1]),
    ]
    filtros = [
        _f("f1", "Muestra solo el primer paquete del handshake (SYN sin ACK).", "tcp.flags.syn==1 && tcp.flags.ack==0",
           "Usa los campos tcp.flags.*"),
        _f("f2", "Muestra solo la petición HTTP.", "http.request", "Hay un campo booleano para peticiones HTTP."),
        _f("f3", "Muestra los paquetes que cierran la conexión (con FIN).", "tcp.flags.fin==1"),
    ]
    return cap, preguntas, filtros, {"cliente": cli[1], "servidor": srv_ip, "frames_clave": [f_req, f_resp]}


def _e_dns(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    dns_mac, dns_ip = mac_azar(rnd, "00:1e:bd"), rnd.choice(["8.8.8.8", "1.1.1.1", _host(red, 1)])
    dominios = rnd.sample(["correo.empresa.mx", "github.com", "netacad.com", "wireshark.org", "cisco.com",
                           "drive.google.com", "campus.universidad.mx", "update.microsoft.com"], 4)
    malo = rnd.choice(["intranett.empresa.mx", "serividor-local.lan", "printer01.oficina"])
    orden = dominios[:2] + [malo] + dominios[2:]
    resp = {}
    ids = {}
    for d in orden:
        tid = rnd.randint(1, 65000)
        ids[d] = tid
        sport = rnd.randint(49152, 65000)
        q = cap.agrega(ethernet(pc_mac, dns_mac, 0x0800, ipv4(pc, dns_ip, 17, udp(pc, dns_ip, sport, 53,
                                                                                dns_consulta(tid, d)))), 0.3)
        if d == malo:
            cap.agrega(ethernet(dns_mac, pc_mac, 0x0800, ipv4(dns_ip, pc, 17, udp(dns_ip, pc, 53, sport,
                                                                                  dns_respuesta(tid, d, [], 3)))),
                       0.02)
        else:
            ips = [f"{rnd.randint(23, 200)}.{rnd.randint(1, 250)}.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}"]
            resp[d] = ips[0]
            cap.agrega(ethernet(dns_mac, pc_mac, 0x0800, ipv4(dns_ip, pc, 17, udp(dns_ip, pc, 53, sport,
                                                                                  dns_respuesta(tid, d, ips)))),
                       0.02)
    pregunta_ip = rnd.choice(dominios)
    preguntas = [
        _p("p1", "¿Qué servidor DNS usa la PC (IP)?", dns_ip, "ip", "Es el destino de las consultas al puerto 53."),
        _p("p2", "¿Cuál fue el primer dominio que se consultó?", orden[0], "texto", "Primera consulta en orden de tiempo."),
        _p("p3", "¿Qué dominio no existe (respuesta NXDOMAIN)?", malo, "texto",
           "La respuesta trae rcode 3 (No such name)."),
        _p("p4", f"¿Qué IP devolvió el DNS para {pregunta_ip}?", resp[pregunta_ip], "ip",
           "Está en la sección Answers de la respuesta."),
        _p("p5", f"¿Qué ID de transacción (en decimal) tuvo la consulta de {orden[1]}?", ids[orden[1]], "num",
           "dns.id; Wireshark lo muestra en hexadecimal y en decimal.",
           alternativas=[hex(ids[orden[1]]), f"0x{ids[orden[1]]:04x}"]),
    ]
    filtros = [
        _f("f1", "Muestra solo las respuestas DNS con error.", "dns.flags.rcode != 0", "Campo dns.flags.rcode"),
        _f("f2", "Muestra solo las consultas (no las respuestas).", "dns.flags.response == 0"),
        _f("f3", f"Muestra la consulta y la respuesta de {orden[-1]}.", f'dns.qry.name == "{orden[-1]}"'),
    ]
    return cap, preguntas, filtros, {}


def _e_dhcp(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac = mac_azar(rnd, "3c:52:82")
    srv_mac, srv = mac_azar(rnd, "00:1e:bd"), _host(red, 1)
    asignada = _host(red, rnd.randint(50, 200))
    gw = _host(red, 1)
    lease = rnd.choice([3600, 28800, 86400])
    mascara = "255.255.255.0"
    xid = rnd.randint(1, 2**31)
    bc = "ff:ff:ff:ff:ff:ff"
    from struct import pack
    op_srv = {54: ip(srv), 51: pack("!I", lease), 1: ip(mascara), 3: ip(gw), 6: ip("8.8.8.8")}
    d = cap.agrega(ethernet(pc_mac, bc, 0x0800, ipv4("0.0.0.0", "255.255.255.255", 17, udp(
        "0.0.0.0", "255.255.255.255", 68, 67, dhcp(1, xid, pc_mac, 1, opciones={55: bytes([1, 3, 6])})),
        ttl=128)), 0.5)
    o = cap.agrega(ethernet(srv_mac, bc, 0x0800, ipv4(srv, "255.255.255.255", 17, udp(
        srv, "255.255.255.255", 67, 68, dhcp(2, xid, pc_mac, 2, yiaddr=asignada, siaddr=srv, opciones=op_srv)))),
        0.003)
    r = cap.agrega(ethernet(pc_mac, bc, 0x0800, ipv4("0.0.0.0", "255.255.255.255", 17, udp(
        "0.0.0.0", "255.255.255.255", 68, 67, dhcp(1, xid, pc_mac, 3, opciones={50: ip(asignada), 54: ip(srv)})),
        ttl=128)), 0.01)
    a = cap.agrega(ethernet(srv_mac, bc, 0x0800, ipv4(srv, "255.255.255.255", 17, udp(
        srv, "255.255.255.255", 67, 68, dhcp(2, xid, pc_mac, 5, yiaddr=asignada, siaddr=srv, opciones=op_srv)))),
        0.003)
    preguntas = [
        _p("p1", "¿Qué IP le asignó el servidor a la PC?", asignada, "ip", "Campo 'Your (client) IP address' del ACK."),
        _p("p2", "¿Cuál es la IP del servidor DHCP?", srv, "ip", "Opción 54 (DHCP Server Identifier)."),
        _p("p3", "¿Cuántos segundos dura el préstamo (lease)?", lease, "num", "Opción 51 del Offer/ACK."),
        _p("p4", "¿Qué gateway (router) le entrega el servidor?", gw, "ip", "Opción 3 (Router)."),
        _p("p5", "¿En qué número de frame está el DHCP Request?", r, "num", "D-O-R-A: el tercero es el Request."),
        _p("p6", "¿Qué MAC tiene la PC que pide dirección?", pc_mac, "mac", "Client MAC address del Discover."),
    ]
    filtros = [
        _f("f1", "Muestra solo los mensajes que envía el cliente (Discover y Request).",
           "dhcp.option.dhcp == 1 || dhcp.option.dhcp == 3", "En Wireshark 3+ el protocolo se llama dhcp."),
        _f("f2", "Muestra solo el ACK.", "dhcp.option.dhcp == 5"),
        _f("f3", "Muestra todo lo que viene del servidor.", f"ip.src == {srv}"),
    ]
    return cap, preguntas, filtros, {"frames": [d, o, r, a]}


def _e_arp_icmp(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    destinos = sorted(rnd.sample(range(2, 20), 4))
    vivos = sorted(rnd.sample(destinos, 2))
    macs = {n: mac_azar(rnd, "00:50:56") for n in destinos}
    ttl = rnd.choice([64, 128, 255])
    bc, cero = "ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"
    ident = rnd.randint(1, 60000)
    sin_resp = 0
    for n in destinos:
        dst = _host(red, n)
        cap.agrega(ethernet(pc_mac, bc, 0x0806, arp(1, pc_mac, pc, cero, dst)), 0.2)
        if n in vivos:
            cap.agrega(ethernet(macs[n], pc_mac, 0x0806, arp(2, macs[n], dst, pc_mac, pc)), 0.001)
            for sq in range(1, 3):
                cap.agrega(ethernet(pc_mac, macs[n], 0x0800, ipv4(pc, dst, 1, icmp_eco(8, ident, sq))), 0.01)
                cap.agrega(ethernet(macs[n], pc_mac, 0x0800, ipv4(dst, pc, 1, icmp_eco(0, ident, sq), ttl=ttl)),
                           0.001)
        else:
            sin_resp += 1
            cap.agrega(ethernet(pc_mac, bc, 0x0806, arp(1, pc_mac, pc, cero, dst)), 1.0)
    preguntas = [
        _p("p1", "¿Cuántos hosts sí respondieron al ARP?", len(vivos), "num", "Cuenta los ARP reply (opcode 2).",
           conteo="arp.opcode == 2"),
        _p("p2", f"¿Qué MAC tiene {_host(red, vivos[0])}?", macs[vivos[0]], "mac", "Está en el ARP reply de esa IP."),
        _p("p3", "¿Qué TTL traen las respuestas ICMP?", ttl, "num",
           "Campo ip.ttl de los Echo reply; da pista del sistema operativo."),
        _p("p4", "¿Cuál es la IP de la PC que hace los pings?", pc, "ip", "Origen de los ARP request y Echo request."),
        _p("p5", f"¿Cuántas IPs no contestaron nada?", sin_resp, "num", "ARP request repetidos sin reply."),
    ]
    filtros = [
        _f("f1", "Muestra solo las respuestas ARP.", "arp.opcode == 2"),
        _f("f2", "Muestra solo los Echo reply.", "icmp.type == 0"),
        _f("f3", f"Muestra solo el tráfico de la IP {_host(red, vivos[-1])} (cualquier protocolo).",
           f"ip.addr == {_host(red, vivos[-1])} || arp.dst.proto_ipv4 == {_host(red, vivos[-1])} || "
           f"arp.src.proto_ipv4 == {_host(red, vivos[-1])}", "Ojo: ARP no tiene capa IP."),
    ]
    return cap, preguntas, filtros, {}


def _e_retransmisiones(rnd):
    cap, red = Captura(), _red(rnd)
    cli = (mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90)), rnd.randint(49152, 65000))
    srv = (mac_azar(rnd, "00:1e:bd"), _host(red, rnd.randint(200, 250)), rnd.choice([445, 8080, 3306]))
    s = SesionTCP(cap, cli, srv, rnd, rtt=0.01)
    s.handshake()
    n_retx = 0
    bloques = rnd.randint(5, 8)
    perdidos = set(rnd.sample(range(bloques), rnd.randint(2, 3)))
    for i in range(bloques):
        payload = bytes(rnd.getrandbits(8) for _ in range(rnd.choice([536, 1024, 1460])))
        s.datos(False, payload, dt=0.004)
        if i in perdidos:
            s.retransmite(False, payload, dt=0.25)
            n_retx += 1
        s.ack(True, dt=0.005)
    s.cierre()
    preguntas = [
        _p("p1", "¿Cuántas retransmisiones hay en la captura?", n_retx, "num",
           "Wireshark las marca en el análisis TCP (Expert Info).", conteo="tcp.analysis.retransmission"),
        _p("p2", "¿Qué IP es la que tiene que retransmitir?", srv[1], "ip", "Las retransmisiones salen del servidor."),
        _p("p3", "¿Qué puerto de servidor se usa?", srv[2], "num", "Puerto destino del SYN."),
    ]
    filtros = [
        _f("f1", "Muestra solo las retransmisiones.", "tcp.analysis.retransmission",
           "Wireshark tiene campos tcp.analysis.*"),
        _f("f2", "Muestra solo los segmentos que llevan datos.", "tcp.len > 0"),
    ]
    return cap, preguntas, filtros, {}


def _e_escaneo(rnd):
    cap, red = Captura(), _red(rnd)
    at_mac, atac = mac_azar(rnd, "08:00:27"), _host(red, rnd.randint(100, 199))
    v_mac, victima = mac_azar(rnd, "00:50:56"), _host(red, rnd.randint(2, 20))
    puertos = sorted(rnd.sample([21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3306, 3389, 5900, 8080], 9))
    abiertos = sorted(rnd.sample(puertos, 3))
    sport = rnd.randint(40000, 60000)
    ident = rnd.randint(1, 50000)
    for p_ in puertos:
        seq = rnd.randint(1, 2**31)
        ident += 1
        cap.agrega(ethernet(at_mac, v_mac, 0x0800, ipv4(atac, victima, 6, tcp(atac, victima, sport, p_, seq, 0, SYN,
                                                                               ventana=1024, mss=True),
                                                        ident=ident, ttl=44)), 0.003)
        if p_ in abiertos:
            sseq = rnd.randint(1, 2**31)
            cap.agrega(ethernet(v_mac, at_mac, 0x0800, ipv4(victima, atac, 6, tcp(
                victima, atac, p_, sport, sseq, seq + 1, SYN | ACK, mss=True))), 0.0005)
            cap.agrega(ethernet(at_mac, v_mac, 0x0800, ipv4(atac, victima, 6, tcp(
                atac, victima, sport, p_, seq + 1, 0, RST, ventana=0), ident=ident, ttl=44)), 0.0003)
        else:
            cap.agrega(ethernet(v_mac, at_mac, 0x0800, ipv4(victima, atac, 6, tcp(
                victima, atac, p_, sport, 0, seq + 1, RST | ACK, ventana=0))), 0.0005)
    preguntas = [
        _p("p1", "¿Qué IP está haciendo el escaneo?", atac, "ip", "Es la que manda muchos SYN a puertos distintos."),
        _p("p2", "¿Qué IP es la víctima?", victima, "ip", "Destino de los SYN."),
        _p("p3", "¿Cuántos puertos se escanearon?", len(puertos), "num", "Cuenta los SYN distintos.",
           conteo="tcp.flags.syn==1 && tcp.flags.ack==0"),
        _p("p4", "Escribe los puertos ABIERTOS separados por comas, de menor a mayor.",
           ",".join(map(str, abiertos)), "lista", "Abiertos = respondieron SYN/ACK; cerrados = RST/ACK."),
        _p("p5", "¿Qué TTL traen los paquetes del atacante?", 44, "num", "ip.ttl de los SYN del escaneo."),
    ]
    filtros = [
        _f("f1", "Muestra solo las respuestas de puertos abiertos.", "tcp.flags.syn==1 && tcp.flags.ack==1"),
        _f("f2", "Muestra solo las respuestas de puertos cerrados.",
           f"ip.src == {victima} && tcp.flags.reset==1"),
        _f("f3", "Muestra los SYN del escaneo hacia puertos menores a 1024.",
           "tcp.flags.syn==1 && tcp.flags.ack==0 && tcp.dstport < 1024"),
    ]
    return cap, preguntas, filtros, {}


def _e_ftp_claro(rnd):
    cap, red = Captura(), _red(rnd)
    cli = (mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90)), rnd.randint(49152, 65000))
    srv = (mac_azar(rnd, "00:1e:bd"), _host(red, rnd.randint(200, 250)), 21)
    usuario = rnd.choice(["admin", "j.perez", "respaldo", "soporte", "invitado"])
    clave = rnd.choice(["Cisco123!", "Verano2026", "qwerty99", "P@ssw0rd", "redes2026"])
    archivo = rnd.choice(["nomina.xlsx", "backup.cfg", "clientes.csv", "router-config.txt"])
    s = SesionTCP(cap, cli, srv, rnd, rtt=0.008)
    s.handshake()
    for desde, linea in ((False, "220 (vsFTPd 3.0.3)"), (True, f"USER {usuario}"),
                         (False, "331 Please specify the password."), (True, f"PASS {clave}"),
                         (False, "230 Login successful."), (True, "SYST"), (False, "215 UNIX Type: L8"),
                         (True, f"RETR {archivo}"), (False, "150 Opening BINARY mode data connection."),
                         (False, "226 Transfer complete."), (True, "QUIT"), (False, "221 Goodbye.")):
        s.datos(desde, (linea + "\r\n").encode(), dt=0.02)
        s.ack(not desde)
    s.cierre()
    preguntas = [
        _p("p1", "¿Qué usuario inició sesión?", usuario, "texto", "Comando USER en texto claro."),
        _p("p2", "¿Qué contraseña se usó?", clave, "exacto", "Comando PASS: FTP no cifra nada."),
        _p("p3", "¿Qué archivo se descargó?", archivo, "texto", "Comando RETR."),
        _p("p4", "¿Qué código de respuesta confirma que el login fue exitoso?", 230, "num", "230 Login successful."),
    ]
    filtros = [
        _f("f1", "Muestra solo el paquete con la contraseña.", 'ftp.request.command == "PASS"'),
        _f("f2", "Muestra solo los paquetes del servidor que traen un código de respuesta FTP (220, 331…).",
           "ftp.response.code", "Cada respuesta FTP tiene un campo de código."),
    ]
    return cap, preguntas, filtros, {}


def _e_arp_spoof(rnd):
    cap, red = Captura(), _red(rnd)
    gw_ip, gw_mac = _host(red, 1), mac_azar(rnd, "00:1e:bd")
    at_ip, at_mac = _host(red, rnd.randint(100, 199)), mac_azar(rnd, "08:00:27")
    victimas = [(_host(red, n), mac_azar(rnd, "3c:52:82")) for n in rnd.sample(range(20, 90), 2)]
    bc, cero = "ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"
    # tráfico normal: la víctima pregunta por el gateway y el gateway real contesta
    v_ip, v_mac = victimas[0]
    cap.agrega(ethernet(v_mac, bc, 0x0806, arp(1, v_mac, v_ip, cero, gw_ip)), 0.1)
    cap.agrega(ethernet(gw_mac, v_mac, 0x0806, arp(2, gw_mac, gw_ip, v_mac, v_ip)), 0.001)
    cap.agrega(ethernet(v_mac, gw_mac, 0x0800, ipv4(v_ip, "8.8.8.8", 1, icmp_eco(8, 7, 1))), 0.01)
    # ataque: respuestas ARP no pedidas diciendo que el gateway es la MAC del atacante
    primer_falso = None
    n_falsos = rnd.randint(4, 7)
    for i in range(n_falsos):
        for vip, vmac in victimas:
            f = cap.agrega(ethernet(at_mac, vmac, 0x0806, arp(2, at_mac, gw_ip, vmac, vip)), 0.5 if i else 0.3)
            primer_falso = primer_falso or f
    cap.agrega(ethernet(v_mac, at_mac, 0x0800, ipv4(v_ip, "8.8.8.8", 1, icmp_eco(8, 7, 2))), 0.01)
    preguntas = [
        _p("p1", "¿Qué IP está siendo suplantada?", gw_ip, "ip", "Es la IP que aparece con dos MAC distintas."),
        _p("p2", "¿Cuál es la MAC del atacante?", at_mac, "mac", "La MAC que anuncia la IP del gateway sin que nadie pregunte."),
        _p("p3", "¿Cuál es la MAC legítima del gateway?", gw_mac, "mac", "La primera respuesta ARP, que sí fue pedida."),
        _p("p4", "¿En qué número de frame empieza el ataque?", primer_falso, "num", "Primer ARP reply no solicitado."),
        _p("p5", "¿Cuántas víctimas recibe respuestas falsas?", len(victimas), "num", "Cuenta los destinos de los ARP falsos."),
    ]
    filtros = [
        _f("f1", "Muestra los ARP reply que dicen ser el gateway pero con la MAC del atacante.",
           f"arp.opcode == 2 && arp.src.proto_ipv4 == {gw_ip} && arp.src.hw_mac == {at_mac}"),
        _f("f2", "Usa el detector de Wireshark: muestra los paquetes con IP duplicada detectada.",
           "arp.duplicate-address-frame", "Wireshark lo marca solo; busca en arp.duplicate-*"),
    ]
    return cap, preguntas, filtros, {}


_GENERADORES = {
    "handshake_http": _e_handshake_http, "dns": _e_dns, "dhcp": _e_dhcp, "arp_icmp": _e_arp_icmp,
    "retransmisiones": _e_retransmisiones, "escaneo": _e_escaneo, "ftp_claro": _e_ftp_claro,
    "arp_spoof": _e_arp_spoof,
}


# ---------------------------------------------------------------- escenarios nivel WCA
def _ip_publica(rnd):
    return f"{rnd.choice([23, 34, 52, 104, 142, 151, 172, 185])}.{rnd.randint(1, 250)}.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}"


def _icmp(tipo, codigo, resto=b"\0\0\0\0", datos=b""):
    msg = struct.pack("!BBH", tipo, codigo, 0) + resto + datos
    return msg[:2] + struct.pack("!H", _checksum(msg)) + msg[4:]


def _e_traceroute(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    gw_mac = mac_azar(rnd, "00:1e:bd")
    destino = _ip_publica(rnd)
    saltos = [_host(red, 1)] + [f"10.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.1" for _ in range(rnd.randint(2, 4))]
    sport = rnd.randint(40000, 60000)
    for ttl in range(1, len(saltos) + 2):
        dport = 33433 + ttl
        sonda = ipv4(pc, destino, 17, udp(pc, destino, sport, dport, b"\0" * 24), ttl=ttl, ident=1000 + ttl)
        cap.agrega(ethernet(pc_mac, gw_mac, 0x0800, sonda), 0.05)
        original = sonda[:28]  # cabecera IP + 8 bytes de UDP, como manda el RFC
        if ttl <= len(saltos):
            cap.agrega(ethernet(gw_mac, pc_mac, 0x0800, ipv4(saltos[ttl - 1], pc, 1, _icmp(11, 0, datos=original), ttl=255 - ttl)), 0.01 * ttl)
        else:
            cap.agrega(ethernet(gw_mac, pc_mac, 0x0800, ipv4(destino, pc, 1, _icmp(3, 3, datos=original), ttl=50)), 0.03)
    preguntas = [
        _p("p1", "¿A qué IP le está haciendo traceroute la PC?", destino, "ip", "Es el destino de las sondas UDP."),
        _p("p2", "¿Qué IP tiene el SEGUNDO salto (router)?", saltos[1], "ip", "El que responde Time exceeded a la sonda con TTL=2."),
        _p("p3", "¿Cuántos routers hay antes del destino?", len(saltos), "num", "Cuenta los ICMP Time exceeded (tipo 11).", conteo="icmp.type == 11"),
        _p("p4", "¿Qué código ICMP manda el destino al final?", 3, "num", "Destination unreachable (tipo 3) con código 3 = puerto inalcanzable: así sabe traceroute que llegó."),
        _p("p5", "¿Qué TTL lleva la primera sonda?", 1, "num", "traceroute empieza con TTL 1 y lo sube de uno en uno."),
    ]
    filtros = [
        _f("f1", "Muestra solo los mensajes ICMP Time exceeded.", "icmp.type == 11"),
        _f("f2", "Muestra solo el ICMP de puerto inalcanzable.", "icmp.type == 3 && icmp.code == 3"),
        _f("f3", "Muestra solo las sondas UDP que salen de la PC (sin los ICMP).", "udp && !icmp",
           "Ojo: los ICMP de error llevan copiada la cabecera UDP original, así que 'udp' solo también los muestra."),
    ]
    return cap, preguntas, filtros, {}


def _e_http_basic(rnd):
    import base64 as b64
    cap, red = Captura(), _red(rnd)
    cli = (mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90)), rnd.randint(49152, 65000))
    srv = (mac_azar(rnd, "00:1e:bd"), _host(red, rnd.randint(200, 250)), rnd.choice([80, 8080]))
    usuario = rnd.choice(["admin", "camara", "operador", "soporte"])
    clave = rnd.choice(["admin123", "Camara2026", "123456", "Sw1tch!"])
    uri = rnd.choice(["/admin/", "/config", "/cgi-bin/panel", "/router/status"])
    host = f"{srv[1]}:{srv[2]}" if srv[2] != 80 else srv[1]
    s = SesionTCP(cap, cli, srv, rnd, rtt=0.004)
    s.handshake()
    s.datos(True, f"GET {uri} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: curl/8.5\r\n\r\n".encode())
    s.datos(False, b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="Panel"\r\nContent-Length: 0\r\n\r\n')
    tok = b64.b64encode(f"{usuario}:{clave}".encode()).decode()
    s.datos(True, f"GET {uri} HTTP/1.1\r\nHost: {host}\r\nAuthorization: Basic {tok}\r\nUser-Agent: curl/8.5\r\n\r\n".encode(), dt=1.2)
    s.datos(False, b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 13\r\n\r\n<h1>Panel</h1>")
    s.ack(True)
    s.cierre()
    preguntas = [
        _p("p1", "¿Qué código responde el servidor la PRIMERA vez?", 401, "num", "401 Unauthorized + WWW-Authenticate: pide credenciales."),
        _p("p2", "¿Qué usuario se usó?", usuario, "texto", "Expande Authorization: Wireshark decodifica el Base64 en 'Credentials'."),
        _p("p3", "¿Qué contraseña se usó?", clave, "exacto", "Base64 NO es cifrado: cualquiera que vea el tráfico la lee."),
        _p("p4", "¿Qué ruta (URI) está protegida?", uri, "exacto", "Request URI del GET."),
        _p("p5", "¿A qué puerto TCP se conecta el cliente?", srv[2], "num", "Puerto destino del SYN."),
    ]
    filtros = [
        _f("f1", "Muestra solo la petición que lleva credenciales.", "http.authorization", "Hay un campo para el encabezado Authorization."),
        _f("f2", "Muestra solo la respuesta que pidió autenticación.", "http.response.code == 401"),
    ]
    return cap, preguntas, filtros, {}


def _e_vlan(rnd):
    cap = Captura()
    v_dns, v_icmp, v_voz = rnd.sample([10, 20, 30, 40, 50, 99], 3)
    pcp_voz = 5
    sw1, sw2 = mac_azar(rnd, "00:1b:54"), mac_azar(rnd, "00:1b:55")

    def tagged(src, dst, vid, tipo, payload, pcp=0):
        tag = struct.pack("!HH", (pcp << 13) | vid, tipo)
        trama = mac(dst) + mac(src) + b"\x81\x00" + tag + payload
        return trama + b"\0" * max(0, 64 - len(trama))
    a1, a2 = f"192.168.{v_dns}.{rnd.randint(10, 90)}", f"192.168.{v_dns}.1"
    n_dns = 0
    for k in range(3):
        tid = rnd.randint(1, 60000)
        nombre = rnd.choice(["intranet.local", "cisco.com", "netacad.com"])
        cap.agrega(tagged(sw1, sw2, v_dns, 0x0800, ipv4(a1, a2, 17, udp(a1, a2, 50000 + k, 53, dns_consulta(tid, nombre)))), 0.2)
        cap.agrega(tagged(sw2, sw1, v_dns, 0x0800, ipv4(a2, a1, 17, udp(a2, a1, 53, 50000 + k, dns_respuesta(tid, nombre, ["10.1.1.1"])))), 0.01)
        n_dns += 2
    b1, b2 = f"192.168.{v_icmp}.{rnd.randint(10, 90)}", f"192.168.{v_icmp}.{rnd.randint(100, 200)}"
    n_icmp = rnd.randint(2, 4)
    for sq in range(1, n_icmp + 1):
        cap.agrega(tagged(sw1, sw2, v_icmp, 0x0800, ipv4(b1, b2, 1, icmp_eco(8, 77, sq))), 0.3)
        cap.agrega(tagged(sw2, sw1, v_icmp, 0x0800, ipv4(b2, b1, 1, icmp_eco(0, 77, sq))), 0.001)
    c1, c2 = f"192.168.{v_voz}.{rnd.randint(10, 90)}", f"192.168.{v_voz}.{rnd.randint(100, 200)}"
    for k in range(4):
        cap.agrega(tagged(sw1, sw2, v_voz, 0x0800, ipv4(c1, c2, 17, udp(c1, c2, 16384, 16386, bytes(rnd.getrandbits(8) for _ in range(160)))), pcp=pcp_voz), 0.02)
    total_icmp = 2 * n_icmp
    preguntas = [
        _p("p1", "¿En qué VLAN viaja el tráfico DNS?", v_dns, "num", "Abre la capa 802.1Q Virtual LAN: campo ID."),
        _p("p2", "¿Cuántas tramas van en la VLAN del ping (ICMP)?", total_icmp, "num", "Filtra por esa VLAN y cuenta.", conteo=f"vlan.id == {v_icmp}"),
        _p("p3", "¿Qué prioridad (PCP / CoS) llevan las tramas de voz?", pcp_voz, "num", "Campo Priority de la etiqueta 802.1Q; 5 es la típica de voz."),
        _p("p4", "¿Qué valor de EtherType (hex) indica que la trama trae etiqueta 802.1Q?", "0x8100", "texto", "En la cabecera Ethernet, Type = 0x8100.",
           alternativas=["8100"]),
    ]
    filtros = [
        _f("f1", "Muestra solo el tráfico de la VLAN de voz.", f"vlan.id == {v_voz}"),
        _f("f2", "Muestra solo las tramas con prioridad 5.", "vlan.priority == 5"),
    ]
    return cap, preguntas, filtros, {}


def _tls_ext(tipo, datos):
    return struct.pack("!HH", tipo, len(datos)) + datos


def _client_hello(rnd, sni, tls13):
    exts = _tls_ext(0x0000, struct.pack("!HBH", len(sni) + 3, 0, len(sni)) + sni.encode())
    exts += _tls_ext(0x000a, struct.pack("!HHH", 4, 0x001d, 0x0017))
    exts += _tls_ext(0x000d, struct.pack("!HHHH", 6, 0x0403, 0x0804, 0x0401))
    if tls13:
        exts += _tls_ext(0x002b, bytes([4]) + struct.pack("!HH", 0x0304, 0x0303))
        exts += _tls_ext(0x0033, struct.pack("!HHH", 36, 0x001d, 32) + bytes(rnd.getrandbits(8) for _ in range(32)))
    suites = [0x1301, 0x1302, 0xc02b, 0xc02f, 0xc030] if tls13 else [0xc02b, 0xc02f, 0xc030, 0x009c]
    cuerpo = struct.pack("!H", 0x0303) + bytes(rnd.getrandbits(8) for _ in range(32)) + bytes([32]) + bytes(rnd.getrandbits(8) for _ in range(32))
    cuerpo += struct.pack("!H", 2 * len(suites)) + b"".join(struct.pack("!H", x) for x in suites) + b"\x01\x00"
    cuerpo += struct.pack("!H", len(exts)) + exts
    hs = b"\x01" + struct.pack("!I", len(cuerpo))[1:] + cuerpo
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def _server_hello(rnd, suite, tls13):
    exts = _tls_ext(0x002b, struct.pack("!H", 0x0304)) if tls13 else b""
    cuerpo = struct.pack("!H", 0x0303) + bytes(rnd.getrandbits(8) for _ in range(32)) + bytes([32]) + bytes(rnd.getrandbits(8) for _ in range(32))
    cuerpo += struct.pack("!H", suite) + b"\x00" + struct.pack("!H", len(exts)) + exts
    hs = b"\x02" + struct.pack("!I", len(cuerpo))[1:] + cuerpo
    rec = b"\x16\x03\x03" + struct.pack("!H", len(hs)) + hs
    if tls13:
        rec += b"\x14\x03\x03\x00\x01\x01"  # change_cipher_spec de compatibilidad
    return rec


SUITES = {0x1301: "TLS_AES_128_GCM_SHA256", 0x1302: "TLS_AES_256_GCM_SHA384",
          0xc02f: "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", 0xc030: "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384"}


def _e_tls(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    gw = mac_azar(rnd, "00:1e:bd")
    sitios = rnd.sample(["banco.ejemplo.mx", "correo.empresa.com", "github.com", "netacad.com", "drive.google.com", "portal.universidad.mx"], 3)
    conexiones = []
    for k, sni in enumerate(sitios):
        tls13 = k != 1  # la segunda conexión es TLS 1.2
        suite = rnd.choice([0x1301, 0x1302]) if tls13 else rnd.choice([0xc02f, 0xc030])
        ip_srv = _ip_publica(rnd)
        s = SesionTCP(cap, (pc_mac, pc, rnd.randint(49152, 65000)), (gw, ip_srv, 443), rnd, rtt=0.03)
        s.handshake()
        f_ch = s.datos(True, _client_hello(rnd, sni, tls13))
        s.datos(False, _server_hello(rnd, suite, tls13), dt=0.03)
        s.datos(True, b"\x17\x03\x03\x00\x30" + bytes(rnd.getrandbits(8) for _ in range(48)), dt=0.01)
        s.datos(False, b"\x17\x03\x03\x00\x40" + bytes(rnd.getrandbits(8) for _ in range(64)), dt=0.02)
        s.ack(True)
        conexiones.append({"sni": sni, "ip": ip_srv, "tls13": tls13, "suite": suite, "frame": f_ch})
    c12 = conexiones[1]
    preguntas = [
        _p("p1", f"¿A qué sitio (SNI) se conectó la PC en la IP {conexiones[0]['ip']}?", conexiones[0]["sni"], "texto",
           "En el Client Hello: Extension server_name. El SNI viaja SIN cifrar (por eso un firewall puede ver a qué sitio vas)."),
        _p("p2", f"¿Qué versión de TLS se negoció con {c12['sni']}? (escribe 1.2 o 1.3)", "1.2", "texto",
           "Si el Server Hello trae la extensión supported_versions = TLS 1.3, es 1.3; si no, vale el campo Version (1.2)."),
        _p("p3", f"¿Qué cipher suite eligió el servidor de {conexiones[2]['sni']}?", SUITES[conexiones[2]["suite"]], "texto",
           "Server Hello → Cipher Suite. El cliente ofrece una lista; el servidor escoge una.", alternativas=[hex(conexiones[2]["suite"])]),
        _p("p4", "¿Cuántos Client Hello hay en la captura?", 3, "num", "Uno por conexión TLS.", conteo="tls.handshake.type == 1"),
    ]
    filtros = [
        _f("f1", "Muestra solo los Client Hello.", "tls.handshake.type == 1"),
        _f("f2", f"Muestra el Client Hello hacia {sitios[2]} usando el SNI.", f'tls.handshake.extensions_server_name == "{sitios[2]}"'),
        _f("f3", "Muestra solo los registros de datos de aplicación (cifrados).", "tls.record.content_type == 23"),
    ]
    return cap, preguntas, filtros, {}


def _e_zero_window(rnd):
    cap, red = Captura(), _red(rnd)
    cli = (mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90)), rnd.randint(49152, 65000))
    srv = (mac_azar(rnd, "00:1e:bd"), _host(red, rnd.randint(200, 250)), rnd.choice([445, 2049, 8080]))
    s = SesionTCP(cap, cli, srv, rnd, rtt=0.002)
    s.handshake()
    ventana = 8192
    n_cero = 0
    bloques = rnd.randint(6, 8)
    for i in range(bloques):
        payload = bytes(rnd.getrandbits(8) for _ in range(1460))
        s.datos(False, payload, dt=0.002)
        ventana = max(0, ventana - 2920 if i >= 2 else ventana)
        # el cliente confirma pero su búfer se va llenando
        seg = tcp(cli[1], srv[1], cli[2], srv[2], s.cseq, s.sseq, ACK, ventana=ventana)
        s.ident += 1
        cap.agrega(ethernet(cli[0], srv[0], 0x0800, ipv4(cli[1], srv[1], 6, seg, ident=s.ident)), 0.003)
        if ventana == 0:
            n_cero += 1
            if n_cero >= 2:
                break
            cap.avanza(0.4)
    # el cliente por fin lee: window update
    seg = tcp(cli[1], srv[1], cli[2], srv[2], s.cseq, s.sseq, ACK, ventana=65535)
    s.ident += 1
    cap.agrega(ethernet(cli[0], srv[0], 0x0800, ipv4(cli[1], srv[1], 6, seg, ident=s.ident)), 0.8)
    s.datos(False, bytes(500), dt=0.002)
    s.ack(True)
    s.cierre()
    preguntas = [
        _p("p1", "¿Qué IP anuncia ventana cero (se le llenó el búfer)?", cli[1], "ip", "Busca 'TCP ZeroWindow' en Info o en Expert Info."),
        _p("p2", "¿Cuántos paquetes con ventana cero hay?", n_cero, "num", "Wireshark los marca con tcp.analysis.zero_window.", conteo="tcp.analysis.zero_window"),
        _p("p3", "¿Qué tamaño de ventana anuncia el cliente cuando se recupera?", 65535, "num", "El 'TCP Window Update' que reabre la ventana."),
        _p("p4", "¿Quién es el lento: el que envía o el que recibe? (escribe emisor o receptor)", "receptor", "texto",
           "Ventana cero = el RECEPTOR no alcanza a leer; la red no es el problema."),
    ]
    filtros = [
        _f("f1", "Muestra solo los paquetes de ventana cero.", "tcp.analysis.zero_window"),
        _f("f2", "Muestra solo el aviso de que la ventana se reabrió.", "tcp.analysis.window_update"),
    ]
    return cap, preguntas, filtros, {}


def _e_syn_flood(rnd):
    cap, red = Captura(), _red(rnd)
    v_mac, victima = mac_azar(rnd, "00:50:56"), _host(red, rnd.randint(2, 20))
    gw = mac_azar(rnd, "00:1e:bd")
    puerto = rnd.choice([80, 443, 8080])
    n = rnd.randint(18, 30)
    origenes = set()
    respondidas = 0
    for k in range(n):
        falsa = f"{rnd.randint(11, 220)}.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}"
        origenes.add(falsa)
        sp, seq = rnd.randint(1024, 65000), rnd.randint(1, 2**31)
        cap.agrega(ethernet(gw, v_mac, 0x0800, ipv4(falsa, victima, 6, tcp(falsa, victima, sp, puerto, seq, 0, SYN, ventana=512),
                                                     ttl=rnd.randint(40, 250), ident=rnd.randint(1, 65000))), 0.001)
        if k % 3 == 0:
            respondidas += 1
            cap.agrega(ethernet(v_mac, gw, 0x0800, ipv4(victima, falsa, 6, tcp(victima, falsa, puerto, sp, rnd.randint(1, 2**31), seq + 1,
                                                                             SYN | ACK, mss=True))), 0.0005)
    preguntas = [
        _p("p1", "¿Qué IP está siendo atacada?", victima, "ip", "Todos los SYN van hacia ella."),
        _p("p2", "¿A qué puerto atacan?", puerto, "num", "Puerto destino de los SYN."),
        _p("p3", "¿Cuántos SYN llegaron?", n, "num", "SYN sin ACK.", conteo="tcp.flags.syn==1 && tcp.flags.ack==0"),
        _p("p4", "¿Cuántas IPs de origen distintas hay en los SYN?", len(origenes), "num",
           "Statistics → Endpoints o Conversations. Tantas IPs distintas y ningún ACK final = IPs falsificadas."),
        _p("p5", "¿Algún atacante completó el handshake? (si / no)", "no", "texto", "No hay un tercer paquete ACK de vuelta: son medias conexiones."),
    ]
    filtros = [
        _f("f1", "Muestra solo los SYN del ataque.", "tcp.flags.syn==1 && tcp.flags.ack==0"),
        _f("f2", "Muestra solo lo que responde la víctima.", f"ip.src == {victima}"),
    ]
    return cap, preguntas, filtros, {}


def _e_dns_tunel(rnd):
    import base64 as b64
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    dns_mac, dns_ip = mac_azar(rnd, "00:1e:bd"), _host(red, 1)
    dominio = rnd.choice(["cdn-sync.net", "update-check.org", "telemetria.xyz", "img-cache.info"])
    secreto = rnd.choice(["usuarios.csv: ana,juan,pedro;claves...", "BACKUP DB nomina 2026 ...", "id_rsa -----BEGIN OPENSSH-----"]) * 3
    trozos = [b64.b32encode(secreto.encode()).decode().rstrip("=").lower()[i:i + 40] for i in range(0, 200, 40)]
    trozos = [t for t in trozos if t]
    normales = rnd.sample(["github.com", "cisco.com", "outlook.office.com", "netacad.com"], 3)
    eventos = [("n", d) for d in normales] + [("t", (i, t)) for i, t in enumerate(trozos)]
    eventos = eventos[:2] + eventos[3:] + eventos[2:3]
    n_tunel = 0
    for tipo, x in eventos:
        tid, sp = rnd.randint(1, 60000), rnd.randint(49152, 65000)
        if tipo == "n":
            q = x
            cap.agrega(ethernet(pc_mac, dns_mac, 0x0800, ipv4(pc, dns_ip, 17, udp(pc, dns_ip, sp, 53, dns_consulta(tid, q)))), 0.4)
            cap.agrega(ethernet(dns_mac, pc_mac, 0x0800, ipv4(dns_ip, pc, 17, udp(dns_ip, pc, 53, sp, dns_respuesta(tid, q, [_ip_publica(rnd)])))), 0.02)
        else:
            i, t = x
            q = f"{t}.{i}.{dominio}"
            n_tunel += 1
            cap.agrega(ethernet(pc_mac, dns_mac, 0x0800, ipv4(pc, dns_ip, 17, udp(pc, dns_ip, sp, 53, dns_consulta(tid, q, 16)))), 0.15)
            cap.agrega(ethernet(dns_mac, pc_mac, 0x0800, ipv4(dns_ip, pc, 17, udp(dns_ip, pc, 53, sp, dns_respuesta(tid, q, [])))), 0.02)
    preguntas = [
        _p("p1", "¿Qué dominio se usa para sacar datos?", dominio, "texto", "Es el que recibe subdominios larguísimos y sin sentido."),
        _p("p2", "¿Qué tipo de registro DNS usan esas consultas? (A, AAAA, TXT, MX…)", "TXT", "texto",
           "Campo Type de la consulta: TXT (16) permite respuestas con texto, por eso lo usan los túneles."),
        _p("p3", "¿Cuántas consultas van a ese dominio?", n_tunel, "num", "Filtra por el dominio y que no sean respuestas.",
           conteo=f'dns.qry.name contains "{dominio}" && dns.flags.response == 0'),
        _p("p4", "¿Qué IP interna está filtrando datos?", pc, "ip", "Origen de esas consultas."),
    ]
    filtros = [
        _f("f1", "Muestra solo las consultas TXT.", "dns.qry.type == 16"),
        _f("f2", "Muestra las consultas con nombres de más de 40 caracteres (sin las respuestas).",
           "len(dns.qry.name) > 40 && dns.flags.response == 0", "Wireshark tiene la función len()."),
    ]
    return cap, preguntas, filtros, {}


def _e_dhcp_starvation(rnd):
    from struct import pack
    cap, red = Captura(), _red(rnd)
    srv_mac, srv = mac_azar(rnd, "00:1e:bd"), _host(red, 1)
    at_mac = mac_azar(rnd, "08:00:27")
    bc = "ff:ff:ff:ff:ff:ff"
    pool = rnd.randint(6, 10)
    n = pool + rnd.randint(4, 8)
    ofertas = 0
    for k in range(n):
        falsa = mac_azar(rnd, rnd.choice(["02:11:22", "0a:bb:cc", "12:34:56"]))
        xid = rnd.randint(1, 2**31)
        cap.agrega(ethernet(falsa, bc, 0x0800, ipv4("0.0.0.0", "255.255.255.255", 17, udp(
            "0.0.0.0", "255.255.255.255", 68, 67, dhcp(1, xid, falsa, 1)), ttl=128)), 0.02)
        if ofertas < pool:
            ofertas += 1
            ip_o = _host(red, 100 + ofertas)
            cap.agrega(ethernet(srv_mac, bc, 0x0800, ipv4(srv, "255.255.255.255", 17, udp(
                srv, "255.255.255.255", 67, 68, dhcp(2, xid, falsa, 2, yiaddr=ip_o, siaddr=srv,
                                                      opciones={54: ip(srv), 51: pack("!I", 3600), 1: ip("255.255.255.0")})))), 0.003)
    preguntas = [
        _p("p1", "¿Cuántos DHCP Discover hay?", n, "num", "Filtra por el tipo de mensaje DHCP 1.", conteo="dhcp.option.dhcp == 1"),
        _p("p2", "¿Cuántas ofertas (Offer) alcanzó a mandar el servidor antes de quedarse sin IPs?", ofertas, "num",
           "Después ya no contesta: el pool se agotó.", conteo="dhcp.option.dhcp == 2"),
        _p("p3", "¿Cuál es la IP del servidor DHCP?", srv, "ip", "Origen de los Offer."),
        _p("p4", "¿Qué función del switch frena este ataque?", "DHCP snooping", "texto",
           "DHCP snooping con límite de tasa por puerto (ip dhcp snooping limit rate) y port security.",
           alternativas=["dhcp snooping", "snooping", "port security", "port-security"]),
    ]
    filtros = [
        _f("f1", "Muestra solo los Discover.", "dhcp.option.dhcp == 1"),
        _f("f2", "Muestra solo lo que manda el servidor.", f"ip.src == {srv}"),
    ]
    return cap, preguntas, filtros, {}


_GENERADORES.update({
    "traceroute": _e_traceroute, "http_basic": _e_http_basic, "vlan": _e_vlan, "tls": _e_tls,
    "zero_window": _e_zero_window, "syn_flood": _e_syn_flood, "dns_tunel": _e_dns_tunel, "dhcp_starvation": _e_dhcp_starvation,
})


def _e_beaconing(rnd):
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    gw = mac_azar(rnd, "00:1e:bd")
    c2 = rnd.choice(["cdn-telemetry.xyz", "update-metrics.top", "static-cache.info", "api-sync.click"])
    c2_ip = _ip_publica(rnd)
    intervalo = rnd.choice([30, 45, 60])
    n = rnd.randint(7, 10)
    ident = f"{rnd.randint(1000, 9999)}"
    normales = [("www.cisco.com", "/c/en/us/index.html"), ("intranet.empresa.mx", "/nomina"), ("www.netacad.com", "/courses"),
                ("docs.python.org", "/3/library/")]
    eventos = [("c2", k * intervalo + rnd.uniform(-1.2, 1.2)) for k in range(n)]
    eventos += [("ok", rnd.uniform(0, n * intervalo)) for _ in range(rnd.randint(4, 6))]
    eventos.sort(key=lambda e: e[1])
    t_prev = 0.0
    for tipo, t in eventos:
        cap.avanza(max(0.05, t - t_prev))
        t_prev = t
        if tipo == "c2":
            host, uri, srv_ip, cuerpo = c2, f"/api/v2/beacon?id={ident}", c2_ip, b'{"cmd":"sleep"}'
        else:
            host, uri = rnd.choice(normales)
            srv_ip, cuerpo = _ip_publica(rnd), b"<html>ok</html>"
        s = SesionTCP(cap, (pc_mac, pc, rnd.randint(49152, 65000)), (gw, srv_ip, 80), rnd, rtt=0.03)
        s.handshake()
        s.datos(True, f"GET {uri} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n\r\n".encode(), dt=0.002)
        s.datos(False, f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(cuerpo)}\r\n\r\n".encode() + cuerpo, dt=0.03)
        s.ack(True)
        s.cierre()
    preguntas = [
        _p("p1", "¿A qué dominio (Host) se conecta el malware para pedir órdenes?", c2, "texto",
           "Es el que se repite como un reloj, siempre con la misma URI corta. Statistics → HTTP → Requests lo deja ver de golpe."),
        _p("p2", "¿Cada cuántos segundos llama a casa (intervalo del beacon)?", intervalo, "num",
           "Resta los tiempos entre peticiones a ese Host (View → Time Display Format → Seconds Since Previous Displayed Packet con el filtro puesto).",
           alternativas=[intervalo - 1, intervalo + 1]),
        _p("p3", "¿Cuántas peticiones hizo al servidor de comando y control?", n, "num", "Filtra por ese Host y solo peticiones.",
           conteo=f'http.request && http.host == "{c2}"'),
        _p("p4", "¿Qué IP interna está infectada?", pc, "ip", "Origen de los beacons."),
    ]
    filtros = [
        _f("f1", "Muestra solo las peticiones HTTP al servidor de comando y control.", f'http.request && http.host == "{c2}"'),
        _f("f2", "Muestra las peticiones cuya URI contiene la palabra beacon.", 'http.request.uri contains "beacon"'),
    ]
    return cap, preguntas, filtros, {}


def _e_ssh_bruta(rnd):
    cap, red = Captura(), _red(rnd)
    at_mac, atac = mac_azar(rnd, "08:00:27"), _ip_publica(rnd)
    gw = mac_azar(rnd, "00:1e:bd")
    srv = (mac_azar(rnd, "00:50:56"), _host(red, rnd.randint(2, 20)), 22)
    n = rnd.randint(12, 20)
    for k in range(n):
        s = SesionTCP(cap, (gw, atac, rnd.randint(40000, 60000)), srv, rnd, rtt=0.06)
        s.handshake()
        s.datos(False, b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.10\r\n", dt=0.01)
        s.datos(True, b"SSH-2.0-libssh2_1.10.0\r\n", dt=0.01)
        s.datos(True, bytes(rnd.getrandbits(8) for _ in range(rnd.randint(180, 260))), dt=0.02)
        s.datos(False, bytes(rnd.getrandbits(8) for _ in range(rnd.randint(300, 420))), dt=0.03)
        s.cierre()
        cap.avanza(rnd.uniform(0.6, 2.0))
    preguntas = [
        _p("p1", "¿Desde qué IP viene el ataque de fuerza bruta?", atac, "ip", "Es la que abre una conexión tras otra al puerto 22."),
        _p("p2", "¿Cuántas conexiones SSH intentó?", n, "num", "Cuenta los SYN hacia el puerto 22.",
           conteo="tcp.flags.syn==1 && tcp.flags.ack==0 && tcp.dstport==22"),
        _p("p3", "¿Qué librería/herramienta usa el cliente según su banner SSH?", "libssh2", "texto",
           "El banner del cliente dice SSH-2.0-libssh2_…: no es un cliente humano (OpenSSH, PuTTY); es lo que usan herramientas automáticas como Hydra.",
           alternativas=["libssh2_1.10.0", "libssh"]),
        _p("p4", "¿Qué servidor SSH (software) tiene la víctima? (solo el nombre)", "OpenSSH", "texto", "Banner del servidor: SSH-2.0-OpenSSH_8.9p1.",
           alternativas=["openssh_8.9p1"]),
    ]
    filtros = [
        _f("f1", "Muestra solo los intentos de conexión (SYN) al puerto 22.", "tcp.flags.syn==1 && tcp.flags.ack==0 && tcp.dstport==22"),
        _f("f2", "Muestra solo los paquetes donde el cliente se presenta con libssh.", 'frame contains "libssh"',
           "Busca el texto dentro del paquete (contains)."),
    ]
    return cap, preguntas, filtros, {}


def _e_icmp_tunel(rnd):
    import base64 as b64
    cap, red = Captura(), _red(rnd)
    pc_mac, pc = mac_azar(rnd, "3c:52:82"), _host(red, rnd.randint(20, 90))
    gw = mac_azar(rnd, "00:1e:bd")
    destino = _ip_publica(rnd)
    secreto = rnd.choice(["clientes_2026.csv|nombre,tarjeta,cp|", "id_rsa|-----BEGIN OPENSSH PRIVATE KEY-----|", "nomina.xlsx|rfc,sueldo|"]) * 80
    datos = b64.b64encode(secreto.encode())
    tam = rnd.choice([400, 448, 512])
    trozos = [datos[i:i + tam] for i in range(0, tam * rnd.randint(6, 10), tam)]
    eventos = [("t", t) for t in trozos] + [("n", None)] * rnd.randint(4, 6)
    rnd.shuffle(eventos)
    ident, seq_t, seq_n, n_t = rnd.randint(1, 60000), 0, 0, 0
    for tipo, x in eventos:
        if tipo == "t":
            seq_t += 1
            n_t += 1
            cap.agrega(ethernet(pc_mac, gw, 0x0800, ipv4(pc, destino, 1, icmp_eco(8, ident, seq_t, x))), rnd.uniform(0.3, 1.5))
            cap.agrega(ethernet(gw, pc_mac, 0x0800, ipv4(destino, pc, 1, icmp_eco(0, ident, seq_t, x), ttl=51)), 0.04)
        else:
            seq_n += 1
            cap.agrega(ethernet(pc_mac, gw, 0x0800, ipv4(pc, "8.8.8.8", 1, icmp_eco(8, 1, seq_n), ttl=128)), rnd.uniform(0.3, 1.5))
            cap.agrega(ethernet(gw, pc_mac, 0x0800, ipv4("8.8.8.8", pc, 1, icmp_eco(0, 1, seq_n), ttl=117)), 0.018)
    preguntas = [
        _p("p1", "¿A qué IP externa van los pings que llevan datos escondidos?", destino, "ip",
           "Los pings normales (a 8.8.8.8) llevan 32 bytes; los del túnel llevan cientos de bytes en Base64."),
        _p("p2", "¿Cuántas solicitudes de eco (echo request) van a esa IP?", n_t, "num", "icmp.type == 8 y ese destino.",
           conteo=f"icmp.type == 8 && ip.dst == {destino}"),
        _p("p3", "¿Cuántos bytes de datos lleva un ping normal de Windows?", 32, "num", "Los de 8.8.8.8: 'abcdefghijklmnopqrstuvw…' = 32 bytes."),
        _p("p4", "¿Qué IP interna está sacando la información?", pc, "ip", "Origen de los pings grandes."),
    ]
    filtros = [
        _f("f1", "Muestra solo las solicitudes de eco anormalmente grandes (más de 200 bytes en total).", "icmp.type == 8 && frame.len > 200"),
        _f("f2", "Muestra todo el tráfico ICMP con esa IP externa (ida y vuelta).", f"icmp && ip.addr == {destino}"),
    ]
    return cap, preguntas, filtros, {}


_GENERADORES.update({"beaconing": _e_beaconing, "ssh_bruta": _e_ssh_bruta, "icmp_tunel": _e_icmp_tunel})


def generar(escenario: str, semilla: int) -> dict:
    rnd = random.Random(semilla)
    cap, preguntas, filtros, extra = _GENERADORES[escenario](rnd)
    info = ESCENARIOS[escenario]
    return {"escenario": escenario, "semilla": semilla, "titulo": info["nombre"], "nivel": info["nivel"],
            "temas": info["temas"], "pcap": cap.bytes(), "paquetes": len(cap.paquetes),
            "preguntas": preguntas, "filtros": filtros}


# ---------------------------------------------------------------- calificación de preguntas

def _norm(v: str, tipo: str) -> str:
    v = (v or "").strip()
    if tipo == "exacto":
        return v
    v = v.lower().strip().rstrip(".")
    if tipo == "mac":
        return re.sub(r"[^0-9a-f]", "", v)
    if tipo == "ip":
        try:
            return str(ipaddress.IPv4Address(v))
        except ValueError:
            return v
    if tipo == "num":
        v = v.replace(" ", "")
        try:
            return str(int(v, 16)) if v.startswith("0x") else str(int(float(v)))
        except ValueError:
            return v
    if tipo == "lista":
        return ",".join(sorted((x.strip() for x in re.split(r"[,\s;]+", v) if x.strip()), key=lambda x: int(x) if x.isdigit() else 0))
    return v


def calificar_respuesta(p: dict, dada: str) -> bool:
    buenas = [p["respuesta"]] + p.get("alternativas", [])
    return any(_norm(dada, p["tipo"]) == _norm(b, p["tipo"]) for b in buenas) and bool((dada or "").strip())


# ---------------------------------------------------------------- captura en vivo y filtros de captura (BPF)
def _exe(nombre: str) -> str | None:
    t = tshark()
    if t:
        p = os.path.join(os.path.dirname(t), nombre + (".exe" if os.name == "nt" else ""))
        if os.path.isfile(p):
            return p
    return shutil.which(nombre)


def _correr(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def interfaz_principal() -> str:
    """Nombre de la interfaz con la ruta por defecto (la que de verdad sale a internet)."""
    if os.name != "nt":
        return ""
    try:
        r = _correr(["powershell", "-NoProfile", "-Command",
                     "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Sort-Object RouteMetric | Select-Object -First 1).InterfaceAlias"], 20)
        return r.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def interfaces() -> list[dict]:
    """[{id, nombre}] según 'tshark -D' (necesita Npcap, que viene con Wireshark)."""
    t = tshark()
    if not t:
        return []
    try:
        r = _correr([t, "-D"], 30)
    except subprocess.TimeoutExpired:
        return []
    out = []
    principal = interfaz_principal()
    for l in r.stdout.splitlines():
        m = re.match(r"(\d+)\.\s+(\S+)(?:\s+\((.+)\))?", l.strip())
        if m:
            nombre = m.group(3) or m.group(2)
            out.append({"id": m.group(1), "nombre": nombre, "dispositivo": m.group(2), "principal": nombre == principal})
    return out


def capturar(interfaz: str, segundos: int, ruta: str, filtro: str = "") -> dict:
    t = tshark()
    if not t:
        return {"ok": False, "error": "No encontré tshark."}
    args = [t, "-i", interfaz, "-a", f"duration:{segundos}", "-q", "-w", ruta]
    if filtro:
        args[3:3] = ["-f", filtro]
    try:
        r = _correr(args, segundos + 30)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "La captura no terminó a tiempo."}
    if not os.path.isfile(ruta) or os.path.getsize(ruta) < 100:
        msg = (r.stderr or "").strip().splitlines()
        return {"ok": False, "error": (msg[-1] if msg else "No se capturó nada") + " (¿Npcap instalado? viene con Wireshark)"}
    return {"ok": True}


def _campo(ruta: str, campo: str, filtro: str = "") -> list[str]:
    args = [tshark(), "-n", "-r", ruta, "-T", "fields", "-e", campo] + (["-Y", filtro] if filtro else [])
    try:
        return [x for x in _correr(args, 90).stdout.splitlines() if x.strip()]
    except subprocess.TimeoutExpired:
        return []


def preguntas_de_captura(ruta: str) -> tuple[list[dict], list[dict], int]:
    """Preguntas con respuesta exacta sacada por tshark de TU captura."""
    from collections import Counter
    frames = _campo(ruta, "frame.number")
    preg, fil = [], []

    def top(lista):
        c = Counter(lista).most_common()
        if not c:
            return None, []
        return c[0][0], [k for k, v in c if v == c[0][1]]
    src = [x.split(",")[0] for x in _campo(ruta, "ip.src")]
    ip_top, empates = top(src)
    if ip_top:
        preg.append(_p("p1", "¿Qué IP envió más paquetes?", ip_top, "ip", "Statistics → Endpoints → IPv4, ordena por Tx Packets.",
                       alternativas=empates))
        fil.append(_f("f1", f"Muestra todo el tráfico de {ip_top} (entrante y saliente).", f"ip.addr == {ip_top}"))
    proto, emp_p = top(_campo(ruta, "_ws.col.Protocol"))
    if proto:
        preg.append(_p("p2", "¿Qué protocolo aparece más veces en la columna Protocol?", proto, "texto",
                       "Ordena por la columna Protocol o usa Statistics → Protocol Hierarchy.", alternativas=emp_p))
    dns_q = _campo(ruta, "dns.qry.name", "dns.flags.response == 0")
    if dns_q:
        dom, emp_d = top(dns_q)
        preg.append(_p("p3", "¿Cuántas consultas DNS (no respuestas) hay?", len(dns_q), "num", "Filtra consultas DNS y mira el contador abajo.",
                       conteo="dns.flags.response == 0"))
        preg.append(_p("p4", "¿Qué nombre se consultó más veces por DNS?", dom, "texto", "dns.qry.name en las consultas.", alternativas=emp_d))
        fil.append(_f("f2", "Muestra solo las consultas DNS.", "dns.flags.response == 0"))
    syns = _campo(ruta, "frame.number", "tcp.flags.syn==1 && tcp.flags.ack==0")
    if syns:
        preg.append(_p("p5", "¿Cuántas conexiones TCP se intentaron abrir (SYN sin ACK)?", len(syns), "num", "El primer paquete de cada handshake.",
                       conteo="tcp.flags.syn==1 && tcp.flags.ack==0"))
        fil.append(_f("f3", "Muestra solo los SYN iniciales.", "tcp.flags.syn==1 && tcp.flags.ack==0"))
    sni = _campo(ruta, "tls.handshake.extensions_server_name", "tls.handshake.type == 1")
    if sni:
        s1, emp_s = top(sni)
        preg.append(_p("p6", "¿A qué sitio (SNI) se hicieron más conexiones TLS?", s1, "texto", "Client Hello → server_name.", alternativas=emp_s))
        fil.append(_f("f4", "Muestra solo los Client Hello de TLS.", "tls.handshake.type == 1"))
    return preg, fil, len(frames)


# ---- máquina virtual BPF: ejecuta el código que compila dumpcap sobre tramas de prueba ----
_CACHE: dict = {}


def _bpf_parse(codigo: list[str]) -> list[tuple]:
    prog = []
    for l in codigo:
        m = re.match(r"\((\d+)\)\s+(\w+)\s*(.*)", l.strip())
        if not m:
            continue
        op, resto = m.group(2), m.group(3)
        jt = re.search(r"jt (\d+)", resto)
        jf = re.search(r"jf (\d+)", resto)
        prog.append((op, resto.split("jt")[0].strip(), int(jt.group(1)) if jt else None, int(jf.group(1)) if jf else None))
    return prog


def _bpf_correr(prog: list[tuple], p: bytes) -> bool:
    A = X = 0
    M = [0] * 16
    pc = 0

    def carga(arg, tam):
        m = re.match(r"\[(?:x\s*\+\s*)?(\d+)\]", arg)
        off = int(m.group(1)) + (X if "x" in arg else 0)
        if off + tam > len(p):
            raise IndexError
        return int.from_bytes(p[off:off + tam], "big")

    def valor(arg):
        arg = arg.strip()
        if arg.startswith("#"):
            return int(arg[1:], 0)
        if arg == "x":
            return X
        raise ValueError(arg)
    try:
        for _ in range(4096):
            op, arg, jt, jf = prog[pc]
            pc += 1
            if op in ("ld", "ldh", "ldb"):
                tam = {"ld": 4, "ldh": 2, "ldb": 1}[op]
                if arg.startswith("#"):
                    A = int(arg[1:], 0)
                elif arg.startswith("M["):
                    A = M[int(arg[2:-1])]
                elif arg == "#pktlen" or arg == "len":
                    A = len(p)
                else:
                    A = carga(arg, tam)
            elif op == "ldx" or op == "ldxb":
                if arg.startswith("4*"):
                    off = int(re.search(r"\[(\d+)\]", arg).group(1))
                    X = 4 * (p[off] & 0xF)
                elif arg.startswith("#"):
                    X = int(arg[1:], 0)
                elif arg.startswith("M["):
                    X = M[int(arg[2:-1])]
                else:
                    X = carga(arg, 1 if op == "ldxb" else 4)
            elif op == "st":
                M[int(arg[2:-1])] = A
            elif op == "stx":
                M[int(arg[2:-1])] = X
            elif op in ("add", "sub", "mul", "div", "and", "or", "lsh", "rsh", "mod", "xor"):
                v = valor(arg)
                A = {"add": A + v, "sub": A - v, "mul": A * v, "div": A // v if v else 0, "and": A & v, "or": A | v,
                     "lsh": A << v, "rsh": A >> v, "mod": A % v if v else 0, "xor": A ^ v}[op] & 0xFFFFFFFF
            elif op == "neg":
                A = (-A) & 0xFFFFFFFF
            elif op == "tax":
                X = A
            elif op == "txa":
                A = X
            elif op == "ja":
                pc = int(arg.strip())
            elif op in ("jeq", "jgt", "jge", "jset"):
                v = valor(arg)
                c = {"jeq": A == v, "jgt": A > v, "jge": A >= v, "jset": bool(A & v)}[op]
                pc = jt if c else jf
            elif op == "ret":
                return valor(arg) != 0 if arg.strip() != "a" else A != 0
            else:
                raise ValueError(op)
    except IndexError:
        return False
    return False


def _tramas_prueba(textos: list[str]) -> list[bytes]:
    """Tramas variadas + paquetes con las IPs, redes y puertos que mencionan los filtros."""
    rnd = random.Random(7)
    if "base" not in _CACHE:
        _CACHE["base"] = [d for e in ("handshake_http", "dns", "dhcp", "arp_icmp", "escaneo", "tls", "vlan", "traceroute", "syn_flood")
                          for sem in (1, 2) for _, d in leer_pcap(generar(e, sem)["pcap"])]
    tramas = list(_CACHE["base"])
    ips = set(re.findall(r"\d+\.\d+\.\d+\.\d+", " ".join(textos)))
    ips = {i if not i.endswith(".0") else i[:-1] + str(rnd.randint(1, 254)) for i in ips} | {"192.168.1.10", "8.8.8.8", "10.0.0.5"}
    puertos = {int(x) for x in re.findall(r"(?<![\d.])(\d{1,5})(?![\d.])", " ".join(textos)) if 0 < int(x) < 65536}
    puertos |= {22, 53, 80, 443, 3389, 1023, 1024, 5000}
    m1, m2 = "3c:52:82:00:00:01", "00:1e:bd:00:00:02"
    for a in ips:
        for b in ("172.16.5.5", "203.0.113.9"):
            for sport, dport in [(rnd.randint(40000, 60000), p) for p in puertos] + [(p, rnd.randint(40000, 60000)) for p in puertos]:
                for s, d in ((a, b), (b, a)):
                    tramas.append(ethernet(m1, m2, 0x0800, ipv4(s, d, 6, tcp(s, d, sport, dport, 1, 0, SYN))))
                    tramas.append(ethernet(m1, m2, 0x0800, ipv4(s, d, 6, tcp(s, d, sport, dport, 1, 1, ACK))))
                    tramas.append(ethernet(m1, m2, 0x0800, ipv4(s, d, 17, udp(s, d, sport, dport, b"x" * 12))))
            tramas.append(ethernet(m1, m2, 0x0800, ipv4(a, b, 1, icmp_eco(8, 1, 1))))
        tramas.append(ethernet(m1, "ff:ff:ff:ff:ff:ff", 0x0806, arp(1, m1, a, "00:00:00:00:00:00", "172.16.5.5")))
    return tramas


def equivalentes_bpf(codigo_a: list[str], codigo_b: list[str], textos: list[str]) -> bool:
    if codigo_a == codigo_b:
        return True
    pa, pb = _bpf_parse(codigo_a), _bpf_parse(codigo_b)
    return all(_bpf_correr(pa, t) == _bpf_correr(pb, t) for t in _tramas_prueba(textos))


def compilar_bpf(filtro: str) -> dict:
    """Compila un filtro de captura con dumpcap (-d) para comprobar que es válido y comparar lo que hace."""
    d = _exe("dumpcap")
    if not d:
        return {"ok": False, "error": "No encontré dumpcap (viene con Wireshark)."}
    if "\n" in filtro or len(filtro) > 300:
        return {"ok": False, "error": "El filtro debe ser de una línea."}
    if "if" not in _CACHE:
        try:  # cualquier interfaz sirve para compilar; se busca una vez
            r0 = _correr([d, "-D"], 30)
            m = re.match(r"(\d+)\.", r0.stdout.strip())
            _CACHE["if"] = m.group(1) if m else None
        except subprocess.TimeoutExpired:
            _CACHE["if"] = None
    if not _CACHE["if"]:
        _CACHE.pop("if", None)
        return {"ok": False, "error": "No hay interfaces de captura (¿Npcap instalado?)."}
    if filtro in _CACHE.setdefault("bpf", {}):
        return _CACHE["bpf"][filtro]
    try:
        r = _correr([d, "-i", _CACHE["if"], "-d", "-f", filtro], 30)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "dumpcap tardó demasiado."}
    codigo = [l for l in r.stdout.splitlines() if re.match(r"\(\d+\)", l.strip())]
    if r.returncode != 0 or not codigo:
        err = [l for l in (r.stderr or "").splitlines() if l.strip()]
        return {"ok": False, "error": "Filtro de captura inválido: " + (err[-1] if err else "error de sintaxis")}
    _CACHE["bpf"][filtro] = {"ok": True, "codigo": codigo}
    return _CACHE["bpf"][filtro]
