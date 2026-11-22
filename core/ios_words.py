"""Expansión de abreviaturas de IOS ('int g0/1', 'sw mo acc', 'sh ip int br', 'no shut')."""
from __future__ import annotations

import re

from .ios_parser import norm_iface

# Orden = prioridad cuando una abreviatura es ambigua (como lo resuelve uno en la práctica).
KEYWORDS = [
    "show", "interface", "ip", "ipv6", "address", "no", "shutdown", "switchport", "mode", "access",
    "trunk", "vlan", "native", "allowed", "nonegotiate", "encapsulation", "dot1q", "router", "ospf",
    "network", "area", "router-id", "passive-interface", "default-information", "originate",
    "running-config", "startup-config", "copy", "configure", "terminal", "enable", "secret",
    "password", "line", "console", "vty", "login", "local", "transport", "input", "output", "ssh",
    "telnet", "hostname", "description", "domain-name", "domain-lookup", "username", "privilege",
    "service", "password-encryption", "banner", "motd", "crypto", "key", "generate", "rsa",
    "modulus", "version", "dhcp", "pool", "default-router", "dns-server", "excluded-address",
    "helper-address", "nat", "inside", "outside", "source", "list", "overload", "static",
    "access-list", "access-group", "access-class", "permit", "deny", "any", "host", "eq",
    "standard", "extended", "remark", "route", "routing", "unicast-routing", "default-gateway",
    "spanning-tree", "portfast", "bpduguard", "rapid-pvst", "pvst", "priority", "root", "primary",
    "secondary", "cost", "channel-group", "active", "passive", "desirable", "auto", "on",
    "port-security", "maximum", "violation", "restrict", "protect", "sticky", "mac-address",
    "standby", "preempt", "track", "cdp", "lldp", "run", "neighbors", "detail", "brief",
    "interfaces", "status", "summary", "protocols", "database", "binding", "translations",
    "statistics", "eigrp", "bgp", "neighbor", "remote-as", "ntp", "server", "logging", "snmp-server",
    "community", "clock", "set", "timezone", "duplex", "speed", "full", "half", "exec-timeout",
    "synchronous", "history", "write", "memory", "erase", "reload", "ping", "traceroute",
    "debug", "undebug", "all", "exit", "end", "do", "name", "state", "mtu", "bandwidth",
    "delay", "hello-interval", "dead-interval", "authentication", "message-digest",
    "message-digest-key", "md5", "snooping", "trust", "inspection", "arp", "errdisable",
    "recovery", "cause", "vtp", "domain", "transparent", "client",
    "in", "out", "default", "limit", "rate", "block-for", "attempts", "within", "quiet-mode", "validate",
]

_FREE_TEXT_AFTER = {"hostname", "description", "name", "username", "banner", "remark",
                    "domain-name", "pool", "secret", "password", "community", "key"}
_CONTEXT = {
    ("no", "sh"): "shutdown", ("no", "shu"): "shutdown", ("no", "shut"): "shutdown",
    (None, "sh"): "show", (None, "int"): "interface", (None, "conf"): "configure",
    ("configure", "t"): "terminal", ("mode", "acc"): "access", ("mode", "tr"): "trunk",
    ("ip", "add"): "address", ("ip", "int"): "interface", ("interface", "br"): "brief",
    ("show", "run"): "running-config", ("show", "start"): "startup-config",
    ("copy", "run"): "running-config", ("copy", "start"): "startup-config",
    ("running-config", "start"): "startup-config", ("ip", "ro"): "route",
    ("show", "ip"): "ip", (None, "wr"): "write", ("access", "vl"): "vlan",
    (None, "sw"): "switchport", ("switchport", "mo"): "mode", ("switchport", "acc"): "access",
    ("show", "int"): "interfaces", ("show", "vl"): "vlan", ("vlan", "br"): "brief",
    ("show", "cdp"): "cdp", ("line", "con"): "console", ("line", "vt"): "vty", ("cdp", "nei"): "neighbors", ("ip", "nat"): "nat",
    ("bpduguard", "en"): "enable", ("bpduguard", "dis"): "disable", ("service", "pass"): "password-encryption",
    ("service", "password"): "password-encryption",
}


def _expand_token(prev: str | None, tok: str) -> str:
    low = tok.lower()
    if (prev, low) in _CONTEXT:
        return _CONTEXT[(prev, low)]
    if prev is not None and (None, low) in _CONTEXT and low not in ("sh",):
        return _CONTEXT[(None, low)]
    if low in KEYWORDS or not re.fullmatch(r"[a-z][a-z0-9\-]*", low) or len(low) < 2:
        return low if low in KEYWORDS else tok
    for kw in KEYWORDS:
        if kw.startswith(low):
            return kw
    return tok


def expand_command(line: str) -> str:
    """Expande abreviaturas de un comando. Deja intactos nombres, contraseñas y textos libres."""
    toks = line.strip().split()
    out: list[str] = []
    prev = None
    for i, tok in enumerate(toks):
        if prev in _FREE_TEXT_AFTER:
            out.extend(toks[i:])
            break
        if re.fullmatch(r"(?i)[a-z\-]+\d[\d/.:]*", tok) and prev in ("interface", "interfaces", "passive-interface", "range"):
            out.append(norm_iface(tok))
            prev = "<iface>"
            continue
        exp = _expand_token(prev, tok)
        out.append(exp)
        prev = exp.lower()
    return " ".join(out)


def normalize_answer(cmd: str) -> str:
    """Forma canónica para comparar respuestas de tipo comando en exámenes."""
    cmd = re.sub(r"^[\w.\-]+(\([\w\-./]*\))?[#>]\s*", "", cmd.strip())
    cmd = expand_command(cmd)
    cmd = re.sub(r"\s+", " ", cmd).strip().lower()
    # 'interface g0/1' y 'interface GigabitEthernet 0/1'
    cmd = re.sub(r"\b(interfaces?|passive-interface|range) (gigabitethernet|fastethernet|serial|ethernet|loopback|vlan|port-channel) (\d)",
                 r"\1 \2\3", cmd)
    return cmd
