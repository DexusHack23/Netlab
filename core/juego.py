"""Modo videojuego: XP, nivel, racha y logros calculados a partir de tu historial (nada extra que guardar)."""
from __future__ import annotations

import datetime

TITULOS = [(1, "Novato de capa 1"), (3, "Aprendiz de switch"), (5, "Domador de VLANs"), (8, "Enrutador junior"),
           (11, "Cazador de paquetes"), (14, "Admin de servidores"), (17, "Analista SOC N1"), (20, "Ingeniero de redes"),
           (25, "Arquitecto CCNA"), (30, "Leyenda del NOC")]


AREA_MUNDO = {"linux": "Linux", "wireshark": "Wireshark", "rust": "Rust", "rustproj": "Proyectos Rust", "ia": "IA", "torch": "PyTorch",
              "cpu": "Procesadores", "chisel": "Chisel", "soc": "SOC",
              "sv": "SystemVerilog", "purple": "Ruta ofensiva"}

JEFES_RUST = {"rs0_5", "rs1_4", "rs2_4", "rs3_5", "rs4_4", "rs5_4", "rs6_5", "rs7_4"}


def _nivel(xp: int) -> tuple[int, int, int]:
    """(nivel, xp_inicio_nivel, xp_siguiente_nivel). Cada nivel pide 100 XP más que el anterior."""
    n, base = 1, 0
    while xp >= base + 100 * n:
        base += 100 * n
        n += 1
    return n, base, base + 100 * n


