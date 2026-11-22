"""Convierte una práctica en un script para la extensión PTBuilder de Packet Tracer.

PTBuilder (github.com/kimmknight/PTBuilder) agrega a Packet Tracer un editor de código:
Extensions -> Builder Code Editor. Pegas el script, le das Run y Packet Tracer crea los
equipos, los cables y (si quieres) la configuración. Este módulo es determinista: no usa IA.

Niveles:
  topologia -> solo equipos y cables (tú configuras todo)
  inicial   -> + la configuración inicial de la práctica (modo guiado)
  completa  -> + la solución y las IPs de las PCs (la práctica resuelta, para comparar)
"""
from __future__ import annotations

import json
import re

_MODELOS = {
    # lo que escribe el modelo -> nombre exacto de PTBuilder
    "2911": "2911", "1941": "1941", "2901": "2901", "1841": "1841", "2811": "2811",
    "isr4331": "ISR4331", "4331": "ISR4331", "isr4321": "ISR4321", "4321": "ISR4321",
    "2960-24tt": "2960-24TT", "2960": "2960-24TT", "2950-24": "2950-24", "2950t-24": "2950T-24",
    "3650-24ps": "3650-24PS", "3650": "3650-24PS", "3560-24ps": "3560-24PS", "3560": "3560-24PS",
    "pc-pt": "PC-PT", "pc": "PC-PT", "laptop-pt": "Laptop-PT", "laptop": "Laptop-PT",
    "server-pt": "Server-PT", "server": "Server-PT", "servidor": "Server-PT",
    "router-pt": "Router-PT", "switch-pt": "Switch-PT",
}
_POR_TIPO = {"router": "2911", "switch": "2960-24TT", "switch_l3": "3650-24PS",
             "pc": "PC-PT", "laptop": "Laptop-PT", "servidor": "Server-PT"}
_CABLES = {"directo": "straight", "cruzado": "cross", "serial": "serial", "fibra": "fiber", "consola": "console"}
_HOSTS = ("pc", "laptop", "servidor")


def modelo_pt(dispositivo: dict) -> str:
    m = re.sub(r"^(cisco|router|switch)\s+", "", str(dispositivo.get("modelo", "")).strip().lower())
    m = m.replace(" ", "-")
    return _MODELOS.get(m) or _POR_TIPO.get(dispositivo.get("tipo", ""), "PC-PT")


def posiciones(p: dict) -> dict[str, tuple[int, int]]:
    """Mismo acomodo que el diagrama de la app: routers arriba, switches en medio, PCs abajo."""
    fila = {"router": 0, "switch_l3": 1, "switch": 2}
    devs = p.get("dispositivos", [])
    vecinos: dict[str, list[str]] = {}
    for e in p.get("enlaces", []):
        vecinos.setdefault(e["a"], []).append(e["b"])
        vecinos.setdefault(e["b"], []).append(e["a"])
    filas: dict[int, list[dict]] = {}
    for d in devs:
        filas.setdefault(fila.get(d.get("tipo"), 3), []).append(d)
    pos: dict[str, tuple[int, int]] = {}
    ancho = max((len(f) for f in filas.values()), default=1) * 170 + 170
    for i, k in enumerate(sorted(filas)):
        f = filas[k]
        def orden(d):
            xs = [pos[v][0] for v in vecinos.get(d["nombre"], []) if v in pos]
            return sum(xs) / len(xs) if xs else 1e9
        f.sort(key=orden)
        for j, d in enumerate(f):
            # routers en zigzag: así un triángulo o un anillo no quedan con cables encimados
            zig = -80 if (k == 0 and len(f) >= 3 and j % 2 == 1) else 0
            pos[d["nombre"]] = (int(ancho / (len(f) + 1) * (j + 1)), 200 + i * 170 + zig)
    return pos


_ABRE_SECCION = re.compile(
    r"^(interface |router |line |ip dhcp pool |vlan \d|ip access-list |ipv6 access-list |class-map |"
    r"policy-map |ipv6 router |key chain |spanning-tree mst configuration)", re.I)
_RUIDO = re.compile(r"^(enable|configure terminal|conf t|end|exit|write( memory)?|copy run.*|!.*)$", re.I)


def _con_exits(texto: str) -> str:
    """Pone 'exit' al salir de cada submodo. Probado en PT 9.0.1: sin 'exit', configureIosDevice
    no crea subinterfaces y las IPs caen en la interfaz física."""
    out: list[str] = []
    en_seccion = False
    for raw in (texto or "").splitlines():
        if not raw.strip() or _RUIDO.match(raw.strip()):
            continue
        sangria = raw[:1] in (" ", "\t")
        linea = raw.strip()
        if _ABRE_SECCION.match(linea) and not (sangria and en_seccion):
            if en_seccion:
                out.append("exit")
            en_seccion = True
        elif not sangria and en_seccion:
            out.append("exit")
            en_seccion = False
        out.append(linea)
    if en_seccion:
        out.append("exit")
    return "\n".join(out)


def _cfg_por_disp(items) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items or []:
        d = (it.get("dispositivo") or "").strip()
        txt = _con_exits(it.get("config") or "")
        if d and txt:
            out[d] = (out.get(d, "") + "\n" + txt).strip()
    return out


def script(p: dict, nivel: str = "topologia") -> str:
    js = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    pos = posiciones(p)
    # Sin comentarios '//': probado en PT 9.0.1, el Builder Code Editor no ejecuta nada si hay uno.
    L: list[str] = []
    for d in p.get("dispositivos", []):
        x, y = pos.get(d["nombre"], (100, 100))
        L.append(f"addDevice({js(d['nombre'])}, {js(modelo_pt(d))}, {x}, {y});")
    L.append("")
    for e in p.get("enlaces", []):
        tipo = _CABLES.get(str(e.get("cable", "")).lower(), "straight")
        L.append(f"addLink({js(e['a'])}, {js(e['puerto_a'])}, {js(e['b'])}, {js(e['puerto_b'])}, {js(tipo)});")

    if nivel in ("inicial", "completa"):
        # En troubleshooting la config inicial es la averiada: la versión resuelta usa solo la correcta
        cfgs = {} if (nivel == "completa" and p.get("fallas")) else _cfg_por_disp(p.get("config_inicial"))
        if nivel == "completa":
            sol = _cfg_por_disp(p.get("solucion"))
            for d, c in sol.items():
                cfgs[d] = (cfgs.get(d, "") + "\n" + c).strip()
        tipos = {d["nombre"]: d.get("tipo") for d in p.get("dispositivos", [])}
        if cfgs:
            L.append("")
        for d, c in cfgs.items():
            if tipos.get(d) not in _HOSTS:
                L.append(f"configureIosDevice({js(d)}, {js(c)});")
    # IPs de las PCs: la práctica resuelta usa las correctas; un troubleshooting arma las averiadas
    direcc = None
    if nivel == "completa":
        direcc = p.get("direccionamiento", [])
    elif nivel == "inicial" and p.get("direccionamiento_inicial"):
        direcc = p["direccionamiento_inicial"]
    if direcc:
        L.append("")
        for a in direcc:
            d = a.get("dispositivo")
            if tipos.get(d) not in _HOSTS:
                continue
            if str(a.get("ip", "")).lower() == "dhcp":
                L.append(f"configurePcIp({js(d)}, true);")
            elif a.get("ip"):
                L.append(f"configurePcIp({js(d)}, false, {js(a['ip'])}, {js(a.get('mascara', ''))}, "
                         f"{js(a.get('gateway', '') or '')});")
    return "\n".join(L) + "\n"
