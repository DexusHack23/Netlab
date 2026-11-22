"""Verificador determinista: compara lo que hiciste contra los criterios de la práctica.

Cada verificación devuelve uno de tres estados:
  ok        -> se cumple
  falla     -> no se cumple (con el motivo)
  sin_datos -> no hay evidencia suficiente (ej. falta pegar `show vlan brief` o el ping)

El LLM nunca decide si algo está bien: solo explica lo que este módulo encontró.
"""
from __future__ import annotations

import ipaddress
import re

from .ios_parser import (
    Config,
    expand_numlist,
    norm_iface,
    parse_config,
    parse_ipconfig,
    parse_show_vlan_brief,
    ping_results,
)

TIPOS = {
    "hostname": "nombre",
    "ip_interfaz": "interfaz, ip, mascara",
    "interfaz_activa": "interfaz",
    "descripcion_interfaz": "interfaz, patron",
    "vlan": "vlan, nombre?",
    "puerto_acceso": "interfaz, vlan",
    "puerto_troncal": "interfaz, vlan? (permitidas), nativa?",
    "subinterfaz": "interfaz, vlan, ip, mascara",
    "ruta_estatica": "red, mascara, siguiente_salto?",
    "ruta_default": "siguiente_salto?",
    "ospf_red": "red, wildcard, area, proceso?",
    "ospf_router_id": "ip, proceso?",
    "ospf_pasiva": "interfaz, proceso?",
    "dhcp_pool": "red, mascara, gateway?, nombre?",
    "dhcp_excluido": "ip, ip_fin?",
    "ip_helper": "interfaz, ip",
    "nat_interfaz": "interfaz, rol (inside|outside)",
    "ssh": "(sin parámetros)",
    "port_security": "interfaz, maximo?, violacion?",
    "ip_pc": "ip, mascara?, gateway?",
    "ping": "ip (destino)",
    "contiene": "patron (regex), seccion? (regex del encabezado)",
}


# --------------------------------------------------------------------------- #
def _p(chk: dict, key: str) -> str:
    v = chk.get(key)
    return str(v).strip() if v is not None else ""


def _has(lines: list[str], rx: str) -> bool:
    r = re.compile(rx, re.I)
    return any(r.search(l) for l in lines)


def _ip_mask_ok(lines: list[str], ip: str, mask: str) -> bool:
    for l in lines:
        m = re.match(r"^ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)", l, re.I)
        if m and m.group(1) == ip and (not mask or m.group(2) == mask):
            return True
        m = re.match(r"^ip address (\d+\.\d+\.\d+\.\d+)/(\d+)", l, re.I)
        if m and m.group(1) == ip:
            if not mask:
                return True
            try:
                if str(ipaddress.IPv4Network(f"0.0.0.0/{m.group(2)}").netmask) == mask:
                    return True
            except ValueError:
                pass
    return False


def _shutdown(lines: list[str], ev: "Evidence | None" = None, name: str = "") -> bool:
    if any(l.lower() == "shutdown" for l in lines):
        return True
    if ev is not None and ev.es_router and not ev.es_running and "." not in name:
        return not any(l.lower() == "no shutdown" for l in lines)
    return False


def _iface_ips(cfg: Config) -> list[tuple[str, ipaddress.IPv4Interface]]:
    out = []
    for name, lines in cfg.interfaces().items():
        for l in lines:
            m = re.match(r"^ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)", l, re.I)
            if m:
                try:
                    out.append((name, ipaddress.IPv4Interface(f"{m.group(1)}/{m.group(2)}")))
                except ValueError:
                    pass
    return out


def _wild_match(ip: str, net: str, wc: str) -> bool:
    try:
        i = int(ipaddress.IPv4Address(ip))
        n = int(ipaddress.IPv4Address(net))
        w = int(ipaddress.IPv4Address(wc))
    except ValueError:
        return False
    return (i & ~w & 0xFFFFFFFF) == (n & ~w & 0xFFFFFFFF)


def _ospf_sections(cfg: Config, proceso: str):
    rx = r"^router ospf\s+" + (re.escape(proceso) + r"\b" if proceso else r"\d+")
    return cfg.find_sections(rx)


