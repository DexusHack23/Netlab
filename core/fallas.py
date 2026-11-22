"""Troubleshooting: mete fallas a una red que funciona, por código y no por IA.

Cada falla se comprueba antes de dártela: la verificación que la detecta debe FALLAR con la
configuración averiada y PASAR con la correcta. Si no, se descarta y se intenta otra.
"""
from __future__ import annotations

import copy
import ipaddress
import random
import re

from .checker import Evidence, grade
from .ios_parser import norm_iface

# ---------------------------------------------------------------- utilidades


def _bloques(cfg: str) -> list[list[str]]:
    """Separa la config en bloques: [encabezado, hijos...] o [línea global]."""
    out: list[list[str]] = []
    for raw in (cfg or "").splitlines():
        if not raw.strip():
            continue
        if raw[:1] in (" ", "\t") and out:
            out[-1].append(raw)
        else:
            out.append([raw.rstrip()])
    return out


def _unir(bloques: list[list[str]]) -> str:
    return "\n".join(l for b in bloques for l in b)


def _iface_de(bloque: list[str]) -> str | None:
    m = re.match(r"^interface\s+(\S+)", bloque[0].strip(), re.I)
    return norm_iface(m.group(1)) if m else None


def _otra_ip_misma_red(ip: str, mascara: str, usadas: set[str]) -> str | None:
    try:
        red = ipaddress.IPv4Network(f"{ip}/{mascara}", strict=False)
    except ValueError:
        return None
    candidatos = [h for h in list(red.hosts())[-12:] if str(h) not in usadas and str(h) != ip]
    return str(random.choice(candidatos)) if candidatos else None


# ---------------------------------------------------------------- tipos de falla
# Cada función recibe (práctica, configs{disp: texto}, ips_usadas) y devuelve una lista de
# candidatos: dict(dispositivo, nuevo_config | nuevo_pc, check, pista, explicacion)

def _f_vlan_acceso(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        vlans = sorted({int(m) for m in re.findall(r"switchport access vlan (\d+)", cfg)})
        for i, b in enumerate(bloques):
            iface = _iface_de(b)
            for j, l in enumerate(b):
                m = re.match(r"^(\s*)switchport access vlan (\d+)\s*$", l, re.I)
                if iface and m:
                    actual = int(m.group(2))
                    otras = [v for v in vlans if v != actual] or [actual + 1]
                    nueva = random.choice(otras)
                    bb = copy.deepcopy(bloques)
                    bb[i][j] = f"{m.group(1)}switchport access vlan {nueva}"
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo="puerto_acceso", interfaz=iface, vlan=str(actual),
                                   descripcion=f"{iface} de {d} en la VLAN correcta"),
                        pista="Hay un equipo final que quedó en el segmento equivocado.",
                        explicacion=f"En {d}, {iface} estaba en la VLAN {nueva}; debía estar en la VLAN {actual}."))
    return out


def _f_shutdown(p, cfgs, usadas):
    out = []
    routers = {x["nombre"] for x in p.get("dispositivos", []) if x.get("tipo") == "router"}
    for d, cfg in cfgs.items():
        if d not in routers:
            continue
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            iface = _iface_de(b)
            if not iface or "." in iface:
                continue
            for j, l in enumerate(b):
                if l.strip().lower() == "no shutdown":
                    bb = copy.deepcopy(bloques)
                    bb[i][j] = l.replace("no shutdown", "shutdown")
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo="interfaz_activa", interfaz=iface, descripcion=f"{iface} de {d} encendida"),
                        pista="Revisa el estado de las interfaces de los routers (show ip interface brief).",
                        explicacion=f"En {d}, {iface} estaba apagada (shutdown)."))
    return out


def _f_ip_router(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            iface = _iface_de(b)
            for j, l in enumerate(b):
                m = re.match(r"^(\s*)ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)\s*$", l, re.I)
                if iface and m:
                    nueva = _otra_ip_misma_red(m.group(2), m.group(3), usadas)
                    if not nueva:
                        continue
                    bb = copy.deepcopy(bloques)
                    bb[i][j] = f"{m.group(1)}ip address {nueva} {m.group(3)}"
                    tipo = "subinterfaz" if "." in iface else "ip_interfaz"
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo=tipo, interfaz=iface, ip=m.group(2), mascara=m.group(3),
                                   descripcion=f"IP de {iface} en {d}"),
                        pista="Compara la tabla de direccionamiento con lo que de verdad tiene cada interfaz.",
                        explicacion=f"En {d}, {iface} tenía {nueva}; según la tabla debía ser {m.group(2)}."))
    return out


def _f_troncal(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            iface = _iface_de(b)
            for j, l in enumerate(b):
                if iface and re.match(r"^\s*switchport mode trunk\s*$", l, re.I):
                    bb = copy.deepcopy(bloques)
                    bb[i][j] = l.replace("trunk", "access")
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo="puerto_troncal", interfaz=iface, descripcion=f"{iface} de {d} como troncal"),
                        pista="Algún enlace entre equipos de red no está llevando todas las VLANs.",
                        explicacion=f"En {d}, {iface} estaba en modo access; debía ser troncal."))
    return out


