"""Parser tolerante de configuraciones Cisco IOS.

Acepta tanto la salida de `show running-config` (con sangría) como una lista de
comandos tecleados en modo configuración (sin sangría, con `exit`, prompts, etc.).
Devuelve una estructura simple: líneas globales + secciones con sus hijos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Interfaces
# --------------------------------------------------------------------------- #
_IFACE_PREFIXES = [
    # (regex del prefijo, nombre canónico) — el orden importa (más largo primero)
    (r"tengigabitethernet|tengig|te", "TenGigabitEthernet"),
    (r"gigabitethernet|gigabit|gig|gi|g", "GigabitEthernet"),
    (r"fastethernet|fast|fa|f", "FastEthernet"),
    (r"ethernet|eth|et|e", "Ethernet"),
    (r"serial|ser|se|s", "Serial"),
    (r"port-channel|portchannel|po", "Port-channel"),
    (r"loopback|loop|lo", "Loopback"),
    (r"vlan|vl", "Vlan"),
    (r"tunnel|tu", "Tunnel"),
]
_IFACE_RE = re.compile(
    r"^\s*(" + "|".join(p for p, _ in _IFACE_PREFIXES) + r")\s*([0-9][0-9/.:]*)\s*$",
    re.IGNORECASE,
)


def norm_iface(name: str) -> str:
    """'g0/0.10' -> 'GigabitEthernet0/0.10'. Si no se reconoce, se devuelve tal cual."""
    if not name:
        return ""
    m = _IFACE_RE.match(name.strip())
    if not m:
        return name.strip()
    pref, num = m.group(1).lower(), m.group(2)
    for pat, canon in _IFACE_PREFIXES:
        if re.fullmatch(pat, pref):
            return canon + num
    return name.strip()


def expand_iface_range(spec: str) -> list[str]:
    """'fa0/1 - 5, g0/1' -> [FastEthernet0/1 ... FastEthernet0/5, GigabitEthernet0/1]."""
    out: list[str] = []
    last_prefix = ""
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([A-Za-z-]*)\s*([0-9/]*?)(\d+)\s*-\s*(\d+)$", part)
        if m:
            pref = m.group(1) or last_prefix
            base, a, b = m.group(2), int(m.group(3)), int(m.group(4))
            last_prefix = pref
            for i in range(min(a, b), max(a, b) + 1):
                out.append(norm_iface(f"{pref}{base}{i}"))
            continue
        m = re.match(r"^([A-Za-z-]*)\s*([0-9/.]+)$", part)
        if m:
            pref = m.group(1) or last_prefix
            last_prefix = pref
            out.append(norm_iface(f"{pref}{m.group(2)}"))
    return out


# --------------------------------------------------------------------------- #
# Estructura
# --------------------------------------------------------------------------- #
@dataclass
class Section:
    header: str
    children: list[str] = field(default_factory=list)


@dataclass
class Config:
    hostname: str = ""
    global_lines: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    # -- utilidades -------------------------------------------------------- #
    def interfaces(self) -> dict[str, list[str]]:
        res: dict[str, list[str]] = {}
        for s in self.sections:
            m = re.match(r"^interface\s+(\S+.*)$", s.header, re.I)
            if m:
                res.setdefault(norm_iface(m.group(1).replace(" ", "")), []).extend(s.children)
        return res

    def iface(self, name: str) -> list[str] | None:
        return self.interfaces().get(norm_iface(name))

    def find_sections(self, header_regex: str) -> list[Section]:
        rx = re.compile(header_regex, re.I)
        return [s for s in self.sections if rx.search(s.header)]

    def all_lines(self) -> list[str]:
        lines = list(self.global_lines)
        for s in self.sections:
            lines.append(s.header)
            lines.extend(" " + c for c in s.children)
        return lines

    def text(self) -> str:
        return "\n".join(self.all_lines())


# Comandos que abren una sección (modo submodo)
_SECTION_OPENERS = re.compile(
    r"^(interface\s|router\s|line\s|ip dhcp pool\s|vlan\s+\d|ip access-list\s|"
    r"ipv6 access-list\s|class-map\s|policy-map\s|crypto isakmp policy|crypto map\s|"
    r"ipv6 dhcp pool\s|key chain\s|spanning-tree mst configuration|ip sla\s+\d|"
    r"track\s+\d|zone security|zone-pair|parameter-map|archive|redundancy|"
    r"controller\s|voice\s|telephony-service|ephone|dial-peer|wlan\s|"
    r"username\s+\S+\s+privilege\s+\d+\s+view\b)",
    re.I,
)
# Comandos globales que, sin sangría, cierran una sección abierta
_GLOBAL_ONLY = re.compile(
    r"^(hostname|ip route|ipv6 route|ip default-gateway|ip routing|ipv6 unicast-routing|"
    r"ip dhcp excluded-address|ip domain-name|ip domain name|ip domain-lookup|no ip domain-lookup|"
    r"no ip domain lookup|ip name-server|ip ssh|crypto key|username|enable secret|enable password|"
    r"service\s|no service|banner|access-list|ip nat (inside|outside) source|ip nat pool|"
    r"spanning-tree (mode|vlan|portfast default|loopguard|extend)|vtp\s|cdp run|no cdp run|lldp run|"
    r"ntp\s|logging\s|snmp-server|clock\s|aaa\s|radius|tacacs|license|boot|"
    r"ip http|security passwords|login block-for|login on-|errdisable|mac address-table|"
    r"port-channel load-balance|ip dhcp snooping|ip arp inspection|ip cef|ipv6 cef|"
    r"ip flow-export|ip scp|file prompt|no ip http)",
    re.I,
)
_NOISE = re.compile(
    r"^(building configuration|current configuration|last configuration change|"
    r"version\s|end$|exit$|exit-address-family$|enable$|disable$|configure terminal|conf t$|"
    r"config t$|configure$|write|wr$|copy run|copy running|do\s|show\s|sh\s|"
    r"enter configuration commands|%|\^|reload)",
    re.I,
)
_PROMPT = re.compile(r"^[\w.\-]+(\([\w\-./]*\))?[#>]\s?")


def _strip_prompt(line: str) -> tuple[str, bool]:
    """Quita prompts tipo 'R1(config-if)#'. Devuelve (línea, venía_de_submodo)."""
    m = _PROMPT.match(line.strip())
    if not m:
        return line, False
    sub = m.group(1) or ""
    in_sub = sub not in ("", "(config)")
    return line.strip()[m.end():], in_sub


def parse_config(text: str) -> Config:
    cfg = Config()
    current: list[Section] = []  # secciones activas (pueden ser varias por 'interface range')
    for raw in (text or "").replace("\r", "").split("\n"):
        if not raw.strip():
            continue
        line, from_sub = _strip_prompt(raw)
        if not line.strip():
            continue
        indented = line[:1] in (" ", "\t") or from_sub
        stripped = line.strip()
        if stripped.startswith("!"):
            current = []
            continue
        low = stripped.lower()
        if not _NOISE.match(low):
            from .ios_words import expand_command  # import diferido (evita ciclo)
            stripped = expand_command(stripped)
            low = stripped.lower()
        if _NOISE.match(low):
            if low in ("exit", "end") or low.startswith("end"):
                current = []
            continue
        if low.startswith("do "):
            continue

        # ¿Nueva sección?
        if _SECTION_OPENERS.match(stripped) and not (indented and current and low.startswith("vlan")):
            m = re.match(r"^interface\s+range\s+(.*)$", stripped, re.I)
            if m:
                current = []
                for name in expand_iface_range(m.group(1)):
                    sec = Section(f"interface {name}")
                    cfg.sections.append(sec)
                    current.append(sec)
                continue
            m = re.match(r"^interface\s+(.*)$", stripped, re.I)
            if m:
                stripped = "interface " + norm_iface(m.group(1).replace(" ", ""))
            m = re.match(r"^vlan\s+([\d,\-\s]+)$", stripped, re.I)
            if m and ("," in m.group(1) or "-" in m.group(1)):
                current = []
                for vid in _expand_numlist(m.group(1)):
                    sec = Section(f"vlan {vid}")
                    cfg.sections.append(sec)
                    current.append(sec)
                continue
            sec = Section(re.sub(r"\s+", " ", stripped))
            cfg.sections.append(sec)
            current = [sec]
            continue

        if current and (indented or not _GLOBAL_ONLY.match(stripped)):
            for sec in current:
                sec.children.append(re.sub(r"\s+", " ", stripped))
            continue

        current = []
        stripped = re.sub(r"\s+", " ", stripped)
        cfg.global_lines.append(stripped)
        m = re.match(r"^hostname\s+(\S+)", stripped, re.I)
        if m:
            cfg.hostname = m.group(1)
    return cfg


def _expand_numlist(spec: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a.isdigit() and b.isdigit():
                out.extend(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.append(int(part))
    return out


expand_numlist = _expand_numlist


def merge_configs(*texts: str) -> Config:
    """Combina varios textos (ej. config inicial + solución) en una sola Config."""
    return parse_config("\n!\n".join(t for t in texts if t))


# --------------------------------------------------------------------------- #
# Salidas de comandos show / ping / ipconfig
# --------------------------------------------------------------------------- #
def parse_show_vlan_brief(text: str) -> dict[int, dict]:
    """Extrae VLANs de `show vlan brief`: {id: {'nombre':..., 'puertos':[...]}}."""
    vlans: dict[int, dict] = {}
    last = None
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(\d{1,4})\s+(\S+)\s+(active|act/\S+|suspended)\s*(.*)$", line, re.I)
        if m:
            vid = int(m.group(1))
            ports = [norm_iface(p.strip()) for p in m.group(4).split(",") if p.strip()]
            vlans[vid] = {"nombre": m.group(2), "puertos": ports}
            last = vid
            continue
        if last is not None and re.match(r"^\s{20,}\S", line):
            vlans[last]["puertos"] += [norm_iface(p.strip()) for p in line.split(",") if p.strip()]
        else:
            last = None if not line.strip() else last
    return vlans


def ping_results(text: str) -> dict[str, bool]:
    """Devuelve {ip_destino: éxito} a partir de salidas de ping de IOS o de PC de Packet Tracer.

    Si hay varios pings al mismo destino, basta con que uno tenga éxito.
    """
    res: dict[str, bool] = {}
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # IOS: "Sending 5, 100-byte ICMP Echos to 192.168.1.1, timeout is 2 seconds:"
        m = re.search(r"Echos to (\d+\.\d+\.\d+\.\d+)", line)
        # PC: "Pinging 192.168.1.1 with 32 bytes of data:"
        m2 = re.search(r"Pinging (\d+\.\d+\.\d+\.\d+)", line, re.I)
        if m or m2:
            dst = (m or m2).group(1)
            ok = False
            j = i + 1
            while j < len(lines) and j < i + 15:
                l2 = lines[j]
                if re.search(r"(Echos to|Pinging)\s", l2, re.I):
                    break
                sr = re.search(r"Success rate is (\d+) percent", l2)
                if sr and int(sr.group(1)) > 0:
                    ok = True
                if re.search(r"Reply from " + re.escape(dst) + r"\b", l2):
                    ok = True
                lost = re.search(r"Received = (\d+)", l2)
                if lost and int(lost.group(1)) > 0:
                    ok = True
                j += 1
            res[dst] = res.get(dst, False) or ok
            i = j
            continue
        i += 1
    return res


def parse_ipconfig(text: str) -> dict:
    """Saca IP, máscara y gateway de la salida de `ipconfig` de una PC de Packet Tracer."""
    out = {}
    for key, rx in (
        ("ip", r"IP(?:v4)? Address[ .]*:\s*(\d+\.\d+\.\d+\.\d+)"),
        ("mascara", r"Subnet Mask[ .]*:\s*(\d+\.\d+\.\d+\.\d+)"),
        ("gateway", r"Default Gateway[ .]*:\s*(?:::\s*)?(\d+\.\d+\.\d+\.\d+)"),
    ):
        m = re.search(rx, text or "", re.I)
        if m:
            out[key] = m.group(1)
    return out


def reindentar(texto: str) -> str:
    """Devuelve la config con los hijos de cada sección con un espacio de sangría, aunque el modelo
    los haya escrito pegados al margen. Usa las mismas reglas que parse_config."""
    out: list[str] = []
    en_seccion = False
    for raw in (texto or "").replace("\r", "").split("\n"):
        if not raw.strip():
            continue
        linea = raw.strip()
        low = linea.lower()
        indentada = raw[:1] in (" ", "\t")
        if linea.startswith("!") or low in ("exit", "end") or re.match(
                r"^(enable|configure terminal|conf t|write( memory)?|copy run.*)$", low):
            en_seccion = False if not indentada or low != "exit" else en_seccion
            continue
        if _SECTION_OPENERS.match(linea) and not (indentada and en_seccion and low.startswith("vlan")):
            out.append(linea)
            en_seccion = True
        elif en_seccion and (indentada or not _GLOBAL_ONLY.match(linea)):
            out.append(" " + linea)
        else:
            out.append(linea)
            en_seccion = False
    return "\n".join(out)