def _area_eq(a: str, b: str) -> bool:
    def n(x):
        x = x.strip()
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", x):
            return int(ipaddress.IPv4Address(x))
        return int(x) if x.isdigit() else x
    try:
        return n(a) == n(b)
    except ValueError:
        return a.strip() == b.strip()


# --------------------------------------------------------------------------- #
class Evidence:
    """Todo lo que el alumno pegó de un dispositivo."""

    def __init__(self, config_text: str = "", outputs_text: str = ""):
        self.config_text = config_text or ""
        self.outputs_text = outputs_text or ""
        self.cfg = parse_config(self.config_text)
        self.vlan_table = parse_show_vlan_brief(self.outputs_text)
        self.pings = ping_results(self.outputs_text)
        self.ipconfig = parse_ipconfig(self.outputs_text + "\n" + self.config_text)
        # ¿Es una running-config real o comandos tecleados? En comandos, un router necesita
        # 'no shutdown' explícito; en la running-config, lo apagado aparece como 'shutdown'.
        self.es_running = bool(re.search(r"Current configuration|Building configuration|^version \d",
                                         self.config_text, re.I | re.M))
        self.es_router = False

    @property
    def empty(self) -> bool:
        return not (self.config_text.strip() or self.outputs_text.strip())


def run_check(chk: dict, ev: Evidence) -> dict:
    tipo = _p(chk, "tipo")
    res = {"id": _p(chk, "id"), "dispositivo": _p(chk, "dispositivo"), "tipo": tipo,
           "descripcion": _p(chk, "descripcion"), "estado": "falla", "detalle": ""}

    def ok(msg=""):
        res.update(estado="ok", detalle=msg)
        return res

    def fail(msg):
        res.update(estado="falla", detalle=msg)
        return res

    def nodata(msg):
        res.update(estado="sin_datos", detalle=msg)
        return res

    if ev is None or ev.empty:
        return nodata("No pegaste nada de este dispositivo.")

    cfg = ev.cfg
    try:
        fn = _CHECKS.get(tipo)
        if fn is None:
            return nodata(f"Tipo de verificación desconocido: '{tipo}'.")
        return fn(chk, ev, cfg, ok, fail, nodata)
    except Exception as e:  # nunca romper la calificación por un check raro
        return nodata(f"No se pudo evaluar ({type(e).__name__}: {e}).")


# ---- implementaciones ------------------------------------------------------ #
def _c_hostname(chk, ev, cfg, ok, fail, nodata):
    want = _p(chk, "nombre")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    if cfg.hostname.lower() == want.lower():
        return ok()
    return fail(f"El hostname es '{cfg.hostname or '(sin configurar)'}', se esperaba '{want}'.")


def _need_iface(cfg, name, nodata, fail):
    if not cfg.global_lines and not cfg.sections:
        return None, nodata("Falta la running-config.")
    lines = cfg.iface(name)
    if lines is None:
        return None, fail(f"La interfaz {norm_iface(name)} no aparece en la configuración.")
    return lines, None


def _c_ip_interfaz(chk, ev, cfg, ok, fail, nodata):
    name, ip, mask = _p(chk, "interfaz"), _p(chk, "ip"), _p(chk, "mascara")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    if _ip_mask_ok(lines, ip, mask):
        if _shutdown(lines, ev, name):
            return fail(f"{norm_iface(name)} tiene la IP correcta pero está en shutdown (falta 'no shutdown').")
        return ok()
    actual = [l for l in lines if l.lower().startswith("ip address")]
    return fail(f"{norm_iface(name)}: se esperaba 'ip address {ip} {mask}'. "
                f"Encontré: {actual[0] if actual else 'sin IP'}.")


def _c_interfaz_activa(chk, ev, cfg, ok, fail, nodata):
    name = _p(chk, "interfaz")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    return fail(f"{norm_iface(name)} está en shutdown (falta 'no shutdown').") if _shutdown(lines, ev, name) else ok()


def _c_descripcion(chk, ev, cfg, ok, fail, nodata):
    name, pat = _p(chk, "interfaz"), _p(chk, "patron") or "."
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    for l in lines:
        if l.lower().startswith("description") and re.search(pat, l[11:], re.I):
            return ok()
    return fail(f"{norm_iface(name)} no tiene la descripción esperada.")