def calcular(d: dict, n_escenarios_ws: int, n_misiones_lx: int) -> dict:
    xp = {"Prácticas": 0, "Exámenes": 0, "Subneteo": 0, "Wireshark": 0, "Linux": 0, "Teoría": 0, "Red vs Blue": 0, "Repaso y misiones": 0,
          "Rust": 0, "IA": 0, "Procesadores": 0, "SOC": 0, "SIEM": 0, "PyTorch": 0, "Chisel": 0, "Proyectos Rust": 0,
          "SystemVerilog": 0, "Ruta ofensiva": 0}
    for p in d["practicas"]:
        xp["Prácticas"] += round((p["mejor"] or 0) * 10)
    for e in d["examenes"]:
        c = e["calificacion"] or 0
        mundo = e.get("mundo") or "ccna"
        if e["subneteo"]:
            xp["Subneteo"] += round(c * 5)
        elif mundo in AREA_MUNDO:    # exámenes y jefes de cada mundo → ese mundo (antes todos sumaban a CCNA)
            xp[AREA_MUNDO[mundo]] += round(c * 10)
        else:
            xp["Exámenes"] += round(c * (20 if e["simulacro"] else 10))
    mejor_ws: dict[str, float] = {}
    for w in d["capturas"]:
        xp["Wireshark"] += round((w["calificacion"] or 0) * 10)
        mejor_ws[w["escenario"]] = max(mejor_ws.get(w["escenario"], 0), w["calificacion"] or 0)
    for m in d["linux"]:
        xp["Linux"] += 20 * (m["estrellas"] or 0)
    xp["Teoría"] = 15 * len(d["lecciones"])
    rv = d.get("rvb", [])
    xp["Red vs Blue"] = sum(r["puntos"] for r in rv) // 5
    xp["Repaso y misiones"] = 3 * sum(r["aciertos"] or 0 for r in d.get("repaso", [])) + 50 * len(d.get("mision_dia", []))
    ix = d.get("indice", [])
    xp["Ruta ofensiva"] = 30 * len(ix)  # cada sala/máquina/lab que marcas como hecha (con su teoría y detección)
    ac = d.get("academia", [])
    # cada mundo con su propia clave (antes SIEM→SOC, PyTorch→IA, Chisel→Procesadores, Proyectos→Rust y lo desconocido→Rust)
    nombres = {"rust": "Rust", "ia": "IA", "cpu": "Procesadores", "linuxreal": "Linux", "soc": "SOC", "siem": "SIEM",
               "torch": "PyTorch", "chisel": "Chisel", "rustproj": "Proyectos Rust"}
    for a in ac:
        area = nombres.get(a["curso"])
        if area:
            xp[area] += 25 * (a["estrellas"] or 0)
        else:
            xp.setdefault("Otros", 0)
            xp["Otros"] += 25 * (a["estrellas"] or 0)
    total = sum(xp.values())
    nivel, ini, sig = _nivel(total)
    titulo = [t for n, t in TITULOS if nivel >= n][-1]

    dias = set()
    for lista in d.values():
        for r in lista:
            if not isinstance(r, dict):
                continue
            if r.get("fecha"):
                dias.add(r["fecha"][:10])
    hoy = datetime.date.today()
    racha, dia = 0, hoy if hoy.isoformat() in dias else hoy - datetime.timedelta(days=1)
    while dia.isoformat() in dias:
        racha += 1
        dia -= datetime.timedelta(days=1)

    ex = [e for e in d["examenes"] if not e["subneteo"] and e["calificacion"] is not None]
    sub = [e for e in d["examenes"] if e["subneteo"] and e["calificacion"] is not None]
    logros = [
        ("primera", "🚀", "Primer paso", "Califica tu primera práctica de Packet Tracer", any((p["mejor"] or 0) > 0 for p in d["practicas"])),
        ("perfecto", "💯", "Perfección", "Saca 10 en un examen", any(e["calificacion"] >= 10 for e in ex)),
        ("simulacro", "🎓", "Listo para el CCNA", "Aprueba un simulacro con 8.25 o más", any(e["simulacro"] and e["calificacion"] >= 8.25 for e in ex)),
        ("troubleshooter", "🔧", "Troubleshooter", "Arregla una red rota (troubleshooting) con 8 o más", any(p["modo"] == "troubleshooting" and (p["mejor"] or 0) >= 8 for p in d["practicas"])),
        ("subneteo", "🧮", "Ninja del subneteo", "9 o más en un examen de subneteo", any(e["calificacion"] >= 9 for e in sub)),
        ("ws1", "🦈", "Primer paquete", "Califica tu primera captura de Wireshark", bool(mejor_ws)),
        ("ws_todo", "🕵️", "Detective de paquetes", f"8 o más en los {n_escenarios_ws} tipos de captura",
         len([v for v in mejor_ws.values() if v >= 8]) >= n_escenarios_ws),
        ("lx1", "🐧", "Hola, terminal", "Completa tu primera misión de Linux", bool(d["linux"])),
        ("lx3", "⭐", "Sin ayuda", "10 misiones de Linux con 3 estrellas", len([m for m in d["linux"] if m["estrellas"] == 3]) >= 10),
        ("lx_todo", "👑", "root", f"Completa las {n_misiones_lx} misiones de Linux", len(d["linux"]) >= n_misiones_lx),
        ("lector", "📚", "Lector", "Lee o escucha 5 lecciones completas", len(d["lecciones"]) >= 5),
        ("repaso", "🧠", "Memoria de elefante", "Domina 25 preguntas de tu cuaderno de errores", len([r for r in d.get("repaso", []) if (r["caja"] or 0) >= 4]) >= 25),
        ("mision7", "📅", "Constancia", "Completa 7 misiones del día", len(d.get("mision_dia", [])) >= 7),
        ("blue1", "🛡️", "Blue team", "Gana una partida de Red vs Blue", any(r["gano"] for r in rv)),
        ("blue3", "🏰", "Defensa total", "Gana Red vs Blue en CCNA, Wireshark y Linux", {r["modo"] for r in rv if r["gano"]} >= {"ccna", "wireshark", "linux"}),
        ("blue5", "🛡️", "Muralla", "Gana Red vs Blue en los 5 modos (CCNA, Wireshark, Linux, Web y Windows / AD)",
         {r["modo"] for r in rv if r["gano"]} >= {"ccna", "wireshark", "linux", "web", "ad"}),
        ("soc", "🦾", "SOC élite", "Gana Red vs Blue en Difícil", any(r["gano"] and r["dificultad"] in ("dificil", "pesadilla") for r in rv)),
        ("apt", "☠️", "Sobreviviste al APT", "Gana Red vs Blue en Pesadilla", any(r["gano"] and r["dificultad"] == "pesadilla" for r in rv)),
        ("rust1", "🦀", "Hola, Ferris", "Completa tu primera misión de Rust", any(a["curso"] == "rust" for a in ac)),
        ("rust_jefe", "⚙️", "Domador del borrow checker", "Vence al jefe de Ownership y préstamos", any(a["mision"] == "rs1_4" for a in ac)),
        ("rustacean", "🦀", "Rustacean", "Vence a los 8 jefes de Rust", len({a["mision"] for a in ac if a["mision"] in JEFES_RUST}) >= len(JEFES_RUST)),
        ("ia_jefe", "🤖", "Hice mi propio LLM", "Vence al jefe de Modelos de lenguaje", any(a["mision"] == "ia3_3" for a in ac)),
        ("cpu_jefe", "💾", "Emulador propio", "Vence al jefe de RISC-V", any(a["mision"] == "cpu2_3" for a in ac)),
        ("vm1", "🖥️", "Root de verdad", "Completa una misión en la máquina Ubuntu real", any(a["curso"] == "linuxreal" for a in ac)),
        ("vm_ir", "🚨", "Incident responder", "Contén el incidente completo en la máquina real", any(a["mision"] == "vm_r15" for a in ac)),
        ("soc1", "🚨", "Analista N1", "Cierra un ticket del SOC con 10/10", any(a["curso"] == "soc" and a["estrellas"] == 3 for a in ac)),
        ("idx1", "🗺️", "Primera sala", "Marca como hecha tu primera sala de TryHackMe, máquina de HTB o lab local", bool(ix)),
        ("idx10", "🎯", "Purple team", "Completa 10 salas/máquinas del índice", len(ix) >= 10),
        ("racha3", "🔥", "En racha", "Estudia 3 días seguidos", racha >= 3),
        ("racha7", "☄️", "Imparable", "Estudia 7 días seguidos", racha >= 7),
        ("nivel10", "🏆", "Nivel 10", "Llega al nivel 10", nivel >= 10),
    ]
    return {"xp": total, "por_area": xp, "nivel": nivel, "titulo": titulo, "xp_nivel": total - ini, "xp_para_subir": sig - ini,
            "racha": racha, "estudio_hoy": hoy.isoformat() in dias,
            "logros": [{"id": i, "icono": ic, "nombre": n, "desc": ds, "ok": bool(ok)} for i, ic, n, ds, ok in logros]}


