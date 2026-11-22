"""Tus laboratorios de Jeremy's IT Lab: los lista y adivina el tema por el nombre del archivo."""
from __future__ import annotations

import os
import re

# palabra clave en el nombre del archivo -> tema de la ruta (el primero que coincida gana)
_CLAVES = [
    (r"router.?on.?a.?stick|roas|inter.?vlan", "roas"),
    (r"\bsvi\b|multilayer|layer ?3 switch", "svi_l3"),
    (r"etherchannel|lacp|pagp", "etherchannel"),
    (r"rapid|rstp|\bstp\b|spanning", "stp"),
    (r"\bdtp\b|\bvtp\b|trunk", "troncales"),
    (r"vlan", "vlans"),
    (r"ospf.*(multi|area)", "ospf_multi"),
    (r"ospf", "ospf"),
    (r"eigrp", "eigrp"),
    (r"\bbgp\b", "bgp"),
    (r"ipv6.*(rout|static|ospf)", "ipv6_routing"),
    (r"ipv6", "ipv6"),
    (r"static|default route|floating", "estaticas"),
    (r"extended acl|standard acl|\bacls?\b", "acl"),
    (r"\bnat\b|\bpat\b", "nat"),
    (r"dhcp snooping|\bdai\b|arp inspection|port.?security", "port_security"),
    (r"dhcp", "dhcp"),
    (r"\bssh\b|device security|password", "ssh_seguridad"),
    (r"hsrp|fhrp|vrrp|glbp", "fhrp"),
    (r"cdp|lldp|ntp|syslog|snmp|dns", "cdp_lldp"),
    (r"subnet|vlsm|ipv4 address|ipv4", "ipv4"),
    (r"switching|mac address|ethernet", "switching"),
    (r"router config|initial config|\bcli\b|configure", "cli"),
    (r"routing|routes", "estaticas"),
]
_IGNORAR = re.compile(r"template|plantilla", re.I)


def carpeta_por_defecto(app_dir: str) -> str:
    return os.path.join(os.path.dirname(app_dir), "1-JITL")


def tema_de(nombre: str) -> str | None:
    n = nombre.lower().replace("_", " ").replace("-", " ")
    for rx, tema in _CLAVES:
        if re.search(rx, n):
            return tema
    return None


def listar(carpeta: str) -> list[dict]:
    if not os.path.isdir(carpeta):
        return []
    out = []
    for raiz, _dirs, archivos in os.walk(carpeta):
        for a in archivos:
            if os.path.splitext(a)[1].lower() not in (".pkt", ".pka") or _IGNORAR.search(a):
                continue
            ruta = os.path.join(raiz, a)
            nombre = os.path.splitext(a)[0]
            m = re.search(r"day\s*0*(\d+)", nombre, re.I)
            titulo = re.sub(r"(?i)^day\s*\d+\s*(lab)?\s*[-–:]?\s*", "", nombre).strip() or nombre
            out.append({
                "archivo": os.path.relpath(ruta, carpeta).replace("\\", "/"),
                "nombre": nombre,
                "titulo": titulo,
                "dia": int(m.group(1)) if m else None,
                "tema": tema_de(nombre),
                "modificado": os.path.getmtime(ruta),
            })
    out.sort(key=lambda x: (x["dia"] is None, x["dia"] or 0, x["nombre"].lower()))
    return out


def ruta_segura(carpeta: str, relativa: str) -> str | None:
    """Solo deja abrir archivos que estén dentro de la carpeta de JITL."""
    base = os.path.realpath(carpeta)
    ruta = os.path.realpath(os.path.join(base, relativa))
    if ruta.startswith(base + os.sep) and os.path.isfile(ruta):
        return ruta
    return None