def _f_dot1q(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            iface = _iface_de(b)
            for j, l in enumerate(b):
                m = re.match(r"^(\s*)encapsulation dot1q (\d+)(.*)$", l, re.I)
                if iface and m:
                    actual = int(m.group(2))
                    nueva = actual + random.choice([1, 10, 100])
                    bb = copy.deepcopy(bloques)
                    bb[i][j] = f"{m.group(1)}encapsulation dot1Q {nueva}{m.group(3)}"
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo="subinterfaz", interfaz=iface, vlan=str(actual),
                                   descripcion=f"Etiqueta 802.1Q de {iface} en {d}"),
                        pista="Una subinterfaz del router no coincide con la VLAN que atiende.",
                        explicacion=f"En {d}, {iface} usaba 'encapsulation dot1Q {nueva}'; debía ser la VLAN {actual}."))
    return out


def _f_ospf_network(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            mh = re.match(r"^router ospf (\d+)", b[0].strip(), re.I)
            if not mh:
                continue
            for j, l in enumerate(b):
                m = re.match(r"^\s*network (\S+) (\S+) area (\S+)\s*$", l, re.I)
                if m:
                    bb = copy.deepcopy(bloques)
                    del bb[i][j]
                    out.append(dict(
                        dispositivo=d, nuevo_config=_unir(bb),
                        check=dict(tipo="ospf_red", red=m.group(1), wildcard=m.group(2), area=m.group(3),
                                   proceso=mh.group(1), descripcion=f"{d} anuncia {m.group(1)} en OSPF"),
                        pista="A algún router le falta anunciar una de sus redes (show ip protocols, show ip route).",
                        explicacion=f"En {d} faltaba 'network {m.group(1)} {m.group(2)} area {m.group(3)}' en router ospf."))
    return out


def _f_ruta_estatica(p, cfgs, usadas):
    out = []
    for d, cfg in cfgs.items():
        bloques = _bloques(cfg)
        for i, b in enumerate(bloques):
            m = re.match(r"^ip route (\S+) (\S+) (\d+\.\d+\.\d+\.\d+)\s*$", b[0].strip(), re.I)
            if m and len(b) == 1:
                partes = m.group(3).split(".")
                partes[3] = str((int(partes[3]) + random.choice([1, 2, 4])) % 254 or 1)
                malo = ".".join(partes)
                bb = copy.deepcopy(bloques)
                bb[i][0] = f"ip route {m.group(1)} {m.group(2)} {malo}"
                out.append(dict(
                    dispositivo=d, nuevo_config=_unir(bb),
                    check=dict(tipo="ruta_estatica", red=m.group(1), mascara=m.group(2), siguiente_salto=m.group(3),
                               descripcion=f"Ruta de {d} hacia {m.group(1)}"),
                    pista="Una ruta estática apunta a un siguiente salto que no existe.",
                    explicacion=f"En {d}, la ruta a {m.group(1)} apuntaba a {malo}; debía ser {m.group(3)}."))
    return out


def _f_gateway_pc(p, cfgs, usadas):
    out = []
    hosts = {x["nombre"] for x in p.get("dispositivos", []) if x.get("tipo") in ("pc", "laptop", "servidor")}
    for idx, a in enumerate(p.get("direccionamiento", [])):
        if a.get("dispositivo") in hosts and a.get("gateway") and a.get("ip") and a["ip"].lower() != "dhcp":
            malo = _otra_ip_misma_red(a["ip"], a.get("mascara", "255.255.255.0"), usadas | {a["gateway"]})
            if not malo:
                continue
            out.append(dict(
                dispositivo=a["dispositivo"], nuevo_pc=(idx, malo),
                check=dict(tipo="ip_pc", ip=a["ip"], mascara=a.get("mascara", ""), gateway=a["gateway"],
                           descripcion=f"IP y gateway de {a['dispositivo']}"),
                pista="Alguna PC no sabe por dónde salir de su red.",
                explicacion=f"{a['dispositivo']} tenía el gateway {malo}; debía ser {a['gateway']}."))
    return out


TIPOS_FALLA = [_f_vlan_acceso, _f_shutdown, _f_ip_router, _f_troncal, _f_dot1q,
               _f_ospf_network, _f_ruta_estatica, _f_gateway_pc]


# ---------------------------------------------------------------- armado


def _cfgs(p) -> dict[str, str]:
    """Configuración correcta completa de cada equipo (config inicial + solución)."""
    out: dict[str, str] = {}
    for it in (p.get("config_inicial") or []) + (p.get("solucion") or []):
        d = it.get("dispositivo")
        if d:
            out[d] = (out.get(d, "") + "\n" + (it.get("config") or "")).strip()
    return out


def _ipconfig(direcc: list[dict], dev: str) -> str:
    for a in direcc:
        if a.get("dispositivo") == dev:
            return (f"IPv4 Address......: {a.get('ip', '')}\nSubnet Mask......: {a.get('mascara', '')}\n"
                    f"Default Gateway......: {a.get('gateway', '')}\n")
    return ""


def _evidencias(p, cfgs, direcc) -> dict[str, Evidence]:
    hosts = {x["nombre"] for x in p.get("dispositivos", []) if x.get("tipo") in ("pc", "laptop", "servidor")}
    ev = {}
    for x in p.get("dispositivos", []):
        d = x["nombre"]
        ev[d] = Evidence("", _ipconfig(direcc, d)) if d in hosts else Evidence(cfgs.get(d, ""))
    return ev


def averiar(p: dict, n: int, semilla: int | None = None) -> dict:
    """Devuelve una copia de la topología `p` (con 'solucion' correcta) con n fallas comprobadas."""
    rnd_state = random.getstate()
    if semilla is not None:
        random.seed(semilla)
    try:
        cfgs = _cfgs(p)
        direcc = copy.deepcopy(p.get("direccionamiento", []))
        usadas = {a.get("ip") for a in direcc if a.get("ip")}
        tipos = TIPOS_FALLA[:]
        random.shuffle(tipos)
        elegidas, tocados = [], set()
        # una pasada por tipo para que las fallas sean variadas; luego se rellena si hace falta
        for ronda in range(3):
            for f in tipos:
                if len(elegidas) >= n:
                    break
                cands = [c for c in f(p, cfgs, usadas) if ronda > 0 or c["dispositivo"] not in tocados]
                random.shuffle(cands)
                for c in cands:
                    if _aplicar_y_probar(p, cfgs, direcc, c):
                        elegidas.append(c)
                        tocados.add(c["dispositivo"])
                        break
            if len(elegidas) >= n:
                break
    finally:
        random.setstate(rnd_state)

    q = copy.deepcopy(p)
    q["solucion"] = [{"dispositivo": d, "config": c} for d, c in _cfgs(p).items()]
    q["config_inicial"] = [{"dispositivo": d, "config": c} for d, c in cfgs.items()]
    q["direccionamiento_inicial"] = direcc
    q["fallas"] = [{"dispositivo": c["dispositivo"], "explicacion": c["explicacion"]} for c in elegidas]
    checks = []
    for i, c in enumerate(elegidas, 1):
        checks.append(dict(c["check"], id=f"f{i}", dispositivo=c["dispositivo"]))
    q["verificaciones"] = checks + _pings(p)
    q["pistas"] = list(dict.fromkeys(c["pista"] for c in elegidas))
    q["tareas"] = [
        f"Esta red tiene {len(elegidas)} falla(s) escondida(s). Encuéntralas y arréglalas.",
        "Objetivo: que todas las PCs se puedan hacer ping entre ellas.",
        "Empieza por lo básico: show ip interface brief, show vlan brief, show interfaces trunk, "
        "show ip route, y en las PCs ipconfig.",
        "Cuando termines, pega abajo la running-config de cada equipo y los pings para revisar.",
    ]
    return q


def _aplicar_y_probar(p, cfgs, direcc, c) -> bool:
    """La falla vale si su verificación falla con la red averiada y pasa con la correcta."""
    nuevo_cfgs = dict(cfgs)
    nuevo_dir = copy.deepcopy(direcc)
    if "nuevo_config" in c:
        nuevo_cfgs[c["dispositivo"]] = c["nuevo_config"]
    if "nuevo_pc" in c:
        idx, gw = c["nuevo_pc"]
        nuevo_dir[idx]["gateway"] = gw
    chk = dict(c["check"], id="x", dispositivo=c["dispositivo"])
    prac = {"dispositivos": p.get("dispositivos", []), "verificaciones": [chk]}
    roto = grade(prac, _evidencias(p, nuevo_cfgs, nuevo_dir))["resultados"][0]["estado"]
    bien = grade(prac, _evidencias(p, _cfgs(p), p.get("direccionamiento", [])))["resultados"][0]["estado"]
    if roto == "falla" and bien == "ok":
        cfgs.clear()
        cfgs.update(nuevo_cfgs)
        direcc[:] = nuevo_dir
        return True
    return False


def _pings(p) -> list[dict]:
    hosts = [a for a in p.get("direccionamiento", [])
             if a.get("dispositivo") in {x["nombre"] for x in p.get("dispositivos", [])
                                         if x.get("tipo") in ("pc", "laptop", "servidor")}
             and a.get("ip") and a["ip"].lower() != "dhcp"]
    out = []
    for i in range(min(len(hosts) - 1, 3)):
        a, b = hosts[i], hosts[-1 - i]
        if a["dispositivo"] != b["dispositivo"]:
            out.append({"id": f"p{i + 1}", "dispositivo": a["dispositivo"], "tipo": "ping", "ip": b["ip"],
                        "descripcion": f"{a['dispositivo']} hace ping a {b['dispositivo']} ({b['ip']})"})
    return out