def listo(prog: dict, prog_ws: dict, misiones: dict, dominios, escenarios: dict, n_misiones: int) -> dict:
    """¿Qué tan listo estás para cada examen? Porcentajes por dominio con tus mejores notas."""
    mejor = lambda t: min((prog.get(t) or {}).get("mejor") or 0, 10) / 10  # noqa: E731
    ccna = []
    for nombre, peso, temas in dominios:
        ccna.append({"dominio": nombre, "peso": round(peso * 100), "pct": round(100 * sum(mejor(t) for t in temas) / len(temas))})
    sim = (prog.get("simulacro") or {}).get("mejor_examen")
    total_ccna = round(sum(d["pct"] * d["peso"] for d in ccna) / 100)
    niveles = {}
    for k, e in escenarios.items():
        niveles.setdefault(e["nivel"], []).append(min((prog_ws.get(k) or {}).get("mejor") or 0, 10) / 10)
    wca = [{"dominio": f"Escenarios · {n}", "pct": round(100 * sum(v) / len(v))} for n, v in niveles.items()]
    ex_ws = (prog.get("wireshark") or {}).get("mejor_examen")
    wca.append({"dominio": "Examen tipo WCA-101", "pct": round((ex_ws or 0) * 10)})
    ex_tema = lambda pref, n: round(10 * sum(min(v.get("mejor_examen") or 0, 10) for k, v in prog.items() if k.startswith(pref)) / n)  # noqa: E731
    wca.append({"dominio": "Exámenes por tema", "pct": min(100, ex_tema("ws_", len(escenarios) + 2))})
    wca.append({"dominio": "Jefes vencidos", "pct": min(100, ex_tema("jefe_ws_", 4))})
    lx_est = sum(misiones.values())
    ex_lx = (prog.get("linux") or {}).get("mejor_examen")
    lx = [{"dominio": "Misiones (estrellas)", "pct": round(100 * lx_est / max(1, 3 * n_misiones))},
          {"dominio": "Examen de Linux", "pct": round((ex_lx or 0) * 10)},
          {"dominio": "Exámenes por tema", "pct": min(100, ex_tema("lx_", 13))},
          {"dominio": "Jefes vencidos", "pct": min(100, ex_tema("jefe_lx_", 4))}]
    prom = lambda l: round(sum(d["pct"] for d in l) / len(l))  # noqa: E731
    return {
        "ccna": {"total": total_ccna, "dominios": ccna, "simulacro": sim,
                 "veredicto": "¡Listo para agendar!" if total_ccna >= 80 and all(d["pct"] >= 70 for d in ccna) and (sim or 0) >= 8.25
                 else "Aún no: sube los dominios en rojo y aprueba un simulacro con 8.25"},
        "wca": {"total": prom(wca), "dominios": wca,
                "veredicto": "¡Listo para el WCA-101!" if prom(wca) >= 80 and all(d["pct"] >= 70 for d in wca) else "Aún no: completa los escenarios con ★★ y aprueba el examen WCA"},
        "linux": {"total": prom(lx), "dominios": lx,
                  "veredicto": "¡Nivel sólido de Linux!" if prom(lx) >= 80 else "Sigue con las misiones y el examen de Linux"},
    }
