"""Chequeo de estado de NetLab: en unos segundos dice qué está listo y qué no.

Revisa modelos de IA, compiladores/herramientas (rustc, cargo, Java, sbt, Python IA, tshark),
la máquina virtual + el SIEM, y por cada mundo si su "motor" está disponible. Todo son comprobaciones
rápidas (presencia y servicios), sin compilar ni arrancar nada.
"""
from __future__ import annotations


def _try(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def reporte(config: dict) -> dict:
    from . import academia, chisel_lab, ollama, pytorch_lab, rustproj, siem, vm, wireshark

    modelos = _try(ollama.list_models)
    ollama_ok = modelos is not None
    modelos = modelos or []

    def hay_modelo(nombre: str) -> bool:
        if not nombre:
            return False
        base = nombre.split(":")[0]
        return any(m == nombre or m.split(":")[0] == base for m in modelos)

    # --- herramientas / compiladores
    rustc = _try(academia.buscar_rustc)
    cargo = _try(rustproj.buscar_cargo)
    herr = _try(chisel_lab.herramientas, {}) or {}
    java = bool(herr.get("java_home"))
    sbt = bool(herr.get("sbt"))
    py_ia = bool(_try(pytorch_lab.python_ia))
    tshark = bool(_try(wireshark.tshark))
    herramientas = {
        "rustc": {"ok": bool(rustc), "detalle": rustc or "No encontrado (instala Rust con rustup.rs)"},
        "cargo": {"ok": bool(cargo), "detalle": cargo or "No encontrado (viene con rustup)"},
        "java": {"ok": java, "detalle": herr.get("java_home") or "No encontrado (instala Temurin/Adoptium JDK 17)"},
        "sbt": {"ok": sbt, "detalle": herr.get("sbt") or "No encontrado (instala sbt)"},
        "python_ia": {"ok": py_ia, "detalle": "ia_env listo" if py_ia else "Falta ia_env (corre la instalación de PyTorch)"},
        "tshark": {"ok": tshark, "detalle": "Wireshark/tshark listo" if tshark else "tshark no encontrado (los filtros no se verifican)"},
    }

    # --- modelos de IA
    roles = {}
    for rol, etiqueta in (("pesado", "Tutor principal / lecciones"), ("ligero", "Modelo ligero"),
                          ("codigo", "Tutor de la Academia"), ("seguridad", "Tutor de seguridad")):
        pedido = config.get(f"modelo_{rol}", "")
        roles[rol] = {"etiqueta": etiqueta, "pedido": pedido or "(automático)", "ok": ollama_ok and (hay_modelo(pedido) or not pedido)}
    modelos_info = {"ollama": ollama_ok, "instalados": modelos, "roles": roles}

    # --- máquina virtual + SIEM
    vmst = _try(vm.estado, {}) or {}
    corriendo = bool(vmst.get("corriendo"))
    siem_inst = bool(_try(vm.siem_instalado))
    sst = _try(siem.estado_siem, {}) if (corriendo and siem_inst) else {}
    maquina = {
        "virtualbox": {"ok": bool(_try(vm.vboxmanage)), "detalle": "VirtualBox encontrado" if _try(vm.vboxmanage) else "VBoxManage no encontrado"},
        "existe": {"ok": bool(vmst.get("existe")), "detalle": "VM creada" if vmst.get("existe") else "La VM Ubuntu aún no se ha creado"},
        "corriendo": {"ok": corriendo, "detalle": "VM encendida" if corriendo else "VM apagada"},
        "instantanea": {"ok": bool(vmst.get("snapshot")), "detalle": "Instantánea limpia lista" if vmst.get("snapshot") else "Sin instantánea"},
        "siem": {"ok": siem_inst, "detalle": "SIEM instalado" if siem_inst else "SIEM no instalado en la VM"},
        "elasticsearch": {"ok": bool(sst.get("es")), "detalle": "Elasticsearch responde" if sst.get("es") else "Elasticsearch no responde (enciende la VM y espera)"},
        "kibana": {"ok": bool(sst.get("kibana")), "detalle": "Kibana responde" if sst.get("kibana") else "Kibana no responde (tarda 1-3 min en calentar)"},
    }

    # --- mundos: ¿está listo el motor de cada uno? (teoría/práctica/examen existen para todos)
    def mundo(nombre, icono, dep_ok, dep_txt, partes):
        return {"nombre": nombre, "icono": icono, "ok": dep_ok, "dependencia": dep_txt, "partes": partes}

    modelo_base_ok = roles["pesado"]["ok"]
    mundos = [
        mundo("CCNA", "🌐", modelo_base_ok, "Modelo de IA", ["Teoría", "Prácticas Packet Tracer", "Examen", "Simulacro", "Jefe"]),
        mundo("Wireshark", "🦈", modelo_base_ok, "Modelo de IA" + ("" if tshark else " (tshark opcional)"), ["Teoría", "Escenarios", "Filtros verificados" if tshark else "Filtros (sin verificar)"]),
        mundo("Linux", "🐧", modelo_base_ok, "Modelo de IA + VM (opcional)", ["Teoría", "Misiones", "Examen por tema", "VM real", "Jefe"]),
        mundo("SOC", "🚨", modelo_base_ok, "Modelo de IA", ["Casos Windows/Sysmon/phishing", "Mini SIEM"]),
        mundo("Red vs Blue", "⚔️", roles["seguridad"]["ok"] or roles["pesado"]["ok"], "Modelo de seguridad", ["Ataque y defensa", "Pesadilla"]),
        mundo("SIEM", "🛰️", siem_inst and bool(sst.get("es")), "VM + Elasticsearch", ["Casos de detección", "Kibana real"]),
        mundo("Rust", "🦀", bool(rustc), "rustc", ["Teoría", "Misiones", "Retos infinitos", "Rustlings", "Jefe"]),
        mundo("Proyectos Rust", "🛠️", bool(cargo), "cargo", ["Escáner", "Parser pcap", "Mini IDS"]),
        mundo("IA (Academia)", "🧠", bool(rustc), "rustc", ["Teoría", "Misiones", "Retos infinitos", "Jefe"]),
        mundo("PyTorch", "🔥", py_ia, "ia_env (Python)", ["Misiones MNIST/CNN", "nanoGPT"]),
        mundo("Chisel", "🔩", java and sbt, "Java + sbt", ["Misiones", "Verilog generado"]),
        mundo("Procesadores", "🔧", bool(rustc), "rustc", ["Teoría", "Misiones", "Simulador RISC-V"]),
    ]

    listos = sum(1 for m in mundos if m["ok"])
    return {"ok_global": ollama_ok and listos >= len(mundos) - 3,
            "resumen": {"mundos_listos": listos, "mundos_total": len(mundos)},
            "modelos": modelos_info, "herramientas": herramientas, "maquina": maquina, "mundos": mundos}