def _c_vlan(chk, ev, cfg, ok, fail, nodata):
    vid = int(_p(chk, "vlan") or 0)
    nombre = _p(chk, "nombre")
    # 1) tabla de show vlan brief
    if vid in ev.vlan_table:
        got = ev.vlan_table[vid]["nombre"]
        if nombre and got.lower() != nombre.lower():
            return fail(f"La VLAN {vid} existe pero se llama '{got}', se esperaba '{nombre}'.")
        return ok("Confirmada con show vlan brief.")
    if ev.vlan_table:
        return fail(f"La VLAN {vid} no aparece en show vlan brief.")
    # 2) definida en la config
    for s in cfg.find_sections(rf"^vlan {vid}$"):
        got = next((c[5:].strip() for c in s.children if c.lower().startswith("name ")), "")
        if nombre and got.lower() != nombre.lower():
            return fail(f"La VLAN {vid} se llama '{got or '(sin nombre)'}', se esperaba '{nombre}'.")
        return ok()
    # 3) creada implícitamente por un puerto de acceso (no valida el nombre)
    if not nombre:
        for lines in cfg.interfaces().values():
            if _has(lines, rf"^switchport access vlan {vid}$"):
                return ok("Creada al asignarla a un puerto.")
    return nodata(f"No encuentro la VLAN {vid}. En Packet Tracer las VLAN no siempre salen en la "
                  "running-config: pega también la salida de 'show vlan brief'.")


def _c_puerto_acceso(chk, ev, cfg, ok, fail, nodata):
    name, vid = _p(chk, "interfaz"), _p(chk, "vlan")
    if ev.vlan_table and not ev.config_text.strip():
        for v, d in ev.vlan_table.items():
            if norm_iface(name) in d["puertos"]:
                return ok() if str(v) == vid else fail(f"{norm_iface(name)} está en la VLAN {v}, no en la {vid}.")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    if not _has(lines, r"^switchport mode access$"):
        return fail(f"{norm_iface(name)}: falta 'switchport mode access'.")
    m = next((re.match(r"^switchport access vlan (\d+)", l, re.I) for l in lines
              if re.match(r"^switchport access vlan (\d+)", l, re.I)), None)
    got = m.group(1) if m else "1"
    return ok() if got == vid else fail(f"{norm_iface(name)} está en la VLAN {got}, se esperaba la {vid}.")


def _c_puerto_troncal(chk, ev, cfg, ok, fail, nodata):
    name, permitidas, nativa = _p(chk, "interfaz"), _p(chk, "vlan"), _p(chk, "nativa")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    if not _has(lines, r"^switchport mode trunk$"):
        return fail(f"{norm_iface(name)}: falta 'switchport mode trunk'.")
    if permitidas:
        allowed: set[int] = set()
        found = False
        for l in lines:
            m = re.match(r"^switchport trunk allowed vlan (?:add )?([\d,\-\s]+)$", l, re.I)
            if m:
                found = True
                allowed |= set(expand_numlist(m.group(1)))
        need = set(expand_numlist(permitidas))
        if found and not need <= allowed:
            return fail(f"{norm_iface(name)}: faltan VLANs permitidas {sorted(need - allowed)}.")
    if nativa and not _has(lines, rf"^switchport trunk native vlan {re.escape(nativa)}$"):
        return fail(f"{norm_iface(name)}: la VLAN nativa debe ser {nativa}.")
    return ok()


def _c_subinterfaz(chk, ev, cfg, ok, fail, nodata):
    name, vid, ip, mask = _p(chk, "interfaz"), _p(chk, "vlan"), _p(chk, "ip"), _p(chk, "mascara")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    if vid and not _has(lines, rf"^encapsulation dot1q {re.escape(vid)}( native)?$"):
        return fail(f"{norm_iface(name)}: falta 'encapsulation dot1Q {vid}'.")
    if ip and not _ip_mask_ok(lines, ip, mask):
        return fail(f"{norm_iface(name)}: falta 'ip address {ip} {mask}'.")
    parent = norm_iface(name).split(".")[0]
    plines = cfg.iface(parent)
    if plines is not None and _shutdown(plines, ev, parent):
        return fail(f"La interfaz física {parent} está en shutdown; las subinterfaces no funcionarán.")
    return ok()


