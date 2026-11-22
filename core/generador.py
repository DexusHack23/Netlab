"""Generación de prácticas y exámenes con tus modelos locales, con autovalidación.

Filosofía (potente pero balanceado):
  * El LLM propone; el código verifica. Una práctica solo te llega si su propia
    solución pasa sus propias verificaciones y el direccionamiento es coherente.
  * En exámenes, el modelo vuelve a contestar sus preguntas sin ver la clave; las que
    no coinciden se descartan (o se marcan si faltan).
"""
from __future__ import annotations

import ipaddress
import json
import random
import re

from . import ollama
from .checker import RUNTIME_ONLY, TIPOS, Evidence, grade
from .ios_words import normalize_answer
from .temario import tema as get_tema

# --------------------------------------------------------------------------- #
# Esquemas JSON (Ollama los respeta con `format`)
# --------------------------------------------------------------------------- #
_S = {"type": "string"}
_PARAMS = ["interfaz", "ip", "mascara", "vlan", "nombre", "red", "wildcard", "area", "proceso",
           "siguiente_salto", "gateway", "ip_fin", "rol", "maximo", "violacion", "nativa", "patron", "seccion"]

ESQUEMA_PRACTICA = {
    "type": "object",
    "properties": {
        "titulo": _S, "objetivo": _S, "escenario": _S,
        "dispositivos": {"type": "array", "items": {"type": "object", "properties": {
            "nombre": _S,
            "tipo": {"type": "string", "enum": ["router", "switch", "switch_l3", "pc", "servidor", "laptop"]},
            "modelo": _S}, "required": ["nombre", "tipo", "modelo"]}},
        "enlaces": {"type": "array", "items": {"type": "object", "properties": {
            "a": _S, "puerto_a": _S, "b": _S, "puerto_b": _S,
            "cable": {"type": "string", "enum": ["directo", "cruzado", "serial", "fibra"]}},
            "required": ["a", "puerto_a", "b", "puerto_b", "cable"]}},
        "direccionamiento": {"type": "array", "items": {"type": "object", "properties": {
            "dispositivo": _S, "interfaz": _S, "ip": _S, "mascara": _S, "gateway": _S},
            "required": ["dispositivo", "interfaz", "ip", "mascara"]}},
        "tareas": {"type": "array", "items": _S},
        "config_inicial": {"type": "array", "items": {"type": "object", "properties": {
            "dispositivo": _S, "config": _S}, "required": ["dispositivo", "config"]}},
        "solucion": {"type": "array", "items": {"type": "object", "properties": {
            "dispositivo": _S, "config": _S}, "required": ["dispositivo", "config"]}},
        "verificaciones": {"type": "array", "items": {"type": "object", "properties": {
            "id": _S, "dispositivo": _S, "tipo": {"type": "string", "enum": list(TIPOS)},
            "descripcion": _S, **{p: _S for p in _PARAMS}},
            "required": ["id", "dispositivo", "tipo", "descripcion"]}},
        "pistas": {"type": "array", "items": _S},
    },
    "required": ["titulo", "objetivo", "escenario", "dispositivos", "enlaces", "direccionamiento",
                 "tareas", "config_inicial", "solucion", "verificaciones", "pistas"],
}

_EJEMPLO = {
    "titulo": "Router-on-a-stick para dos departamentos",
    "objetivo": "Comunicar las VLAN 10 y 20 a través de un router con subinterfaces.",
    "escenario": "Una oficina pequeña separa Ventas y Contabilidad en VLANs distintas...",
    "dispositivos": [{"nombre": "R1", "tipo": "router", "modelo": "2911"},
                     {"nombre": "SW1", "tipo": "switch", "modelo": "2960-24TT"},
                     {"nombre": "PC1", "tipo": "pc", "modelo": "PC-PT"},
                     {"nombre": "PC2", "tipo": "pc", "modelo": "PC-PT"}],
    "enlaces": [{"a": "R1", "puerto_a": "GigabitEthernet0/0", "b": "SW1", "puerto_b": "GigabitEthernet0/1", "cable": "directo"},
                {"a": "PC1", "puerto_a": "FastEthernet0", "b": "SW1", "puerto_b": "FastEthernet0/1", "cable": "directo"},
                {"a": "PC2", "puerto_a": "FastEthernet0", "b": "SW1", "puerto_b": "FastEthernet0/2", "cable": "directo"}],
    "direccionamiento": [
        {"dispositivo": "R1", "interfaz": "GigabitEthernet0/0.10", "ip": "192.168.10.1", "mascara": "255.255.255.0", "gateway": ""},
        {"dispositivo": "R1", "interfaz": "GigabitEthernet0/0.20", "ip": "192.168.20.1", "mascara": "255.255.255.0", "gateway": ""},
        {"dispositivo": "PC1", "interfaz": "FastEthernet0", "ip": "192.168.10.10", "mascara": "255.255.255.0", "gateway": "192.168.10.1"},
        {"dispositivo": "PC2", "interfaz": "FastEthernet0", "ip": "192.168.20.10", "mascara": "255.255.255.0", "gateway": "192.168.20.1"}],
    "tareas": ["En SW1 crea la VLAN 10 (VENTAS) y la 20 (CONTA).", "...", "Comprueba que PC1 haga ping a PC2."],
    "config_inicial": [{"dispositivo": "R1", "config": "hostname R1\nno ip domain-lookup"},
                       {"dispositivo": "SW1", "config": "hostname SW1\nno ip domain-lookup"}],
    "solucion": [
        {"dispositivo": "SW1", "config": "vlan 10\n name VENTAS\nvlan 20\n name CONTA\ninterface FastEthernet0/1\n switchport mode access\n switchport access vlan 10\ninterface FastEthernet0/2\n switchport mode access\n switchport access vlan 20\ninterface GigabitEthernet0/1\n switchport mode trunk"},
        {"dispositivo": "R1", "config": "interface GigabitEthernet0/0\n no shutdown\ninterface GigabitEthernet0/0.10\n encapsulation dot1Q 10\n ip address 192.168.10.1 255.255.255.0\ninterface GigabitEthernet0/0.20\n encapsulation dot1Q 20\n ip address 192.168.20.1 255.255.255.0"}],
    "verificaciones": [
        {"id": "v1", "dispositivo": "SW1", "tipo": "vlan", "descripcion": "VLAN 10 llamada VENTAS", "vlan": "10", "nombre": "VENTAS"},
        {"id": "v2", "dispositivo": "SW1", "tipo": "puerto_acceso", "descripcion": "Fa0/1 en VLAN 10", "interfaz": "FastEthernet0/1", "vlan": "10"},
        {"id": "v3", "dispositivo": "SW1", "tipo": "puerto_troncal", "descripcion": "Troncal hacia R1", "interfaz": "GigabitEthernet0/1"},
        {"id": "v4", "dispositivo": "R1", "tipo": "interfaz_activa", "descripcion": "G0/0 encendida", "interfaz": "GigabitEthernet0/0"},
        {"id": "v5", "dispositivo": "R1", "tipo": "subinterfaz", "descripcion": "Subinterfaz de la VLAN 10", "interfaz": "GigabitEthernet0/0.10", "vlan": "10", "ip": "192.168.10.1", "mascara": "255.255.255.0"},
        {"id": "v6", "dispositivo": "PC1", "tipo": "ip_pc", "descripcion": "IP y gateway de PC1", "ip": "192.168.10.10", "mascara": "255.255.255.0", "gateway": "192.168.10.1"},
        {"id": "v7", "dispositivo": "PC1", "tipo": "ping", "descripcion": "PC1 llega a PC2", "ip": "192.168.20.10"}],
    "pistas": ["El puerto del switch hacia el router debe llevar varias VLANs.", "..."],
}

_REGLAS_PT = """Equipos de Packet Tracer 9 y sus puertos (usa SOLO estos nombres de puerto, completos):
- Router 2911: GigabitEthernet0/0, GigabitEthernet0/1, GigabitEthernet0/2 (preferido).
- Router ISR4331: GigabitEthernet0/0/0, GigabitEthernet0/0/1, GigabitEthernet0/0/2.
- Switch 2960-24TT: FastEthernet0/1 a FastEthernet0/24, GigabitEthernet0/1 y GigabitEthernet0/2.
- Switch multicapa 3560-24PS (solo si de verdad se necesita capa 3: SVIs con 'ip routing'): FastEthernet0/1 a FastEthernet0/24, GigabitEthernet0/1 y GigabitEthernet0/2.
- NO uses el 3650 (Packet Tracer lo trae apagado, sin fuente) ni switches de capa 3 como switches de acceso.
- PC-PT, Laptop-PT y Server-PT: FastEthernet0.
- Evita enlaces seriales (requieren módulo HWIC-2T); si los usas, dilo en las tareas.
Si el tema es DHCP, las PCs que reciben dirección por DHCP llevan "ip": "dhcp" y sin máscara ni gateway.
Cables: router-switch, switch-PC = directo; router-router o switch-switch con Gigabit = directo (auto-MDIX); PC-router directo = cruzado."""

_TIPOS_TXT = "\n".join(f"- {k}: {v}" for k, v in TIPOS.items())

_PROMPT_PRACTICA = """Eres instructor CCNA y diseñas laboratorios para Cisco Packet Tracer 9. Todo en español de México.

{reglas}

Tipos de verificación disponibles (el campo 'tipo') y sus parámetros:
{tipos}
Reglas de las verificaciones:
- Cada tarea importante debe tener al menos una verificación. Entre 6 y 15 verificaciones.
- Usa los tipos específicos; 'contiene' solo para lo que no cubra otro tipo (ACL, NAT source, STP, EtherChannel, HSRP...). En 'contiene', 'patron' es una regex de Python sobre UNA línea de la running-config, sin abreviaturas (ej. '^access-list 10 permit 192\\.168\\.10\\.0 0\\.0\\.0\\.255$').
- Las PCs se verifican con 'ip_pc' (de ipconfig) y 'ping'. Los routers y switches por su configuración.
- Nombres de interfaz COMPLETOS (GigabitEthernet0/0, no g0/0).

Sobre las configuraciones:
- 'solucion' tiene los comandos IOS en modo configuración global (sin 'enable', 'configure terminal' ni 'end'), con las líneas de submodo con un espacio de sangría. Para PCs no pongas solución (se configuran por GUI).
- 'config_inicial' es lo que el alumno pega ANTES de empezar para no repetir lo que no es el tema (hostnames, IPs que no son del tema, etc.). En modo 'desde cero' deja config_inicial vacía.
- La solución + la config inicial deben cumplir TODAS las verificaciones. La config inicial sola NO debe cumplirlas.
- Direccionamiento coherente: ambos extremos de un enlace en la misma subred; el gateway de cada PC es una IP de un router o SVI en su subred.

Ejemplo del formato (resumido):
{ejemplo}"""


# Material de las guías del alumno: la app lo conecta (consulta -> texto). Sin guías, no hace nada.
REFERENCIAS = None


def mundo_de(tema_id: str) -> str:
    """Mundo de un id de tema: lx_* → linux, ws_* → wireshark, ac_<curso>_* → curso, jefe_lx/ws_* igual; lo demás CCNA."""
    t = tema_id or ""
    if t.startswith(("lx_", "jefe_lx_")) or t == "linux":
        return "linux"
    if t.startswith(("ws_", "jefe_ws_")) or t == "wireshark":
        return "wireshark"
    if t.startswith(("soc_", "jefe_soc")):
        return "soc"
    if t.startswith(("idx_", "jefe_idx_")):
        return "purple"
    if t.startswith(("sv_", "jefe_sv_")) or t == "sv":
        return "sv"
    if t.startswith("jefe_ac_"):
        return t[8:] or "ccna"
    if t.startswith("ac_"):
        return t[3:].rsplit("_", 1)[0] or "ccna"
    return "ccna"


_MATERIA_A_MUNDO = {"redes": "ccna"}


def _refs(consulta: str, progreso=lambda m: None, mundo: str | None = None) -> str:
    """Fragmentos de las guías del alumno, SOLO de las guías de ese mundo (antes se mezclaban todas)."""
    if not REFERENCIAS or not consulta.strip():
        return ""
    try:
        texto = REFERENCIAS(consulta, mundo)
    except TypeError:  # REFERENCIAS viejo sin mundo
        texto = REFERENCIAS(consulta)
    if not texto:
        return ""
    progreso("Consultando tus guías…")
    return ("\n\nMaterial de referencia de las guías del alumno. Úsalo para que comandos, nombres de campos y "
            "conceptos sean exactos; si contradice lo que crees, manda la guía. No lo copies tal cual:\n"
            "<<<\n" + texto + "\n>>>")


def _nivel_txt(nivel: str) -> str:
    return {
        "Básico": "nivel básico: 1 router o 1-2 switches, pocos equipos, pasos guiados.",
        "Intermedio": "nivel intermedio: 3-6 equipos de red, tareas menos guiadas.",
        "Avanzado": "nivel avanzado: 4-8 equipos de red, varias tecnologías combinadas, tareas de alto nivel.",
        "Superior": "nivel superior: escenario realista tipo examen, requisitos de negocio y no pasos.",
    }.get(nivel, nivel)


def _pedido_practica(tema_id: str, nivel: str, modo: str, descripcion: str) -> str:
    t = get_tema(tema_id) if tema_id else None
    partes = []
    if t:
        partes.append(f"Tema: {t['nombre']} (conceptos clave: {t['clave']}).")
    if descripcion:
        partes.append(f"Lo que pide el alumno: {descripcion}")
    partes.append(f"Dificultad: {_nivel_txt(nivel)}")
    partes.append("Modo: " + ("desde cero (el alumno configura todo)." if modo == "desde_cero"
                              else "guiado (dale una config_inicial con lo que no es del tema)."))
    partes.append("Devuelve solo el JSON.")
    return "\n".join(partes)


# --------------------------------------------------------------------------- #
# Validación determinista de una práctica
# --------------------------------------------------------------------------- #
def _cfg_map(items) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items or []:
        d = (it.get("dispositivo") or "").strip()
        if d:
            out[d] = (out.get(d, "") + "\n" + (it.get("config") or "")).strip()
    return out