def _routes(cfg):
    out = []
    for l in cfg.global_lines:
        m = re.match(r"^ip route (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+) (.+?)(?:\s+\d+)?$", l, re.I)
        if m:
            out.append((m.group(1), m.group(2), m.group(3).strip()))
    return out


def _nh_eq(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower() or norm_iface(a) == norm_iface(b)


def _c_ruta_estatica(chk, ev, cfg, ok, fail, nodata):
    red, mask, nh = _p(chk, "red"), _p(chk, "mascara"), _p(chk, "siguiente_salto")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    for r, m, n in _routes(cfg):
        if r == red and m == mask:
            if not nh or any(_nh_eq(part, nh) for part in n.split()):
                return ok()
            return fail(f"La ruta a {red} {mask} existe pero apunta a '{n}', se esperaba '{nh}'.")
    return fail(f"Falta 'ip route {red} {mask} {nh or '<siguiente salto>'}'.")


def _c_ruta_default(chk, ev, cfg, ok, fail, nodata):
    chk = dict(chk, red="0.0.0.0", mascara="0.0.0.0")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    if _has(cfg.global_lines, r"^ip default-gateway "):
        gw = _p(chk, "siguiente_salto")
        if not gw or _has(cfg.global_lines, rf"^ip default-gateway {re.escape(gw)}$"):
            return ok("Con ip default-gateway.")
    return _c_ruta_estatica(chk, ev, cfg, ok, fail, nodata)


def _c_ospf_red(chk, ev, cfg, ok, fail, nodata):
    red, wc, area, proc = _p(chk, "red"), _p(chk, "wildcard"), _p(chk, "area") or "0", _p(chk, "proceso")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    secs = _ospf_sections(cfg, proc)
    stmts = []
    for s in secs:
        for c in s.children:
            m = re.match(r"^network (\S+) (\S+) area (\S+)$", c, re.I)
            if m:
                stmts.append(m.groups())
    # interfaces del equipo que caen en la red pedida
    targets = [(n, i) for n, i in _iface_ips(cfg) if wc and _wild_match(str(i.ip), red, wc)]
    if targets:
        missing = []
        for n, i in targets:
            lines = cfg.iface(n) or []
            proc_rx = re.escape(proc) if proc else r"\d+"
            via_if = _has(lines, rf"^ip ospf {proc_rx} area {re.escape(area)}$")
            via_net = any(_wild_match(str(i.ip), sn, sw) and _area_eq(sa, area) for sn, sw, sa in stmts)
            if not (via_if or via_net):
                missing.append(n)
        if not missing:
            return ok()
        if not secs and not any(_has(cfg.iface(n) or [], r"^ip ospf ") for n, _ in targets):
            return fail("No hay proceso OSPF configurado (router ospf ...).")
        return fail(f"Estas interfaces no quedaron en OSPF área {area}: {', '.join(missing)}.")
    # sin interfaces conocidas: comparar el enunciado literal
    for sn, sw, sa in stmts:
        if sn == red and sw == wc and _area_eq(sa, area):
            return ok()
    if not secs:
        return fail("No hay proceso OSPF configurado (router ospf ...).")
    return fail(f"Falta 'network {red} {wc} area {area}' dentro de router ospf.")


def _c_ospf_rid(chk, ev, cfg, ok, fail, nodata):
    ip, proc = _p(chk, "ip"), _p(chk, "proceso")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    for s in _ospf_sections(cfg, proc):
        if _has(s.children, rf"^router-id {re.escape(ip)}$"):
            return ok()
    return fail(f"Falta 'router-id {ip}' en router ospf.")


def _c_ospf_pasiva(chk, ev, cfg, ok, fail, nodata):
    name, proc = norm_iface(_p(chk, "interfaz")), _p(chk, "proceso")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    for s in _ospf_sections(cfg, proc):
        for c in s.children:
            m = re.match(r"^passive-interface (\S+)$", c, re.I)
            if m and norm_iface(m.group(1)) == name:
                return ok()
    return fail(f"Falta 'passive-interface {name}' en router ospf.")


def _c_dhcp_pool(chk, ev, cfg, ok, fail, nodata):
    red, mask, gw, nombre = _p(chk, "red"), _p(chk, "mascara"), _p(chk, "gateway"), _p(chk, "nombre")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    for s in cfg.find_sections(r"^ip dhcp pool "):
        patron = rf"^network {re.escape(red)} {re.escape(mask)}$" if mask else rf"^network {re.escape(red)}( \S+)?$"
        if not _has(s.children, patron):
            continue
        if nombre and s.header.split()[-1].lower() != nombre.lower():
            return fail(f"El pool de {red} se llama '{s.header.split()[-1]}', se esperaba '{nombre}'.")
        if gw and not _has(s.children, rf"^default-router {re.escape(gw)}$"):
            return fail(f"El pool de {red} no tiene 'default-router {gw}'.")
        return ok()
    return fail(f"No hay un 'ip dhcp pool' con 'network {red} {mask}'.")


def _c_dhcp_excluido(chk, ev, cfg, ok, fail, nodata):
    a, b = _p(chk, "ip"), _p(chk, "ip_fin")
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    try:
        ia, ib = ipaddress.IPv4Address(a), ipaddress.IPv4Address(b or a)
    except ValueError:
        return nodata("Parámetros de IP inválidos en la verificación.")
    for l in cfg.global_lines:
        m = re.match(r"^ip dhcp excluded-address (\S+)(?: (\S+))?$", l, re.I)
        if m:
            x = ipaddress.IPv4Address(m.group(1))
            y = ipaddress.IPv4Address(m.group(2) or m.group(1))
            if x <= ia and ib <= y:
                return ok()
    return fail(f"Falta 'ip dhcp excluded-address {a}{' ' + b if b else ''}'.")


def _c_ip_helper(chk, ev, cfg, ok, fail, nodata):
    name, ip = _p(chk, "interfaz"), _p(chk, "ip")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    return ok() if _has(lines, rf"^ip helper-address {re.escape(ip)}$") else \
        fail(f"{norm_iface(name)}: falta 'ip helper-address {ip}'.")


def _c_nat_interfaz(chk, ev, cfg, ok, fail, nodata):
    name, rol = _p(chk, "interfaz"), _p(chk, "rol").lower() or "inside"
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    return ok() if _has(lines, rf"^ip nat {rol}$") else fail(f"{norm_iface(name)}: falta 'ip nat {rol}'.")


def _c_ssh(chk, ev, cfg, ok, fail, nodata):
    if not ev.config_text.strip():
        return nodata("Falta la running-config.")
    faltan = []
    if not _has(cfg.global_lines, r"^ip domain[- ]name \S+"):
        faltan.append("ip domain-name")
    if not _has(cfg.global_lines, r"^username \S+ .*(secret|password)"):
        faltan.append("username ... secret")
    vty = cfg.find_sections(r"^line vty")
    if not vty or not any(_has(s.children, r"^transport input (ssh|all|telnet ssh|ssh telnet)$") for s in vty):
        faltan.append("transport input ssh (line vty)")
    if vty and not any(_has(s.children, r"^login local$") for s in vty):
        faltan.append("login local (line vty)")
    # las llaves RSA no aparecen en la running-config; se aceptan si 'ip ssh version 2' está
    # o si pegó la salida de 'show ip ssh' / 'crypto key generate'.
    has_keys = _has(cfg.global_lines, r"^(ip ssh version 2|crypto key generate rsa)") or \
        re.search(r"SSH Enabled|modulus|RSA key", ev.outputs_text, re.I)
    if not has_keys:
        faltan.append("llaves RSA / ip ssh version 2")
    return ok() if not faltan else fail("Para SSH falta: " + ", ".join(faltan) + ".")


def _c_port_security(chk, ev, cfg, ok, fail, nodata):
    name, mx, vio = _p(chk, "interfaz"), _p(chk, "maximo"), _p(chk, "violacion")
    lines, err = _need_iface(cfg, name, nodata, fail)
    if err:
        return err
    if not _has(lines, r"^switchport port-security$"):
        return fail(f"{norm_iface(name)}: falta 'switchport port-security'.")
    if mx and mx != "1" and not _has(lines, rf"^switchport port-security maximum {re.escape(mx)}$"):
        return fail(f"{norm_iface(name)}: el máximo de MACs debe ser {mx}.")
    if vio and vio.lower() != "shutdown" and not _has(lines, rf"^switchport port-security violation {re.escape(vio)}$"):
        return fail(f"{norm_iface(name)}: la violación debe ser '{vio}'.")
    return ok()


def _c_ip_pc(chk, ev, cfg, ok, fail, nodata):
    ip, mask, gw = _p(chk, "ip"), _p(chk, "mascara"), _p(chk, "gateway")
    got = ev.ipconfig
    if not got:
        return nodata("Pega la salida de 'ipconfig' de esta PC.")
    if ip and ip.lower() != "dhcp" and got.get("ip") != ip:
        return fail(f"La PC tiene IP {got.get('ip', '?')}, se esperaba {ip}.")
    if mask and got.get("mascara") and got["mascara"] != mask:
        return fail(f"La máscara es {got['mascara']}, se esperaba {mask}.")
    if gw and got.get("gateway") != gw:
        return fail(f"El gateway es {got.get('gateway', '(vacío)')}, se esperaba {gw}.")
    return ok()


def _c_ping(chk, ev, cfg, ok, fail, nodata):
    dst = _p(chk, "ip")
    if dst not in ev.pings:
        return nodata(f"No encontré un ping a {dst} en lo que pegaste de este equipo.")
    return ok() if ev.pings[dst] else fail(f"El ping a {dst} falló.")


def _c_contiene(chk, ev, cfg, ok, fail, nodata):
    pat, sec = _p(chk, "patron"), _p(chk, "seccion")
    if not ev.config_text.strip() and not ev.outputs_text.strip():
        return nodata("No hay datos.")
    try:
        rx = re.compile(pat, re.I)
    except re.error:
        return nodata("La expresión de la verificación es inválida.")
    if sec:
        for s in cfg.find_sections(sec):
            if any(rx.search(c) for c in s.children):
                return ok()
        return fail("No encontré lo esperado en la sección correspondiente.")
    if any(rx.search(l) for l in cfg.all_lines()) or rx.search(ev.outputs_text):
        return ok()
    return fail("No encontré lo esperado en la configuración.")


_CHECKS = {
    "hostname": _c_hostname,
    "ip_interfaz": _c_ip_interfaz,
    "interfaz_activa": _c_interfaz_activa,
    "descripcion_interfaz": _c_descripcion,
    "vlan": _c_vlan,
    "puerto_acceso": _c_puerto_acceso,
    "puerto_troncal": _c_puerto_troncal,
    "subinterfaz": _c_subinterfaz,
    "ruta_estatica": _c_ruta_estatica,
    "ruta_default": _c_ruta_default,
    "ospf_red": _c_ospf_red,
    "ospf_router_id": _c_ospf_rid,
    "ospf_pasiva": _c_ospf_pasiva,
    "dhcp_pool": _c_dhcp_pool,
    "dhcp_excluido": _c_dhcp_excluido,
    "ip_helper": _c_ip_helper,
    "nat_interfaz": _c_nat_interfaz,
    "ssh": _c_ssh,
    "port_security": _c_port_security,
    "ip_pc": _c_ip_pc,
    "ping": _c_ping,
    "contiene": _c_contiene,
}

# Checks que no se pueden comprobar con la sola configuración de la solución
RUNTIME_ONLY = {"ping"}


def grade(practice: dict, evidence_by_device: dict[str, Evidence]) -> dict:
    """Califica toda la práctica. Los 'sin_datos' no cuentan como error, pero sí bajan la cobertura."""
    routers = {d.get("nombre") for d in practice.get("dispositivos", []) if d.get("tipo") == "router"}
    for name, ev in evidence_by_device.items():
        if ev is not None:
            ev.es_router = name in routers
    results = []
    for chk in practice.get("verificaciones", []):
        dev = _p(chk, "dispositivo")
        ev = evidence_by_device.get(dev) or evidence_by_device.get(dev.upper()) or evidence_by_device.get(dev.lower())
        results.append(run_check(chk, ev))
    total = len(results)
    oks = sum(r["estado"] == "ok" for r in results)
    fails = sum(r["estado"] == "falla" for r in results)
    nod = total - oks - fails
    return {
        "resultados": results,
        "total": total,
        "ok": oks,
        "fallas": fails,
        "sin_datos": nod,
        "calificacion": round(10 * oks / total, 1) if total else 0.0,
    }