def _fake_ipconfig(practica: dict, dev: str) -> str:
    for a in practica.get("direccionamiento", []):
        if a.get("dispositivo") == dev:
            return (f"IPv4 Address......: {a.get('ip', '')}\nSubnet Mask......: {a.get('mascara', '')}\n"
                    f"Default Gateway......: {a.get('gateway', '')}\n")
    return ""


def _es_host(practica: dict, dev: str) -> bool:
    for d in practica.get("dispositivos", []):
        if d.get("nombre") == dev:
            return d.get("tipo") in ("pc", "servidor", "laptop")
    return False


# Puertos válidos por modelo (nombres completos, como los usa Packet Tracer)
_R = lambda a, b: "(" + "|".join(str(i) for i in range(a, b + 1)) + ")"  # noqa: E731
_PUERTOS = {
    "2911": rf"GigabitEthernet0/{_R(0, 2)}",
    "1941": rf"GigabitEthernet0/{_R(0, 1)}",
    "2901": rf"GigabitEthernet0/{_R(0, 1)}",
    "isr4331": rf"GigabitEthernet0/0/{_R(0, 2)}",
    "isr4321": rf"GigabitEthernet0/0/{_R(0, 1)}",
    "2960-24tt": rf"FastEthernet0/{_R(1, 24)}|GigabitEthernet0/{_R(1, 2)}",
    "3560-24ps": rf"FastEthernet0/{_R(1, 24)}|GigabitEthernet0/{_R(1, 2)}",
    "3650-24ps": rf"GigabitEthernet1/0/{_R(1, 24)}|GigabitEthernet1/1/{_R(1, 4)}",
    "pc-pt": r"FastEthernet0", "laptop-pt": r"FastEthernet0", "server-pt": r"FastEthernet0",
}


def _puerto_valido(modelo: str, puerto: str) -> bool | None:
    m = re.sub(r"^(cisco|router|switch)\s+", "", (modelo or "").strip().lower()).replace(" ", "-")
    m = {"4331": "isr4331", "4321": "isr4321", "2960": "2960-24tt", "3650": "3650-24ps",
         "3560": "3560-24ps", "pc": "pc-pt", "laptop": "laptop-pt", "server": "server-pt"}.get(m, m)
    if m not in _PUERTOS:
        return None  # modelo que no conozco: no lo juzgo
    if re.match(r"(?i)^serial", puerto or ""):
        return True  # seriales dependen del módulo instalado
    return re.fullmatch(_PUERTOS[m], puerto or "") is not None


def _validar_red(p: dict) -> list[str]:
    """Revisiones comunes a prácticas y topologías libres: equipos, cables, puertos, IPs y subredes."""
    errs: list[str] = []
    devs = {d.get("nombre"): d for d in p.get("dispositivos", [])}
    if not devs:
        errs.append("No hay dispositivos.")
    if len(devs) != len(p.get("dispositivos", [])):
        errs.append("Hay dos dispositivos con el mismo nombre.")
    puertos_usados: dict[tuple, int] = {}
    for e in p.get("enlaces", []):
        for d, pt in ((e.get("a"), e.get("puerto_a")), (e.get("b"), e.get("puerto_b"))):
            if d not in devs:
                errs.append(f"El enlace usa '{d}', que no está en dispositivos.")
                continue
            puertos_usados[(d, pt)] = puertos_usados.get((d, pt), 0) + 1
            if "3650" in str(devs[d].get("modelo", "")):
                errs.append(f"{d} es un 3650: Packet Tracer lo trae sin fuente de poder. Usa 2960-24TT "
                            f"(o 3560-24PS si necesita capa 3) y sus puertos.")
            if _puerto_valido(devs[d].get("modelo", ""), pt) is False:
                errs.append(f"El puerto '{pt}' no existe en {d} (modelo {devs[d].get('modelo')}).")
        if e.get("a") == e.get("b"):
            errs.append(f"Hay un cable de {e.get('a')} a sí mismo.")
    for (d, pt), n in puertos_usados.items():
        if n > 1:
            errs.append(f"El puerto {pt} de {d} se usa en {n} enlaces.")

    ips_conocidas = {a.get("ip") for a in p.get("direccionamiento", [])}
    por_iface: dict[tuple, ipaddress.IPv4Interface] = {}
    vistos: dict[str, str] = {}
    for a in p.get("direccionamiento", []):
        d, ip = a.get("dispositivo"), (a.get("ip") or "").strip()
        if d not in devs:
            errs.append(f"El direccionamiento menciona '{d}', que no está en dispositivos.")
        if not ip or ip.lower() == "dhcp":
            continue
        try:
            i = ipaddress.IPv4Interface(f"{ip}/{a.get('mascara')}")
        except ValueError:
            errs.append(f"IP o máscara inválida en {d} {a.get('interfaz')}: {ip} {a.get('mascara')}.")
            continue
        if i.ip in (i.network.network_address, i.network.broadcast_address) and i.network.prefixlen < 31:
            errs.append(f"{ip}/{i.network.prefixlen} en {d} es la dirección de red o de broadcast.")
        if ip in vistos:
            errs.append(f"IP duplicada {ip} ({vistos[ip]} y {d}).")
        vistos[ip] = d
        por_iface[(d, a.get("interfaz"))] = i
        gw = (a.get("gateway") or "").strip()
        if gw and _es_host(p, d):
            try:
                if ipaddress.IPv4Address(gw) not in i.network:
                    errs.append(f"El gateway {gw} de {d} no está en su subred {i.network}.")
                elif gw not in ips_conocidas:
                    errs.append(f"El gateway {gw} de {d} no es la IP de ningún equipo.")
            except ValueError:
                errs.append(f"Gateway inválido en {d}: {gw}.")
    # los dos extremos de un cable con IP deben estar en la misma subred
    for e in p.get("enlaces", []):
        ia, ib = por_iface.get((e.get("a"), e.get("puerto_a"))), por_iface.get((e.get("b"), e.get("puerto_b")))
        if ia and ib and ia.network != ib.network:
            errs.append(f"El cable {e['a']} {e['puerto_a']} ↔ {e['b']} {e['puerto_b']} une subredes distintas "
                        f"({ia.network} y {ib.network}).")
    return list(dict.fromkeys(errs))


def validar_practica(p: dict) -> list[str]:
    """Devuelve la lista de problemas (vacía = práctica coherente)."""
    errs = _validar_red(p)
    nombres = {d.get("nombre") for d in p.get("dispositivos", [])}
    checks = p.get("verificaciones", [])
    if len(checks) < 4:
        errs.append("Hay muy pocas verificaciones (mínimo 4).")
    ips_conocidas = {a.get("ip") for a in p.get("direccionamiento", [])}
    for c in checks:
        if c.get("dispositivo") not in nombres:
            errs.append(f"La verificación {c.get('id')} es de '{c.get('dispositivo')}', que no existe.")
        if c.get("tipo") == "ping" and c.get("ip") not in ips_conocidas:
            errs.append(f"La verificación {c.get('id')} hace ping a {c.get('ip')}, que no está en el direccionamiento.")

    # La solución debe cumplir sus propias verificaciones
    ini, sol = _cfg_map(p.get("config_inicial")), _cfg_map(p.get("solucion"))
    ev_full, ev_ini = {}, {}
    for d in nombres:
        if _es_host(p, d):
            ev_full[d] = Evidence("", _fake_ipconfig(p, d))
            ev_ini[d] = Evidence("", "")
        else:
            ev_full[d] = Evidence((ini.get(d, "") + "\n!\n" + sol.get(d, "")).strip())
            ev_ini[d] = Evidence(ini.get(d, ""))
    sin_ping = {"dispositivos": p.get("dispositivos", []),
                "verificaciones": [c for c in checks if c.get("tipo") not in RUNTIME_ONLY]}
    r = grade(sin_ping, ev_full)
    for res in r["resultados"]:
        if res["estado"] != "ok":
            errs.append(f"La solución NO cumple la verificación {res['id']} ({res['tipo']} en {res['dispositivo']}): "
                        f"{res['detalle']}")
    r0 = grade(sin_ping, ev_ini)
    if r0["total"] and r0["ok"] / r0["total"] > 0.5:
        errs.append("La config_inicial ya cumple más de la mitad de las verificaciones: deja más trabajo al alumno.")
    completas = {d: (ini.get(d, "") + "\n" + sol.get(d, "")).strip() for d in nombres if not _es_host(p, d)}
    errs += _coherencia_config(p, completas)
    return errs


def _normaliza_red(p: dict) -> dict:
    """Arregla formas que los modelos escriben distinto pero significan lo mismo (no son errores de red):
    '10.0.0.1/30' en el campo ip, 'Gi0/0' en vez de 'GigabitEthernet0/0', espacios de más."""
    from .ios_parser import norm_iface
    for e in p.get("enlaces", []) or []:
        for k in ("puerto_a", "puerto_b"):
            if e.get(k):
                e[k] = norm_iface(str(e[k]).replace(" ", ""))
    for a in p.get("direccionamiento", []) or []:
        if a.get("interfaz"):
            a["interfaz"] = norm_iface(str(a["interfaz"]).replace(" ", ""))
        ip = str(a.get("ip") or "").strip()
        m = re.fullmatch(r"(\d+\.\d+\.\d+\.\d+)\s*/\s*(\d{1,2})", ip)
        if m:
            a["ip"] = m.group(1)
            if not a.get("mascara"):
                a["mascara"] = str(ipaddress.IPv4Network(f"0.0.0.0/{m.group(2)}").netmask)
        a["mascara"] = str(a.get("mascara") or "").strip()
        gw = str(a.get("gateway") or "").strip()
        a["gateway"] = re.sub(r"\s*/\s*\d{1,2}$", "", gw)
    for c in p.get("verificaciones", []) or []:
        if c.get("interfaz"):
            c["interfaz"] = norm_iface(str(c["interfaz"]).replace(" ", ""))
    from .ios_parser import reindentar
    for campo in ("configuracion", "solucion", "config_inicial"):
        for it in p.get(campo, []) or []:
            it["config"] = reindentar(it.get("config") or "")
    return p


def _normaliza_practica(p: dict) -> dict:
    _normaliza_red(p)
    for i, c in enumerate(p.get("verificaciones", []), 1):
        c["id"] = str(c.get("id") or f"v{i}")
        for k in list(c):
            if c[k] is None:
                c[k] = ""
    p.setdefault("pistas", [])
    return p


def generar_practica(modelo: str, tema_id: str, nivel: str, modo: str, descripcion: str,
                     progreso=lambda msg: None, max_reparaciones: int = 2) -> dict:
    sistema = _PROMPT_PRACTICA.format(reglas=_REGLAS_PT, tipos=_TIPOS_TXT,
                                      ejemplo=json.dumps(_EJEMPLO, ensure_ascii=False))
    msgs = [{"role": "system", "content": sistema},
            {"role": "user", "content": _pedido_practica(tema_id, nivel, modo, descripcion)}]
    t_ = get_tema(tema_id) if tema_id else None
    msgs[1]["content"] += _refs(" ".join(x for x in ((t_ or {}).get("nombre", ""), (t_ or {}).get("clave", ""),
                                                      descripcion) if x), progreso, mundo="ccna")
    progreso("Diseñando la práctica con " + modelo + "…")
    p = _normaliza_practica(ollama.chat_json(modelo, msgs, ESQUEMA_PRACTICA, temperature=0.6, num_ctx=12288))
    errs = validar_practica(p)
    ronda = 0
    while errs and ronda < max_reparaciones:
        ronda += 1
        progreso(f"Revisando: encontré {len(errs)} problema(s); corrigiendo (ronda {ronda})…")
        msgs += [{"role": "assistant", "content": json.dumps(p, ensure_ascii=False)},
                 {"role": "user", "content": "Un verificador automático encontró estos problemas. Corrígelos y "
                  "devuelve el JSON completo corregido:\n- " + "\n- ".join(errs[:20])}]
        p = _normaliza_practica(ollama.chat_json(modelo, msgs, ESQUEMA_PRACTICA, temperature=0.3, num_ctx=16384))
        errs = validar_practica(p)
    p["tema"] = tema_id
    p["nivel"] = nivel
    p["modo"] = modo
    p["pedido"] = descripcion
    p["validacion"] = {"ok": not errs, "problemas": errs, "rondas": ronda}
    return p


# --------------------------------------------------------------------------- #
# Constructor libre de topologías
# --------------------------------------------------------------------------- #
ESQUEMA_TOPOLOGIA = {
    "type": "object",
    "properties": {
        "titulo": _S, "descripcion": _S,
        "dispositivos": ESQUEMA_PRACTICA["properties"]["dispositivos"],
        "enlaces": ESQUEMA_PRACTICA["properties"]["enlaces"],
        "direccionamiento": ESQUEMA_PRACTICA["properties"]["direccionamiento"],
        "configuracion": ESQUEMA_PRACTICA["properties"]["solucion"],
        "notas": {"type": "array", "items": _S},
    },
    "required": ["titulo", "descripcion", "dispositivos", "enlaces", "direccionamiento", "configuracion", "notas"],
}

_PROMPT_TOPOLOGIA = """Eres ingeniero de redes y diseñas topologías para Cisco Packet Tracer 9. Todo en español de México.
El usuario describe la red que quiere armar; tú devuelves el diseño completo en JSON.

{reglas}

Reglas:
- Respeta exactamente lo que pidió (cantidad de equipos, protocolos, forma). Si no dice algo, elige lo más común en CCNA.
- Nombres cortos y claros (R1, R2, SW1, PC1, SRV1...).
- 'direccionamiento': TODAS las interfaces con IP (routers, SVIs, subinterfaces, PCs y servidores con su gateway).
  Enlaces router-router en /30. Redes privadas.
- 'configuracion': comandos IOS en modo configuración global para cada router y switch (sin 'enable',
  'configure terminal' ni 'end'), con las líneas de submodo con un espacio de sangría. Incluye hostname,
  'no shutdown' en cada interfaz de router que se use, y TODO lo necesario para que haya conectividad de
  extremo a extremo (rutas u OSPF, VLANs, troncales, etc.). Sin configuración para PCs ni servidores.
- 'notas': 2 a 5 cosas útiles para probar la red (qué ping hacer, qué 'show' revisar).
- Antes de responder revisa: puertos válidos para cada modelo, ningún puerto repetido, ninguna IP repetida,
  ambos extremos de cada cable en la misma subred y el gateway de cada PC igual a una IP de su router o SVI."""


def a_practica(t: dict) -> dict:
    """La topología libre con la forma de una práctica (para reutilizar diagrama, tablas y PTBuilder)."""
    p = dict(t)
    p["solucion"] = t.get("configuracion", [])
    p.setdefault("config_inicial", [])
    p.setdefault("verificaciones", [])
    p.setdefault("tareas", [])
    p["objetivo"] = t.get("descripcion", "")
    p["escenario"] = ""
    p["libre"] = True
    return p


def _wild(ip: str, red: str, wc: str) -> bool:
    try:
        i, n, w = (int(ipaddress.IPv4Address(x)) for x in (ip, red, wc))
    except ValueError:
        return False
    return (i & ~w & 0xFFFFFFFF) == (n & ~w & 0xFFFFFFFF)


def _coherencia_config(p: dict, cfgs: dict[str, str]) -> list[str]:
    """La configuración completa debe coincidir con la tabla de direccionamiento y cada router debe
    tener cómo llegar a todas las redes de usuarios (conectada, ruta estática/por defecto o protocolo)."""
    from .ios_parser import parse_config
    errs: list[str] = []
    checks = []
    for a in p.get("direccionamiento", []):
        d, iface, ip = a.get("dispositivo"), a.get("interfaz", ""), (a.get("ip") or "").strip()
        if _es_host(p, d) or not ip or ip.lower() == "dhcp":
            continue
        tipo = "subinterfaz" if "." in iface.split("/")[-1] else "ip_interfaz"
        checks.append({"id": f"{d}:{iface}", "dispositivo": d, "tipo": tipo, "interfaz": iface,
                       "ip": ip, "mascara": a.get("mascara", ""), "descripcion": ""})
    evs = {d: Evidence(cfgs.get(d, "")) for d in {c["dispositivo"] for c in checks}}
    for res in grade({"dispositivos": p.get("dispositivos", []), "verificaciones": checks}, evs)["resultados"]:
        if res["estado"] != "ok":
            errs.append(f"La configuración de {res['dispositivo']} no coincide con el direccionamiento: {res['detalle']}")

    # Redes donde hay PCs o servidores
    redes_usuarios = set()
    for a in p.get("direccionamiento", []):
        if _es_host(p, a.get("dispositivo")) and a.get("ip") and a["ip"].lower() != "dhcp":
            try:
                redes_usuarios.add(ipaddress.IPv4Interface(f"{a['ip']}/{a.get('mascara')}").network)
            except ValueError:
                pass
    for d in p.get("dispositivos", []):
        if d.get("tipo") != "router":
            continue
        cfg = parse_config(cfgs.get(d["nombre"], ""))
        conectadas = set()
        for lines in cfg.interfaces().values():
            for l in lines:
                m = re.match(r"^ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)", l, re.I)
                if m:
                    try:
                        conectadas.add(ipaddress.IPv4Interface(f"{m.group(1)}/{m.group(2)}").network)
                    except ValueError:
                        pass
        dinamico = bool(cfg.find_sections(r"^router (ospf|eigrp|rip|bgp)"))
        # Si hay OSPF o EIGRP, cada red conectada debe estar anunciada con un 'network' válido
        # (atrapa errores como 'networks 10.0.0.0 ...' que IOS rechazaría)
        for sec in cfg.find_sections(r"^router (ospf|eigrp)"):
            es_ospf = "ospf" in sec.header.lower()
            stmts = []
            for c in sec.children:
                m = re.match(r"^network (\d+\.\d+\.\d+\.\d+)(?: (\d+\.\d+\.\d+\.\d+))?(?: area (\S+))?$", c, re.I)
                if m and (not es_ospf or m.group(3)):
                    stmts.append((m.group(1), (m.group(2) or "0.0.0.0") if es_ospf else m.group(2)))
            malas = [c for c in sec.children if re.match(r"^network", c, re.I) and not re.match(r"^network \d", c, re.I)]
            for c in malas:
                errs.append(f"En {d['nombre']}, '{c}' no es un comando válido de IOS.")
            for iface, lines in cfg.interfaces().items():
                if any(re.match(r"^ip ospf \d+ area", l, re.I) for l in lines) and es_ospf:
                    continue
                for l in lines:
                    m = re.match(r"^ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)", l, re.I)
                    if not m:
                        continue
                    ip = m.group(1)
                    cubierta = False
                    for red, wc in stmts:
                        if wc is None:  # EIGRP sin wildcard: con clase
                            primer = int(red.split(".")[0])
                            pre = 8 if primer < 128 else 16 if primer < 192 else 24
                            wc = str(ipaddress.IPv4Network(f"0.0.0.0/{pre}").hostmask)
                        if _wild(ip, red, wc):
                            cubierta = True
                            break
                    if not cubierta:
                        proto = "OSPF" if es_ospf else "EIGRP"
                        errs.append(f"{d['nombre']} no anuncia la red de {iface} ({ip}) en {proto}: falta su 'network'.")
        rutas = []
        for l in cfg.global_lines:
            m = re.match(r"^ip route (\S+) (\S+) ", l, re.I)
            if m:
                try:
                    rutas.append(ipaddress.IPv4Network(f"{m.group(1)}/{m.group(2)}", strict=False))
                except ValueError:
                    pass
        if not conectadas or dinamico:
            continue
        for red in sorted(redes_usuarios, key=str):
            if red in conectadas:
                continue
            if not any(red.subnet_of(r) for r in rutas):
                errs.append(f"{d['nombre']} no tiene cómo llegar a {red} (ni conectada, ni ruta estática, ni protocolo).")
    return errs


def validar_topologia(t: dict) -> list[str]:
    p = a_practica(t)
    errs = _validar_red(p)
    con_cable = {e.get("a") for e in p.get("enlaces", [])} | {e.get("b") for e in p.get("enlaces", [])}
    for d in p.get("dispositivos", []):
        if d.get("nombre") not in con_cable:
            errs.append(f"{d.get('nombre')} no tiene ningún cable.")
    return errs + _coherencia_config(p, _cfg_map(p.get("solucion")))


def generar_topologia(modelo: str, descripcion: str, progreso=lambda m: None, max_reparaciones: int = 2) -> dict:
    msgs = [{"role": "system", "content": _PROMPT_TOPOLOGIA.format(reglas=_REGLAS_PT)},
            {"role": "user", "content": descripcion.strip() + "\nDevuelve solo el JSON." + _refs(descripcion, progreso, mundo="ccna")}]
    progreso("Diseñando la topología con " + modelo + "…")
    t = _normaliza_red(ollama.chat_json(modelo, msgs, ESQUEMA_TOPOLOGIA, temperature=0.4, num_ctx=12288))
    errs = validar_topologia(t)
    ronda = 0
    while errs and ronda < max_reparaciones:
        ronda += 1
        progreso(f"Revisando: encontré {len(errs)} problema(s); corrigiendo (ronda {ronda})…")
        msgs += [{"role": "assistant", "content": json.dumps(t, ensure_ascii=False)},
                 {"role": "user", "content": "Un verificador automático encontró estos problemas. Corrígelos y "
                  "devuelve el JSON completo corregido:\n- " + "\n- ".join(errs[:20])}]
        t = _normaliza_red(ollama.chat_json(modelo, msgs, ESQUEMA_TOPOLOGIA, temperature=0.2, num_ctx=16384))
        errs = validar_topologia(t)
    p = a_practica(t)
    p.update(tema="constructor", nivel="Libre", modo="libre", pedido=descripcion,
             validacion={"ok": not errs, "problemas": errs, "rondas": ronda})
    return p


# --------------------------------------------------------------------------- #
# Troubleshooting
# --------------------------------------------------------------------------- #
_FALLAS_POR_NIVEL = {"Básico": 1, "Intermedio": 2, "Avanzado": 3, "Superior": 4}


def generar_troubleshooting(modelo: str, tema_id: str, nivel: str, descripcion: str,
                            progreso=lambda m: None) -> dict:
    from .fallas import averiar  # import diferido para no cargarlo si no se usa
    t = get_tema(tema_id) if tema_id else None
    pedido = descripcion.strip() or (f"Una red para practicar {t['nombre']} ({t['clave']})." if t else
                                     "Una red de oficina con VLANs, enrutamiento entre VLANs y dos routers.")
    pedido += (" Debe tener al menos 4 PCs repartidas en al menos 2 redes distintas, para poder probar "
               "conectividad con ping. Nivel: " + _nivel_txt(nivel))
    n = _FALLAS_POR_NIVEL.get(nivel, 2)
    for intento in range(2):
        p = generar_topologia(modelo, pedido, progreso=progreso)
        if not p["validacion"]["ok"]:
            progreso("La red base no quedó perfecta; diseño otra…")
            continue
        progreso(f"Metiendo {n} falla(s) y comprobando que cada una de verdad rompa algo…")
        q = averiar(p, n)
        if q["fallas"]:
            q.update(tema=tema_id or "", nivel=nivel, modo="troubleshooting", libre=False, pedido=descripcion,
                     titulo="Troubleshooting: " + p.get("titulo", "red"),
                     objetivo=f"Encontrar y corregir {len(q['fallas'])} falla(s) para que toda la red tenga conectividad.",
                     escenario=p.get("descripcion", ""))
            q["validacion"] = {"ok": True, "problemas": [], "rondas": p["validacion"]["rondas"]}
            return q
        progreso("No encontré fallas que se pudieran comprobar en esa red; diseño otra…")
    raise ollama.OllamaError("No pude armar un troubleshooting confiable. Intenta con otra descripción o tema.")


# --------------------------------------------------------------------------- #
# Explicación de resultados
# --------------------------------------------------------------------------- #
def explicar(modelo: str, practica: dict, resultado: dict, evidencia_txt: dict[str, str]) -> str:
    fallas = [r for r in resultado["resultados"] if r["estado"] != "ok"]
    if not fallas:
        return "Todo lo que se pudo verificar está correcto. Buen trabajo."
    disp_falla = {r["dispositivo"] for r in fallas}
    contexto = "\n\n".join(f"### {d}\n{evidencia_txt.get(d, '')[:2500]}" for d in disp_falla)
    msgs = [
        {"role": "system", "content":
            "Eres un instructor CCNA paciente. Explica en español de México, breve y directo. "
            "Un verificador automático YA decidió qué está mal: no lo contradigas ni inventes otros errores. "
            "Para cada falla explica la causa probable y da una pista concreta de cómo corregirla sin "
            "escribir la configuración completa. Para 'sin_datos' di exactamente qué comando debe pegar. "
            "Usa viñetas cortas."},
        {"role": "user", "content":
            f"Práctica: {practica.get('titulo')}\nObjetivo: {practica.get('objetivo')}\n\n"
            f"Resultados del verificador:\n{json.dumps(fallas, ensure_ascii=False, indent=1)}\n\n"
            f"Lo que pegó el alumno de los equipos con fallas:\n{contexto}"},
    ]
    return ollama.chat(modelo, msgs, temperature=0.3)


# --------------------------------------------------------------------------- #
# Exámenes
# --------------------------------------------------------------------------- #
ESQUEMA_EXAMEN = {
    "type": "object",
    "properties": {
        "titulo": _S,
        "preguntas": {"type": "array", "items": {"type": "object", "properties": {
            "tipo": {"type": "string", "enum": ["opcion", "comando"]},
            "enunciado": _S,
            "opciones": {"type": "array", "items": _S},
            "correcta": {"type": "integer"},
            "respuestas_validas": {"type": "array", "items": _S},
            "explicacion": _S,
            "subtema": _S},
            "required": ["tipo", "enunciado", "explicacion"]}},
    },
    "required": ["titulo", "preguntas"],
}

ESQUEMA_VERIF = {
    "type": "object",
    "properties": {"respuestas": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "correctas": {"type": "array", "items": {"type": "string", "enum": ["A", "B", "C", "D", "E", "F"]}}},
        "required": ["n", "correctas"]}}},
    "required": ["respuestas"],
}

ESQUEMA_VERIF_CMD = {
    "type": "object",
    "properties": {"comandos": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "correcto": {"type": "boolean"}}, "required": ["n", "correcto"]}}},
    "required": ["comandos"],
}

ESQUEMA_JUEZ = {
    "type": "object",
    "properties": {"correcta": {"type": "boolean"}, "motivo": _S},
    "required": ["correcta", "motivo"],
}


def _limpia_preguntas(preguntas: list[dict]) -> list[dict]:
    out = []
    for q in preguntas:
        tipo = q.get("tipo")
        if not (q.get("enunciado") or "").strip():
            continue
        if tipo == "opcion":
            ops = [o for o in (q.get("opciones") or []) if str(o).strip()]
            c = q.get("correcta")
            if len(ops) < 3 or not isinstance(c, int) or not 0 <= c < len(ops) or len(set(ops)) != len(ops):
                continue
            # quitar letras "A) " que algunos modelos agregan
            ops = [re.sub(r"^\s*[A-Da-d][).:-]\s+", "", o) for o in ops]
            correcta_txt = ops[c]
            random.shuffle(ops)  # los LLM tienden a poner la correcta siempre en la misma posición
            q = dict(q, opciones=ops, correcta=ops.index(correcta_txt))
        elif tipo == "comando":
            val = list(dict.fromkeys(str(v).strip() for v in (q.get("respuestas_validas") or []) if str(v).strip()))
            # una sola línea de comando; respuestas de varias líneas o cosas sueltas no sirven para calificar
            val = [v for v in val if "\n" not in v and len(v.split()) >= 2]
            if not val:
                continue
            q = dict(q, respuestas_validas=val, opciones=[])
        else:
            continue
        out.append(q)
    return out


_MUNDO_TXT = {"linux": "Linux, bash y administración de servidores", "wireshark": "Wireshark y análisis de tráfico",
              "soc": "análisis de seguridad en un SOC", "rust": "el lenguaje Rust", "ia": "inteligencia artificial y machine learning",
              "torch": "PyTorch y deep learning", "cpu": "arquitectura de computadoras y RISC-V", "chisel": "diseño digital con Chisel",
              "rustproj": "proyectos de seguridad en Rust",
              "sv": "SystemVerilog: diseño digital y verificación de hardware",
              "purple": "técnicas ofensivas explicadas a nivel de concepto y cómo se detectan y mitigan (Purple Team)"}

_DOMINIO = {
    "ccna": ("exámenes estilo CCNA 200-301", "según Cisco IOS 15 y Packet Tracer", "experto CCNA y Cisco IOS"),
    "soc": ("exámenes para analistas SOC nivel 1 (estilo TryHackMe SAL1)", "según MITRE ATT&CK, NIST SP 800-61 y prácticas reales de SOC",
            "experto en análisis de seguridad y respuesta a incidentes"),
    "rust": ("exámenes del lenguaje Rust (estilo The Rust Programming Language)", "según Rust estable actual", "experto en Rust"),
    "ia": ("exámenes de fundamentos de inteligencia artificial y machine learning", "según la teoría estándar de ML",
           "experto en machine learning"),
    "cpu": ("exámenes de arquitectura de computadoras y RISC-V", "según la especificación RISC-V", "experto en arquitectura de computadoras"),
    "chisel": ("exámenes de diseño digital con Chisel", "según Chisel 3/6 y Digital Design with Chisel", "experto en diseño digital y Chisel"),
    "linux": ("exámenes de Linux para administradores y analistas de SOC (estilo LPI Linux Essentials / CompTIA Linux+)",
              "según Ubuntu/Debian actuales y GNU bash/coreutils", "experto en Linux, bash y administración de servidores"),
    "wireshark": ("exámenes estilo Wireshark Certified Analyst (WCA-101)", "según Wireshark 4.x, sus filtros y sus estadísticas",
                  "experto en Wireshark y análisis de tráfico"),
}
_DOMINIO["purple"] = ("exámenes de Purple Team: teoría de técnicas ofensivas a nivel de concepto y su detección (estilo eJPT/SAL1, "
                      "parte teórica)", "según MITRE ATT&CK, OWASP y la documentación de Windows/Linux",
                      "experto en Purple Team (ataque y detección)")
_DOMINIO["sv"] = ("exámenes de SystemVerilog (diseño digital y verificación de hardware)",
                  "según el estándar IEEE 1800-2023 (SystemVerilog) y el simulador Verilator",
                  "experto en SystemVerilog, diseño RTL y verificación")
_DOMINIO["torch"] = _DOMINIO["ia"]
_DOMINIO["rustproj"] = _DOMINIO["rust"]


def generar_examen(modelo: str, tema_id: str, nivel: str, n: int, descripcion: str = "",
                   verificar: bool = True, progreso=lambda m: None, solo_opcion: bool = False,
                   dominio: str = "ccna") -> dict:
    if dominio not in _DOMINIO:
        dominio = "ccna"
    if dominio == "ccna" and tema_id and mundo_de(tema_id) in _DOMINIO:
        dominio = mundo_de(tema_id)  # nunca dejar un tema de otro mundo marcado como CCNA
    tipo_ex, base_ex, experto = _DOMINIO[dominio]
    if dominio != "ccna":
        solo_opcion = True  # la calificación de comandos escritos es para IOS
    t = get_tema(tema_id) if tema_id and dominio == "ccna" else None
    pedir = n + max(3, (n + 1) // 2) if verificar else n  # colchón amplio: generamos de más y nos quedamos solo con las verificadas
    tema_txt = f"{t['nombre']} (conceptos clave: {t['clave']})" if t else descripcion
    if dominio == "ccna":
        sistema = (
            f"Eres un instructor que escribe {tipo_ex} en español de México. "
            f"Las preguntas deben ser técnicamente exactas {base_ex}. "
            "Mezcla dos tipos: 'opcion' (4 opciones, una sola correcta, 'correcta' es el índice 0-3, "
            "distractores plausibles, sin 'todas las anteriores') y 'comando' (el alumno escribe UN comando "
            "IOS; en 'respuestas_validas' pon las formas completas aceptadas, sin prompt). "
            + ("Usa SOLO el tipo 'opcion', como en el examen real. " if solo_opcion else
               "Aproximadamente 75% opción y 25% comando; en 'comando' la respuesta es UNA sola línea completa "
               "(por ejemplo 'standby 1 priority 120', no 'priority 120'). ")
            + "Cada pregunta con explicación breve de por qué.")
    else:
        # otros mundos: NADA de Cisco IOS, Packet Tracer ni CCNA (antes el prompt hablaba de IOS y se colaban temas de redes)
        sistema = (
            f"Eres un instructor que escribe {tipo_ex} en español de México. "
            f"Las preguntas deben ser técnicamente exactas {base_ex}. "
            f"Todas las preguntas son EXCLUSIVAMENTE del tema pedido ({_MUNDO_TXT.get(dominio, dominio)}): no incluyas "
            "preguntas de Cisco IOS, Packet Tracer, CCNA ni de otras materias. "
            "Solo tipo 'opcion' (4 opciones, una sola correcta, 'correcta' es el índice 0-3, distractores plausibles, "
            "sin 'todas las anteriores'). Cada pregunta con explicación breve de por qué.")
        if dominio == "purple":
            sistema += (" Pregunta SOLO por conceptos: qué es la técnica, por qué funciona, qué condición o mala configuración la "
                        "permite, qué rastro deja (Event IDs, logs, tráfico), con qué se detecta, cómo se mitiga y su ID de MITRE "
                        "ATT&CK. PROHIBIDO preguntar por comandos de ataque, opciones de herramientas ofensivas, payloads o pasos "
                        "para explotar algo.")
    msgs = [
        {"role": "system", "content": sistema},
        {"role": "user", "content":
            f"Tema: {tema_txt}\n{('Enfoque pedido: ' + descripcion) if descripcion and t else ''}\n"
            f"Nivel: {_nivel_txt(nivel)}\nNúmero de preguntas: {pedir}. Devuelve solo el JSON."
            + _refs(f"{tema_txt} {descripcion}", progreso, mundo=dominio)},
    ]
    progreso(f"Escribiendo {pedir} preguntas con {modelo}…")
    data = ollama.chat_json(modelo, msgs, ESQUEMA_EXAMEN, temperature=0.7, num_ctx=12288)
    preguntas = _limpia_preguntas(data.get("preguntas", []))
    if solo_opcion:
        preguntas = [q for q in preguntas if q["tipo"] == "opcion"]

    if verificar and preguntas:
        progreso("Verificando la clave de respuestas (el modelo contesta sin verla)…")
        mc = [(i, q) for i, q in enumerate(preguntas) if q["tipo"] == "opcion"]
        if mc:
            letras = "ABCDEF"
            texto = "\n\n".join(
                f"Pregunta {k}. {q['enunciado']}\n" + "\n".join(f"  {letras[j]}) {o}" for j, o in enumerate(q["opciones"]))
                for k, (_, q) in enumerate(mc, 1))
            try:
                ver = ollama.chat_json(modelo, [
                    {"role": "system", "content":
                        f"Eres {experto}. Para cada pregunta indica TODAS las letras de las opciones que "
                        "son técnicamente correctas (puede ser una, varias o ninguna). 'n' es el número de pregunta."},
                    {"role": "user", "content": texto}], ESQUEMA_VERIF, temperature=0.0, num_ctx=12288)
                resp = {r.get("n"): sorted(set(r.get("correctas") or [])) for r in ver.get("respuestas", [])}
                for k, (i, q) in enumerate(mc, 1):
                    # válida solo si el verificador ve exactamente UNA correcta y es la de la clave
                    preguntas[i]["verificada"] = resp.get(k) == [letras[q["correcta"]]]
            except ollama.OllamaError:
                pass
        cmds = [(i, q) for i, q in enumerate(preguntas) if q["tipo"] == "comando"]
        if cmds:
            texto = "\n\n".join(f"Pregunta {k}. {q['enunciado']}\nRespuesta propuesta: {q['respuestas_validas'][0]}"
                                for k, (_, q) in enumerate(cmds, 1))
            try:
                ver = ollama.chat_json(modelo, [
                    {"role": "system", "content":
                        "Eres experto en Cisco IOS. Para cada pregunta di si la respuesta propuesta es UN comando IOS "
                        "real, completo y correcto que hace exactamente lo que se pide (true) o no (false)."},
                    {"role": "user", "content": texto}], ESQUEMA_VERIF_CMD, temperature=0.0, num_ctx=12288)
                resp = {r.get("n"): bool(r.get("correcto")) for r in ver.get("comandos", [])}
                for k, (i, q) in enumerate(cmds, 1):
                    preguntas[i]["verificada"] = resp.get(k, False)
            except ollama.OllamaError:
                pass
        buenas = [q for q in preguntas if q.get("verificada", True)]
        # solo mostramos preguntas que PASARON la verificación (la clave coincide con lo que el modelo contesta sin verla);
        # las dudosas se descartan. Si el verificador falló del todo (0 buenas), usamos las originales para no dejar vacío.
        preguntas = (buenas or preguntas)[:n]
    else:
        preguntas = preguntas[:n]

    return {"titulo": data.get("titulo") or f"Examen: {tema_txt[:60]}", "tema": tema_id if (dominio == "ccna" or tema_id) else dominio,
            "nivel": nivel, "preguntas": preguntas, "dominio": dominio}


def generar_simulacro(modelo: str, n: int, verificar: bool = True, progreso=lambda m: None) -> dict:
    """Simulacro tipo CCNA: preguntas repartidas por dominio según el peso oficial del examen."""
    from .temario import DOMINIOS
    preguntas: list[dict] = []
    restantes = n
    for i, (dom, peso, temas) in enumerate(DOMINIOS):
        k = restantes if i == len(DOMINIOS) - 1 else round(n * peso)
        restantes -= k
        nombres = ", ".join(get_tema(t)["nombre"] for t in temas)
        hechas: list[dict] = []
        intentos = 0
        while len(hechas) < k and intentos < (k // 8 + 3):
            intentos += 1
            lote = min(8, k - len(hechas))
            progreso(f"Escribiendo preguntas de {dom} ({len(preguntas) + len(hechas)}/{n})…")
            desc = (f"Dominio '{dom}' del examen CCNA 200-301. Temas: {nombres}. Reparte las preguntas entre "
                    "esos temas, estilo examen real, sin repetir lo que ya se preguntó.")
            if hechas:
                desc += " Ya se preguntó: " + " | ".join(q["enunciado"][:80] for q in hechas[-10:])
            try:
                e = generar_examen(modelo, "", "Avanzado", lote, desc, verificar=verificar, solo_opcion=True)
            except ollama.OllamaError:
                continue
            hechas += [q for q in e["preguntas"] if not q.get("dudosa")][:lote]
        for q in hechas:
            q["dominio"] = dom
        preguntas += hechas
    random.shuffle(preguntas)
    if not preguntas:
        raise ollama.OllamaError("No se pudieron generar preguntas para el simulacro.")
    return {"titulo": f"Simulacro CCNA ({len(preguntas)} preguntas)", "tema": "simulacro", "nivel": "Mixto",
            "simulacro": True, "minutos": max(10, round(len(preguntas) * 1.2)), "preguntas": preguntas}


def calificar_examen(modelo_juez: str, examen: dict, respuestas: list) -> dict:
    detalle = []
    buenas = 0
    for i, q in enumerate(examen["preguntas"]):
        r = respuestas[i] if i < len(respuestas) else None
        item = {"n": i + 1, "correcta": False, "explicacion": q.get("explicacion", ""), "tipo": q["tipo"]}
        if q["tipo"] == "opcion":
            item["tu_respuesta"] = q["opciones"][r] if isinstance(r, int) and 0 <= r < len(q["opciones"]) else "(sin responder)"
            item["respuesta_correcta"] = q["opciones"][q["correcta"]]
            item["correcta"] = r == q["correcta"]
        else:
            txt = (r or "").strip() if isinstance(r, str) else ""
            item["tu_respuesta"] = txt or "(sin responder)"
            item["respuesta_correcta"] = q["respuestas_validas"][0]
            if txt:
                norm = normalize_answer(txt)
                if any(norm == normalize_answer(v) for v in q["respuestas_validas"]):
                    item["correcta"] = True
                else:
                    try:
                        j = ollama.chat_json(modelo_juez, [
                            {"role": "system", "content": "Eres un calificador estricto de comandos Cisco IOS. "
                             "Acepta abreviaturas válidas de IOS y formas equivalentes, pero NO comandos que hagan "
                             "algo distinto. Responde en JSON."},
                            {"role": "user", "content": f"Pregunta: {q['enunciado']}\nRespuestas válidas: "
                             f"{q['respuestas_validas']}\nRespuesta del alumno: {txt}\n¿Es correcta?"}],
                            ESQUEMA_JUEZ, temperature=0.0)
                        item["correcta"] = bool(j.get("correcta"))
                        item["motivo_juez"] = j.get("motivo", "")
                    except ollama.OllamaError:
                        pass
        buenas += item["correcta"]
        detalle.append(item)
    total = len(examen["preguntas"])
    por_dominio: dict[str, dict] = {}
    for q, item in zip(examen["preguntas"], detalle):
        if q.get("dominio"):
            d = por_dominio.setdefault(q["dominio"], {"buenas": 0, "total": 0})
            d["total"] += 1
            d["buenas"] += item["correcta"]
    return {"detalle": detalle, "buenas": buenas, "total": total, "por_dominio": por_dominio,
            "calificacion": round(10 * buenas / total, 1) if total else 0.0}


# --------------------------------------------------------------------------- #
# Teoría: lecciones para leer (o escuchar) en español o inglés
# --------------------------------------------------------------------------- #
ESQUEMA_LECCION = {
    "type": "object",
    "properties": {
        "titulo": _S,
        "intro": _S,
        "secciones": {"type": "array", "items": {"type": "object", "properties": {"titulo": _S, "texto": _S},
                                                  "required": ["titulo", "texto"]}},
        "comandos": {"type": "array", "items": {"type": "object", "properties": {"comando": _S, "que_hace": _S},
                                                 "required": ["comando", "que_hace"]}},
        "puntos_clave": {"type": "array", "items": _S},
        "errores_comunes": {"type": "array", "items": _S},
    },
    "required": ["titulo", "intro", "secciones", "comandos", "puntos_clave", "errores_comunes"],
}


# Cada "materia" le da al generador el profesor y el estilo de ejemplos correctos (antes todo salía con mentalidad de redes).
MATERIAS = {
    "redes": {
        "es": ("Eres instructor de CCNA (redes Cisco), claro y exacto. Los comandos de IOS, protocolos y campos se dejan en inglés. ",
               "los comandos reales de Cisco IOS 15 / Packet Tracer del tema, tal cual se teclean",
               "un ejemplo concreto pequeño (direcciones IP reales, números de VLAN, interfaces)"),
        "en": ("You are a clear, exact CCNA (Cisco networking) instructor. ",
               "the real Cisco IOS 15 / Packet Tracer commands for the topic, exactly as typed",
               "a small concrete example (real IP addresses, VLAN numbers, interfaces)")},
    "wireshark": {
        "es": ("Eres analista de Wireshark (WCA-101) y enseñas a leer capturas. Los nombres de campos y protocolos van en inglés. ",
               "los display filters reales de Wireshark del tema, uno por elemento, tal cual se escriben",
               "un ejemplo concreto con un paquete o una captura pequeña (IP, puerto, protocolo reales)")},
    "linux": {
        "es": ("Eres instructor de Linux para SOC/administración, claro y práctico. Los comandos van en inglés, como en la terminal. ",
               "los comandos reales de bash/Linux del tema, uno por elemento, tal cual se teclean",
               "un ejemplo concreto pequeño con comandos y su salida típica"),
        "en": ("You are a clear, practical Linux instructor for SOC/sysadmin work. ",
               "the real bash/Linux commands for the topic, one per item, exactly as typed",
               "a small concrete example with commands and their typical output")},
    "rust": {
        "es": ("Eres instructor de programación en Rust, PACIENTE y claro, para alguien que aún tiene poco código encima. "
               "Las palabras clave y tipos del lenguaje (let, mut, ownership, borrow, Vec, Result, match…) se dejan en inglés. ",
               "fragmentos de código o sintaxis clave del tema (por ejemplo `let mut x = 5;`), uno por elemento, tal cual se escriben; NO son comandos de terminal",
               "SIEMPRE un ejemplo de código pequeño y real (3 a 6 líneas) y explica en palabras qué hace cada línea, con casos cotidianos (no de redes)"),
        "en": ("You are a PATIENT, clear Rust programming instructor for someone still newer to coding. "
               "Keep language keywords and types (let, mut, ownership, borrow, Vec, Result, match…) in English. ",
               "key code snippets or syntax for the topic (e.g. `let mut x = 5;`), one per item, exactly as written; they are NOT shell commands",
               "ALWAYS a small, real code example (3 to 6 lines) and explain in words what each line does, with everyday cases (not networking)")},
    "ia": {
        "es": ("Eres instructor de machine learning e IA con Python y PyTorch, claro y concreto. Los nombres de funciones y librerías van en inglés. ",
               "fragmentos de código Python/PyTorch del tema (por ejemplo `x = torch.tensor([1.0, 2.0])`), uno por elemento, tal cual se escriben",
               "SIEMPRE un ejemplo de código pequeño (3 a 6 líneas) y explica qué hace, con intuición antes que fórmulas"),
        "en": ("You are a clear, concrete machine learning and AI instructor using Python and PyTorch. ",
               "Python/PyTorch code snippets for the topic (e.g. `x = torch.tensor([1.0, 2.0])`), one per item, exactly as written",
               "ALWAYS a small code example (3 to 6 lines) and explain what it does, intuition before formulas")},
    "cpu": {
        "es": ("Eres instructor de arquitectura de computadoras y RISC-V, claro y concreto. Los nombres de registros e instrucciones van en inglés. ",
               "ejemplos del tema: instrucciones RISC-V, valores en binario/hex o registros (por ejemplo `addi x5, x0, 10`), uno por elemento",
               "SIEMPRE un ejemplo concreto pequeño (una instrucción, un número en binario y hex, o un registro) resuelto paso a paso"),
        "en": ("You are a clear, concrete computer architecture and RISC-V instructor. ",
               "topic examples: RISC-V instructions, binary/hex values or registers (e.g. `addi x5, x0, 10`), one per item",
               "ALWAYS a small concrete example (an instruction, a number in binary and hex, or a register) worked step by step")},
    "chisel": {
        "es": ("Eres instructor de diseño de hardware digital con Chisel (Scala), claro y concreto. Los nombres de tipos de Chisel van en inglés. ",
               "fragmentos de código Chisel/Scala del tema (por ejemplo `val suma = a + b`), uno por elemento, tal cual se escriben",
               "SIEMPRE un ejemplo de módulo o señal pequeño y explica qué hardware describe")},
}
MATERIAS["sv"] = {
    "es": ("Eres instructor de SystemVerilog (diseño digital y verificación de hardware), claro y concreto. Los nombres de palabras "
           "clave y tipos de SystemVerilog (logic, always_ff, module, etc.) van en inglés tal cual. Distingue siempre lo sintetizable "
           "(hardware real: always_ff/always_comb) de lo que es solo para simulación (initial, clases, aserciones). ",
           "fragmentos de código SystemVerilog del tema (por ejemplo `always_ff @(posedge clk) q <= d;`), uno por elemento, tal cual se escriben",
           "SIEMPRE un ejemplo pequeño de módulo, señal o testbench (3 a 8 líneas) y explica qué hardware describe o qué verifica"),
    "en": ("You are a clear, concrete SystemVerilog instructor (digital design and hardware verification). Always distinguish synthesizable "
           "hardware (always_ff/always_comb) from simulation-only constructs (initial, classes, assertions). ",
           "SystemVerilog code snippets for the topic (e.g. `always_ff @(posedge clk) q <= d;`), one per item, exactly as written",
           "ALWAYS a small module, signal or testbench example (3 to 8 lines) and explain what hardware it describes or what it verifies")}
MATERIAS["soc"] = {
    "es": ("Eres analista SOC senior (estilo TryHackMe SAL1 / Blue Team) y enseñas a investigar alertas de verdad. Los nombres de "
           "eventos, campos, herramientas y técnicas MITRE se dejan en inglés. ",
           "consultas de SIEM (KQL/Lucene en Kibana), comandos de Windows/Linux o reglas de detección del tema, una por elemento, tal cual se escriben",
           "un incidente concreto con IPs, usuarios, Event IDs y horas reales, investigado paso a paso"),
    "en": ("You are a senior SOC analyst (TryHackMe SAL1 / Blue Team style) teaching how to investigate real alerts. ",
           "SIEM queries (KQL/Lucene in Kibana), Windows/Linux commands or detection rules for the topic, one per item, exactly as written",
           "a concrete incident with real IPs, users, Event IDs and timestamps, investigated step by step")}
MATERIAS["purple"] = {
    "es": ("Eres instructor de Purple Team: explicas una técnica ofensiva SOLO a nivel de concepto (qué es, por qué funciona, qué "
           "condición o mala configuración la hace posible) y te centras en cómo se DETECTA (logs, Event IDs, tráfico, reglas) y cómo "
           "se MITIGA. NUNCA des pasos operativos de ataque, comandos de explotación, payloads ni herramientas de ataque con sus "
           "opciones: para practicar el ataque, el alumno usa la sala legal de TryHackMe/HTB. Los nombres de técnicas MITRE, eventos y "
           "campos se dejan en inglés. ",
           "consultas de detección (KQL/Lucene, filtros de Wireshark, comandos de revisión de logs en Linux/Windows) o configuraciones "
           "de mitigación del tema, una por elemento, tal cual se escriben; nada de comandos de ataque",
           "un incidente concreto VISTO DESDE EL DEFENSOR: qué rastro deja la técnica en los logs o en el tráfico y cómo se contiene"),
    "en": ("You are a Purple Team instructor: you explain an offensive technique ONLY at concept level (what it is, why it works, what "
           "condition or misconfiguration enables it) and focus on how it is DETECTED (logs, Event IDs, traffic, rules) and MITIGATED. "
           "NEVER give operational attack steps, exploitation commands, payloads or attack-tool usage: to practice the attack, the "
           "student uses the legal TryHackMe/HTB room. ",
           "detection queries (KQL/Lucene, Wireshark filters, Linux/Windows log review commands) or mitigation settings for the topic, "
           "one per item, exactly as written; no attack commands",
           "a concrete incident SEEN FROM THE DEFENDER: what trace the technique leaves in logs or traffic and how it is contained")}
_MATERIA_A_MUNDO["purple"] = "soc"
MATERIAS["wireshark"]["en"] = ("You are a Wireshark (WCA-101) analyst teaching people to read captures. ",
                               "the real Wireshark display filters for the topic, one per item, exactly as written",
                               "a concrete example with a small packet or capture (real IP, port, protocol)")
MATERIAS["chisel"]["en"] = ("You are a clear, concrete digital hardware design instructor using Chisel (Scala). ",
                            "Chisel/Scala code snippets for the topic (e.g. `val suma = a + b`), one per item, exactly as written",
                            "ALWAYS a small module or signal example and explain what hardware it describes")


def generar_leccion_v1(modelo: str, tema_txt: str, clave: str, idioma: str, enfoque: str = "",
                    progreso=lambda m: None, materia: str = "redes") -> dict:
    ingles = idioma == "en"
    consulta = f"{tema_txt} {clave} {enfoque}"
    refs = _refs(consulta, progreso, mundo=_MATERIA_A_MUNDO.get(materia, materia))
    mat = MATERIAS.get(materia, MATERIAS["redes"])
    persona, que_comandos, que_ejemplo = mat["en" if ingles else "es"] if ("en" if ingles else "es") in mat else mat["es"]
    formato = (
        "Write a clear, technically exact lesson in English. The lesson will also be read aloud by a text-to-speech voice, "
        "so write natural prose in short paragraphs, no tables, no markdown symbols inside 'texto', no ASCII art. "
        f"4 to 7 sections that build from the idea, to how it works, to how to use/verify it. 'comandos': {que_comandos}. "
        f"If the topic has none, leave it empty. Explain with {que_ejemplo}."
        if ingles else
        "Escribes una lección clara y técnicamente exacta en español de México. La lección también la va a leer en voz alta "
        "una voz sintética: escribe prosa natural en párrafos cortos, sin tablas, sin símbolos de markdown dentro de 'texto', "
        f"sin dibujos ASCII. De 4 a 7 secciones que vayan de la idea, a cómo funciona, a cómo se usa y se verifica. "
        f"'comandos': {que_comandos}. Si el tema no tiene, déjalo vacío. Explica con {que_ejemplo}.")
    msgs = [
        {"role": "system", "content": persona + formato},
        {"role": "user", "content": (
            "IMPORTANT: write EVERYTHING in English (titles, text, explanations), even though the topic name "
            "below is written in Spanish.\n"
            f"Topic (in Spanish): {tema_txt}\nKey concepts (in Spanish): {clave}\n"
            + (f"Focus requested: {enfoque}\n" if enfoque else "")
            + "Return only the JSON, in English." if ingles else
            "IMPORTANTE: escribe TODO en español de México (no en portugués ni en inglés), aunque las guías "
            "de referencia estén en inglés.\n"
            f"Tema: {tema_txt}\nConceptos clave: {clave}\n" + (f"Enfoque pedido: {enfoque}\n" if enfoque else "")
            + "Devuelve solo el JSON.") + refs},
    ]
    progreso(("Writing the lesson with " if ingles else "Escribiendo la lección con ") + modelo + "…")
    data = ollama.chat_json(modelo, msgs, ESQUEMA_LECCION, temperature=0.4, num_ctx=12288, idioma_fijo=True)
    texto = " ".join([data.get("titulo", ""), data.get("intro", "")] + [x.get("texto", "") for x in data.get("secciones", [])])
    if _idioma_de(texto) != idioma:  # el modelo a veces se va a otro idioma (p. ej. portugués): una vez más
        progreso("It drifted to another language; rewriting…" if ingles else "Se fue a otro idioma; reescribiendo…")
        msgs += [{"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
                 {"role": "user", "content": "Rewrite the whole JSON in ENGLISH." if ingles else
                  "Reescribe todo el JSON en ESPAÑOL de México."}]
        data = ollama.chat_json(modelo, msgs, ESQUEMA_LECCION, temperature=0.2, num_ctx=12288, idioma_fijo=True)
    data["secciones"] = [s for s in data.get("secciones", []) if (s.get("texto") or "").strip()]
    if not data["secciones"]:
        raise ValueError("El modelo no escribió la lección; inténtalo otra vez.")
    # comandos de una sola línea, sin prompts tipo "R1(config)#"
    cmds = []
    for c in data.get("comandos", []):
        cmd = re.sub(r"^\S*[#>]\s*", "", (c.get("comando") or "").strip().splitlines()[0] if c.get("comando") else "")
        if cmd:
            cmds.append({"comando": cmd, "que_hace": c.get("que_hace", "")})
    data["comandos"] = cmds
    data["con_guias"] = bool(refs)
    return data


_PALABRAS = {
    "en": {"the", "and", "is", "of", "to", "with", "that", "for", "this", "are", "it", "on", "you"},
    "es": {"el", "la", "los", "las", "que", "y", "con", "para", "una", "es", "del", "por", "se", "como"},
    "pt": {"não", "uma", "são", "com", "do", "da", "em", "os", "as", "é", "no", "na", "dos", "das", "ao"},
}


def _idioma_de(texto: str) -> str:
    palabras = re.findall(r"[a-záéíóúñãõâêôçà]+", texto.lower())
    cuenta = {k: sum(p in v for p in palabras) for k, v in _PALABRAS.items()}
    return max(cuenta, key=cuenta.get) if palabras else ""


def responder_duda(modelo: str, leccion: dict, pregunta: str, idioma: str) -> str:
    ingles = idioma == "en"
    resumen = leccion.get("titulo", "") + "\n" + "\n".join(
        f"{s['titulo']}: {s['texto'][:600]}" for s in leccion.get("secciones", []))
    mundo = mundo_de(leccion.get("tema", ""))
    refs = _refs(f"{leccion.get('titulo', '')} {pregunta}", mundo=mundo)
    materia_en = {"ccna": "CCNA networking", "linux": "Linux", "wireshark": "Wireshark", "rust": "Rust", "rustproj": "Rust",
                  "ia": "AI/machine learning", "torch": "PyTorch", "cpu": "computer architecture", "chisel": "Chisel digital design",
                  "sv": "SystemVerilog hardware design and verification"}.get(mundo, "this subject")
    materia_es = {"ccna": "redes CCNA", "linux": "Linux", "wireshark": "Wireshark", "rust": "Rust", "rustproj": "Rust",
                  "ia": "IA y machine learning", "torch": "PyTorch", "cpu": "arquitectura de computadoras", "chisel": "diseño digital con Chisel",
                  "sv": "SystemVerilog: diseño digital y verificación"}.get(mundo, "esta materia")
    msgs = [{"role": "system", "content": (
        f"You are a patient {materia_en} tutor. Stay on this lesson's subject. Answer in English, short (max ~150 words), plain prose that "
        "sounds good read aloud. If the student is wrong, say so kindly and explain. Be technically exact."
        if ingles else
        f"Eres un tutor paciente de {materia_es}. No te salgas de la materia de la lección. Respondes en español de México, breve (máx. ~150 palabras), "
        "en prosa que suene bien leída en voz alta. Si el alumno está equivocado, díselo con amabilidad y "
        "explica. Sé técnicamente exacto.")},
        {"role": "user", "content": f"{'Lesson' if ingles else 'Lección'}:\n{resumen[:4000]}{refs}\n\n"
                                    f"{'Question' if ingles else 'Pregunta'}: {pregunta}"}]
    return ollama.chat(modelo, msgs, temperature=0.3, num_predict=800, idioma_fijo=True).strip()


# =============================================================================================================
# LECCIONES v2: un mini-curso por tema, generado en varias pasadas (plan → cada sección a fondo → cierre).
# Antes era UNA sola llamada que escribía todo de golpe: 2-3 párrafos por sección, sin ejemplos resueltos ni práctica.
# =============================================================================================================
_PASO = {"type": "object", "properties": {"paso": _S, "detalle": _S}, "required": ["paso", "detalle"]}
ESQUEMA_PLAN = {
    "type": "object",
    "properties": {
        "titulo": _S, "intro": _S,
        "objetivos": {"type": "array", "items": _S},
        "metodos_clave": {"type": "array", "items": _S},
        "secciones": {"type": "array", "items": {"type": "object", "properties": {"titulo": _S, "enfoque": _S},
                                                  "required": ["titulo", "enfoque"]}},
    },
    "required": ["titulo", "intro", "objetivos", "metodos_clave", "secciones"],
}
ESQUEMA_SECCION = {
    "type": "object",
    "properties": {
        "texto": _S,
        "analogia": _S,
        "ejemplo": {"type": "object", "properties": {"titulo": _S, "pasos": {"type": "array", "items": _PASO}, "resultado": _S},
                    "required": ["titulo", "pasos", "resultado"]},
        "codigo": {"type": "object", "properties": {"lenguaje": _S, "contenido": _S, "explicacion": _S},
                   "required": ["lenguaje", "contenido", "explicacion"]},
        "practica": {"type": "object", "properties": {"enunciado": _S, "pista": _S, "solucion": _S},
                     "required": ["enunciado", "pista", "solucion"]},
    },
    "required": ["texto", "analogia", "ejemplo", "codigo", "practica"],
}
ESQUEMA_CIERRE = {
    "type": "object",
    "properties": {
        "comandos": {"type": "array", "items": {"type": "object", "properties": {"comando": _S, "que_hace": _S},
                                                 "required": ["comando", "que_hace"]}},
        "puntos_clave": {"type": "array", "items": _S},
        "errores_comunes": {"type": "array", "items": _S},
        "quiz": {"type": "array", "items": {"type": "object", "properties": {
            "pregunta": _S, "opciones": {"type": "array", "items": _S}, "correcta": {"type": "integer"}, "explicacion": _S},
            "required": ["pregunta", "opciones", "correcta", "explicacion"]}},
        "laboratorio": {"type": "object", "properties": {"titulo": _S, "objetivo": _S, "pasos": {"type": "array", "items": _S},
                                                          "verificacion": _S},
                        "required": ["titulo", "objetivo", "pasos", "verificacion"]},
    },
    "required": ["comandos", "puntos_clave", "errores_comunes", "quiz", "laboratorio"],
}

# Lo que un buen instructor de cada certificación SIEMPRE enseña de ciertos temas (se inyecta si el tema coincide).
# (materias donde aplica, palabras que lo activan, método). Las palabras se buscan COMPLETAS (antes "nat" coincidía dentro de
# "originate" y "match" de Wireshark metía métodos de Rust): así la lección de OSPF no se llena de NAT y subneteo.
_METODOS = [
    (("redes",), ("subneteo", "subnetting", "subred", "subredes", "vlsm", "cidr", "direccionamiento ipv4", "ipv4"),
     "Método del NÚMERO MÁGICO (256 − valor del octeto interesante de la máscara = tamaño del bloque; las redes van de bloque en bloque) "
     "con al menos dos ejemplos resueltos completos (uno /26 y uno /20), tabla de potencias de 2, cómo sacar red, broadcast, "
     "primer y último host y número de hosts (2^h − 2), VLSM asignando de la red más grande a la más chica, y la wildcard "
     "(255.255.255.255 − máscara)."),
    (("redes",), ("ospf", "ospfv2", "ospfv3"), "Costo = ancho de banda de referencia / ancho de banda de la interfaz (con números), elección de DR/BDR (prioridad y "
                "router-id), estados de vecino (Down→Full), comando network con wildcard y área, y verificación con show ip ospf neighbor."),
    (("redes",), ("acl", "acls", "access-list", "lista de acceso"), "Orden de evaluación de arriba abajo, deny any implícito al final, ACL estándar cerca del destino y extendida cerca del "
               "origen, cálculo de wildcards con ejemplos, y verificación con show access-lists (contadores de coincidencias)."),
    (("redes",), ("vlan", "vlans", "troncal", "troncales", "802.1q", "svi", "router-on-a-stick"), "Etiqueta 802.1Q (4 bytes, VID de 12 bits), VLAN nativa sin etiquetar, "
                                                                   "puertos de acceso vs troncal, y verificación con show vlan brief y show interfaces trunk."),
    (("redes",), ("stp", "spanning-tree", "spanning"), "Elección del root bridge (bridge ID = prioridad + MAC), costos de puerto, roles (root/designated/blocking) "
                          "resuelto en un ejemplo de 3 switches, PortFast y BPDU Guard."),
    (("redes",), ("nat", "pat"), "Direcciones inside local/inside global/outside, NAT estático vs dinámico vs PAT con un ejemplo de traducción "
                     "paso a paso (IP:puerto antes y después) y show ip nat translations."),
    (("rust",), ("ownership", "préstamos", "prestamos", "borrow", "borrowing"), "Las 3 reglas de ownership, move vs Copy, las reglas del borrow checker (muchas & o UNA "
                                                      "&mut), dibujo de stack vs heap con String, y errores reales del compilador "
                                                      "(E0382 use of moved value, E0502) con su arreglo."),
    (("rust",), ("lifetime", "lifetimes"), "Anotación 'a, por qué existe (referencias colgantes), reglas de elisión, y el ejemplo clásico fn longest<'a>."),
    (("rust",), ("trait", "traits", "genéricos", "genericos"), "Definir e implementar traits, trait bounds (T: Display), impl Trait, y monomorfización."),
    (("rust",), ("enum", "enums", "match", "option", "result"), "Option/Result en vez de null/excepciones, match exhaustivo, if let, y el operador ?."),
    (("linux",), ("permisos", "chmod", "umask", "chown"), "Conversión rwx ↔ octal paso a paso (r=4, w=2, x=1), lectura de ls -l columna por columna, umask "
                                    "(permisos por defecto 666/777 menos umask), y setuid/setgid/sticky con ejemplos reales."),
    (("cpu", "chisel"), ("binario", "bits", "complemento", "hexadecimal", "hex"), "Conversión decimal ↔ binario ↔ hexadecimal paso a paso, "
                                                                            "complemento a dos (invertir y sumar 1), rangos con n bits y desbordamiento."),
    (("wireshark", "redes"), ("handshake", "three-way", "conexión tcp", "análisis tcp"), "Three-way handshake con números de secuencia y ACK reales, flags, ventana, retransmisiones y cierre con FIN."),
    (("ia",), ("backprop", "neuronales", "gradiente"), "Regla de la cadena con un ejemplo NUMÉRICO de una red de 2 neuronas, y un paso de "
                                                    "descenso por gradiente con números (peso nuevo = peso − lr × gradiente)."),
    (("linux", "soc"), ("fuerza bruta", "4625", "auth.log", "fail2ban"), "Patrón de fuerza bruta en logs (muchos fallos 4625 / Failed password "
                                                               "desde una IP y luego un éxito 4624), umbrales, y cómo responder."),
]


def _metodos_para(texto: str, materia: str = "") -> list[str]:
    t = (texto or "").lower()
    def esta(k):
        return re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", t) is not None
    return [m for mats, claves, m in _METODOS if (not materia or materia in mats) and any(esta(k) for k in claves)]


def _es_subneteo(texto: str) -> bool:
    return bool(_metodos_para(texto)) and _METODOS[0][2] in _metodos_para(texto)


def _tabla_subneteo() -> str:
    """Tabla de verdad calculada por código (/8–/30): el modelo la usa en vez de inventar máscaras."""
    filas = []
    for p in range(8, 31):
        m = ipaddress.IPv4Network(f"0.0.0.0/{p}").netmask
        octs = str(m).split(".")
        i = next((k for k, o in enumerate(octs) if o != "255"), 3)
        bloque = 256 - int(octs[i])
        filas.append(f"/{p} = {m} · octeto interesante {i + 1} (valor {octs[i]}) · bloque/número mágico {bloque} · hosts útiles {2 ** (32 - p) - 2}")
    return "\n".join(filas)


_RE_PREF = re.compile(r"/(\d{1,2})\b")
_RE_MASK = re.compile(r"\b(255\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_RE_MAGIC = re.compile(r"256\s*[-−–]\s*(\d{1,3})\s*=\s*(\d{1,3})")


def _errores_ipv4(seccion: dict) -> list[str]:
    """Verificador determinista: prefijo vs máscara en la misma frase/paso, y restas del número mágico."""
    textos = [seccion.get("texto", "")]
    ej = seccion.get("ejemplo") or {}
    textos += [f"{p.get('paso', '')} {p.get('detalle', '')}" for p in ej.get("pasos") or []] + [ej.get("resultado", "")]
    pr = seccion.get("practica") or {}
    textos += [pr.get("enunciado", ""), pr.get("solucion", "")]
    errores = []
    for t in textos:
        # el paso completo Y cada oración: "IP: 172.16.0.0/20. Mask: 255.255.192.0." trae prefijo y máscara en oraciones distintas
        for frase in dict.fromkeys([t or ""] + re.split(r"(?<=[.;\n])\s+", t or "")):
            pref = {int(x) for x in _RE_PREF.findall(frase) if 8 <= int(x) <= 32}
            masks = set(_RE_MASK.findall(frase))
            if len(pref) == 1 and len(masks) == 1:
                p, m = pref.pop(), masks.pop()
                try:
                    bien = str(ipaddress.IPv4Network(f"0.0.0.0/{p}").netmask)
                except ValueError:
                    continue
                if m != bien:
                    errores.append(f"«{frase.strip()[:160]}»: /{p} es {bien}, NO {m}.")
            for a, b in _RE_MAGIC.findall(frase):
                if 256 - int(a) != int(b):
                    errores.append(f"«{frase.strip()[:160]}»: 256 − {a} = {256 - int(a)}, NO {b}.")
    return list(dict.fromkeys(errores))[:8]


_REVISOR = {
    "es": ("Eres un revisor técnico ESTRICTO de material de certificación. Revisa esta sección palabra por palabra: recalcula "
           "paso a paso CADA número, máscara, dirección, fórmula, resultado y comando, y verifica cada afirmación técnica. Corrige "
           "TODO lo incorrecto (y lo que dependa de eso: siguiente red, broadcast, rangos, solución de la práctica). No acortes, no "
           "quites ejemplos ni cambies lo que ya está bien. Mantén el idioma (español de México). Devuelve el MISMO JSON corregido."),
    "en": ("You are a STRICT technical reviewer of certification material. Review this section word by word: recompute step by step "
           "EVERY number, mask, address, formula, result and command, and verify every technical claim. Fix EVERYTHING that is wrong "
           "(and whatever depends on it: next network, broadcast, ranges, the practice solution). Don't shorten, don't remove "
           "examples, don't change what is already right. Keep it in English. Return the SAME JSON, corrected."),
}


def _arreglar_magia(texto: str) -> str:
    """Último recurso determinista para "256 − X = Y" mal hecho: si Y es un bloque válido (potencia de 2 ≤ 128), X = 256 − Y
    (p. ej. "256 - 8 = 8" → "256 - 248 = 8"); si no, se corrige el resultado (Y = 256 − X)."""
    def fix(m):
        a, b = int(m.group(2)), int(m.group(4))
        if 256 - a == b:
            return m.group(0)
        if b in (1, 2, 4, 8, 16, 32, 64, 128):
            return f"{m.group(1)}{256 - b}{m.group(3)}{b}"
        return f"{m.group(1)}{a}{m.group(3)}{256 - a}"
    return re.sub(r"(256\s*[-−–]\s*)(\d{1,3})(\s*=\s*)(\d{1,3})", fix, texto or "")


def _arreglar_seccion(s: dict) -> dict:
    s = json.loads(json.dumps(s))
    s["texto"] = _arreglar_magia(s["texto"])
    for p in s["ejemplo"]["pasos"]:
        p["paso"], p["detalle"] = _arreglar_magia(p["paso"]), _arreglar_magia(p["detalle"])
    s["ejemplo"]["resultado"] = _arreglar_magia(s["ejemplo"]["resultado"])
    for k in ("enunciado", "pista", "solucion"):
        s["practica"][k] = _arreglar_magia(s["practica"][k])
    return s


def _nota_morada(materia: str, lang: str) -> str:
    """Purple Team (índice ofensivo): el revisor tampoco debe dejar pasos de ataque."""
    if materia != "purple":
        return ""
    return ("Regla: esta teoría es de Purple Team. Si encuentras pasos operativos de ataque, comandos de explotación o "
            "payloads, quítalos y deja solo el concepto, la detección y la mitigación." if lang == "es" else
            "Rule: this is Purple Team theory. If you find operational attack steps, exploitation commands or payloads, "
            "remove them and keep only the concept, detection and mitigation.")


def _revisar_seccion(modelo: str, s: dict, lang: str, extra: str = "") -> dict:
    return _arreglar_seccion(_revisar_seccion_modelo(modelo, s, lang, extra))


def _revisar_seccion_modelo(modelo: str, s: dict, lang: str, extra: str = "") -> dict:
    """Segunda pasada de revisión técnica (+ verificador determinista de IPv4). Si algo falla, se queda la original."""
    errores = _errores_ipv4(s)
    pedido = json.dumps({k: s[k] for k in ("texto", "analogia", "ejemplo", "codigo", "practica")}, ensure_ascii=False)
    if errores:
        pedido += ("\n\nErrores DETECTADOS por el verificador automático (corrígelos sí o sí):\n" if lang == "es"
                   else "\n\nErrors DETECTED by the automatic checker (you MUST fix them):\n") + "\n".join(errores)
    if extra:
        pedido += "\n\n" + extra
    try:
        r = _limpia_seccion(ollama.chat_json(modelo, [{"role": "system", "content": _REVISOR[lang]}, {"role": "user", "content": pedido}],
                                             ESQUEMA_SECCION, temperature=0.1, num_ctx=16384, num_predict=4500, idioma_fijo=True))
    except Exception:  # noqa: BLE001
        return s
    # no aceptar una "corrección" que recorte la sección a la mitad o pierda el ejemplo
    if len(r["texto"]) < 0.6 * len(s["texto"]) or (s["ejemplo"]["pasos"] and not r["ejemplo"]["pasos"]):
        return s
    if errores and len(_errores_ipv4(r)) >= len(errores):  # el revisor no arregló lo detectado: segundo intento enfocado
        return s if len(_errores_ipv4(s)) <= len(_errores_ipv4(r)) else r
    return r


# Dónde se hace el laboratorio final de cada materia
_LAB_DONDE = {"redes": "en Cisco Packet Tracer (routers/switches reales del temario CCNA)", "wireshark": "en Wireshark con una captura real",
              "linux": "en una terminal de Ubuntu", "rust": "con cargo en un proyecto nuevo (cargo new)", "ia": "en Python con PyTorch",
              "cpu": "con lápiz y papel y el simulador RISC-V", "chisel": "con sbt y chiseltest", "soc": "en Kibana o con los logs del caso",
              "sv": "en EDA Playground o con Verilator (simulando el módulo y viendo las formas de onda)",
              "purple": "desde el lado del defensor: el ataque se practica en la sala legal de TryHackMe/HTB del tema y aquí solo se "
                        "busca su rastro (logs, Event IDs, filtros) y se escribe cómo detectarlo y mitigarlo"}

_TXT = {
    "es": {
        "idioma": "español de México",
        "plan": ("{persona}Diseña una lección de nivel PROFESIONAL, como un capítulo de un curso de certificación serio, no un resumen. "
                 "Debe ir de lo fundamental a lo avanzado: qué es y por qué existe → cómo funciona por dentro → el método o procedimiento "
                 "paso a paso → ejemplos resueltos → cómo se verifica y se diagnostica → cómo lo pregunta el examen. "
                 "'intro': 2 o 3 oraciones que expliquen por qué importa este tema en el trabajo real. "
                 "'objetivos': 4 a 6 cosas concretas que el alumno sabrá HACER al terminar (verbos de acción). "
                 "'metodos_clave': las técnicas, fórmulas, reglas o atajos que un instructor de la certificación SIEMPRE enseña de este tema. "
                 "'secciones': de 5 a 7, cada una con un título claro y un 'enfoque' de una o dos oraciones con lo que DEBE cubrir. "
                 "TODAS las secciones son de ESTE tema: no agregues secciones de otros temas del temario (si el tema es OSPF, nada de NAT ni "
                 "de subneteo; si es Wireshark, nada de programación). Todo en español de México."),
        "seccion": ("{persona}Escribes la sección {i} de {n} de una lección profesional. Todo en español de México; los comandos, "
                    "palabras clave y nombres técnicos se quedan como se escriben de verdad. Requisitos:\n"
                    "- 'texto': de 4 a 7 párrafos de 3 a 5 oraciones cada uno, separados por un salto de línea. Explica el PORQUÉ y el CÓMO "
                    "con valores y casos concretos; nada de relleno ni generalidades. Si hay un método o fórmula, explícalo con números.\n"
                    "- 'analogia': una analogía breve que de verdad ayude a entender (o \"\" si no aplica).\n"
                    "- 'ejemplo': un ejemplo RESUELTO paso a paso con valores reales: de 3 a 8 pasos; cada 'paso' es la acción o el "
                    "cálculo corto y 'detalle' explica qué se hace y el resultado parcial. 'resultado' es la conclusión final.\n"
                    "- 'codigo': {que_comandos}. Si no aplica a esta sección, deja los tres campos vacíos. 'contenido' puede tener varias "
                    "líneas; 'explicacion' dice qué hace.\n"
                    "- 'practica': un ejercicio corto DISTINTO del ejemplo para que el alumno lo resuelva; 'pista' sin regalar la "
                    "respuesta; 'solucion' completa y explicada paso a paso.\n"
                    "Explica con {que_ejemplo}. No repitas lo de otras secciones."),
        "cierre": ("{persona}Cierra una lección profesional. Todo en español de México. Requisitos:\n"
                   "- 'comandos': {que_comandos}; de 5 a 10, con 'que_hace' claro. Si el tema no tiene, lista vacía.\n"
                   "- 'puntos_clave': de 6 a 8 ideas que el alumno debe recordar para el examen, concretas (con números o reglas).\n"
                   "- 'errores_comunes': de 4 a 6; cada uno dice el error, por qué pasa y cómo evitarlo.\n"
                   "- 'quiz': 5 preguntas de opción múltiple de nivel examen, 4 opciones, UNA sola correcta ('correcta' es el índice 0-3), "
                   "con 'explicacion' de por qué.\n"
                   "- 'laboratorio': un laboratorio práctico final que junte TODA la lección, hecho {lab}: 'titulo', 'objetivo', 'pasos' "
                   "(de 5 a 8 pasos concretos y ejecutables) y 'verificacion' (cómo comprobar que quedó bien)."),
        "usuario_plan": "Tema: {tema}\nConceptos clave: {clave}\n{enfoque}{metodos}Devuelve solo el JSON.",
        "usuario_sec": ("Tema de la lección: {tema}\nPlan completo:\n{plan}\nMétodos clave que la lección debe enseñar: {metodos}\n\n"
                        "Escribe AHORA la sección {i}: «{titulo}». Enfoque: {enfoque}\nDevuelve solo el JSON."),
        "usuario_cierre": "Tema de la lección: {tema}\nSecciones:\n{plan}\nMétodos clave: {metodos}\nDevuelve solo el JSON.",
        "prog_plan": "Planeando la lección con {m}…", "prog_sec": "Escribiendo la sección {i}/{n}: {t}…", "prog_cierre": "Armando quiz, laboratorio y repaso…",
        "prog_rev": "Revisando la sección {i}/{n} (recalculando cada número)…", "prog_quiz": "Verificando las respuestas del quiz…",
        "tabla": "Tabla VERIFICADA calculada por código (úsala y NO la contradigas en ningún número):",
    },
    "en": {
        "idioma": "English",
        "plan": ("{persona}Design a PROFESSIONAL-level lesson, like a chapter of a serious certification course, not a summary. "
                 "Go from fundamentals to advanced: what it is and why it exists → how it works inside → the step-by-step method or "
                 "procedure → worked examples → how to verify and troubleshoot → how the exam asks about it. "
                 "'intro': 2-3 sentences on why this topic matters in real work. 'objetivos': 4-6 concrete things the student will be "
                 "able to DO (action verbs). 'metodos_clave': the techniques, formulas, rules or shortcuts a certification instructor ALWAYS "
                 "teaches for this topic. 'secciones': 5 to 7, each with a clear title and a one-or-two sentence 'enfoque' of what it MUST cover. "
                 "ALL sections are about THIS topic: don't add sections about other syllabus topics (if the topic is OSPF, no NAT or subnetting; "
                 "if it's Wireshark, no programming). Everything in English (the topic below may be written in Spanish)."),
        "seccion": ("{persona}You write section {i} of {n} of a professional lesson, in English. Keep commands, keywords and technical "
                    "names exactly as really written. Requirements:\n"
                    "- 'texto': 4 to 7 paragraphs of 3-5 sentences each, separated by a newline. Explain the WHY and the HOW with concrete "
                    "values and cases; no filler or vague statements. If there is a method or formula, explain it with numbers.\n"
                    "- 'analogia': a short analogy that truly helps (or \"\" if none fits).\n"
                    "- 'ejemplo': a WORKED example step by step with real values: 3 to 8 steps; each 'paso' is the short action or "
                    "calculation and 'detalle' explains it and the partial result. 'resultado' is the final conclusion.\n"
                    "- 'codigo': {que_comandos}. If it doesn't apply to this section, leave all three fields empty. 'contenido' may be "
                    "multi-line; 'explicacion' says what it does.\n"
                    "- 'practica': a short exercise DIFFERENT from the example for the student to solve; 'pista' must not give the "
                    "answer away; 'solucion' complete and explained step by step.\n"
                    "Explain with {que_ejemplo}. Don't repeat other sections."),
        "cierre": ("{persona}Close a professional lesson, in English. Requirements:\n"
                   "- 'comandos': {que_comandos}; 5 to 10, with a clear 'que_hace'. Empty list if the topic has none.\n"
                   "- 'puntos_clave': 6 to 8 concrete ideas to remember for the exam (with numbers or rules).\n"
                   "- 'errores_comunes': 4 to 6; each says the mistake, why it happens and how to avoid it.\n"
                   "- 'quiz': 5 exam-level multiple-choice questions, 4 options, ONE correct ('correcta' is the 0-3 index), with an "
                   "'explicacion' of why.\n"
                   "- 'laboratorio': a final hands-on lab tying the WHOLE lesson together, done {lab}: 'titulo', 'objetivo', 'pasos' "
                   "(5 to 8 concrete, runnable steps) and 'verificacion' (how to check it worked)."),
        "usuario_plan": "Topic (in Spanish): {tema}\nKey concepts (in Spanish): {clave}\n{enfoque}{metodos}Return only the JSON, in English.",
        "usuario_sec": ("Lesson topic: {tema}\nFull plan:\n{plan}\nKey methods the lesson must teach: {metodos}\n\n"
                        "Write NOW section {i}: «{titulo}». Focus: {enfoque}\nReturn only the JSON, in English."),
        "usuario_cierre": "Lesson topic: {tema}\nSections:\n{plan}\nKey methods: {metodos}\nReturn only the JSON, in English.",
        "prog_plan": "Planning the lesson with {m}…", "prog_sec": "Writing section {i}/{n}: {t}…", "prog_cierre": "Building quiz, lab and review…",
        "prog_rev": "Reviewing section {i}/{n} (recomputing every number)…", "prog_quiz": "Verifying the quiz answers…",
        "tabla": "VERIFIED table computed by code (use it and do NOT contradict any number):",
    },
}
_LAB_DONDE_EN = {"redes": "in Cisco Packet Tracer", "wireshark": "in Wireshark with a real capture", "linux": "in an Ubuntu terminal",
                 "rust": "with cargo in a new project (cargo new)", "ia": "in Python with PyTorch", "cpu": "with pen and paper and the RISC-V simulator",
                 "chisel": "with sbt and chiseltest", "soc": "in Kibana or with the case logs",
                 "sv": "in EDA Playground or with Verilator (simulating the module and viewing the waveforms)",
                 "purple": "from the defender's side: the attack is practiced in the legal TryHackMe/HTB room for the topic and here you only "
                           "look for its trace (logs, Event IDs, filters) and write how to detect and mitigate it"}


def _limpia_seccion(s: dict) -> dict:
    ej = s.get("ejemplo") or {}
    cod = s.get("codigo") or {}
    pr = s.get("practica") or {}
    return {
        "texto": (s.get("texto") or "").strip(),
        "analogia": (s.get("analogia") or "").strip(),
        "ejemplo": {"titulo": (ej.get("titulo") or "").strip(),
                    "pasos": [{"paso": (p.get("paso") or "").strip(), "detalle": (p.get("detalle") or "").strip()}
                              for p in (ej.get("pasos") or []) if (p.get("paso") or p.get("detalle"))][:10],
                    "resultado": (ej.get("resultado") or "").strip()},
        "codigo": {"lenguaje": (cod.get("lenguaje") or "").strip(), "contenido": (cod.get("contenido") or "").rstrip(),
                   "explicacion": (cod.get("explicacion") or "").strip()},
        "practica": {"enunciado": (pr.get("enunciado") or "").strip(), "pista": (pr.get("pista") or "").strip(),
                     "solucion": (pr.get("solucion") or "").strip()},
    }


def generar_leccion(modelo: str, tema_txt: str, clave: str, idioma: str, enfoque: str = "",
                    progreso=lambda m: None, materia: str = "redes") -> dict:
    """Lección v2 en varias pasadas: plan → cada sección a fondo (ejemplo resuelto + práctica) → cierre (quiz + laboratorio)."""
    lang = "en" if idioma == "en" else "es"
    T = _TXT[lang]
    mundo = _MATERIA_A_MUNDO.get(materia, materia)
    mat = MATERIAS.get(materia, MATERIAS["redes"])
    persona, que_comandos, que_ejemplo = mat.get(lang) or mat["es"]
    metodos = _metodos_para(f"{tema_txt} {clave} {enfoque}", materia)
    metodos_txt = ("Métodos que DEBES incluir: " if lang == "es" else "Methods you MUST include: ") + " ".join(metodos) + "\n" if metodos else ""
    enfoque_txt = (("Enfoque pedido: " if lang == "es" else "Requested focus: ") + enfoque + "\n") if enfoque else ""
    # temas de subneteo: tabla de verdad calculada por Python (antes el modelo inventó "/20 = 255.255.192.0")
    tabla = f"\n\n{T['tabla']}\n{_tabla_subneteo()}" if _es_subneteo(f"{tema_txt} {clave} {enfoque}") else ""

    # 1) plan
    refs = _refs(f"{tema_txt} {clave} {enfoque}", progreso, mundo=mundo)
    progreso(T["prog_plan"].format(m=modelo))
    plan = ollama.chat_json(modelo, [
        {"role": "system", "content": T["plan"].format(persona=persona)},
        {"role": "user", "content": T["usuario_plan"].format(tema=tema_txt, clave=clave, enfoque=enfoque_txt, metodos=metodos_txt) + refs}],
        ESQUEMA_PLAN, temperature=0.4, num_ctx=12288, num_predict=2500, idioma_fijo=True)
    secciones_plan = [s for s in (plan.get("secciones") or []) if (s.get("titulo") or "").strip()][:7]
    if len(secciones_plan) < 3:
        raise ValueError("El modelo no pudo planear la lección; inténtalo otra vez.")
    metodos_plan = [m for m in (plan.get("metodos_clave") or []) if m.strip()][:8]
    metodos_todos = "; ".join(metodos_plan + metodos) or "-"
    resumen_plan = "\n".join(f"{i}. {s['titulo']} — {s.get('enfoque', '')}" for i, s in enumerate(secciones_plan, 1))

    # 2) cada sección a fondo, con sus propias guías (del mismo mundo)
    secciones = []
    for i, sp in enumerate(secciones_plan, 1):
        progreso(T["prog_sec"].format(i=i, n=len(secciones_plan), t=sp["titulo"]))
        refs_s = _refs(f"{tema_txt} {sp['titulo']} {sp.get('enfoque', '')}", mundo=mundo)
        msgs = [{"role": "system", "content": T["seccion"].format(persona=persona, i=i, n=len(secciones_plan),
                                                                    que_comandos=que_comandos, que_ejemplo=que_ejemplo)},
                {"role": "user", "content": T["usuario_sec"].format(tema=tema_txt, plan=resumen_plan, metodos=metodos_todos, i=i,
                                                                    titulo=sp["titulo"], enfoque=sp.get("enfoque", "")) + tabla + refs_s}]
        try:
            s = _limpia_seccion(ollama.chat_json(modelo, msgs, ESQUEMA_SECCION, temperature=0.4, num_ctx=12288,
                                                 num_predict=4000, idioma_fijo=True))
            if lang and _idioma_de(s["texto"]) not in ("", lang):  # se fue a otro idioma: otra vez
                s = _limpia_seccion(ollama.chat_json(modelo, msgs + [{"role": "user", "content": (
                    "Escríbelo TODO en español de México." if lang == "es" else "Write EVERYTHING in English.")}],
                    ESQUEMA_SECCION, temperature=0.3, num_ctx=12288, num_predict=4000, idioma_fijo=True))
        except ollama.OllamaError:
            raise
        except Exception:  # noqa: BLE001  (una sección fallida no tumba toda la lección)
            continue
        if s["texto"]:
            progreso(T["prog_rev"].format(i=i, n=len(secciones_plan)))
            s = _revisar_seccion(modelo, s, lang, extra=(tabla.strip() + "\n\n" + _nota_morada(materia, lang)).strip())
            secciones.append({"titulo": sp["titulo"].strip(), **s})
    if len(secciones) < 2:
        raise ValueError("El modelo no escribió la lección; inténtalo otra vez.")

    # 3) cierre: comandos, puntos clave, errores comunes, quiz y laboratorio
    progreso(T["prog_cierre"])
    lab = (_LAB_DONDE_EN if lang == "en" else _LAB_DONDE).get(materia, _LAB_DONDE.get(materia, ""))
    try:
        cierre = ollama.chat_json(modelo, [
            {"role": "system", "content": T["cierre"].format(persona=persona, que_comandos=que_comandos, lab=lab)},
            {"role": "user", "content": T["usuario_cierre"].format(tema=tema_txt, plan="\n".join(f"- {s['titulo']}" for s in secciones),
                                                                   metodos=metodos_todos)}],
            ESQUEMA_CIERRE, temperature=0.3, num_ctx=12288, num_predict=5000, idioma_fijo=True)
    except ollama.OllamaError:
        raise
    except Exception:  # noqa: BLE001
        cierre = {}
    cmds = []
    for c in cierre.get("comandos") or []:
        cmd = re.sub(r"^\S*[#>]\s*", "", (c.get("comando") or "").strip().splitlines()[0] if c.get("comando") else "")
        if cmd:
            cmds.append({"comando": cmd, "que_hace": c.get("que_hace", "")})
    quiz = []
    for q in cierre.get("quiz") or []:
        ops = [o for o in (q.get("opciones") or []) if str(o).strip()][:4]
        k = q.get("correcta")
        if len(ops) >= 3 and isinstance(k, int) and 0 <= k < len(ops) and (q.get("pregunta") or "").strip():
            quiz.append({"pregunta": q["pregunta"].strip(), "opciones": ops, "correcta": k, "explicacion": (q.get("explicacion") or "").strip()})
    if quiz:  # el modelo contesta el quiz sin ver la clave; solo se quedan las preguntas en las que coincide
        progreso(T["prog_quiz"])
        quiz = _verificar_quiz(modelo, quiz, tabla) or quiz
    labo = cierre.get("laboratorio") or {}
    return {
        "version": 2,
        "titulo": (plan.get("titulo") or tema_txt).strip(),
        "intro": (plan.get("intro") or "").strip(),
        "objetivos": [o.strip() for o in (plan.get("objetivos") or []) if o.strip()][:6],
        "metodos_clave": metodos_plan,
        "secciones": secciones,
        "comandos": cmds,
        "puntos_clave": [p for p in (cierre.get("puntos_clave") or []) if p.strip()][:10],
        "errores_comunes": [p for p in (cierre.get("errores_comunes") or []) if p.strip()][:8],
        "quiz": quiz[:6],
        "laboratorio": {"titulo": (labo.get("titulo") or "").strip(), "objetivo": (labo.get("objetivo") or "").strip(),
                        "pasos": [p for p in (labo.get("pasos") or []) if str(p).strip()][:10],
                        "verificacion": (labo.get("verificacion") or "").strip()},
        "con_guias": bool(refs),
    }


def _verificar_quiz(modelo: str, quiz: list[dict], contexto: str = "") -> list[dict]:
    letras = "ABCDEF"
    texto = "\n\n".join(f"Pregunta {k}. {q['pregunta']}\n" + "\n".join(f"  {letras[j]}) {o}" for j, o in enumerate(q["opciones"]))
                        for k, q in enumerate(quiz, 1))
    try:
        ver = ollama.chat_json(modelo, [
            {"role": "system", "content": "Eres experto en el tema. Para cada pregunta indica TODAS las letras de las opciones técnicamente "
                                          "correctas (una, varias o ninguna). 'n' es el número de pregunta. Recalcula los números."},
            {"role": "user", "content": texto + (("\n\n" + contexto) if contexto else "")}], ESQUEMA_VERIF, temperature=0.0, num_ctx=12288,
            idioma_fijo=True)
        resp = {r.get("n"): sorted(set(r.get("correctas") or [])) for r in ver.get("respuestas", [])}
    except Exception:  # noqa: BLE001
        return quiz
    return [q for k, q in enumerate(quiz, 1) if resp.get(k) == [letras[q["correcta"]]]]


def generar_teoria_mision(modelo: str, materia: str, titulo: str, contexto: str, idioma: str, progreso=lambda m: None) -> dict:
    """Teoría a fondo de UNA misión (sus textos fijos eran de 30-50 palabras): explicación completa, ejemplo resuelto
    DISTINTO al reto (para no regalar la solución), código, ejercicio de calentamiento. Pasa por el revisor técnico."""
    lang = "en" if idioma == "en" else "es"
    T = _TXT[lang]
    mundo = _MATERIA_A_MUNDO.get(materia, materia)
    persona, que_comandos, que_ejemplo = MATERIAS.get(materia, MATERIAS["redes"]).get(lang) or MATERIAS.get(materia, MATERIAS["redes"])["es"]
    metodos = _metodos_para(f"{titulo} {contexto}", materia)
    extra = ("Esta es la TEORÍA DE APOYO de una misión práctica. Enseña a fondo el concepto que el alumno necesita para resolverla, "
             "pero NO resuelvas el reto de la misión ni des su comando o código exacto: usa ejemplos distintos. "
             if lang == "es" else
             "This is the SUPPORTING THEORY for a hands-on mission. Teach the concept the student needs in depth, but DO NOT solve "
             "the mission's challenge or give its exact command or code: use different examples. ")
    usuario = ((f"Misión: {titulo}\nDe qué trata: {contexto}\n" if lang == "es" else f"Mission: {titulo}\nWhat it is about: {contexto}\n")
               + (("Métodos que DEBES incluir: " if lang == "es" else "Methods you MUST include: ") + " ".join(metodos) + "\n" if metodos else "")
               + ("Devuelve solo el JSON." if lang == "es" else "Return only the JSON, in English."))
    refs = _refs(f"{titulo} {contexto}", progreso, mundo=mundo)
    tabla = f"\n\n{T['tabla']}\n{_tabla_subneteo()}" if _es_subneteo(f"{titulo} {contexto}") else ""
    progreso(("Escribiendo la teoría a fondo con " if lang == "es" else "Writing the in-depth theory with ") + modelo + "…")
    msgs = [{"role": "system", "content": extra + T["seccion"].format(persona=persona, i=1, n=1, que_comandos=que_comandos, que_ejemplo=que_ejemplo)},
            {"role": "user", "content": usuario + tabla + refs}]
    s = _limpia_seccion(ollama.chat_json(modelo, msgs, ESQUEMA_SECCION, temperature=0.4, num_ctx=12288, num_predict=4000, idioma_fijo=True))
    if _idioma_de(s["texto"]) not in ("", lang):
        s = _limpia_seccion(ollama.chat_json(modelo, msgs + [{"role": "user", "content": (
            "Escríbelo TODO en español de México." if lang == "es" else "Write EVERYTHING in English.")}],
            ESQUEMA_SECCION, temperature=0.3, num_ctx=12288, num_predict=4000, idioma_fijo=True))
    if not s["texto"]:
        raise ValueError("El modelo no escribió la teoría; inténtalo otra vez.")
    progreso(T["prog_rev"].format(i=1, n=1))
    morado = _nota_morada(materia, lang)
    s = _revisar_seccion(modelo, s, lang, extra=(tabla.strip() + "\n\n" + morado).strip())
    return {"titulo": titulo, **s, "idioma": lang, "con_guias": bool(refs)}


def traducir_leccion_v2(modelo: str, l: dict, destino: str, progreso=lambda m: None) -> dict:
    """Traduce una lección v2 por partes (una sola llamada con todo se truncaba)."""
    idioma = "natural US English" if destino == "en" else "Mexican Spanish"
    sistema = (f"Translate this lesson part to {idioma}. Keep commands, code, filters, field names, numbers and the JSON keys "
               "EXACTLY as they are (do not translate code or 'comando'/'contenido' values). Return the same JSON structure.")

    def tr_(obj, esquema, n_pred=5000):
        try:
            r = ollama.chat_json(modelo, [{"role": "system", "content": sistema},
                                          {"role": "user", "content": json.dumps(obj, ensure_ascii=False)}],
                                 esquema, temperature=0.1, num_ctx=16384, num_predict=n_pred, idioma_fijo=True)
            return {k: (r.get(k) if r.get(k) else obj[k]) for k in obj}
        except Exception:  # noqa: BLE001
            return obj
    progreso("Traduciendo la lección…")
    cab = tr_({k: l.get(k) for k in ("titulo", "intro", "objetivos", "metodos_clave")},
              {"type": "object", "properties": {k: ESQUEMA_PLAN["properties"][k] for k in ("titulo", "intro", "objetivos", "metodos_clave")},
               "required": ["titulo", "intro", "objetivos", "metodos_clave"]}, 2500)
    secs = []
    esq_s = {"type": "object", "properties": {"titulo": _S, **ESQUEMA_SECCION["properties"]}, "required": ["titulo"] + ESQUEMA_SECCION["required"]}
    for i, s in enumerate(l.get("secciones") or [], 1):
        progreso(f"Traduciendo la sección {i}/{len(l.get('secciones') or [])}…")
        cod = s.get("codigo") or {}
        t = tr_({k: s.get(k) for k in ("titulo", "texto", "analogia", "ejemplo", "codigo", "practica")}, esq_s)
        t["codigo"] = {**(t.get("codigo") or {}), "contenido": cod.get("contenido", "")}  # el código no se traduce
        secs.append(_limpia_seccion(t) | {"titulo": t.get("titulo") or s.get("titulo", "")})
    progreso("Traduciendo quiz y laboratorio…")
    fin = tr_({k: l.get(k) for k in ("comandos", "puntos_clave", "errores_comunes", "quiz", "laboratorio")}, ESQUEMA_CIERRE, 5000)
    for c_new, c_old in zip(fin.get("comandos") or [], l.get("comandos") or []):
        c_new["comando"] = c_old.get("comando", c_new.get("comando"))
    return {**cab, "secciones": secs, **fin}
