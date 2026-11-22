# -*- coding: utf-8 -*-
"""
NETLAB (antes Lab CCNA) — prácticas de Packet Tracer y exámenes con tus modelos locales (Ollama).

- Ruta de temas fija de Básico a Superior (temario CCNA 200-301 + extras).
- Exámenes: el modelo escribe las preguntas y luego las vuelve a contestar sin ver la
  clave; las que no coinciden se descartan. Los comandos se califican expandiendo
  abreviaturas de IOS ('sh ip int br' = 'show ip interface brief').
- Prácticas: topología, direccionamiento, tareas, config inicial lista para pegar y
  solución oculta. Antes de mostrártela, el código comprueba que su propia solución
  pase sus propias verificaciones y que las subredes cuadren; si no, se la regresa
  al modelo para que la corrija.
- Revisión: pegas la running-config / show / ping / ipconfig de cada equipo y un
  verificador determinista califica. La IA solo explica lo que el verificador encontró.
- Sin basura: no escribe temporales ni __pycache__; lo único que guarda es
  datos/historial.db y datos/config.json. Al cerrar (ventana, botón o Ctrl+C) libera
  la VRAM de los modelos que usó.

Sin dependencias externas: solo Python 3.10+ y Ollama.
"""
import sys

sys.dont_write_bytecode = True  # nada de __pycache__

import atexit
import contextlib
import json
import os
import re
import subprocess
import threading
import time
import traceback
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import db, ollama
from core import generador as gen
from core import jitl, packet_tracer, ptbuilder, temario
from core import academia, bench_seg, guias, juego, rvb, salud, siem, vm, vm_misiones
from core import wireshark as ws
from core.checker import TIPOS, Evidence, grade

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos")
WEB = os.path.join(AQUI, "web")
PUERTO = int(os.environ.get("LABCCNA_PUERTO", "8765"))
CONFIG_RUTA = os.path.join(DATOS, "config.json")
ERROR_RUTA = os.path.join(DATOS, "ultimo_error.txt")
GUIAS = os.path.join(AQUI, "guias")       # tus PDFs/txt/md de consulta
GUIAS_DB = os.path.join(DATOS, "guias.db")  # sus vectores (se rehacen solos si cambian los archivos)
TMP = os.path.join(DATOS, "tmp")  # capturas .pcap de trabajo: se borran al abrir y al cerrar la app

CONFIG_DEFECTO = {
    "modelo_pesado": "gemma4:12b",         # diseña prácticas y exámenes (medido en tu PC: ~70-180 tok/s)
    "modelo_ligero": "qwen3:4b-instruct",  # explica errores y califica comandos dudosos
    "espera_pesado": "2m",                 # se descarga solo tras 2 min sin uso
    "espera_ligero": "10m",
    "verificar_examenes": True,
    "vm_auto_calentar": True,   # al abrir NetLab, si el SIEM está instalado, la VM se enciende/reanuda sola
    "vm_auto_caliente": True,   # al quedar listo el SIEM, toma una instantánea en caliente si no hay (necesita ~18 GB libres)
    "explicar_con_pesado": False,
    "modelo_vision": "qwen3-vl:8b",        # lee capturas de pantalla de la CLI (opcional)
    "escala_pt": "1.25",                   # tamaño de Packet Tracer (no guarda su letra; se escala todo)
    "carpeta_jitl": "",                    # vacío = MIS CARPETAS\1-JITL
    "modelo_embed": "",                    # vacío = el mejor que tengas (qwen3-embedding > bge-m3 > nomic)
    "usar_guias": True,                    # meter fragmentos de tus guías al generar
    "idioma": "en",                        # en | es: idioma de la interfaz y de lo que escribe la IA
    "modelo_codigo": "qwen2.5-coder:14b",  # tutor de la Academia (Rust / IA / Procesadores)
    "espera_codigo": "5m",
    "modelo_seguridad": "",                # tutor de Wireshark/Linux/Red vs Blue y atacante de Pesadilla ("" = el ligero)
    "espera_seguridad": "5m",
}

SIN_LATIDO_SEG = 150  # si la ventana se cerró (no hay latidos), la app se apaga sola


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
def cargar_config() -> dict:
    cfg = dict(CONFIG_DEFECTO)
    try:
        with open(CONFIG_RUTA, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def guardar_config(cfg: dict) -> None:
    with open(CONFIG_RUTA, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


CONFIG = cargar_config()
ollama.IDIOMA = CONFIG.get("idioma", "es")
MODELOS_USADOS: set[str] = set()


def modelo(rol: str) -> tuple[str, str]:
    """('pesado'|'ligero') -> (nombre, keep_alive). Si no existe, usa el que haya."""
    nombre = CONFIG.get(f"modelo_{rol}") or CONFIG["modelo_pesado"]
    disponibles = ollama.list_models()
    if rol in ("codigo", "seguridad") and (not CONFIG.get(f"modelo_{rol}") or (disponibles and nombre not in disponibles)):
        rol = "pesado" if rol == "codigo" else "ligero"
        nombre = CONFIG[f"modelo_{rol}"]
    if disponibles and nombre not in disponibles:
        prefer = ["gemma4:12b", "gpt-oss:20b", "qwen3:30b", "qwen3:4b-instruct", "qwen3:4b"]
        nombre = next((m for m in prefer if m in disponibles), disponibles[0])
    if rol in ("pesado", "codigo", "seguridad"):
        # el pesado necesita la VRAM entera: suelta los otros modelos que cargó ESTA app (nunca los de otras apps)
        cargados = set(ollama.loaded_models())
        for otro in MODELOS_USADOS - {nombre}:
            if otro in cargados:
                ollama.unload(otro)
    MODELOS_USADOS.add(nombre)
    return nombre, CONFIG.get(f"espera_{rol}", "2m")


# --------------------------------------------------------------------------- #
# Trabajos largos (una sola llamada pesada a la vez para no saturar la GPU)
# --------------------------------------------------------------------------- #
TRABAJOS: dict[str, dict] = {}
_RUSTC: dict[str, str] = {}
GPU = threading.Lock()


def lanzar(funcion, *args, gpu: bool = True) -> str:
    tid = uuid.uuid4().hex[:10]
    t = {"estado": "en_cola", "mensajes": [], "resultado": None, "error": None, "inicio": time.time()}
    TRABAJOS[tid] = t

    def progreso(msg):
        t["mensajes"].append(msg)

    def correr():
        if gpu and GPU.locked():
            progreso("Esperando turno de la GPU…")
        with (GPU if gpu else contextlib.nullcontext()):
            t["estado"] = "trabajando"
            try:
                t["resultado"] = funcion(progreso, *args)
                t["estado"] = "listo"
                t["duracion"] = round(time.time() - t["inicio"], 1)
            except ollama.OllamaError as e:
                t["error"], t["estado"] = str(e), "error"
            except Exception as e:  # noqa: BLE001
                t["error"], t["estado"] = f"{type(e).__name__}: {e}", "error"
                traceback.print_exc()
    threading.Thread(target=correr, daemon=True).start()
    # limpiar trabajos viejos de memoria
    for k in [k for k, v in TRABAJOS.items() if time.time() - v["inicio"] > 3600]:
        TRABAJOS.pop(k, None)
    return tid


def hay_trabajo_activo() -> bool:
    return any(t["estado"] in ("en_cola", "trabajando") for t in TRABAJOS.values())


# ---- tareas ------------------------------------------------------------------ #
def t_generar_practica(progreso, body):
    m, keep = modelo("pesado")
    with _keep(keep):
        if body.get("modo") == "troubleshooting":
            p = gen.generar_troubleshooting(m, body.get("tema", ""), body.get("nivel", "Intermedio"),
                                            body.get("descripcion", "").strip(), progreso=progreso)
        else:
            p = gen.generar_practica(m, body.get("tema", ""), body.get("nivel", "Intermedio"),
                                     body.get("modo", "guiado"), body.get("descripcion", "").strip(),
                                     progreso=progreso)
    p["modelo"] = m
    pid = db.guardar_practica(p)
    progreso("Lista.")
    return {"id": pid}


def t_revisar(progreso, body):
    p = db.practica(int(body["id"]))
    if not p:
        raise ValueError("No encontré esa práctica.")
    evs, textos = {}, {}
    for d, e in (body.get("evidencias") or {}).items():
        evs[d] = Evidence(e.get("config", ""), e.get("salidas", ""))
        textos[d] = (e.get("config", "") + "\n" + e.get("salidas", "")).strip()
    progreso("Verificando tu configuración…")
    res = grade(p, evs)
    res["explicacion"] = ""
    if body.get("explicar", True) and (res["fallas"] or res["sin_datos"]):
        rol = "pesado" if CONFIG.get("explicar_con_pesado") else "ligero"
        m, keep = modelo(rol)
        progreso(f"Pidiendo a {m} que te explique los errores…")
        with _keep(keep):
            try:
                res["explicacion"] = gen.explicar(m, p, res, textos)
            except ollama.OllamaError as e:
                res["explicacion"] = f"(No se pudo generar la explicación: {e})"
    db.guardar_intento(p["id"], res["calificacion"], {"resultado": res, "evidencias": body.get("evidencias")})
    return res


def _dominio_examen(body) -> str:
    """Mundo del examen: el que pide la UI o, si falta, el que delata el id del tema (lx_*, ws_*, ac_<curso>_*, jefe_*)."""
    d = body.get("dominio")
    if d in gen._DOMINIO:
        return d
    m = gen.mundo_de(str(body.get("tema") or ""))
    return m if m in gen._DOMINIO else "ccna"


def t_generar_examen(progreso, body):
    m, keep = modelo("pesado")
    n = max(3, min(int(body.get("n", 10)), 30))
    with _keep(keep):
        e = gen.generar_examen(m, body.get("tema", ""), body.get("nivel", "Intermedio"), n,
                               body.get("descripcion", "").strip(),
                               verificar=bool(CONFIG.get("verificar_examenes", True)), progreso=progreso,
                               dominio=_dominio_examen(body))
    if not e["preguntas"]:
        raise ValueError("El modelo no generó preguntas válidas. Intenta de nuevo o cambia de modelo.")
    e["modelo"] = m
    return {"id": db.guardar_examen(e)}


def t_generar_topologia(progreso, body):
    desc = (body.get("descripcion") or "").strip()
    if len(desc) < 8:
        raise ValueError("Describe un poco más la red que quieres armar.")
    m, keep = modelo("pesado")
    with _keep(keep):
        p = gen.generar_topologia(m, desc, progreso=progreso)
    p["modelo"] = m
    return {"id": db.guardar_practica(p)}


def t_generar_simulacro(progreso, body):
    n = int(body.get("n", 60))
    n = n if n in (30, 60, 100) else 60
    m, keep = modelo("pesado")
    with _keep(keep):
        e = gen.generar_simulacro(m, n, verificar=bool(CONFIG.get("verificar_examenes", True)), progreso=progreso)
    e["modelo"] = m
    return {"id": db.guardar_examen(e)}


def t_leer_captura(progreso, body):
    """Convierte una captura de la CLI de Packet Tracer en texto, para pegarlo en la revisión."""
    import base64
    datos = (body.get("imagen") or "").split(",", 1)[-1]
    if not datos or len(datos) > 12_000_000:
        raise ValueError("La imagen está vacía o pesa demasiado (máx. ~8 MB).")
    base64.b64decode(datos[:100] + "=" * (-len(datos[:100]) % 4))  # valida que sea base64
    m = CONFIG.get("modelo_vision") or "qwen3-vl:8b"
    if m not in ollama.list_models():
        raise ValueError(f"No tienes el modelo de visión {m}. En PowerShell: ollama pull {m}")
    MODELOS_USADOS.add(m)
    progreso(f"Leyendo la captura con {m}…")
    with _keep(CONFIG.get("espera_ligero", "10m")):
        texto = ollama.chat(m, [{
            "role": "user",
            "content": ("Transcribe EXACTAMENTE el texto de la consola/CLI que aparece en esta captura de Cisco "
                        "Packet Tracer (router, switch o Command Prompt de una PC). Respeta cada línea, los espacios "
                        "y la sangría. No expliques nada, no agregues nada, no uses bloques de código: solo el texto."),
            "images": [datos]}], temperature=0.0, num_ctx=8192, num_predict=4000)
    texto = re.sub(r"^```\w*\n|\n```$", "", texto.strip())
    return {"texto": texto, "modelo": m}


# ---- Guías (RAG) ------------------------------------------------------------ #
def _referencias(consulta: str, mundo: str | None = None) -> str:
    """Fragmentos de tus guías; con `mundo`, solo de las guías de ese mundo (Rust solo ve guías de Rust, etc.)."""
    if not CONFIG.get("usar_guias", True) or not os.path.isfile(GUIAS_DB):
        return ""
    m = guias.modelo_embed(CONFIG.get("modelo_embed", ""))
    if m:
        MODELOS_USADOS.add(m)
    return guias.contexto(GUIAS_DB, consulta, mundo=mundo)


gen.REFERENCIAS = _referencias


def t_indexar_guias(progreso, body):
    r = guias.indexar(GUIAS, GUIAS_DB, CONFIG.get("modelo_embed", ""), progreso)
    MODELOS_USADOS.add(r["modelo"])
    return r


_PCAP_PRUEBA = {}


def _parece_filtro(f: str) -> bool:
    if re.fullmatch(r"[\w.\-]+\.(pcap|pcapng|txt|pdf|md|com|mx|org|net|edu|exe)", f):
        return False
    if len(f) > 200 or f.startswith(("show ", "tshark", "-")) or "/" in (f.split() or [""])[0]:
        return False
    return bool(re.match(r"!?\(?[a-z][\w\-]*\.[a-z]", f) or re.search(r"==|!=|&&|\|\||>=|<=| contains | matches ", f))


def _filtro_valido(f: str):
    """True si tshark lo acepta; si no, el texto de sugerencia (o False). Usa una captura de prueba en datos/tmp."""
    if "ruta" not in _PCAP_PRUEBA or not os.path.isfile(_PCAP_PRUEBA["ruta"]):
        os.makedirs(TMP, exist_ok=True)
        _PCAP_PRUEBA["ruta"] = os.path.join(TMP, "prueba_filtros.pcap")
        with open(_PCAP_PRUEBA["ruta"], "wb") as fh:
            fh.write(ws.generar("dns", 1)["pcap"])
    r = ws.correr_filtro(_PCAP_PRUEBA["ruta"], f)
    return True if r["ok"] else (guias.sugerir_campo(GUIAS, r["error"]) or False)


def validar_filtros_en_texto(texto: str) -> str:
    """Los filtros que sugiere el modelo se prueban con tshark; los que no existen se marcan."""
    if not ws.tshark():
        return texto
    vistos = {}

    def revisa(m):
        f = m.group(1).strip()
        if not _parece_filtro(f):
            return m.group(0)
        if f not in vistos:
            vistos[f] = _filtro_valido(f)
        ok = vistos[f]
        if ok is True:
            return m.group(0)
        return m.group(0) + " ⚠️ *(tshark dice que este filtro no es válido" + (f"; {ok}" if ok else "") + ")*"
    return re.sub(r"`([^`\n]+)`", revisa, texto)


# ---- Wireshark ------------------------------------------------------------- #
def limpiar_tmp():
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)


def pcap_de(c: dict) -> str:
    """Escribe (o reutiliza) el .pcap de un ejercicio en datos/tmp. Se regenera igual a partir de la semilla."""
    os.makedirs(TMP, exist_ok=True)
    if c["escenario"] == "vivo":
        ruta = os.path.join(TMP, f"vivo_{c['id']}.pcapng")
        if not os.path.isfile(ruta):
            raise ValueError("Esa captura en vivo ya se borró: por privacidad se borran al cerrar NetLab. Haz otra.")
        return ruta
    ruta = os.path.join(TMP, f"ejercicio_{c['id'] if 'id' in c else 'nuevo'}_{c['escenario']}.pcap")
    if not os.path.isfile(ruta):
        with open(ruta, "wb") as f:
            f.write(ws.generar(c["escenario"], c["semilla"])["pcap"])
    return ruta


def generar_wireshark(escenario: str) -> dict:
    """Arma el ejercicio y, si hay tshark, comprueba con él cada filtro y cada conteo de la clave."""
    import random as _r
    if escenario not in ws.ESCENARIOS:
        escenario = _r.choice(list(ws.ESCENARIOS))
    semilla = _r.randint(1, 10**9)
    c = ws.generar(escenario, semilla)
    os.makedirs(TMP, exist_ok=True)
    ruta = os.path.join(TMP, f"validando_{semilla}.pcap")
    with open(ruta, "wb") as f:
        f.write(c.pop("pcap"))
    c["validada"] = False
    try:
        if ws.tshark():
            filtros = []
            for fl in c["filtros"]:
                r = ws.correr_filtro(ruta, fl["referencia"])
                if r["ok"] and r["frames"]:
                    filtros.append(fl)
            preguntas = []
            for p in c["preguntas"]:
                if p.get("conteo"):
                    r = ws.correr_filtro(ruta, p["conteo"])
                    if not (r["ok"] and str(len(r["frames"])) == p["respuesta"]):
                        continue
                preguntas.append(p)
            c["filtros"], c["preguntas"], c["validada"] = filtros, preguntas, True
    finally:
        os.remove(ruta)
    c["id"] = db.guardar_captura(c)
    return c


def captura_publica(c: dict) -> dict:
    out = {k: c.get(k) for k in ("id", "fecha", "escenario", "nivel", "titulo", "temas", "paquetes", "validada",
                                 "calificacion", "resultado")}
    out["preguntas"] = [{"id": p["id"], "texto": p["texto"], "pista": p.get("explicacion", "")} for p in c["preguntas"]]
    out["filtros"] = [{"id": f["id"], "texto": f["texto"], "pista": f.get("pista", "")} for f in c["filtros"]]
    return out


def probar_filtro(c: dict, fid: str, filtro: str) -> dict:
    ref = next((f for f in c["filtros"] if f["id"] == fid), None)
    if not ref:
        return {"ok": False, "error": "Ejercicio desconocido."}
    filtro = (filtro or "").strip()
    if not filtro:
        return {"ok": False, "error": "Escribe un filtro."}
    ruta = pcap_de(c)
    tuyo = ws.correr_filtro(ruta, filtro)
    if not tuyo["ok"]:
        sug = guias.sugerir_campo(GUIAS, tuyo["error"])
        return {"ok": False, "correcto": False, "error": tuyo["error"] + (f" {sug}" if sug else "")}
    bueno = ws.correr_filtro(ruta, ref["referencia"])
    if not bueno["ok"]:
        return {"ok": False, "error": bueno["error"]}
    a, b = set(tuyo["frames"]), set(bueno["frames"])
    return {"ok": True, "correcto": a == b, "mostrados": len(a), "esperados": len(b),
            "sobran": sorted(a - b)[:15], "faltan": sorted(b - a)[:15]}


def calificar_wireshark(c: dict, respuestas: dict, filtros: dict) -> dict:
    detalle = []
    for p in c["preguntas"]:
        dada = str(respuestas.get(p["id"], ""))
        detalle.append({"id": p["id"], "clase": "pregunta", "texto": p["texto"], "tuya": dada,
                        "correcta": p["respuesta"], "ok": ws.calificar_respuesta(p, dada),
                        "explicacion": p.get("explicacion", "")})
    for f in c["filtros"]:
        dado = str(filtros.get(f["id"], "")).strip()
        r = probar_filtro(c, f["id"], dado) if dado else {"correcto": False, "error": "Sin contestar"}
        detalle.append({"id": f["id"], "clase": "filtro", "texto": f["texto"], "tuya": dado,
                        "correcta": f["referencia"], "ok": bool(r.get("correcto")),
                        "explicacion": r.get("error") or (f"Mostró {r.get('mostrados')} paquetes; se esperaban "
                                                          f"{r.get('esperados')}." if not r.get("correcto") else "")})
    buenas = sum(d["ok"] for d in detalle)
    res = {"detalle": detalle, "buenas": buenas, "total": len(detalle),
           "calificacion": round(10 * buenas / max(len(detalle), 1), 1)}
    db.guardar_resultado_captura(c["id"], res)
    for d in detalle:  # solo los filtros genéricos (sin IPs) sirven fuera de esa captura
        if d["clase"] == "filtro" and not d["ok"] and not re.search(r"\d+\.\d+\.\d+\.\d+|[0-9a-f]{2}:[0-9a-f]{2}:", d["correcta"]):
            db.agregar_repaso("wsf:" + d["correcta"], "Wireshark", "texto",
                              {"enunciado": f"Filtro de Wireshark: {d['texto']}", "respuestas": [d["correcta"]], "explicacion": "", "origen": c.get("titulo", "")})
    return res


def t_capturar(progreso, body):
    """Captura tu tráfico real unos segundos y arma preguntas con respuesta exacta (sacada con tshark)."""
    seg = max(5, min(int(body.get("segundos", 20)), 120))
    interfaz = str(body.get("interfaz", ""))[:200]
    if not interfaz:
        raise ValueError("Elige una interfaz.")
    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, f"vivo_tmp_{uuid.uuid4().hex[:6]}.pcapng")
    progreso(f"Capturando {seg} s… navega, haz ping o abre páginas para que haya tráfico")
    r = ws.capturar(interfaz, seg, tmp)
    if not r["ok"]:
        raise ValueError(r["error"])
    progreso("Armando preguntas sobre tu tráfico…")
    preguntas, filtros, n = ws.preguntas_de_captura(tmp)
    if not preguntas:
        os.remove(tmp)
        raise ValueError("Casi no hubo tráfico IP. Vuelve a capturar mientras navegas.")
    c = {"escenario": "vivo", "nivel": "En vivo", "titulo": f"Tu captura en vivo ({n} paquetes)", "semilla": 0,
         "preguntas": preguntas, "filtros": filtros, "temas": "tu propio tráfico", "paquetes": n, "validada": True}
    c["id"] = db.guardar_captura(c)
    os.replace(tmp, os.path.join(TMP, f"vivo_{c['id']}.pcapng"))
    return captura_publica(db.captura(c["id"]))


def t_analizar_captura(progreso, body):
    """Tu propia captura: tshark saca las estadísticas y el modelo te las explica. El archivo se borra al terminar."""
    import base64
    if not ws.tshark():
        raise ValueError("No encontré tshark. Viene con Wireshark (C:\\Program Files\\Wireshark).")
    datos = base64.b64decode((body.get("datos") or "").split(",", 1)[-1])
    if not datos:
        raise ValueError("El archivo está vacío.")
    ext = ".pcapng" if datos[:4] == b"\x0a\x0d\x0d\x0a" else ".pcap"
    os.makedirs(TMP, exist_ok=True)
    ruta = os.path.join(TMP, f"tuya_{uuid.uuid4().hex[:8]}{ext}")
    with open(ruta, "wb") as f:
        f.write(datos)
    try:
        progreso("Sacando estadísticas con tshark…")
        resumen = ws.resumen_tshark(ruta)
    finally:
        os.remove(ruta)
    if not resumen.strip():
        raise ValueError("tshark no pudo leer el archivo. ¿Es un .pcap o .pcapng?")
    m, keep = modelo("pesado")
    pregunta = (body.get("pregunta") or "").strip()[:500]
    progreso("Consultando tus guías…")
    refs = _referencias(mundo="wireshark", consulta=(pregunta + " " if pregunta else "") + "filtros de Wireshark análisis de captura "
                        + " ".join(re.findall(r"^\s*(\w+)\s+frames", resumen, re.M)[:8]))
    progreso(f"Explicando con {m}…")
    with _keep(keep):
        texto = ollama.chat(m, [
            {"role": "system", "content": "Eres instructor de redes (CCNA y Wireshark). Respondes en español de México, "
             "claro y concreto, en Markdown breve. Solo afirmas lo que se ve en las estadísticas; si algo no se puede "
             "saber con ellas, lo dices."},
            {"role": "user", "content": f"Estadísticas de tshark de una captura:\n\n{resumen}\n\n"
             + (f"Pregunta del alumno: {pregunta}\n\n" if pregunta else "")
             + (f"Material de referencia de sus guías (úsalo para nombres de campos exactos):\n<<<\n{refs}\n>>>\n\n"
                if refs else "")
             + "Explica: 1) qué protocolos y conversaciones dominan, 2) cualquier cosa rara o problema (retransmisiones, "
             "errores, escaneos, texto claro), 3) tres filtros de Wireshark útiles para investigar esta captura, con "
             "qué muestra cada uno."}], temperature=0.2, num_predict=2500)
    progreso("Comprobando con tshark los filtros que sugirió…")
    return {"texto": validar_filtros_en_texto(texto), "resumen": resumen, "modelo": m}


# ---- Teoría -------------------------------------------------------------------- #
def temas_teoria() -> list[dict]:
    out = [{"id": t["id"], "grupo": f"CCNA · {t['nivel']}", "nombre": t["nombre"], "clave": t["clave"]}
           for t in temario.TEMAS]
    out += [{"id": "ws_" + k, "grupo": "Wireshark (WCA-101)", "nombre": v["nombre"], "clave": v["temas"]}
            for k, v in ws.ESCENARIOS.items()]
    out += [{"id": "lx_" + k, "grupo": "Linux", "nombre": n, "clave": c} for k, n, c in (
        ("fs", "Sistema de archivos y navegación", "jerarquía /, rutas absolutas y relativas, pwd, cd, ls, home, archivos ocultos"),
        ("archivos", "Archivos y carpetas", "touch, mkdir -p, cp -r, mv, rm -r, comodines, nano"),
        ("texto", "Ver y buscar texto", "cat, less, head, tail -f, grep (-i -n -v -c -r -o), find"),
        ("tuberias", "Tuberías y redirecciones", "stdin/stdout/stderr, |, >, >>, 2>, sort, uniq -c, cut, wc, tr, awk básico"),
        ("permisos", "Permisos y dueños", "rwx, notación octal, chmod, chown, umask, sudo, setuid"),
        ("usuarios", "Usuarios y grupos", "/etc/passwd, /etc/shadow, useradd, usermod, groups, sudoers"),
        ("procesos", "Procesos y servicios", "ps aux, top, kill, señales, systemd, systemctl, journalctl"),
        ("paquetes", "Paquetes e instalación", "apt update/upgrade/install/remove, repositorios, dpkg"),
        ("red", "Redes en Linux", "ip a, ip r, ping, ss -tulpn, curl, dig, /etc/hosts, /etc/resolv.conf, ufw"),
        ("logs", "Logs y seguridad para SOC", "/var/log/auth.log, syslog, journalctl, fuerza bruta SSH, fail2ban, permisos de llaves SSH"),
        ("bash", "Scripts de bash", "shebang, variables, if, for, $?, argumentos, cron"),
        ("sedawk", "Texto pro: awk, sed, cut y base64", "awk -F con columnas y sumas, sed s/// y -i, sed '/^#/d', cut -d -f, sort -t -k, base64 -d, tr"),
        ("ir", "Respuesta a incidentes y persistencia", "persistencia en crontab y /etc/cron.*, usuarios con UID 0, llaves SSH autorizadas, procesos y mineros sospechosos, "
         "kill/pkill, usermod -L, passwd -l, last/who, contención y evidencias"))]
    out += [{"id": "soc_" + k, "grupo": "🚨 SOC", "nombre": n, "clave": c} for k, n, c in (
        ("triage", "Triage de alertas y falsos positivos", "severidad, contexto, verdadero/falso positivo, escalamiento, tickets, SLA"),
        ("windows", "Logs de Windows y Sysmon", "Event IDs 4624, 4625, 4688, 4720, 7045, logon types, Sysmon 1/3/11, PowerShell -enc"),
        ("phishing", "Análisis de phishing", "cabeceras, Return-Path, SPF, DKIM, DMARC, URLs y adjuntos sospechosos, sandbox"),
        ("siem", "Búsquedas en un SIEM", "Kibana Discover, KQL/Lucene, filtros, agregaciones, línea de tiempo, correlación"),
        ("red", "Tráfico sospechoso en la red", "escaneos de puertos, beacons C2, exfiltración, DNS tunneling, NetFlow"),
        ("mitre", "MITRE ATT&CK y Cyber Kill Chain", "tácticas, técnicas, sub-técnicas, mapeo de alertas, Kill Chain de Lockheed"),
        ("ir", "Respuesta a incidentes (NIST SP 800-61)", "preparación, detección, contención, erradicación, recuperación, lecciones aprendidas, evidencias"),
        ("cti", "Inteligencia de amenazas e IOCs", "IOCs, pirámide del dolor, VirusTotal, reputación de IPs y dominios, hashes"),
        ("ransomware", "Ransomware: detección y respuesta", "macros, PowerShell, vssadmin delete shadows, wbadmin, bcdedit, cifrado masivo, nota de rescate, T1490, T1486, aislar sin apagar, respaldos"),
        ("c2", "Malware y comando y control (C2)", "beaconing, intervalos regulares, jitter, logs de proxy, User-Agent anómalo, dominios nuevos, exfiltración por el C2, T1071.001, T1041"),
        ("insider", "Amenaza interna y fuga de datos", "accesos fuera de horario, 4663, compresión con contraseña, USB 6416, nube personal, DLP, T1052.001, T1567.002, RH y Legal"),
        ("nube", "Cuentas de nube comprometidas (Entra ID / M365)", "viaje imposible, MFA fatigue, number matching, reglas de bandeja, reenvío externo, BEC, revocar sesiones, T1621, T1564.008"),
        ("web", "Ataques web en el access.log", "formato combined de Apache/Nginx, SQLi, XSS, path traversal/LFI, fuerza bruta, gobuster/ffuf/nikto, inyección de comandos, webshells, WAF, T1190"),
        ("ad", "Ataques a Active Directory", "Kerberoasting 4769 0x17, AS-REP roasting 4768 PreAuthType 0, password spraying 4771, Pass-the-Hash, DCSync 4662, PsExec 7045, Domain Admins 4728"))]
    # 🗺️ Ruta ofensiva (Purple Team): solo concepto + detección + mitigación; el ataque se practica en TryHackMe/HTB
    out += [{"id": "idx_" + k, "grupo": "🗺️ Ruta ofensiva (Purple Team)", "nombre": n, "clave": c} for k, n, c in (
        ("fundamentos", "Metodología de pentesting y Cyber Kill Chain", "fases de un pentest, alcance y permiso por escrito, Cyber Kill Chain, tácticas de MITRE ATT&CK, reporte"),
        ("recon", "Reconocimiento y escaneo de puertos", "descubrimiento de hosts (ARP, ICMP), SYN/connect/UDP scan, estados abierto/cerrado/filtrado, detección de versiones, T1595, T1046, cómo se ve en Wireshark/IDS"),
        ("servicios", "Servicios de red expuestos", "Telnet, FTP anónimo, SMB sin autenticación, Redis abierto, SNMP public, texto claro, endurecimiento, T1021, T1133"),
        ("passwords", "Contraseñas, fuerza bruta y cracking", "ataques en línea vs fuera de línea, hashes, sal, password spraying, 4625/4771, auth.log, MFA, bloqueo, T1110"),
        ("web", "Vulnerabilidades web (OWASP Top 10:2025)", "OWASP Top 10:2025 (A01 control de acceso roto incluye SSRF, A02 mala configuración, A03 fallas de la cadena de suministro, A05 inyección, A10 manejo de condiciones excepcionales), SQLi, XSS, path traversal/LFI, inyección de comandos, subida de archivos, IDOR, WAF, consultas parametrizadas, ASVS 5.0, T1190"),
        ("api", "Seguridad de APIs (OWASP API Security Top 10)", "OWASP API Security Top 10 2023: BOLA (API1), autenticación rota, autorización a nivel de propiedad y asignación masiva, consumo de recursos sin límite, BFLA (API5), flujos de negocio sensibles, SSRF, mala configuración, inventario de APIs, consumo inseguro de APIs; detección en logs de API, rate limiting, T1190"),
        ("privesc_linux", "Escalada de privilegios en Linux", "SUID, sudo mal configurado, cron editable, PATH, capabilities, kernel, auditd, find -perm -4000, T1548, T1053.003"),
        ("privesc_win", "Escalada de privilegios en Windows", "servicios con permisos débiles, rutas sin comillas, SeImpersonate, credenciales guardadas, 7045, 4688, Sysmon 10 a LSASS, T1543.003, T1134"),
        ("ad", "Ataques a Active Directory", "Kerberos y NTLM, Kerberoasting, AS-REP roasting, Pass-the-Hash, DCSync, Golden Ticket, 4769/4768/4624/4662, gMSA, Protected Users, krbtgt"))]
    out += [{"id": "sv_" + k, "grupo": "📐 SystemVerilog", "nombre": n, "clave": c} for k, n, c in (
        ("tipos", "Tipos, señales y vectores", "logic vs wire/reg, 4 estados (0 1 x z), bit/byte/int/logic, vectores [n-1:0], packed vs unpacked, literales 8'hFF, signed/unsigned"),
        ("combinacional", "Lógica combinacional", "always_comb, assign, operadores lógicos/aritméticos/relacionales, if/else, case/casez, prioridad vs paralelo, latches no intencionales"),
        ("secuencial", "Lógica secuencial", "always_ff @(posedge clk), flip-flop D, asignación no bloqueante <= vs bloqueante =, reset síncrono vs asíncrono, registros y contadores"),
        ("fsm", "Máquinas de estado (FSM)", "Moore vs Mealy, enum typedef de estados, registro de estado y lógica de siguiente estado, codificación binaria/one-hot, valores por defecto"),
        ("jerarquia", "Módulos, parámetros e interfaces", "module/endmodule, puertos input/output/inout, parameter y localparam, instanciación por nombre, generate, interface y modport"),
        ("paquetes", "Tareas, funciones y paquetes", "function automatic, task, package/import, typedef, struct/union packed, enum, const, ámbito y reutilización"),
        ("testbench", "Testbenches y estímulos", "initial, timescale/timeunit, generación de reloj, $display/$monitor/$finish, fork/join, retardos #, estímulos y chequeos esperados"),
        ("oop", "Clases y aleatorización (verificación)", "class/objeto solo-simulación, herencia, rand/randc, constraint, randomize(), mailbox y semáforo, transacciones, por qué no es sintetizable"),
        ("cobertura", "Cobertura funcional", "covergroup, coverpoint, bins, cross, cobertura de código vs funcional, cuándo el test es suficiente"),
        ("sva", "Aserciones (SVA)", "immediate vs concurrent, property, sequence, |-> y |=>, $rose/$fell/$past, assert/assume/cover, por qué atrapan bugs"),
        ("verilator", "Simulación con Verilator", "verilator --binary, --lint-only, SV a C++, testbench en C++/SystemC, trazas VCD/FST, formas de onda, advertencias WIDTH/UNOPTFLAT"))]
    for cid, c in academia.CURSOS.items():
        for n, nivel in enumerate(c["niveles"]):
            out.append({"id": f"ac_{cid}_{n}", "grupo": f"{c['icono']} {c['nombre']}", "nombre": f"{nivel['nombre']} ({nivel['cap']})",
                        "clave": "; ".join(m["titulo"].replace("JEFE: ", "") for m in nivel["misiones"])})
    out += [{"id": "ws_filtros", "grupo": "Wireshark (WCA-101)", "nombre": "Filtros de captura y de visualización",
             "clave": "sintaxis BPF vs display filters, operadores, campos, contains, matches, botones de filtro"},
            {"id": "ws_estadisticas", "grupo": "Wireshark (WCA-101)", "nombre": "Estadísticas y Expert Info",
             "clave": "Protocol Hierarchy, Conversations, Endpoints, IO Graph, Expert Information, Follow Stream"}]
    return out


def _materia_de(tid: str) -> str:
    """Elige el 'profesor' correcto para la lección según el mundo del tema."""
    if tid.startswith("ws_"):
        return "wireshark"
    if tid.startswith("lx_"):
        return "linux"
    if tid.startswith("soc_"):
        return "soc"
    if tid.startswith("idx_"):
        return "purple"
    if tid.startswith("sv_"):
        return "sv"
    if tid.startswith("ac_"):
        cur = tid.split("_")[1] if "_" in tid[3:] else tid[3:]
        return {"rust": "rust", "rustproj": "rust", "ia": "ia", "torch": "ia",
                "cpu": "cpu", "chisel": "chisel"}.get(cur, "redes")
    return "redes"


def t_generar_leccion(progreso, body):
    t = next((x for x in temas_teoria() if x["id"] == body.get("tema")), None)
    enfoque = (body.get("enfoque") or "").strip()[:300]
    if not t and not enfoque:
        raise ValueError("Elige un tema o escribe de qué quieres la lección.")
    idioma = "en" if body.get("idioma") == "en" else "es"
    # lección libre (sin tema) pedida desde un mundo: el profesor y las guías son de ese mundo, no de CCNA
    mundo_libre = str(body.get("mundo") or "")
    materia = _materia_de(t["id"]) if t else {"linux": "linux", "wireshark": "wireshark", "rust": "rust", "rustproj": "rust",
                                               "ia": "ia", "torch": "ia", "cpu": "cpu", "chisel": "chisel", "soc": "soc", "sv": "sv", "purple": "purple"}.get(mundo_libre, "redes")
    m, keep = modelo("pesado")
    with _keep(keep):
        l = gen.generar_leccion(m, t["nombre"] if t else enfoque, t["clave"] if t else "", idioma,
                                enfoque if t else "", progreso, materia=materia)
    if ws.tshark():  # los filtros de Wireshark que proponga la lección se comprueban con tshark
        buenos = []
        for c in l["comandos"]:
            if _parece_filtro(c["comando"]) and _filtro_valido(c["comando"]) is not True:
                continue
            buenos.append(c)
        l["comandos"] = buenos
    l.update(tema=t["id"] if t else (f"libre_{mundo_libre}" if mundo_libre else "libre"), idioma=idioma, modelo=m)
    return {"id": db.guardar_leccion(l)}


_ARRANQUE = str(int(time.time()))


def version_web() -> str:
    """Cambia cuando reinicias NetLab o cambia un archivo de la interfaz: la ventana abierta lo ve y se recarga sola."""
    try:
        m = max(os.path.getmtime(os.path.join(WEB, f)) for f in os.listdir(WEB) if f.endswith((".js", ".css", ".html")))
    except (OSError, ValueError):
        m = 0
    return f"{_ARRANQUE}-{int(m)}"


def _filtrar_comandos_ws(l: dict) -> None:
    if ws.tshark():  # los filtros de Wireshark que proponga la lección se comprueban con tshark
        l["comandos"] = [c for c in l["comandos"] if not (_parece_filtro(c["comando"]) and _filtro_valido(c["comando"]) is not True)]


def t_actualizar_lecciones(progreso, body):
    """Regenera en el formato nuevo (v2) todas las lecciones viejas, conservando id, fecha y la marca de leída.
    Las repetidas (mismo tema e idioma) se generan una sola vez; si ya existe una v2 de ese tema, se reutiliza."""
    temas = {t["id"]: t for t in temas_teoria()}
    forzar = {int(x) for x in (body.get("ids") or [])}  # regenerar estas aunque ya estén en el formato nuevo
    filas = db.lecciones()
    nuevas = {(f["tema"], f["idioma"]): f["id"] for f in filas
              if f["version"] == 2 and f["id"] not in forzar and not str(f["tema"]).startswith("libre")}
    grupos: dict = {}
    for f in filas:
        if f["version"] == 2 and f["id"] not in forzar:
            continue
        libre = str(f["tema"]).startswith("libre") or f["tema"] not in temas
        grupos.setdefault((f["tema"], f["idioma"], f["titulo"] if libre else ""), []).append(f)
    if not grupos:
        return {"actualizadas": 0, "errores": []}
    m, keep = modelo("pesado")
    hechas, errores, n = 0, [], len(grupos)
    with _keep(keep):
        for i, ((tema, idioma, titulo_libre), fs) in enumerate(grupos.items(), 1):
            t = temas.get(tema)
            nombre = t["nombre"] if t else (titulo_libre or fs[0]["titulo"])
            try:
                if (tema, idioma) in nuevas:
                    progreso(f"[{i}/{n}] {nombre}: ya hay una versión nueva, la reutilizo…")
                    l = db.leccion(nuevas[(tema, idioma)])
                else:
                    mundo = tema[6:] if str(tema).startswith("libre_") else ""
                    materia = _materia_de(tema) if t else {"linux": "linux", "wireshark": "wireshark", "rust": "rust", "rustproj": "rust",
                                                          "ia": "ia", "torch": "ia", "cpu": "cpu", "chisel": "chisel", "soc": "soc",
                                                          "sv": "sv", "purple": "purple"}.get(mundo, "redes")
                    l = gen.generar_leccion(m, nombre, t["clave"] if t else "", idioma, "" if t else nombre,
                                            lambda msg, i=i: progreso(f"[{i}/{n}] {nombre} · {msg}"), materia=materia)
                    _filtrar_comandos_ws(l)
                    l["modelo"] = m
                for f in fs:
                    db.actualizar_leccion(f["id"], {**l, "tema": tema, "idioma": idioma})
                    hechas += 1
            except ollama.OllamaError:
                raise
            except Exception as e:  # noqa: BLE001  (una lección que falla no detiene las demás)
                errores.append(f"{nombre}: {e}")
    progreso(f"Listo: {hechas} lecciones actualizadas.")
    return {"actualizadas": hechas, "errores": errores}


def t_traducir_leccion(progreso, body):
    """Traduce una lección ya hecha (sin volver a generarla) y la guarda como lección nueva en el otro idioma."""
    l = db.leccion(int(body.get("id", 0)))
    if not l:
        raise ValueError("No encontré esa lección.")
    destino = "en" if body.get("idioma", "en") == "en" else "es"
    if l.get("version") == 2:  # lección nueva (mini-curso): se traduce por partes
        m, keep = modelo("pesado")
        with _keep(keep):
            r = gen.traducir_leccion_v2(m, l, destino, progreso)
        nueva = {**l, **r, "idioma": destino, "traducida_de": l.get("id")}
        nueva.pop("id", None)
        nueva.pop("leida", None)
        return {"id": db.guardar_leccion(nueva)}
    campos = {k: l.get(k) for k in ("titulo", "intro", "secciones", "comandos", "puntos_clave", "errores_comunes")}
    m, keep = modelo("pesado")
    progreso("Traduciendo la lección…")
    with _keep(keep):
        r = ollama.chat_json(m, [
            {"role": "system", "content": f"Translate this lesson to {'natural US English' if destino == 'en' else 'Mexican Spanish'}. "
             "Keep commands, code, filters, field names and numbers EXACTLY as they are (do not translate the 'comando' values). "
             "Return the same JSON structure."},
            {"role": "user", "content": json.dumps(campos, ensure_ascii=False)}],
            gen.ESQUEMA_LECCION, temperature=0.1, num_ctx=16384, num_predict=8000, idioma_fijo=True)
    for k in campos:
        if not r.get(k):
            r[k] = campos[k]
    nueva = {**l, **r, "idioma": destino, "traducida_de": l.get("id")}
    nueva.pop("id", None)
    nueva.pop("leida", None)
    return {"id": db.guardar_leccion(nueva)}


def t_duda_leccion(progreso, body):
    l = db.leccion(int(body.get("id", 0)))
    if not l:
        raise ValueError("No encontré esa lección.")
    pregunta = (body.get("pregunta") or "").strip()[:600]
    if not pregunta:
        raise ValueError("Escribe (o di) tu pregunta.")
    m, keep = modelo("pesado" if CONFIG.get("explicar_con_pesado") else "ligero")
    progreso("Pensando la respuesta…" if l["idioma"] == "es" else "Thinking…")
    with _keep(keep):
        return {"respuesta": gen.responder_duda(m, l, pregunta, l["idioma"])}


_BASE_CISCO = "https://www.cisco.com/c/en/us/td/docs"
GUIAS_CISCO = [  # guías oficiales de configuración (gratis en cisco.com)
    ("Cisco-2960-Switch-Config-Guide-15.0.pdf", "/switches/lan/catalyst2960/software/release/15-0_2_se/configuration/guide/scg2960.pdf"),
    ("Cisco-OSPF-Config-Guide-15MT.pdf", "/ios-xml/ios/iproute_ospf/configuration/15-mt/iro-15-mt-book.pdf"),
    ("Cisco-EIGRP-Config-Guide-15MT.pdf", "/ios-xml/ios/iproute_eigrp/configuration/15-mt/ire-15-mt-book.pdf"),
    ("Cisco-Rutas-Estaticas-PBR-15MT.pdf", "/ios-xml/ios/iproute_pi/configuration/15-mt/iri-15-mt-book.pdf"),
    ("Cisco-NAT-Config-Guide-15MT.pdf", "/ios-xml/ios/ipaddr_nat/configuration/15-mt/nat-15-mt-book.pdf"),
    ("Cisco-DHCP-Config-Guide-15MT.pdf", "/ios-xml/ios/ipaddr_dhcp/configuration/15-mt/dhcp-15-mt-book.pdf"),
    ("Cisco-ACL-Config-Guide-15MT.pdf", "/ios-xml/ios/sec_data_acl/configuration/15-mt/sec-data-acl-15-mt-book.pdf"),
    ("Cisco-FHRP-HSRP-Config-Guide-15MT.pdf", "/ios-xml/ios/ipapp_fhrp/configuration/15-mt/fhp-15-mt-book.pdf"),
    ("Cisco-SSH-Config-Guide-15MT.pdf", "/ios-xml/ios/sec_usr_ssh/configuration/15-mt/sec-usr-ssh-15-mt-book.pdf"),
    ("Cisco-IPv6-Basico-Config-Guide-15MT.pdf", "/ios-xml/ios/ipv6_basic/configuration/15-mt/ip6b-15-mt-book.pdf"),
]


GUIAS_EXTRA = [  # libros libres
    ("Linux-The-Linux-Command-Line-TLCL.pdf",
     "https://sourceforge.net/projects/linuxcommand/files/TLCL/25.12/TLCL-25.12A.pdf/download"),  # CC BY-NC-ND, linuxcommand.org
]


PAQUETES = {  # material libre y oficial, por paquete
    "soc": [
        ("MITRE-ATTACK-Enterprise.md", "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json", "attack"),
        ("NIST-SP-800-61r3-Respuesta-a-incidentes.pdf", "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf", "pdf"),
    ],
    "linux_ws": [
        ("Linux-Bash-Reference-Manual.pdf", "https://www.gnu.org/software/bash/manual/bash.pdf", "pdf"),
        *[(n, "https://wiki.wireshark.org/uploads/" + r, "pcap") for n, r in (
            ("http.cap", "27707187aeb30df68e70c8fb9d614981/http.cap"),
            ("dns.cap", "__moin_import__/attachments/SampleCaptures/dns.cap"),
            ("telnet-cooked.pcap", "__moin_import__/attachments/SampleCaptures/telnet-cooked.pcap"),
            ("FTPv6-1.cap", "__moin_import__/attachments/SampleCaptures/FTPv6-1.cap"),
            ("dhcp.pcap", "__moin_import__/attachments/SampleCaptures/dhcp.pcap"),
            ("arp-storm.pcap", "__moin_import__/attachments/SampleCaptures/arp-storm.pcap"),
            ("ipv4frags.pcap", "__moin_import__/attachments/SampleCaptures/ipv4frags.pcap"),
            ("ospf.cap", "__moin_import__/attachments/SampleCaptures/ospf.cap"),
            ("cdp.pcap", "__moin_import__/attachments/SampleCaptures/cdp.pcap"))],
    ],
    "rust_ia": [
        ("Rust-The-Rust-Programming-Language.md", "https://github.com/rust-lang/book/archive/refs/heads/main.zip", "zip_md"),
        ("Rust-By-Example.md", "https://github.com/rust-lang/rust-by-example/archive/refs/heads/master.zip", "zip_md"),
        ("IA-Dive-into-Deep-Learning.pdf", "https://d2l.ai/d2l-en.pdf", "pdf"),
        ("IA-Mathematics-for-Machine-Learning.pdf", "https://mml-book.github.io/book/mml-book.pdf", "pdf"),
        ("RISC-V", "riscv/riscv-isa-manual", "gh_release_pdf"),
    ],
    "rustlings": [  # los ejercicios oficiales de Rust (licencia MIT)
        ("rustlings.json", "https://github.com/rust-lang/rustlings/archive/refs/heads/main.zip", "rustlings"),
    ],
    "vm_ubuntu": [  # máquina Linux real para VirtualBox (imagen oficial de Canonical)
        ("ubuntu-24.04-server-cloudimg-amd64.ova",
         "https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.ova", "ova"),
    ],
    "cert_extra": [  # lo que faltaba para llegar a nivel de certificación
        *[(f"RFC-{n}-{t}.txt", f"https://www.rfc-editor.org/rfc/rfc{n}.txt", "txt") for n, t in (
            ("9293", "TCP"), ("791", "IPv4"), ("792", "ICMP"), ("768", "UDP"), ("826", "ARP"), ("2131", "DHCP"),
            ("1035", "DNS"), ("8446", "TLS-1.3"), ("9110", "HTTP"), ("8200", "IPv6"), ("4861", "IPv6-NDP"))],
        ("Cisco-Programmability-IOS-XE-17.15.pdf",
         "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1715/b_1715_programmability_cg.pdf", "pdf"),
        ("Rust-Comprehensive-Rust-Google.md", "https://github.com/google/comprehensive-rust/archive/refs/heads/main.zip", "zip_md"),
        ("Rust-Rustonomicon.md", "https://github.com/rust-lang/nomicon/archive/refs/heads/master.zip", "zip_md"),
        ("Rust-Reference.md", "https://github.com/rust-lang/reference/archive/refs/heads/master.zip", "zip_md"),
        ("IA-Understanding-Deep-Learning", "udlbook/udlbook", "gh_release_pdf"),
        ("CPU-Digital-Design-with-Chisel.pdf", "https://www.imm.dtu.dk/~masca/chisel-book.pdf", "pdf"),
    ],
}
CAPTURAS_EJEMPLO = os.path.join(AQUI, "capturas_ejemplo")
VMS = os.path.join(AQUI, "vms")
SIEM_IMPORTAR = os.path.join(AQUI, "siem_importar")  # pon aquí .pcap / .log / .json / .csv reales para cargarlos al SIEM
vm.configurar(VMS, PUERTO)
VM_PARTIDA: dict = {}  # misión real en curso (sus variables solo viven en memoria)


def t_vm_crear(progreso, body):
    vm.crear(progreso)
    return vm.estado()


def t_vm_encender(progreso, body):
    vm.encender(progreso)
    return vm.estado()


def t_vm_reiniciar(progreso, body):
    vm.reiniciar(progreso)
    VM_PARTIDA.clear()
    return vm.estado()


def t_vm_siem(progreso, body):
    vm.preparar_siem(progreso)
    return {**vm.estado(), "siem": vm.siem_instalado()}


# ── 🐳 Laboratorio Docker + Claude Code local (dentro de la VM, aislado) ──────────────────────────────────────────
# Solo acciones FIJAS (no hay endpoint de comandos libres). Imágenes oficiales; DVWA/Juice Shop solo llegan al
# localhost de Windows (reenvío NAT 127.0.0.1:4280 y :4300). Claude Code usa el Ollama de Windows por 10.0.2.2.
LAB_COMPOSE = """name: lab
services:
  dvwa:
    image: ghcr.io/digininja/dvwa:latest
    depends_on: [db]
    environment:
      DB_SERVER: db
    ports: ["4280:80"]
    networks: [web, datos]
  db:
    image: docker.io/library/mariadb:10
    environment:
      MYSQL_ROOT_PASSWORD: dvwa
      MYSQL_DATABASE: dvwa
      MYSQL_USER: dvwa
      MYSQL_PASSWORD: p@ssw0rd
    networks: [datos]
  juice:
    image: docker.io/bkimminich/juice-shop:latest
    ports: ["3000:3000"]
    networks: [web]
  webgoat:
    image: docker.io/webgoat/webgoat:latest
    environment:
      TZ: America/Mexico_City
    ports: ["8080:8080"]
    networks: [web]
networks:
  web: {}
  datos:
    internal: true
"""

LAB_CLAUDE_MD = """# Reglas del laboratorio (NetLab)
- Este laboratorio es SOLO para practicar auditoria y validar defensas contra los contenedores de este compose.
- Objetivos permitidos: dvwa (http://127.0.0.1:4280), juice (http://127.0.0.1:3000) y webgoat (http://127.0.0.1:4290/WebGoat). Nada fuera de esta VM.
- Solo imagenes oficiales: ghcr.io/digininja/dvwa, mariadb oficial, bkimminich/juice-shop y webgoat/webgoat. Nada de copias de terceros.
- No publicar puertos nuevos ni cambiar la red de la VM. La base de datos vive en una red interna sin internet.
- Antes de instalar o descargar algo: decir fuente y tamano y pedir confirmacion.
- Logs para el lado defensivo: `docker compose logs dvwa` / `docker compose logs juice`.
- Al terminar la sesion: `docker compose down -v` (no dejar volumenes ni basura).
"""

LAB_LANZADOR = """#!/bin/bash
# Claude Code con el modelo LOCAL de Ollama (Windows). Solo afecta a esta terminal.
export ANTHROPIC_BASE_URL=http://10.0.2.2:11434
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
# el modelo local tiene 112K de contexto (Modelfile); Claude Code no acepta menos de 100K
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000
MODELO="${1:-qwen3-coder-lab}"
cd ~/lab && exec ~/.local/bin/claude --model "$MODELO"
"""

LAB_INSTALAR = r"""set -e
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  echo "== Docker Engine (repositorio oficial download.docker.com)"
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl >/dev/null
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
fi
systemctl enable --now docker >/dev/null 2>&1
usermod -aG docker alumno
if [ ! -x /home/alumno/.local/bin/claude ]; then
  echo "== Claude Code (instalador oficial claude.ai/install.sh)"
  sudo -u alumno -H bash -lc 'curl -fsSL https://claude.ai/install.sh | bash' >/dev/null
fi
install -d -o alumno -g alumno /home/alumno/lab
cat > /home/alumno/lab/docker-compose.yml <<'NLEOF'
@@COMPOSE@@NLEOF
cat > /home/alumno/lab/CLAUDE.md <<'NLEOF'
@@CLAUDEMD@@NLEOF
cat > /home/alumno/lab/claude-lab.sh <<'NLEOF'
@@LANZADOR@@NLEOF
chmod +x /home/alumno/lab/claude-lab.sh
chown -R alumno:alumno /home/alumno/lab
echo "== Verificacion"
echo "ollama_desde_vm=$(curl -s -m 5 http://10.0.2.2:11434/api/version || echo NO)"
docker --version
docker compose version
sudo -u alumno -H /home/alumno/.local/bin/claude --version
"""

LAB_LEVANTAR = r"""set -e
cd /home/alumno/lab
sudo -u alumno -H docker compose up -d --quiet-pull 2>&1 | tail -5
for i in $(seq 1 60); do
  a=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4280/login.php || true)
  b=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ || true)
  [ "$a" = 200 ] && [ "$b" = 200 ] && break
  sleep 3
done
w=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4290/WebGoat/login || true)
echo "dvwa=$a juice=$b webgoat=$w"
sudo -u alumno -H docker compose ps --format '{{.Service}} {{.State}}'
"""

LAB_ESTADO = r"""cd /home/alumno/lab 2>/dev/null || { echo "sin_lab"; exit 0; }
sudo -u alumno -H docker compose ps --format '{{.Service}} {{.State}}' 2>&1
echo "dvwa=$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:4280/login.php || true) juice=$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:3000/ || true) webgoat=$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:4290/WebGoat/login || true)"
"""

LAB_LOGS = r"""cd /home/alumno/lab && sudo -u alumno -H docker compose logs --no-color dvwa juice webgoat 2>/dev/null | tail -n 20000"""

LAB_APAGAR = r"""cd /home/alumno/lab 2>/dev/null && sudo -u alumno -H docker compose down -v 2>&1 | tail -3; echo apagado"""

LAB_PROBAR_IA = r"""cd /home/alumno/lab
sudo -u alumno -H bash -lc 'cd ~/lab && ANTHROPIC_BASE_URL=http://10.0.2.2:11434 ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY= CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000 timeout 540 ~/.local/bin/claude -p "Lee CLAUDE.md y responde en una sola linea: cuales son los dos objetivos permitidos." --model @@MODELO@@ 2>&1 | tail -5'
"""


# 🧠 Análisis DEFENSIVO de los logs del laboratorio con tu bibliografía (RAG: OWASP/NIST/MITRE de la carpeta guias).
_SOSPECHA = re.compile(r"(union|select|sleep\(|benchmark|%27|'|--|<script|%3c|onerror|\.\./|%2e%2e|etc/passwd|win\.ini|"
                       r"cmd=|exec|;|%3b|\|\||%7c|wget|curl|/api/|/rest/|admin|login|169\.254|file:|<!entity|ftp/|\.env|\.git)", re.I)
_LINEA_HTTP = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3}).*?"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) ([^ "]+)[^"]*" (\d{3})')
ESQUEMA_ANALISIS = {"type": "object", "properties": {
    "resumen": {"type": "string"},
    "hallazgos": {"type": "array", "items": {"type": "object", "properties": {
        "que": {"type": "string"},
        "evidencia": {"type": "string"},
        "owasp": {"type": "string"},
        "attack": {"type": "string"},
        "wstg": {"type": "string"},
        "severidad": {"type": "string"},
        "como_funciona": {"type": "string"},
        "pasos": {"type": "array", "items": {"type": "object", "properties": {
            "peticion": {"type": "string"}, "porque": {"type": "string"}},
            "required": ["peticion", "porque"]}},
        "deteccion": {"type": "array", "items": {"type": "string"}},
        "mitigacion": {"type": "array", "items": {"type": "string"}}},
        "required": ["que", "evidencia", "owasp", "attack", "severidad", "como_funciona", "pasos", "deteccion", "mitigacion"]}},
    "fuentes": {"type": "array", "items": {"type": "string"}}},
    "required": ["resumen", "hallazgos", "fuentes"]}


def _resumen_logs(lineas: list[str]) -> tuple[str, str]:
    """Reduce los logs a lo que importa para que quepan en el modelo: conteos por IP/estado/ruta y las líneas sospechosas."""
    from collections import Counter
    ips, estados, rutas, sosp = Counter(), Counter(), Counter(), []
    for l in lineas:
        m = _LINEA_HTTP.search(l)
        if m:
            ips[m.group(1)] += 1
            estados[m.group(4)] += 1
            rutas[m.group(3).split("?")[0][:80]] += 1
        if _SOSPECHA.search(l):
            sosp.append(l[:300])
    stats = (f"Líneas: {len(lineas)} · peticiones HTTP: {sum(ips.values())}\n"
             f"IPs: {ips.most_common(6)}\nEstados: {estados.most_common(8)}\nRutas más pedidas: {rutas.most_common(12)}")
    muestra = sosp[-120:] if sosp else lineas[-60:]
    return stats, "\n".join(muestra)[:9000]


def _leer_logs_lab() -> list[str]:
    """Logs del laboratorio (de la VM si está arriba; si no, lo último mandado al SIEM). Lanza si no hay nada."""
    lineas = []
    try:
        code, out = vm.ssh(LAB_LOGS, timeout=120)
        if code == 0:
            lineas = [l for l in out.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        pass
    if not lineas:
        ruta = os.path.join(SIEM_IMPORTAR, "lab_web.log")
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8", errors="replace") as f:
                lineas = [l.rstrip("\n") for l in f if l.strip()]
    if not lineas:
        raise RuntimeError("No hay logs del laboratorio todavía: levántalo y úsalo primero.")
    return lineas


def analizar_logs_lab(progreso) -> dict:
    progreso("Sacando los logs del laboratorio…")
    lineas = _leer_logs_lab()
    stats, muestra = _resumen_logs(lineas)
    progreso("Buscando en tus guías (OWASP, NIST, MITRE)…")
    consulta = "detección en logs web y mitigación: " + " ".join(sorted({w.lower() for w in _SOSPECHA.findall(muestra)})[:20])
    refs = _referencias(consulta, mundo="purple")
    m, keep = modelo("seguridad")
    progreso(f"Analizando con {m}…")
    sistema = ("Eres analista senior de un SOC y profesor de seguridad web. Analizas a PROFUNDIDAD los logs de un laboratorio "
               "LOCAL de práctica del propio alumno (DVWA y OWASP Juice Shop, aplicaciones hechas vulnerables a propósito y que "
               "él controla) para que entienda cada vulnerabilidad de verdad, estilo clase magistral. Para CADA hallazgo da: "
               "'que' (una línea), 'evidencia' (las líneas EXACTAS del log, cópialas tal cual), 'owasp' (categoría OWASP "
               "Top 10:2025 o API Security Top 10 con su código, p. ej. A03:2025 o API1:2023), 'attack' (técnica MITRE ATT&CK), "
               "'wstg' (el identificador de la prueba de OWASP WSTG si aplica, p. ej. WSTG-INPV-05), 'severidad' "
               "(alta/media/baja), 'como_funciona' (2-4 frases explicando el MECANISMO: por qué la aplicación es vulnerable y "
               "qué provoca el ataque por dentro), 'pasos' (la secuencia del ataque TAL COMO SE VE EN ESTE LOG: por cada petición "
               "relevante, 'peticion' = la petición o payload del log y 'porque' = qué logra ese paso y por qué funciona; es "
               "reconstrucción didáctica de lo ya ocurrido en el laboratorio del alumno, basada en OWASP WSTG), 'deteccion' "
               "(qué buscar en logs/SIEM para cazarlo) y 'mitigacion' (cómo corregir el código/config, con la defensa de la "
               "Cheat Sheet de OWASP). Explica con la profundidad del material de OWASP. NO inventes payloads que no estén en el "
               "log ni generalices a 'cómo atacar cualquier sitio': cíñete a lo que muestran ESTOS logs. Si no hay actividad "
               "sospechosa, dilo y deja 'hallazgos' vacío. En 'fuentes' pon SOLO nombres de archivo de los fragmentos de "
               "referencia que de verdad usaste.")
    usuario = (f"ESTADÍSTICAS\n{stats}\n\nLÍNEAS RELEVANTES\n{muestra}\n\n"
               + (f"FRAGMENTOS DE REFERENCIA (bibliografía del alumno)\n{refs}" if refs else "Sin fragmentos de referencia."))
    with _keep(keep):
        r = ollama.chat_json(m, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                             ESQUEMA_ANALISIS, temperature=0.2, num_ctx=16384, num_predict=6000)
    validas = set(re.findall(r"\[([^,\]]+?\.(?:pdf|txt|md))[,\]]", refs or "", re.I))
    r["fuentes"] = [f for f in (r.get("fuentes") or []) if f in validas] or sorted(validas)[:4]
    return {"accion": "analizar", "lineas": len(lineas), "modelo": m, **r}

# ------------------------------------------------------------------ #
# Banco de CVEs reales (para la arena "la IA ataca en SIMULACIÓN, tú defiendes"). Cada uno es público y famoso, y la
# mayoría tiene su entorno en Vulhub, así que lo puedes practicar también DE VERDAD (clona Vulhub) con logs reales.
# ------------------------------------------------------------------ #
BANCO_CVE = [
    {"id": "log4shell", "cve": "CVE-2021-44228", "nombre": "Log4Shell", "producto": "Apache Log4j 2",
     "owasp": "A03:2021 Inyección", "cwe": "CWE-502 / CWE-917", "attack": "T1190", "vulhub": "log4j/CVE-2021-44228",
     "resumen": "Un dato controlado por el usuario que se escribe en un log con Log4j dispara una búsqueda JNDI y la carga de una clase remota (RCE). La huella típica es la cadena ${jndi:ldap://…} en cabeceras o parámetros."},
    {"id": "spring4shell", "cve": "CVE-2022-22965", "nombre": "Spring4Shell", "producto": "Spring Framework (JDK 9+)",
     "owasp": "A08:2021 Fallos de integridad", "cwe": "CWE-94", "attack": "T1190", "vulhub": "spring/CVE-2022-22965",
     "resumen": "Abuso del data binding de Spring para llegar a class.module.classLoader y escribir una webshell en el servidor (RCE). Se ve como peticiones con class.module.* en los parámetros."},
    {"id": "struts2_045", "cve": "CVE-2017-5638", "nombre": "Struts2 S2-045", "producto": "Apache Struts 2",
     "owasp": "A03:2021 Inyección", "cwe": "CWE-20", "attack": "T1190", "vulhub": "struts2/s2-045",
     "resumen": "Una expresión OGNL dentro de la cabecera Content-Type se evalúa en el servidor y ejecuta comandos (RCE). La huella es un Content-Type con %{(...)} y llamadas a procesos."},
    {"id": "shellshock", "cve": "CVE-2014-6271", "nombre": "Shellshock", "producto": "GNU Bash vía CGI",
     "owasp": "A03:2021 Inyección", "cwe": "CWE-78", "attack": "T1190", "vulhub": "bash/CVE-2014-6271",
     "resumen": "Bash ejecuta código puesto tras una definición de función en una variable de entorno; vía CGI, cabeceras como User-Agent se vuelven comandos. Huella: () { :; }; en las cabeceras del access.log."},
    {"id": "drupalgeddon2", "cve": "CVE-2018-7600", "nombre": "Drupalgeddon2", "producto": "Drupal 7/8",
     "owasp": "A03:2021 Inyección", "cwe": "CWE-20", "attack": "T1190", "vulhub": "drupal/CVE-2018-7600",
     "resumen": "El renderizado de formularios de Drupal evalúa propiedades que empiezan con # desde la entrada del usuario, lo que permite ejecutar comandos sin autenticación (RCE). Huella: parámetros con #post_render o mail[#...]."},
    {"id": "confluence_26134", "cve": "CVE-2022-26134", "nombre": "Confluence OGNL", "producto": "Atlassian Confluence",
     "owasp": "A03:2021 Inyección", "cwe": "CWE-917", "attack": "T1190", "vulhub": "confluence/CVE-2022-26134",
     "resumen": "Inyección OGNL en la URL (ruta) de Confluence que ejecuta comandos sin autenticación (RCE). Huella: rutas con ${...} y procesos hijos del servicio de Confluence."},
    {"id": "gitlab_22205", "cve": "CVE-2021-22205", "nombre": "GitLab ExifTool", "producto": "GitLab CE/EE",
     "owasp": "A06:2021 Componentes vulnerables", "cwe": "CWE-94", "attack": "T1190", "vulhub": "gitlab/CVE-2021-22205",
     "resumen": "Una imagen malformada subida a GitLab llega a ExifTool, que procesa metadatos DjVu y ejecuta comandos (RCE sin autenticar). Huella: subidas de imagen seguidas de procesos raros del usuario git."},
    {"id": "weblogic_10271", "cve": "CVE-2017-10271", "nombre": "WebLogic WLS-WSAT", "producto": "Oracle WebLogic",
     "owasp": "A08:2021 Fallos de integridad", "cwe": "CWE-611", "attack": "T1190", "vulhub": "weblogic/CVE-2017-10271",
     "resumen": "El endpoint WLS-WSAT deserializa XML sin validar y ejecuta comandos (RCE). Huella: POST a /wls-wsat/ con XML que contiene <java>…<void> y comandos del sistema."},
]
_BANCO_POR_ID = {c["id"]: c for c in BANCO_CVE}

ESQUEMA_SIM = {"type": "object", "properties": {
    "escenario": {"type": "string"},
    "fases": {"type": "array", "items": {"type": "object", "properties": {
        "fase": {"type": "string"}, "que_ocurre": {"type": "string"}, "huella": {"type": "string"}},
        "required": ["fase", "que_ocurre", "huella"]}},
    "logs_sinteticos": {"type": "array", "items": {"type": "string"}},
    "pistas_deteccion": {"type": "array", "items": {"type": "string"}},
    "mitigacion": {"type": "array", "items": {"type": "string"}},
    "fuentes": {"type": "array", "items": {"type": "string"}}},
    "required": ["escenario", "fases", "logs_sinteticos", "pistas_deteccion", "mitigacion"]}

_ULTIMA_SIM: dict = {}  # app local de un solo usuario: guarda la última simulación para calificar la caza después


def simular_ataque(progreso, body) -> dict:
    """🤖 La IA ataca en SIMULACIÓN: a partir de un CVE público y conocido reconstruye el ataque a nivel conceptual y
    GENERA LOGS SINTÉTICOS (inventados, con formato realista) para que el alumno practique cazarlo. No entrega un exploit
    ejecutable ni pasos operativos para atacar un sistema real: es un ejercicio de DETECCIÓN para el equipo azul."""
    cid = re.sub(r"[^a-z0-9_]", "", str(body.get("cve", "")))[:24]
    c = _BANCO_POR_ID.get(cid)
    if not c:
        raise ValueError("CVE no válido.")
    progreso(f"Preparando el ejercicio de {c['nombre']} ({c['cve']})…")
    progreso("Buscando en tus guías (OWASP, NIST, MITRE)…")
    refs = _referencias(f"{c['producto']} {c['owasp']} detección en logs y mitigación de {c['nombre']}", mundo="purple")
    m, keep = modelo("seguridad")
    progreso(f"Montando el ataque simulado con {m}…")
    sistema = ("Eres instructor de ciberseguridad y, SOLO con fin didáctico de DEFENSA, montas un ejercicio de equipo rojo "
               "SIMULADO sobre un CVE PÚBLICO y muy conocido para que un analista aprenda a CAZARLO. "
               "REGLAS ESTRICTAS: NO entregues un exploit funcional, ni payloads listos para pegar y usar contra un sistema "
               "real, ni pasos operativos de explotación. Describe las 'fases' a nivel CONCEPTUAL (qué ocurre y por qué, en la "
               "Kill Chain) y GENERA 'logs_sinteticos': líneas de log INVENTADAS pero con formato realista (access.log, auth.log, "
               "Sysmon…) como las que dejaría ese ataque, incluyendo el INDICADOR público que un SIEM buscaría (esa firma es "
               "material defensivo conocido). En 'pistas_deteccion' di qué buscar en los logs/SIEM y en 'mitigacion' cómo "
               "corregir (parche, config, WAF). En 'fuentes' pon SOLO nombres de archivo de los fragmentos de referencia que "
               "de verdad usaste. Responde en español. Recuerda: el objetivo es que el alumno DETECTE, no que ataque.")
    usuario = (f"CVE: {c['cve']} — {c['nombre']} ({c['producto']})\nOWASP: {c['owasp']} · CWE: {c['cwe']} · ATT&CK: {c['attack']}\n"
               f"Resumen público: {c['resumen']}\n\n"
               + (f"FRAGMENTOS DE REFERENCIA (bibliografía del alumno)\n{refs}" if refs else "Sin fragmentos de referencia.")
               + "\n\nMonta el ejercicio: escenario, fases (conceptuales), logs_sinteticos realistas, pistas_deteccion y mitigacion.")
    with _keep(keep):
        r = ollama.chat_json(m, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                             ESQUEMA_SIM, temperature=0.3, num_ctx=16384, num_predict=5000)
    validas = set(re.findall(r"\[([^,\]]+?\.(?:pdf|txt|md))[,\]]", refs or "", re.I))
    r["fuentes"] = [f for f in (r.get("fuentes") or []) if f in validas] or sorted(validas)[:4]
    logs = [str(x) for x in (r.get("logs_sinteticos") or []) if str(x).strip()]
    _ULTIMA_SIM.clear()
    _ULTIMA_SIM.update(cve=c["cve"], nombre=c["nombre"], producto=c["producto"], owasp=c["owasp"],
                       attack=c["attack"], resumen=c["resumen"], logs=logs)
    return {"accion": "simular", "cve": c["cve"], "nombre": c["nombre"], "producto": c["producto"],
            "owasp": c["owasp"], "cwe": c["cwe"], "attack": c["attack"], "vulhub": c.get("vulhub", ""),
            "modelo": m, **r}


def calificar_caza(progreso, body) -> dict:
    """🔵 Califica la CAZA del alumno sobre la última simulación: compara su respuesta con la verdad del CVE y con los logs
    sintéticos que se le mostraron. Reusa el esquema del reto morado (puntaje/nivel/mejoras). Solo lado defensivo."""
    if not _ULTIMA_SIM.get("logs"):
        raise RuntimeError("Primero genera un ataque simulado (botón «Generar ataque») y luego califico tu caza.")
    respuesta = str(body.get("respuesta", ""))[:1500].strip()
    s = _ULTIMA_SIM
    muestra = "\n".join(s["logs"][:40])
    progreso("Buscando en tus guías (OWASP, NIST, MITRE)…")
    refs = _referencias(f"detección en logs y mitigación de {s['nombre']} {s['owasp']}", mundo="purple")
    m, keep = modelo("seguridad")
    progreso(f"Calificando tu caza con {m}…")
    sistema = ("Eres el EQUIPO AZUL y evaluador. Al alumno se le mostraron estos LOGS SINTÉTICOS de un ataque SIMULADO y se le "
               "pidió cazarlo: decir qué ve y cómo lo detectaría y mitigaría. Tú SÍ sabes la verdad del ataque (te la doy). "
               "Califica SU respuesta: en 'ataques' confirma lo que de verdad se ve en los logs (con 'que', 'evidencia' = línea "
               "exacta, 'owasp', 'severidad'); en 'cobertura' di si con esos logs un SOC podría cazarlo y qué falta registrar; "
               "en 'reglas_siem' da búsquedas/reglas concretas; en 'evaluacion_respuesta' di qué acertó el alumno, qué se le "
               "pasó frente a la verdad y a OWASP; 'puntaje' 0-100 y 'nivel' (Novato/Analista/Senior) según la calidad de SU "
               "respuesta; 'mejoras' qué reforzar. NO des pasos ni payloads de ataque. En 'fuentes' pon SOLO nombres de archivo "
               "de los fragmentos que de verdad usaste. Responde en español.")
    usuario = (f"VERDAD DEL ATAQUE (no la reveles entera, úsala para evaluar): {s['cve']} — {s['nombre']} ({s['producto']}). "
               f"{s['resumen']} OWASP {s['owasp']}, ATT&CK {s['attack']}.\n\n"
               f"LOGS SINTÉTICOS QUE VIO EL ALUMNO\n{muestra}\n\n"
               f"RESPUESTA DEL ALUMNO (a calificar)\n{respuesta or '(no escribió nada)'}\n\n"
               + (f"FRAGMENTOS DE REFERENCIA\n{refs}" if refs else "Sin fragmentos de referencia."))
    with _keep(keep):
        r = ollama.chat_json(m, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                             ESQUEMA_RETO, temperature=0.2, num_ctx=16384, num_predict=5000)
    validas = set(re.findall(r"\[([^,\]]+?\.(?:pdf|txt|md))[,\]]", refs or "", re.I))
    r["fuentes"] = [f for f in (r.get("fuentes") or []) if f in validas] or sorted(validas)[:4]
    try:
        r["puntaje"] = max(0, min(100, int(r.get("puntaje", 0))))
    except Exception:  # noqa: BLE001
        r["puntaje"] = 0
    return {"accion": "calificar_caza", "cve": s["cve"], "lineas": len(s["logs"]), "modelo": m, **r}


ESQUEMA_RETO = {"type": "object", "properties": {
    "resumen": {"type": "string"},
    "ataques": {"type": "array", "items": {"type": "object", "properties": {
        "que": {"type": "string"}, "evidencia": {"type": "string"}, "owasp": {"type": "string"},
        "severidad": {"type": "string"}}, "required": ["que", "evidencia", "owasp", "severidad"]}},
    "cobertura": {"type": "string"},
    "reglas_siem": {"type": "array", "items": {"type": "string"}},
    "evaluacion_respuesta": {"type": "string"},
    "puntaje": {"type": "integer"},
    "nivel": {"type": "string"},
    "mejoras": {"type": "array", "items": {"type": "string"}},
    "fuentes": {"type": "array", "items": {"type": "string"}}},
    "required": ["resumen", "ataques", "cobertura", "reglas_siem", "puntaje", "nivel", "mejoras", "fuentes"]}


def calificar_defensa(progreso, body) -> dict:
    """🟣 Reto morado: el ALUMNO ataca su blanco legal; la IA hace de equipo azul, evalua la detectabilidad y, si el alumno
    escribio como lo detectaria/mitigaria, CALIFICA esa respuesta. Solo lado defensivo (no ataca nada)."""
    arena = re.sub(r"[^a-z]", "", str(body.get("arena", "")))[:16] or "lab"
    respuesta = str(body.get("respuesta", ""))[:1500].strip()
    progreso("Sacando los logs del laboratorio…")
    lineas = _leer_logs_lab()
    stats, muestra = _resumen_logs(lineas)
    progreso("Buscando en tus guías (OWASP, NIST, MITRE)…")
    consulta = "detección en logs web, reglas de SIEM y mitigación: " + " ".join(sorted({w.lower() for w in _SOSPECHA.findall(muestra)})[:20])
    refs = _referencias(consulta, mundo="purple")
    m, keep = modelo("seguridad")
    progreso(f"Calificando con {m}…")
    sistema = ("Eres el EQUIPO AZUL y evaluador de un ejercicio morado. El alumno acaba de ATACAR su propio laboratorio legal "
               "(DVWA / Juice Shop / WebGoat, apps vulnerables a proposito que el controla) y estos son los logs resultantes. "
               "Tu trabajo es SOLO defensivo: (1) 'resumen' de la sesion; (2) 'ataques' que se ven en el log, cada uno con 'que', "
               "'evidencia' (linea exacta), 'owasp' (codigo Top 10:2025 o API) y 'severidad'; (3) 'cobertura': si con estos logs un "
               "SOC podria detectar lo que paso y que falta registrar; (4) 'reglas_siem': reglas o busquedas concretas (ej. KQL/Lucene "
               "para Kibana, o condiciones tipo 'muchos 500 por IP + UNION SELECT') para cazar cada ataque; (5) 'puntaje' 0-100 y "
               "'nivel' (Novato/Analista/Senior) de la POSTURA DEFENSIVA; (6) 'mejoras': que reforzar. "
               "NO des pasos, payloads ni comandos para atacar ni para mejorar un ataque. Cinete a lo que muestran ESTOS logs. "
               "En 'fuentes' pon SOLO nombres de archivo de los fragmentos de referencia que de verdad usaste. Responde en espanol.")
    if respuesta:
        sistema += (" El alumno escribio como detectaria y mitigaria lo ocurrido; en 'evaluacion_respuesta' CALIFICA esa respuesta: "
                    "que acerto, que le falto frente a la verdad del log y a OWASP, y ajusta 'puntaje' segun la calidad de SU respuesta.")
    else:
        sistema += " El alumno no escribio respuesta; deja 'evaluacion_respuesta' vacio y puntua la detectabilidad de la sesion."
    usuario = (f"ESTADISTICAS\n{stats}\n\nLINEAS RELEVANTES\n{muestra}\n\n"
               + (f"RESPUESTA DEFENSIVA DEL ALUMNO (a calificar)\n{respuesta}\n\n" if respuesta else "")
               + (f"FRAGMENTOS DE REFERENCIA (bibliografia del alumno)\n{refs}" if refs else "Sin fragmentos de referencia."))
    with _keep(keep):
        r = ollama.chat_json(m, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                             ESQUEMA_RETO, temperature=0.2, num_ctx=16384, num_predict=5000)
    validas = set(re.findall(r"\[([^,\]]+?\.(?:pdf|txt|md))[,\]]", refs or "", re.I))
    r["fuentes"] = [f for f in (r.get("fuentes") or []) if f in validas] or sorted(validas)[:4]
    try:
        r["puntaje"] = max(0, min(100, int(r.get("puntaje", 0))))
    except Exception:  # noqa: BLE001
        r["puntaje"] = 0
    return {"accion": "calificar", "arena": arena, "lineas": len(lineas), "modelo": m, **r}


# Vulhub: repositorio oficial con entornos de CVEs reales (uno por carpeta). NetLab solo lo clona; cada CVE se corre
# a mano desde la terminal de la VM, porque cada entorno tiene sus propios puertos y pasos (ver su README).
LAB_VULHUB_INSTALAR = r"""set -e
if [ ! -d /home/alumno/vulhub/.git ]; then
  echo "== Clonando Vulhub (github.com/vulhub/vulhub, repo oficial)"
  sudo -u alumno -H git clone --depth 1 https://github.com/vulhub/vulhub.git /home/alumno/vulhub 2>&1 | tail -2
fi
n=$(find /home/alumno/vulhub -name docker-compose.yml 2>/dev/null | wc -l)
echo "entornos_disponibles=$n"
git -C /home/alumno/vulhub log -1 --format='commit=%h fecha=%ci' 2>/dev/null || true
"""


def t_vm_lab(progreso, body):
    accion = str(body.get("accion", ""))
    if accion not in ("instalar", "levantar", "apagar", "probar_ia", "hornear", "estado", "logs", "analizar",
                      "limpiar_discos", "recursos", "calificar", "vulhub", "banco", "simular", "calificar_caza"):
        raise ValueError("Acción no válida.")
    if accion == "banco":  # 📚 catálogo estático de CVEs (no toca la VM ni el modelo)
        return {"accion": accion, "cves": BANCO_CVE}
    if accion == "simular":  # 🤖 la IA ataca en simulación (solo modelo, sin VM)
        return simular_ataque(progreso, body)
    if accion == "calificar_caza":  # 🔵 califica la caza (solo modelo, sin VM)
        return calificar_caza(progreso, body)
    if accion == "limpiar_discos":  # 🧹 solo VirtualBox (VM apagada): no necesita SSH
        return {"accion": accion, **vm.limpiar_discos(progreso)}
    if accion == "recursos":  # 🧠 sube RAM/núcleos (apaga, modifyvm, rehornea): no necesita SSH previo
        return {"accion": accion, **vm.ampliar_recursos(progreso)}
    if not vm.corriendo():
        vm.encender(progreso)
    vm.esperar_ssh(progreso)
    if accion == "instalar":
        progreso("Instalando Docker oficial y Claude Code en la VM y creando ~/lab (2-5 min)…")
        script = (LAB_INSTALAR.replace("@@COMPOSE@@", LAB_COMPOSE).replace("@@CLAUDEMD@@", LAB_CLAUDE_MD)
                  .replace("@@LANZADOR@@", LAB_LANZADOR))
        vm.reenvios_lab_en_caliente()
        code, out = vm.ssh(script, timeout=900)
    elif accion == "levantar":
        progreso("Levantando DVWA y Juice Shop (la primera vez baja las imágenes oficiales)…")
        vm.reenvios_lab_en_caliente()
        code, out = vm.ssh(LAB_LEVANTAR, timeout=900)
    elif accion == "apagar":
        progreso("Apagando el laboratorio y borrando sus volúmenes…")
        code, out = vm.ssh(LAB_APAGAR, timeout=180)
    elif accion == "estado":
        code, out = vm.ssh(LAB_ESTADO, timeout=60)
        return {"accion": accion, "salida": out[-800:], "arriba": "dvwa=200" in out or "juice=200" in out}
    elif accion == "logs":
        # 📥 lado defensivo: los logs de DVWA/Juice Shop van a siem_importar/lab_web.log (se SOBRESCRIBE: no se acumula
        # basura) y se cargan al SIEM si Elasticsearch está arriba, para buscarte en Kibana (índice de importados).
        progreso("Sacando los logs de DVWA y Juice Shop de la VM…")
        code, out = vm.ssh(LAB_LOGS, timeout=120)
        if code != 0:
            raise RuntimeError(f"No pude leer los logs (código {code}): {out[-300:]}")
        lineas = [l for l in out.splitlines() if l.strip()]
        if not lineas:
            raise RuntimeError("El laboratorio no tiene logs todavía: levántalo y úsalo primero.")
        os.makedirs(SIEM_IMPORTAR, exist_ok=True)
        with open(os.path.join(SIEM_IMPORTAR, "lab_web.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n")
        res = {"accion": accion, "lineas": len(lineas), "archivo": "lab_web.log", "importado": False}
        try:
            progreso(f"Cargando {len(lineas)} líneas al SIEM…")
            r = siem.importar(SIEM_IMPORTAR, ["lab_web.log"], ws.tshark(), progreso)
            res.update(importado=True, reporte=r.get("reporte"), indice=r.get("indice"))
        except Exception as e:  # sin SIEM encendido: queda el archivo listo para importarlo después
            res["aviso"] = str(e)[:200]
        return res
    elif accion == "analizar":
        return analizar_logs_lab(progreso)
    elif accion == "calificar":
        return calificar_defensa(progreso, body)
    elif accion == "vulhub":
        progreso("Clonando Vulhub en la VM (repo oficial; la primera vez tarda)…")
        code, out = vm.ssh(LAB_VULHUB_INSTALAR, timeout=600)
        if code != 0:
            raise RuntimeError(f"No pude clonar Vulhub (código {code}): {out[-400:]}")
        import re as _re
        n = (_re.search(r"entornos_disponibles=(\d+)", out) or [None, "0"])[1]
        return {"accion": accion, "entornos": int(n), "salida": out[-600:]}
    elif accion == "hornear":
        # deja Docker + imágenes + ~/lab dentro de la instantánea 'limpio' (con el lab APAGADO, sin volúmenes)
        progreso("Bajando las imágenes del laboratorio para dejarlas guardadas…")
        code, out = vm.ssh("cd /home/alumno/lab && sudo -u alumno -H docker compose pull --quiet 2>&1 | tail -3; "
                           "sudo -u alumno -H docker compose down -v 2>&1 | tail -2; sync; docker images --format '{{.Repository}}:{{.Tag}}'",
                           timeout=900)
        if code != 0:
            raise RuntimeError(f"No pude preparar las imágenes (código {code}): {out[-400:]}")
        vm.hornear_limpio(progreso)
        return {"accion": accion, "salida": out[-800:]}
    else:
        modelo = re.sub(r"[^a-zA-Z0-9_.:\-]", "", str(body.get("modelo", "qwen3-coder-lab")))[:60] or "qwen3-coder-lab"
        progreso(f"Probando Claude Code con {modelo} (la primera carga del modelo tarda)…")
        code, out = vm.ssh(LAB_PROBAR_IA.replace("@@MODELO@@", modelo), timeout=600)
    if code != 0:
        raise RuntimeError(f"Falló '{accion}' (código {code}): {out[-600:]}")
    return {"accion": accion, "salida": out[-1500:]}


SIEM_PARTIDA: dict = {}  # escenario de detección en curso (su verdad solo vive en memoria del servidor)


def t_siem_mision(progreso, body):
    esc = re.sub(r"[^a-z_]", "", str(body.get("escenario", "")))[:20]
    progreso("Generando el incidente y cargándolo en Elasticsearch…")
    import random as _r
    d = siem.sembrar(esc, _r.randrange(1 << 30))
    SIEM_PARTIDA.clear()
    SIEM_PARTIDA.update({"id": esc, "verdad": d["verdad"], "preguntas": d["preguntas"], "pistas": d["pistas"]})
    return {k: d[k] for k in ("id", "titulo", "info", "preguntas", "n")}


def t_vm_autoprueba(progreso, body):
    """Diagnóstico: cada misión con su solución debe pasar, y sin hacer nada debe fallar. Al final deja la VM limpia."""
    import random as _r
    vm.encender(progreso)
    rep = []
    ids = body.get("ids") or [m["id"] for m in vm_misiones.MISIONES]
    for mid in ids:
        progreso(f"Probando misión {mid}…")
        m = vm_misiones.preparar(mid, _r.randrange(1 << 30))
        c0, o0 = vm.ssh(m["setup"], timeout=240)
        sin, _ = vm.ssh(m["check"], timeout=90)
        cs, os_ = vm.ssh(m["solucion"].replace("~/", "/home/alumno/"), timeout=180, root=False)
        con, oc = vm.ssh(m["check"], timeout=90)
        rep.append({"id": mid, "setup": c0, "sin_hacer_falla": sin != 0, "con_solucion_pasa": con == 0,
                    "salida": (oc if con else "")[-300:], "sol": os_[-300:] if cs else "", "setup_out": o0[-200:] if c0 else ""})
    if body.get("limpiar", True):
        vm.reiniciar(progreso)
    return {"reporte": rep}


def t_vm_mision(progreso, body):
    import random as _r
    m = vm_misiones.preparar(str(body.get("id")), _r.randrange(1 << 30))
    vm.encender(progreso)
    progreso("Preparando el escenario dentro de Ubuntu…")
    code, out = vm.ssh(m["setup"], timeout=240)
    if code != 0:
        raise RuntimeError(f"No se pudo preparar la misión (código {code}): {out[-400:]}")
    VM_PARTIDA.clear()
    VM_PARTIDA.update(m)
    base = next(x for x in vm_misiones.MISIONES if x["id"] == m["id"])  # textos sin rellenar (para traducirlos)
    return {k: m[k] for k in ("id", "nivel", "titulo", "historia", "objetivo")} | {
        "n_pistas": len(m["pistas"]), "vars": m["vars"], "objetivo_t": base["objetivo"]}


def _curl(url: str, destino: str, timeout: int = 900) -> str:
    import shutil
    curl = shutil.which("curl.exe") or shutil.which("curl")
    r = subprocess.run([curl, "-sSfL", "--max-time", str(timeout), "-o", destino, url], capture_output=True, text=True,
                       timeout=timeout + 30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "" if r.returncode == 0 else (r.stderr or "error de descarga").strip()[:200]


def _zip_a_md(zip_ruta: str, destino: str) -> None:
    """Junta los capítulos .md de un libro mdBook (en el orden de su SUMMARY.md) en un solo archivo."""
    import zipfile
    with zipfile.ZipFile(zip_ruta) as z:
        nombres = z.namelist()
        resumen = min((n for n in nombres if n.endswith("src/SUMMARY.md")), key=len, default=None)  # el del libro, no el de sus herramientas
        base = resumen.rsplit("SUMMARY.md", 1)[0] if resumen else ""
        orden = re.findall(r"\]\(([^)]+\.md)\)", z.read(resumen).decode("utf-8", "replace")) if resumen else []
        partes = []
        for rel in orden or [n[len(base):] for n in nombres if n.startswith(base) and n.endswith(".md")]:
            ruta = base + rel.lstrip("./")
            if ruta in nombres:
                partes.append(z.read(ruta).decode("utf-8", "replace"))
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n\n".join(partes))


def _attack_a_md(json_ruta: str, destino: str) -> None:
    """MITRE ATT&CK (STIX) → un .md con cada técnica, sus tácticas, plataformas y cómo detectarla."""
    with open(json_ruta, encoding="utf-8") as f:
        objs = json.load(f)["objects"]
    out = ["# MITRE ATT&CK Enterprise\n"]
    tecnicas = []
    for o in objs:
        if o.get("type") != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        tid = next((r["external_id"] for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), "")
        tac = ", ".join(p["phase_name"] for p in o.get("kill_chain_phases", []))
        tecnicas.append((tid, f"## {tid} {o.get('name', '')}\nTácticas: {tac}\nPlataformas: {', '.join(o.get('x_mitre_platforms', []))}\n\n"
                              f"{o.get('description', '')}\n\nDetección: {o.get('x_mitre_detection', '')}\n"))
    out += [t for _, t in sorted(tecnicas)]
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def t_bajar_paquetes(progreso, body):
    paquetes = [p for p in (body.get("paquetes") or []) if p in PAQUETES]
    os.makedirs(GUIAS, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    res = []
    for paq in paquetes:
        for nombre, url, tipo in PAQUETES[paq]:
            carpeta = CAPTURAS_EJEMPLO if tipo == "pcap" else VMS if tipo == "ova" else DATOS if tipo == "rustlings" else GUIAS
            os.makedirs(carpeta, exist_ok=True)
            destino = os.path.join(carpeta, nombre)
            if tipo != "gh_release_pdf" and os.path.isfile(destino) and (tipo == "pcap" or os.path.getsize(destino) > (100_000_000 if tipo == "ova" else 10_000)):
                res.append({"nombre": nombre, "ok": True, "ya": True})
                continue
            progreso(f"Bajando {nombre}…")
            tmp = os.path.join(TMP, "bajando_" + uuid.uuid4().hex[:6])
            try:
                if tipo == "gh_release_pdf":
                    err = _curl(f"https://api.github.com/repos/{url}/releases/latest", tmp, 60)
                    if err:
                        raise RuntimeError(err)
                    with open(tmp, encoding="utf-8") as f:
                        assets = [x["browser_download_url"] for x in json.load(f).get("assets", []) if x["name"].endswith(".pdf")]
                    for au in assets[:3]:
                        dn = os.path.join(GUIAS, f"{nombre}-{au.rsplit('/', 1)[-1]}")
                        if not os.path.isfile(dn):
                            e2 = _curl(au, dn)
                            if e2:
                                raise RuntimeError(e2)
                    res.append({"nombre": f"{nombre} ({len(assets[:3])} PDFs)", "ok": bool(assets)})
                    continue
                err = _curl(url, tmp)
                if err:
                    raise RuntimeError(err)
                if tipo == "pdf":
                    with open(tmp, "rb") as f:
                        if f.read(4) != b"%PDF":
                            raise RuntimeError("no llegó un PDF")
                    os.replace(tmp, destino)
                elif tipo in ("pcap", "ova"):
                    os.replace(tmp, destino)
                elif tipo == "txt":
                    with open(tmp, "rb") as f:
                        if f.read(200).lstrip().lower().startswith((b"<!doctype", b"<html")):
                            raise RuntimeError("llegó una página web, no el texto")
                    os.replace(tmp, destino)
                elif tipo == "rustlings":
                    with open(destino, "w", encoding="utf-8") as f:
                        json.dump(academia.rustlings_desde_zip(tmp), f, ensure_ascii=False)
                elif tipo == "zip_md":
                    _zip_a_md(tmp, destino)
                elif tipo == "attack":
                    _attack_a_md(tmp, destino)
                res.append({"nombre": nombre, "ok": True, "mb": round(os.path.getsize(destino) / 1e6, 1)})
            except Exception as e:  # noqa: BLE001
                res.append({"nombre": nombre, "ok": False, "error": str(e)[:200]})
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
    return {"resultados": res}


def t_bajar_cisco(progreso, body):
    """Baja las guías de Cisco con curl.exe de Windows (si cisco.com lo rechaza, se reporta: no se disfraza)."""
    import shutil
    curl = shutil.which("curl.exe") or shutil.which("curl")
    os.makedirs(GUIAS, exist_ok=True)
    res = []
    lista = [(n, _BASE_CISCO + r) for n, r in GUIAS_CISCO] + GUIAS_EXTRA
    for nombre, url in lista:
        destino = os.path.join(GUIAS, nombre)
        if os.path.isfile(destino):
            res.append({"nombre": nombre, "ok": True, "ya": True})
            continue
        progreso(f"Bajando {nombre}…")
        tmp = destino + ".parcial"
        try:
            r = subprocess.run([curl, "-sSfL", "--max-time", "300", "-o", tmp, url],
                               capture_output=True, text=True, timeout=320,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            with open(tmp, "rb") as f:
                es_pdf = f.read(4) == b"%PDF"
            if r.returncode == 0 and es_pdf:
                os.replace(tmp, destino)
                res.append({"nombre": nombre, "ok": True, "mb": round(os.path.getsize(destino) / 1e6, 1)})
            else:
                res.append({"nombre": nombre, "ok": False, "error": (r.stderr or "no es PDF").strip()[:150]})
        except Exception as e:  # noqa: BLE001
            res.append({"nombre": nombre, "ok": False, "error": str(e)[:150]})
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return {"resultados": res}


def t_tutor(progreso, body):
    """Tutor para cualquier parte del lab: explica con tus guías como referencia."""
    area = str(body.get("area", "redes"))[:40]
    contexto = str(body.get("contexto", ""))[:3000]
    pregunta = str(body.get("pregunta", "")).strip()[:800] or "Explícame esto."
    es_codigo = bool(body.get("codigo"))
    de_seguridad = any(x in area.lower() for x in ("wireshark", "linux", "red vs blue", "seguridad", "soc"))
    m, keep = modelo("codigo" if es_codigo else "seguridad" if de_seguridad and CONFIG.get("modelo_seguridad")
                     else "pesado" if CONFIG.get("explicar_con_pesado") else "ligero")
    progreso("Consultando tus guías…")
    al = area.lower()
    mundo_tutor = next((m for k, m in (("wireshark", "wireshark"), ("linux", "linux"), ("soc", "soc"), ("siem", "soc"),
                                       ("red vs blue", "soc"), ("rust", "rust"), ("pytorch", "torch"), ("chisel", "chisel"),
                                       ("risc", "cpu"), ("procesador", "cpu"), ("inteligencia", "ia"), ("machine learning", "ia"),
                                       ("ccna", "ccna"), ("redes", "ccna"))
                        if k in al), None)
    refs = _referencias(f"{area} {pregunta} {contexto[:300]}", mundo_tutor)
    if es_codigo:
        progreso(f"{m} está revisando tu código…")
        with _keep(keep):
            texto = ollama.chat(m, [
                {"role": "system", "content": f"Eres un mentor experto en {area} y en programación segura con Rust. Respondes en "
                 "español de México, en Markdown breve (máx. ~250 palabras). Explica el error del compilador o de las pruebas en palabras "
                 "simples, di QUÉ línea cambiar y POR QUÉ (ownership, tipos, lifetimes…). Da a lo mucho un fragmento corto de código: "
                 "NO resuelvas el ejercicio completo, guía al alumno para que lo termine él."},
                {"role": "user", "content": f"Ejercicio y estado:\n{contexto}\n\n"
                 + (f"Material de referencia (Rust Book y guías):\n<<<\n{refs}\n>>>\n\n" if refs else "")
                 + f"Pregunta del alumno: {pregunta}"}], temperature=0.2, num_predict=1100)
        return {"respuesta": texto, "modelo": m}
    progreso("El tutor está pensando…")
    with _keep(keep):
        texto = ollama.chat(m, [
            {"role": "system", "content": f"Eres un tutor paciente y muy claro de {area} (CCNA, Linux, Wireshark). Respondes en "
             "español de México, en Markdown breve (máx. ~200 palabras): primero la idea en una frase, luego el porqué y un "
             "ejemplo corto. Técnicamente exacto. Si el alumno se equivocó, dile qué estuvo mal sin regañarlo."},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\n"
             + (f"Material de referencia de sus guías:\n<<<\n{refs}\n>>>\n\n" if refs else "")
             + f"Pregunta del alumno: {pregunta}"}], temperature=0.3, num_predict=900)
    return {"respuesta": validar_filtros_en_texto(texto) if "wireshark" in area.lower() else texto}


# ---- Rustlings y retos infinitos ------------------------------------------------ #
_RL: dict = {}


def rustlings() -> list[dict]:
    ruta = os.path.join(DATOS, "rustlings.json")
    try:
        mt = os.path.getmtime(ruta)
    except OSError:
        return []
    if _RL.get("mt") != mt:
        with open(ruta, encoding="utf-8") as f:
            _RL.update(mt=mt, lista=json.load(f))
    return _RL["lista"]


def t_generar_reto(progreso, body):
    curso = body.get("curso") if body.get("curso") in academia.CURSOS else "rust"
    nivel = max(0, int(body.get("nivel", 0)))
    dif = "difícil (tipo jefe, varios pasos)" if body.get("dificultad") == "dificil" else "normal"
    m, keep = modelo("codigo")
    previos = [r["titulo"] for r in db.retos(curso)]
    msgs = academia.mensajes_reto(curso, nivel, dif, previos)
    ultimo = ""
    with _keep(keep):
        for intento in range(4):
            progreso(f"{m} está inventando un reto ({intento + 1}/4)…" if not intento else f"Corrigiendo el reto ({intento + 1}/4): {ultimo[:80]}…")
            try:
                r = ollama.chat_json(m, msgs, academia.ESQUEMA_RETO, temperature=0.7 if not intento else 0.2, num_ctx=12288, num_predict=6000)
            except ollama.OllamaError as e:
                ultimo = str(e)
                continue
            progreso("Compilando la solución contra sus pruebas en tu Rust…")
            ok, ultimo = academia.validar_reto(r, TMP)
            if ok:
                r["pistas"] = [str(x) for x in (r.get("pistas") or [])][:3]
                rid = db.guardar_reto(curso, nivel, r)
                return {"id": f"g{rid}"}
            msgs = msgs + [{"role": "assistant", "content": json.dumps(r, ensure_ascii=False)[:12000]},
                           {"role": "user", "content": f"No sirve: {ultimo}. Corrígelo y devuelve el JSON completo otra vez."}]
    raise RuntimeError("No logré un reto que pasara sus propias pruebas. Intenta otra vez (el modelo a veces se equivoca). " + ultimo[:300])


# ---- traducción de la interfaz (una sola vez, con tu modelo; se guarda en datos/i18n_en.json) ----- #
I18N_RUTA = os.path.join(DATOS, "i18n_en.json")


def _i18n() -> dict:
    try:
        with open(I18N_RUTA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _i18n_faltan() -> list[str]:
    try:
        with open(os.path.join(AQUI, "web", "i18n_textos.json"), encoding="utf-8") as f:
            textos = json.load(f)
    except (OSError, ValueError):
        return []
    hechos = _i18n()
    return [t for t in textos if t not in hechos]


def t_traducir_ui(progreso, body):
    faltan = _i18n_faltan()
    hechos = _i18n()
    m, keep = modelo("pesado")
    esquema = {"type": "object", "properties": {"t": {"type": "array", "items": {"type": "object", "properties": {
        "i": {"type": "integer"}, "en": {"type": "string"}}, "required": ["i", "en"]}}}, "required": ["t"]}
    lote = 25
    with _keep(keep):
        for k in range(0, len(faltan), lote):
            parte = faltan[k:k + lote]
            progreso(f"Traduciendo la interfaz al inglés… {min(k + lote, len(faltan))}/{len(faltan)}")
            try:
                r = ollama.chat_json(m, [
                    {"role": "system", "content": "You translate the UI and lessons of NetLab, a gamified study app for networking (CCNA), "
                     "Wireshark, Linux, cybersecurity, Rust, AI and CPU design, from Mexican Spanish to natural, concise US English. "
                     "Keep EXACTLY: emojis, markdown (`code`, **bold**), placeholders like {n} and {{VAR}} (never translate them), punctuation at the start/end, "
                     "commands, code, file paths, protocol and field names. Never add explanations. Return every item with its index i."},
                    {"role": "user", "content": json.dumps([{"i": i, "es": t} for i, t in enumerate(parte)], ensure_ascii=False)}],
                    esquema, temperature=0.1, num_ctx=16384, num_predict=8000, idioma_fijo=True)
            except Exception:  # noqa: BLE001
                continue
            for it in r.get("t", []):
                i, en = it.get("i"), str(it.get("en", "")).strip()
                if not isinstance(i, int) or not (0 <= i < len(parte)) or not en:
                    continue
                es = parte[i]
                if es.count("{n}") != en.count("{n}") or es.count("`") != en.count("`") or es.count("{{") != en.count("{{"):
                    continue  # rompió algo: mejor dejarlo en español
                hechos[es] = en
            with open(I18N_RUTA, "w", encoding="utf-8") as f:
                json.dump(hechos, f, ensure_ascii=False)
    return {"traducidos": len(hechos), "faltan": len(_i18n_faltan())}


# ---- comparar modelos de seguridad ---------------------------------------------- #
def candidatos_seguridad() -> list[str]:
    disp = ollama.list_models()
    out = [m for m in disp if "foundation-sec" in m.lower()]
    for m in (CONFIG["modelo_pesado"], CONFIG["modelo_ligero"]):
        if m in disp and m not in out:
            out.append(m)
    return out


def t_comparar_seguridad(progreso, body):
    modelos = [m for m in (body.get("modelos") or candidatos_seguridad()) if isinstance(m, str)][:5]
    res = []
    for m in modelos:
        progreso(f"Cargando {m}…")
        cargados = set(ollama.loaded_models())
        for otro in MODELOS_USADOS - {m}:
            if otro in cargados:
                ollama.unload(otro)
        MODELOS_USADOS.add(m)
        aciertos, tiempos, fallas = 0, [], []
        try:  # calentar: la primera llamada carga el modelo y no debe contar
            ollama.chat(m, [{"role": "user", "content": "Responde solo: listo"}], num_predict=5, keep_alive="2m", idioma_fijo=True)
        except Exception:  # noqa: BLE001
            pass
        for i, (preg, ops, ok) in enumerate(bench_seg.PREGUNTAS):
            progreso(f"{m}: pregunta {i + 1}/{len(bench_seg.PREGUNTAS)}…")
            t0 = time.time()
            try:
                r = ollama.chat_json(m, bench_seg.mensajes(i), bench_seg.ESQUEMA, temperature=0, num_ctx=2048, num_predict=300,
                                     keep_alive="2m", idioma_fijo=True)
                letra = str(r.get("respuesta", "")).strip().upper()[:1]
            except Exception:  # noqa: BLE001
                letra = "?"
            tiempos.append(time.time() - t0)
            if letra == ok:
                aciertos += 1
            else:
                fallas.append(preg[:70])
        res.append({"modelo": m, "aciertos": aciertos, "total": len(bench_seg.PREGUNTAS),
                    "seg_por_respuesta": round(sum(tiempos) / max(1, len(tiempos)), 2), "fallas": fallas})
        ollama.unload(m)
    res.sort(key=lambda r: (-r["aciertos"], r["seg_por_respuesta"]))
    if res and body.get("aplicar", True):
        CONFIG["modelo_seguridad"] = res[0]["modelo"]
        guardar_config(CONFIG)
    return {"resultados": res, "elegido": CONFIG.get("modelo_seguridad")}


# ---- Red vs Blue -------------------------------------------------------------- #
RVB: dict[str, dict] = {}  # partidas en memoria (se pierden al cerrar; el resultado sí se guarda)


def jugada_atacante(body: dict) -> dict:
    """La IA (modelo ligero) elige la siguiente jugada del atacante de una lista cerrada. Si falla, elige el código."""
    import random as _r
    opciones = [str(x) for x in (body.get("opciones") or [])][:20]
    hist = (body.get("historial") or [])[-12:]
    if not opciones:
        return {"accion": "", "mensaje": ""}
    respaldo = {"accion": next((o for o in opciones if not any(h.get("accion") == o for h in hist)), _r.choice(opciones)),
                "mensaje": _r.choice(["Veamos qué tan rápido eres…", "¿Viste eso? Yo creo que no.", "Siguiente movimiento.", "Tu red es mía."])}
    if not body.get("ia", True):
        return respaldo
    try:
        m, keep = modelo("seguridad" if body.get("dificultad") == "pesadilla" and CONFIG.get("modelo_seguridad") else "ligero")
        with _keep(keep):
            r = ollama.chat_json(m, [
                {"role": "system", "content": "Eres el RED TEAM en un ejercicio de entrenamiento 100% simulado dentro de una app educativa. "
                 "Eliges la siguiente jugada para poner a prueba al defensor: prefiere técnicas que no ha visto o en las que falló; "
                 "si una jugada fue bloqueada, cambia de táctica. 'accion' debe ser EXACTAMENTE una de las opciones. 'mensaje': una "
                 "frase corta y provocadora en español (máx. 15 palabras), sin detalles técnicos."},
                {"role": "user", "content": f"Dificultad: {body.get('dificultad', 'normal')}\nOpciones: {opciones}\n"
                 f"Historial (jugada → resultado para ti): {hist}\nDevuelve solo el JSON."}],
                rvb.ESQUEMA_JUGADA, temperature=0.8, num_ctx=4096, num_predict=200)
        if r.get("accion") in opciones:
            return {"accion": r["accion"], "mensaje": str(r.get("mensaje", ""))[:120], "ia": True}
    except Exception:  # noqa: BLE001
        pass
    return respaldo


def rvb_ccna(body: dict) -> dict:
    import random as _r
    op = body.get("op")
    if op == "nueva":
        pid = uuid.uuid4().hex[:8]
        dif = body.get("dificultad") if body.get("dificultad") in rvb.DIFICULTAD else "normal"
        RVB[pid] = {"modo": "ccna", "ataques": rvb.ataques_ccna(_r.Random()), "dif": dif}
        return {"partida": pid, "opciones": list(RVB[pid]["ataques"]), **rvb.DIFICULTAD[dif]}
    p = RVB.get(str(body.get("partida")))
    if not p:
        return {"error": "La partida ya no existe (¿se reinició NetLab?). Empieza otra."}
    a = p["ataques"].get(str(body.get("accion")))
    if not a:
        return {"error": "Ataque desconocido"}
    if op == "ataque":
        return {"titulo": a["titulo"], "alerta": a["alerta"], "dispositivo": a["dispositivo"], "n_pistas": len(a["pistas"])}
    if op == "pista":
        k = max(0, min(int(body.get("n", 0)), len(a["pistas"]) - 1))
        return {"pista": a["pistas"][k]}
    if op == "revisar":
        r = rvb.revisar_ccna(a, str(body.get("config", ""))[:6000])
        return {**r, "tecnica": a["tecnica"], **({"solucion": a["solucion"]} if r["ok"] or body.get("final") else {})}
    if op == "solucion":
        return {"solucion": a["solucion"], "tecnica": a["tecnica"]}
    return {"error": "op desconocida"}


def rvb_ws(body: dict) -> dict:
    import random as _r
    op = body.get("op")
    if op == "nueva":
        pid = uuid.uuid4().hex[:8]
        dif = body.get("dificultad") if body.get("dificultad") in rvb.DIFICULTAD else "normal"
        RVB[pid] = {"modo": "wireshark", "dif": dif, "oleadas": {}}
        return {"partida": pid, "opciones": list(rvb.OLEADAS_WS), "tecnicas": rvb.TECNICAS, **rvb.DIFICULTAD[dif]}
    p = RVB.get(str(body.get("partida")))
    if not p:
        return {"error": "La partida ya no existe (¿se reinició NetLab?). Empieza otra."}
    esc = str(body.get("accion"))
    if esc not in rvb.OLEADAS_WS:
        return {"error": "Oleada desconocida"}
    tecnica, pid_preg, pid_fil = rvb.OLEADAS_WS[esc]
    if op == "oleada":
        semilla = _r.randint(1, 10**9)
        c = ws.generar(esc, semilla)
        os.makedirs(TMP, exist_ok=True)
        ruta = os.path.join(TMP, f"rvb_{body['partida']}_{esc}.pcap")
        with open(ruta, "wb") as f:
            f.write(c["pcap"])
        preg = next(x for x in c["preguntas"] if x["id"] == pid_preg)
        fil = next(x for x in c["filtros"] if x["id"] == pid_fil)
        p["oleadas"][esc] = {"ruta": ruta, "preg": preg, "fil": fil}
        return {"pregunta": preg["texto"], "filtro": fil["texto"], "paquetes": c["paquetes"]}
    o = p["oleadas"].get(esc)
    if not o:
        return {"error": "Primero pide la oleada"}
    if op == "abrir":
        exe = ws.wireshark_exe()
        if not exe:
            return {"ok": False, "error": "No encontré Wireshark.exe."}
        subprocess.Popen([exe, "-r", o["ruta"]], close_fds=True)
        return {"ok": True}
    if op == "revisar":
        ok_p = ws.calificar_respuesta(o["preg"], str(body.get("respuesta", "")))
        ok_t = body.get("tecnica") == tecnica
        tuyo, ref = ws.correr_filtro(o["ruta"], str(body.get("filtro", ""))), ws.correr_filtro(o["ruta"], o["fil"]["referencia"])
        ok_f = bool(tuyo.get("ok") and ref.get("ok") and set(tuyo["frames"]) == set(ref["frames"]))
        return {"respuesta": ok_p, "tecnica": ok_t, "filtro": ok_f, "error_filtro": tuyo.get("error", ""),
                "correctas": {"respuesta": o["preg"]["respuesta"], "tecnica": tecnica, "filtro": o["fil"]["referencia"],
                              "explicacion": o["preg"].get("explicacion", "")}}
    return {"error": "op desconocida"}


def _hay_pypdf() -> bool:
    import importlib.util
    return importlib.util.find_spec("pypdf") is not None


def carpeta_jitl() -> str:
    return CONFIG.get("carpeta_jitl") or jitl.carpeta_por_defecto(AQUI)


def t_calificar_examen(progreso, body):
    e = db.examen(int(body["id"]))
    if not e:
        raise ValueError("No encontré ese examen.")
    m, keep = modelo("ligero")
    progreso("Calificando…")
    with _keep(keep):
        res = gen.calificar_examen(m, e, body.get("respuestas") or [])
    db.guardar_resultado_examen(e["id"], res)
    area = {"linux": "Linux", "wireshark": "Wireshark", "rust": "Rust", "rustproj": "Proyectos Rust", "ia": "IA", "torch": "PyTorch",
            "cpu": "Procesadores", "chisel": "Chisel", "soc": "SOC"}.get(e.get("dominio"), "CCNA")
    for d, q in zip(res["detalle"], e["preguntas"]):
        if not d["correcta"]:
            datos = {"enunciado": q["enunciado"], "explicacion": q.get("explicacion", ""), "origen": e.get("titulo", "")}
            if q["tipo"] == "opcion":
                db.agregar_repaso("ex:" + q["enunciado"], area, "opcion", {**datos, "opciones": q["opciones"], "correcta": q["correcta"]})
            else:
                db.agregar_repaso("ex:" + q["enunciado"], area, "comando", {**datos, "respuestas": q["respuestas_validas"]})
    return res


class _keep:
    """Durante la llamada, el modelo se queda en VRAM el tiempo del rol (pesado 2m, ligero 10m)."""

    def __init__(self, valor):
        self.valor = valor

    def __enter__(self):
        self.prev, ollama.KEEP_ALIVE = ollama.KEEP_ALIVE, self.valor

    def __exit__(self, *a):
        ollama.KEEP_ALIVE = self.prev


# --------------------------------------------------------------------------- #
# Vistas para el navegador
# --------------------------------------------------------------------------- #
def examen_publico(e: dict) -> dict:
    """El examen sin la clave de respuestas (la clave nunca sale del servidor antes de calificar)."""
    out = {k: e[k] for k in ("id", "titulo", "tema", "nivel", "calificacion", "resultado", "simulacro", "minutos", "dominio")
           if k in e}
    out["preguntas"] = [{"tipo": q["tipo"], "enunciado": q["enunciado"], "opciones": q.get("opciones", []),
                         "dudosa": q.get("dudosa", False), "subtema": q.get("subtema", "")}
                        for q in e["preguntas"]]
    return out


def practica_publica(p: dict, con_solucion: bool) -> dict:
    out = dict(p)
    if not con_solucion and not p.get("libre"):
        out.pop("solucion", None)
        out.pop("fallas", None)
        out["verificaciones"] = [{"id": c["id"], "dispositivo": c["dispositivo"], "tipo": c["tipo"],
                                  "descripcion": c["descripcion"],
                                  # el destino de un ping no es spoiler: hace falta para saber qué probar
                                  **({"ip": c.get("ip", "")} if c["tipo"] == "ping" else {})}
                                 for c in p.get("verificaciones", [])]
    return out


def exportar_md(p: dict, con_solucion: bool) -> str:
    L = [f"# {p.get('titulo', 'Práctica')}", "", f"**Tema:** {p.get('tema', '')} · **Nivel:** {p.get('nivel', '')}",
         "", f"**Objetivo:** {p.get('objetivo', '')}", "", p.get("escenario", ""), "", "## Equipos", ""]
    L += [f"- {d['nombre']}: {d['tipo']} {d.get('modelo', '')}" for d in p.get("dispositivos", [])]
    L += ["", "## Conexiones", "", "| Desde | Puerto | Hacia | Puerto | Cable |", "|---|---|---|---|---|"]
    L += [f"| {e['a']} | {e['puerto_a']} | {e['b']} | {e['puerto_b']} | {e.get('cable', '')} |" for e in p.get("enlaces", [])]
    L += ["", "## Direccionamiento", "", "| Equipo | Interfaz | IP | Máscara | Gateway |", "|---|---|---|---|---|"]
    L += [f"| {a['dispositivo']} | {a['interfaz']} | {a['ip']} | {a['mascara']} | {a.get('gateway', '')} |"
          for a in p.get("direccionamiento", [])]
    L += ["", "## Tareas", ""] + [f"{i}. {t}" for i, t in enumerate(p.get("tareas", []), 1)]
    if p.get("config_inicial"):
        L += ["", "## Configuración inicial (pégala antes de empezar)", ""]
        for c in p["config_inicial"]:
            L += [f"### {c['dispositivo']}", "```", "enable", "configure terminal", c["config"], "end", "```"]
    if con_solucion and p.get("solucion"):
        L += ["", "## Solución", ""]
        for c in p["solucion"]:
            L += [f"### {c['dispositivo']}", "```", c["config"], "```"]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# Servidor HTTP
# --------------------------------------------------------------------------- #
ULTIMO_LATIDO = {"t": None}
SERVIDOR: ThreadingHTTPServer | None = None

TIPOS_MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Manejador(BaseHTTPRequestHandler):
    # HTTP/1.1 con keep-alive: el navegador reusa ~6 conexiones en vez de abrir ~25 nuevas en cada carga, que es cuando
    # Windows rechazaba algunas (ERR_CONNECTION_RESET/TIMED_OUT) y la página quedaba sin traducciones o sin app.js.
    # Es seguro porque TODAS las respuestas mandan Content-Length. timeout: suelta las conexiones ociosas.
    protocol_version = "HTTP/1.1"
    timeout = 30

    def log_message(self, *a):  # silencioso
        pass

    # -- respuestas --
    def _json(self, data, code=200):
        cuerpo = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta):
        ruta = os.path.normpath(os.path.join(WEB, ruta))
        if not ruta.startswith(WEB) or not os.path.isfile(ruta):
            return self._json({"error": "no encontrado"}, 404)
        with open(ruta, "rb") as f:
            datos = f.read()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS_MIME.get(os.path.splitext(ruta)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _cuerpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _subir_guia(self, nombre: str) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        nombre = re.sub(r"[^\w.\- ]", "", os.path.basename(nombre or ""))[:120]
        if not nombre.lower().endswith((".pdf", ".txt", ".md")):
            return {"ok": False, "error": "Solo .pdf, .txt o .md"}
        if not 0 < n <= 150_000_000:
            return {"ok": False, "error": "Archivo vacío o demasiado grande"}
        datos = self.rfile.read(n)
        if nombre.lower().endswith(".pdf") and not datos.startswith(b"%PDF"):
            return {"ok": False, "error": "No es un PDF"}
        os.makedirs(GUIAS, exist_ok=True)
        with open(os.path.join(GUIAS, nombre), "wb") as f:
            f.write(datos)
        return {"ok": True, "nombre": nombre, "mb": round(n / 1e6, 1)}

    def _local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    # -- GET --
    def do_GET(self):
        if self.path.startswith("/ci/"):  # cloud-init de la VM (llega por la NAT de VirtualBox)
            vm.CI_LOG.append(f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {self.path}")
            del vm.CI_LOG[:-20]
            txt = vm.cloud_init(self.path[4:].split("?")[0])
            if txt is None:
                return self._json({"error": "no existe"}, 404)
            cuerpo = txt.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        if not self._local():
            return self._json({"error": "solo local"}, 403)
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        ruta = url.path
        try:
            if ruta in ("/", "/index.html"):
                return self._archivo("index.html")
            if ruta.startswith("/web/"):
                return self._archivo(ruta[5:])
            if ruta == "/api/rustlings":
                prog = db.academia()
                return self._json({"ejercicios": [{"nombre": e["nombre"], "tema": e["tema"], "test": e["test"],
                                                   "estrellas": (prog.get("rl_" + e["nombre"]) or {}).get("estrellas", 0)} for e in rustlings()]})
            m_rl = re.fullmatch(r"/api/rustlings/(\w+)", ruta)
            if m_rl:
                e = next((x for x in rustlings() if x["nombre"] == m_rl.group(1)), None)
                if not e:
                    return self._json({"error": "no existe"}, 404)
                guardado = (db.academia().get("rl_" + e["nombre"]) or {}).get("codigo")
                return self._json({k: e[k] for k in ("nombre", "tema", "test", "pista", "codigo")} | {"guardado": guardado})
            if ruta == "/api/academia/retos":
                return self._json({"retos": db.retos(q.get("curso", ["rust"])[0])})
            m_g = re.fullmatch(r"/api/academia/reto/g(\d+)", ruta)
            if m_g:
                r = db.reto(int(m_g.group(1)))
                if not r:
                    return self._json({"error": "no existe"}, 404)
                return self._json({k: r.get(k) for k in ("id", "curso", "nivel", "titulo", "teoria", "enunciado", "inicial", "pistas")}
                                  | {"jefe": False, "modo": "tests", "generado": True})
            if ruta == "/api/i18n":
                return self._json({"en": _i18n(), "faltan": len(_i18n_faltan()), "idioma": CONFIG.get("idioma", "en")})
            if ruta == "/api/vm/diag":
                return self._json(vm.diagnostico())
            if ruta == "/api/vm/estado":
                return self._json({**vm.estado(), "misiones": [{k: m[k] for k in ("id", "nivel", "titulo", "historia", "objetivo")}
                                                             for m in vm_misiones.MISIONES],
                                   "progreso": {k[3:]: v["estrellas"] for k, v in db.academia().items() if k.startswith("vm_")},
                                   "actual": VM_PARTIDA.get("id"), "ci_log": vm.CI_LOG[-5:],
                                   "siem_instalado": vm.siem_instalado()})
            if ruta == "/api/salud":
                return self._json(salud.reporte(CONFIG))
            if ruta == "/api/siem/estado":
                st = siem.estado_siem() if vm.corriendo() else {"es": False, "kibana": False}
                vst = vm.estado()
                return self._json({"instalado": vm.siem_instalado(), "corriendo": vst.get("corriendo", False), **st,
                                   "vmstate": vst.get("vmstate", ""), "modo": vst.get("modo"), "cpus": vst.get("cpus"),
                                   "caliente": vst.get("caliente", False), "espacio": vst.get("espacio", {}),
                                   "calor": vm.CALOR, "auto": bool(CONFIG.get("vm_auto_calentar", True)),
                                   "importar": {"carpeta": SIEM_IMPORTAR, "archivos": siem.listar_importables(SIEM_IMPORTAR)},
                                   "kibana_url": siem.KIBANA, "catalogo": siem.CATALOGO,
                                   "progreso": {k[5:]: v["estrellas"] for k, v in db.academia().items() if k.startswith("siem_")},
                                   "actual": SIEM_PARTIDA.get("id")})
            if ruta == "/api/estado":
                modelos = ollama.list_models()
                prog = db.progreso()
                return self._json({
                    "ollama": bool(modelos), "modelos": modelos, "config": CONFIG,
                    "niveles": temario.NIVELES, "temas": temario.TEMAS, "progreso": prog,
                    "recomendado": temario.recomendado(prog)["id"], "tipos_verificacion": TIPOS,
                    "packet_tracer": bool(packet_tracer.exe()), "cargados": ollama.loaded_models(),
                })
            if ruta == "/api/jitl":
                carpeta = carpeta_jitl()
                return self._json({"carpeta": carpeta, "existe": os.path.isdir(carpeta),
                                   "labs": jitl.listar(carpeta)})
            if ruta == "/api/diagnostico":
                m, _ = modelo("pesado")
                return self._json({"modelo": m, **ollama.diagnostico(m), "ultima_llamada": ollama.ULTIMA_LLAMADA})
            if ruta == "/api/llamadas":
                return self._json(ollama.HISTORIAL_LLAMADAS)
            if ruta == "/api/historial":
                return self._json(db.historial())
            m = re.fullmatch(r"/api/trabajo/(\w+)", ruta)
            if m:
                t = TRABAJOS.get(m.group(1))
                return self._json(t if t else {"estado": "error", "error": "Trabajo desconocido"})
            m = re.fullmatch(r"/api/practica/(\d+)", ruta)
            if m:
                p = db.practica(int(m.group(1)))
                if not p:
                    return self._json({"error": "No existe"}, 404)
                return self._json(practica_publica(p, q.get("solucion", ["0"])[0] == "1"))
            m = re.fullmatch(r"/api/practica/(\d+)/exportar", ruta)
            if m:
                p = db.practica(int(m.group(1)))
                md = exportar_md(p, q.get("solucion", ["0"])[0] == "1").encode("utf-8")
                nombre = re.sub(r"[^\w\- ]", "", p.get("titulo", "practica"))[:60].strip() or "practica"
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f"attachment; filename*=UTF-8''{urllib.parse.quote(nombre)}.md")
                self.send_header("Content-Length", str(len(md)))
                self.end_headers()
                self.wfile.write(md)
                return
            m = re.fullmatch(r"/api/practica/(\d+)/ptbuilder", ruta)
            if m:
                p = db.practica(int(m.group(1)))
                if not p:
                    return self._json({"error": "No existe"}, 404)
                nivel = q.get("nivel", ["topologia"])[0]
                if nivel not in ("topologia", "inicial", "completa"):
                    nivel = "topologia"
                return self._json({"script": ptbuilder.script(p, nivel), "nivel": nivel})
            if ruta == "/api/jugador":
                n_mis = int(q.get("misiones", ["44"])[0])
                j = juego.calcular(db.para_juego(), len(ws.ESCENARIOS), n_mis)
                j["listo"] = juego.listo(db.progreso(), db.progreso_wireshark(), db.misiones(), temario.DOMINIOS, ws.ESCENARIOS, n_mis)
                return self._json(j)
            if ruta == "/api/linux":
                return self._json({"estrellas": db.misiones()})
            if ruta == "/api/academia":
                if "rustc" not in _RUSTC:
                    _RUSTC["rustc"] = academia.version()
                return self._json({"cursos": academia.para_ui(), "progreso": db.academia(), "rustc": _RUSTC["rustc"],
                                   "modelo_codigo": CONFIG.get("modelo_codigo")})
            if ruta == "/api/indice":
                return self._json({"progreso": db.indice()})
            if ruta == "/api/mitre":
                return self._json(db.evidencia_mitre())
            if ruta == "/api/repaso":
                return self._json({"cola": db.repasos_pendientes(), **db.resumen_repaso()})
            if ruta == "/api/mision_dia":
                prog = db.progreso()
                return self._json({"actividad": db.actividad_de_hoy(), "repaso": db.resumen_repaso(),
                                   "recomendado": temario.recomendado(prog), "progreso_ws": db.progreso_wireshark(),
                                   "misiones": db.misiones(), "escenarios": ws.ESCENARIOS})
            if ruta == "/api/teoria":
                return self._json({"temas": temas_teoria(), "lecciones": db.lecciones()})
            m = re.fullmatch(r"/api/teoria/(\d+)", ruta)
            if m:
                l = db.leccion(int(m.group(1)))
                return self._json(l if l else {"error": "No existe"}, 200 if l else 404)
            if ruta == "/api/guias":
                me = guias.modelo_embed(CONFIG.get("modelo_embed", ""))
                return self._json({**guias.estado(GUIAS, GUIAS_DB, me), "modelo": me,
                                   "campos": len(guias.campos(GUIAS)), "pypdf": _hay_pypdf()})
            if ruta == "/api/wireshark":
                return self._json({"escenarios": ws.ESCENARIOS, "niveles": ws.NIVELES_WS, "progreso": db.progreso_wireshark(),
                                   "tshark": bool(ws.tshark()), "wireshark": bool(ws.wireshark_exe())})
            m = re.fullmatch(r"/api/wireshark/(\d+)", ruta)
            if m:
                c = db.captura(int(m.group(1)))
                return self._json(captura_publica(c) if c else {"error": "No existe"}, 200 if c else 404)
            if ruta == "/api/wireshark/interfaces":
                return self._json({"interfaces": ws.interfaces()})
            m = re.fullmatch(r"/api/wireshark/(\d+)/pcap", ruta)
            if m:
                c = db.captura(int(m.group(1)))
                if not c:
                    return self._json({"error": "No existe"}, 404)
                if c["escenario"] == "vivo":
                    with open(pcap_de(c), "rb") as fh:
                        datos = fh.read()
                else:
                    datos = ws.generar(c["escenario"], c["semilla"])["pcap"]
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.tcpdump.pcap")
                self.send_header("Content-Disposition", f"attachment; filename=netlab_{c['escenario']}_{c['id']}.{'pcapng' if c['escenario'] == 'vivo' else 'pcap'}")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)
                return
            m = re.fullmatch(r"/api/examen/(\d+)", ruta)
            if m:
                e = db.examen(int(m.group(1)))
                if not e:
                    return self._json({"error": "No existe"}, 404)
                return self._json(examen_publico(e))
            return self._json({"error": "ruta desconocida"}, 404)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    # -- POST --
    def do_POST(self):
        if not self._local():
            return self._json({"error": "solo local"}, 403)
        url = urllib.parse.urlparse(self.path)
        ruta = url.path
        try:
            if ruta == "/api/guias/subir":  # un PDF crudo para la carpeta guias (lo manda tu navegador)
                return self._json(self._subir_guia(urllib.parse.parse_qs(url.query).get("nombre", [""])[0]))
            body = self._cuerpo()
            if ruta == "/api/latido":
                ULTIMO_LATIDO["t"] = time.time()
                return self._json({"ok": True, "ver": version_web()})
            if ruta == "/api/teoria/mision":  # 📖 teoría a fondo de una misión (se genera una vez y queda en caché)
                idioma = "en" if body.get("idioma") == "en" else "es"
                clave = f"{str(body.get('clave', ''))[:120]}|{idioma}"
                hecha = db.teoria_cache(clave)
                if hecha and not body.get("rehacer"):
                    return self._json({"trabajo": lanzar(lambda progreso, b: {"datos": hecha}, body, gpu=False)})

                def t_teo(progreso, b):
                    mundo = str(b.get("mundo") or "")
                    materia = {"linux": "linux", "linuxreal": "linux", "wireshark": "wireshark", "rust": "rust", "rustproj": "rust",
                               "ia": "ia", "torch": "ia", "cpu": "cpu", "chisel": "chisel", "soc": "soc", "sv": "sv", "indice": "purple"}.get(mundo, "redes")
                    m, keep = modelo("pesado")
                    with _keep(keep):
                        d = gen.generar_teoria_mision(m, materia, str(b.get("titulo", ""))[:200], str(b.get("contexto", ""))[:1500],
                                                      idioma, progreso)
                    db.guardar_teoria_cache(clave, d)
                    return {"datos": d}
                return self._json({"trabajo": lanzar(t_teo, body)})
            if ruta == "/api/teoria/actualizar":  # pasa las lecciones viejas al formato nuevo (mini-curso)
                return self._json({"trabajo": lanzar(t_actualizar_lecciones, body)})
            if ruta == "/api/config":
                for k in CONFIG_DEFECTO:
                    if k in body:
                        CONFIG[k] = body[k]
                ollama.IDIOMA = "en" if CONFIG.get("idioma") == "en" else "es"
                guardar_config(CONFIG)
                return self._json(CONFIG)
            if ruta == "/api/practica/generar":
                return self._json({"trabajo": lanzar(t_generar_practica, body)})
            if ruta == "/api/practica/revisar":
                return self._json({"trabajo": lanzar(t_revisar, body)})
            if ruta == "/api/practica/borrar":
                db.borrar_practica(int(body["id"]))
                return self._json({"ok": True})
            if ruta == "/api/examen/generar":
                return self._json({"trabajo": lanzar(t_generar_examen, body)})
            if ruta == "/api/examen/calificar":
                return self._json({"trabajo": lanzar(t_calificar_examen, body)})
            if ruta == "/api/liberar":
                for m in list(MODELOS_USADOS) or ollama.loaded_models():
                    ollama.unload(m)
                return self._json({"ok": True, "cargados": ollama.loaded_models()})
            if ruta == "/api/abrir_pt":
                archivo = None
                if body.get("archivo"):
                    archivo = jitl.ruta_segura(carpeta_jitl(), body["archivo"])
                    if not archivo:
                        return self._json({"ok": False, "error": "No encontré ese laboratorio."})
                return self._json(packet_tracer.abrir(archivo))
            if ruta == "/api/wireshark/generar":
                c = generar_wireshark(body.get("escenario", ""))
                return self._json(captura_publica(db.captura(c["id"])))
            if ruta in ("/api/wireshark/abrir", "/api/wireshark/filtro", "/api/wireshark/calificar"):
                c = db.captura(int(body.get("id", 0)))
                if not c:
                    return self._json({"ok": False, "error": "No encontré ese ejercicio."})
                if ruta.endswith("abrir"):
                    exe = ws.wireshark_exe()
                    if not exe:
                        return self._json({"ok": False, "error": "No encontré Wireshark.exe."})
                    subprocess.Popen([exe, "-r", pcap_de(c)], close_fds=True)
                    return self._json({"ok": True})
                if ruta.endswith("filtro"):
                    return self._json(probar_filtro(c, body.get("filtro_id", ""), body.get("filtro", "")))
                return self._json(calificar_wireshark(c, body.get("respuestas") or {}, body.get("filtros") or {}))
            if ruta == "/api/reto/resultado":
                total = max(int(body.get("total", 0)), 0)
                buenas = min(max(float(body.get("buenas", 0)), 0), total)
                area = body.get("area") if body.get("area") in ("ccna", "wireshark", "linux", "todo") else "ccna"
                if total:
                    eid = db.guardar_examen({"titulo": f"Retos de arrastrar ({ {'ccna': 'CCNA', 'wireshark': 'Wireshark', 'linux': 'Linux', 'todo': 'mezclado'}[area] })",
                                             "tema": "retos", "nivel": "", "preguntas": [], "reto": area})
                    db.guardar_resultado_examen(eid, {"detalle": [], "buenas": buenas, "total": total,
                                                                         "calificacion": round(10 * buenas / total, 1)})
                return self._json({"ok": True})
            if ruta == "/api/indice/marcar":  # mundo índice: solo guarda tu avance y tus notas (no genera ataques)
                item = re.sub(r"[^\w:.-]", "", str(body.get("item", "")))[:80]
                if not item:
                    return self._json({"error": "falta item"})
                est = body.get("estado")
                est = est if est in ("pendiente", "en_curso", "hecha") else None
                notas = str(body["notas"])[:4000] if "notas" in body else None
                return self._json(db.guardar_indice(item, est, notas))
            if ruta == "/api/rvb/jugada":
                return self._json(jugada_atacante(body))
            if ruta == "/api/rvb/ccna":
                return self._json(rvb_ccna(body))
            if ruta == "/api/rvb/ws":
                return self._json(rvb_ws(body))
            if ruta == "/api/rvb/resultado":
                modo = body.get("modo") if body.get("modo") in ("ccna", "wireshark", "linux", "web", "ad") else "linux"
                dif = body.get("dificultad") if body.get("dificultad") in rvb.DIFICULTAD else "normal"
                db.guardar_rvb(modo, dif, max(0, min(int(body.get("puntos", 0)), 1000)), bool(body.get("gano")),
                               str(body.get("detalle", ""))[:4000])
                return self._json({"ok": True})
            if ruta == "/api/repaso/agregar":
                tipo = body.get("tipo") if body.get("tipo") in ("opcion", "texto", "flash", "comando") else "flash"
                datos = body.get("datos") or {}
                if datos.get("enunciado"):
                    db.agregar_repaso(str(body.get("clave") or datos["enunciado"])[:300], str(body.get("area", "CCNA"))[:20], tipo, datos)
                return self._json({"ok": True})
            if ruta == "/api/repaso/responder":
                return self._json(db.responder_repaso(int(body.get("id", 0)), bool(body.get("bien"))))
            if ruta == "/api/mision_dia/completar":
                return self._json({"nueva": db.marcar_mision_dia()})
            if ruta == "/api/tutor":
                return self._json({"trabajo": lanzar(t_tutor, body)})
            if ruta == "/api/i18n/traducir":
                return self._json({"trabajo": lanzar(t_traducir_ui, body)})
            if ruta == "/api/vm/crear":
                return self._json({"trabajo": lanzar(t_vm_crear, body, gpu=False)})
            if ruta == "/api/vm/encender":
                return self._json({"trabajo": lanzar(t_vm_encender, body, gpu=False)})
            if ruta == "/api/vm/reiniciar":
                return self._json({"trabajo": lanzar(t_vm_reiniciar, body, gpu=False)})
            if ruta == "/api/vm/autoprueba":
                return self._json({"trabajo": lanzar(t_vm_autoprueba, body, gpu=False)})
            if ruta == "/api/vm/lab":  # 🐳 laboratorio Docker: instalar | levantar | apagar | probar_ia | hornear
                return self._json({"trabajo": lanzar(t_vm_lab, body, gpu=False)})
            if ruta == "/api/vm/siem":
                return self._json({"trabajo": lanzar(t_vm_siem, body, gpu=False)})
            if ruta == "/api/vm/suspender":  # ⏸️ Pausar: guarda el estado (RAM a disco) y libera la memoria
                def t_susp(progreso, b):
                    if vm.espacio()["poco"]:
                        raise RuntimeError("Poco espacio en disco para guardar el estado de la VM (~8 GB). Libera espacio o apágala.")
                    progreso("Pausando la VM (guardando su memoria en disco)…")
                    ok = vm.suspender()
                    return {"suspendida": ok, "estado": vm.info().get("VMState")}
                return self._json({"trabajo": lanzar(t_susp, body, gpu=False)})
            if ruta == "/api/vm/calentar":  # ▶️ Reanudar / encender y esperar a Elastic+Kibana con indicador de fases
                def t_cal(progreso, b):
                    vm.calentar(progreso, auto_caliente=bool(CONFIG.get("vm_auto_caliente", True)))
                    if vm.CALOR.get("fase") == "error":
                        raise RuntimeError(vm.CALOR.get("error") or "No calentó el SIEM.")
                    return {"calor": vm.CALOR}
                return self._json({"trabajo": lanzar(t_cal, body, gpu=False)})
            if ruta == "/api/vm/caliente":  # 📸 tomar (o rehacer) la instantánea en caliente
                def t_snap(progreso, b):
                    vm.tomar_caliente(progreso)
                    return vm.estado()
                return self._json({"trabajo": lanzar(t_snap, body, gpu=False)})
            if ruta == "/api/vm/caliente_borrar":
                def t_snapb(progreso, b):
                    vm.borrar_caliente(progreso)
                    return vm.estado()
                return self._json({"trabajo": lanzar(t_snapb, body, gpu=False)})
            if ruta == "/api/vm/descartar_estado":  # libera los ~8 GB del .sav
                return self._json({"ok": vm.descartar_estado(), **vm.estado()})
            if ruta == "/api/vm/auto":
                CONFIG["vm_auto_calentar"] = bool(body.get("auto"))
                guardar_config(CONFIG)
                return self._json({"auto": CONFIG["vm_auto_calentar"]})
            if ruta == "/api/siem/importar":
                nombres = [str(n) for n in (body.get("archivos") or [])][:50]
                return self._json({"trabajo": lanzar(lambda progreso, b: siem.importar(SIEM_IMPORTAR, nombres, ws.tshark(), progreso),
                                                     body, gpu=False)})
            if ruta == "/api/siem/importar_carpeta":  # abre la carpeta en el Explorador (la crea si falta)
                os.makedirs(SIEM_IMPORTAR, exist_ok=True)
                if os.name == "nt":
                    os.startfile(SIEM_IMPORTAR)  # noqa: S606
                return self._json({"carpeta": SIEM_IMPORTAR})
            if ruta == "/api/siem/importados_borrar":
                siem.borrar_importados()
                return self._json({"ok": True})
            if ruta == "/api/siem/mision":
                if not vm.siem_instalado():
                    return self._json({"error": "El SIEM aún no está instalado en la VM. Usa 'Instalar SIEM' primero."})
                return self._json({"trabajo": lanzar(t_siem_mision, body, gpu=False)})
            if ruta == "/api/siem/revisar":
                if not SIEM_PARTIDA or SIEM_PARTIDA.get("id") != body.get("id"):
                    return self._json({"error": "Ese escenario ya no está activo. Empiézalo de nuevo."})
                r = siem.calificar(SIEM_PARTIDA["verdad"], SIEM_PARTIDA["preguntas"], body.get("respuestas", {}))
                return self._json(r)
            if ruta == "/api/siem/pista":
                if not SIEM_PARTIDA or SIEM_PARTIDA.get("id") != body.get("id"):
                    return self._json({"error": "Ese escenario ya no está activo."})
                n = max(1, int(body.get("n", 1)))
                return self._json({"pistas": SIEM_PARTIDA["pistas"][:n]})
            if ruta == "/api/siem/solucion":
                if not SIEM_PARTIDA or SIEM_PARTIDA.get("id") != body.get("id"):
                    return self._json({"error": "Ese escenario ya no está activo."})
                return self._json({"verdad": SIEM_PARTIDA["verdad"]})
            if ruta == "/api/siem/resultado":
                mid = re.sub(r"[^\w]", "", str(body.get("id", "")))[:20]
                est = max(1, min(int(body.get("estrellas", 1)), 3))
                return self._json(db.guardar_academia("siem_" + mid, "siem", est, ""))
            if ruta == "/api/vm/recrear":
                def t_recrear(progreso, b):
                    progreso("Borrando la máquina anterior…")
                    vm.borrar_vm()
                    VM_PARTIDA.clear()
                    vm.crear(progreso)
                    return vm.estado()
                return self._json({"trabajo": lanzar(t_recrear, body, gpu=False)})
            if ruta == "/api/vm/apagar":
                vm.apagar()
                return self._json(vm.estado())
            if ruta == "/api/vm/terminal":
                vm.abrir_terminal()
                return self._json({"ok": True})
            if ruta == "/api/vm/mision":
                return self._json({"trabajo": lanzar(t_vm_mision, body, gpu=False)})
            if ruta in ("/api/vm/revisar", "/api/vm/pista", "/api/vm/solucion"):
                if not VM_PARTIDA or VM_PARTIDA.get("id") != body.get("id"):
                    return self._json({"error": "Esa misión ya no está preparada (¿reiniciaste NetLab o la VM?). Empiézala otra vez."})
                if ruta.endswith("pista"):
                    base = next(x for x in vm_misiones.MISIONES if x["id"] == VM_PARTIDA["id"])
                    n = max(1, int(body.get("n", 1)))
                    return self._json({"pistas": VM_PARTIDA["pistas"][:n], "pistas_t": base["pistas"][:n], "vars": VM_PARTIDA["vars"]})
                if ruta.endswith("solucion"):
                    return self._json({"solucion": VM_PARTIDA["solucion"]})
                code, out = vm.ssh(VM_PARTIDA["check"], timeout=90)
                return self._json({"ok": code == 0, "salida": out[-1500:]})
            if ruta == "/api/vm/resultado":
                mid = re.sub(r"[^\w]", "", str(body.get("id", "")))[:10]
                est = max(1, min(int(body.get("estrellas", 1)), 3))
                return self._json(db.guardar_academia("vm_" + mid, "linuxreal", est, ""))
            if ruta == "/api/seguridad/comparar":
                return self._json({"trabajo": lanzar(t_comparar_seguridad, body)})
            if ruta == "/api/academia/generar":
                return self._json({"trabajo": lanzar(t_generar_reto, body)})
            if ruta == "/api/academia/calificar":
                mid, cod = str(body.get("id", "")), str(body.get("codigo", ""))[:60000]
                if mid.startswith("pt"):  # entrena en la GPU: suelta los modelos de NetLab para dejarle la VRAM
                    liberar_vram()
                if mid.startswith("g") and mid[1:].isdigit():
                    r = db.reto(int(mid[1:]))
                    if not r:
                        return self._json({"error": "reto desconocido"})
                    res = academia.calificar_libre(cod, TMP, pruebas=r["pruebas"])
                    if "todo!()" in cod:
                        res["aprobado"], res["reglas"] = False, ["Todavía hay `todo!()` sin resolver"]
                    return self._json(res)
                if mid.startswith("rl_"):
                    e = next((x for x in rustlings() if x["nombre"] == mid[3:]), None)
                    if not e:
                        return self._json({"error": "ejercicio desconocido"})
                    return self._json(academia.calificar_libre(cod, TMP, con_tests=e["test"], edicion="2024"))
                return self._json(academia.calificar(mid, cod, TMP))
            if ruta == "/api/academia/correr" and body.get("lenguaje") == "python":
                from core import pytorch_lab
                return self._json(pytorch_lab.correr(str(body.get("codigo", ""))[:60000], TMP))
            if ruta == "/api/academia/verilog":
                from core import chisel_lab
                return self._json(chisel_lab.verilog(str(body.get("codigo", ""))[:60000], str(body.get("modulo", ""))))
            if ruta == "/api/academia/nanogpt":
                from core import pytorch_lab
                return self._json({"trabajo": lanzar(lambda progreso, b: pytorch_lab.entrenar_nanogpt(progreso, max(200, min(int(b.get("iteraciones", 1500)), 5000))), body)})
            if ruta == "/api/academia/correr":
                r = academia.compilar_y_correr(str(body.get("codigo", ""))[:60000], TMP, entrada=str(body.get("entrada", ""))[:20000])
                return self._json(r)
            if ruta == "/api/academia/solucion":
                mid = str(body.get("id", ""))
                if mid.startswith("g") and mid[1:].isdigit():
                    r = db.reto(int(mid[1:]))
                    return self._json({"solucion": r["solucion"]} if r else {"error": "reto desconocido"})
                if mid.startswith("rl_"):
                    e = next((x for x in rustlings() if x["nombre"] == mid[3:]), None)
                    return self._json({"solucion": e["solucion"]} if e else {"error": "ejercicio desconocido"})
                m = academia.MISIONES.get(mid)
                return self._json({"solucion": m["solucion"]} if m else {"error": "misión desconocida"})
            if ruta == "/api/academia/resultado":
                mid = str(body.get("id", ""))
                m = academia.MISIONES.get(mid)
                if mid.startswith("g") and mid[1:].isdigit() and db.reto(int(mid[1:])):
                    m = {"id": mid, "curso": db.reto(int(mid[1:]))["curso"]}
                elif mid.startswith("rl_") and any(x["nombre"] == mid[3:] for x in rustlings()):
                    m = {"id": mid, "curso": "rust"}
                elif re.fullmatch(r"(asm_[a-z]+|cpue_\d{8})", mid):
                    m = {"id": mid, "curso": "cpu"}
                elif re.fullmatch(r"soc_(windows|phishing|ransomware|c2|insider|nube)_\d{8}", mid):
                    m = {"id": mid, "curso": "soc"}
                if not m:
                    return self._json({"error": "misión desconocida"})
                est = max(1, min(int(body.get("estrellas", 1)), 3))
                return self._json(db.guardar_academia(m["id"], m["curso"], est, str(body.get("codigo", ""))[:60000]))
            if ruta == "/api/linux/resultado":
                mision = re.sub(r"[^\w]", "", str(body.get("mision", "")))[:20]
                est = max(1, min(int(body.get("estrellas", 1)), 3))
                return self._json(db.guardar_mision(mision, est) if mision else {"error": "misión vacía"})
            if ruta == "/api/teoria/generar":
                return self._json({"trabajo": lanzar(t_generar_leccion, body)})
            if ruta == "/api/teoria/traducir":
                return self._json({"trabajo": lanzar(t_traducir_leccion, body)})
            if ruta == "/api/teoria/duda":
                return self._json({"trabajo": lanzar(t_duda_leccion, body)})
            if ruta == "/api/teoria/leida":
                return self._json({"nueva": db.marcar_leida(int(body.get("id", 0)))})
            if ruta == "/api/teoria/borrar":
                db.borrar_leccion(int(body["id"]))
                return self._json({"ok": True})
            if ruta == "/api/guias/bajar_paquetes":
                return self._json({"trabajo": lanzar(t_bajar_paquetes, body, gpu=False)})
            if ruta == "/api/guias/bajar_cisco":
                return self._json({"trabajo": lanzar(t_bajar_cisco, body)})
            if ruta == "/api/guias/abrir_url":  # abre una guía de Cisco en tu navegador predeterminado
                url = str(body.get("url", ""))
                if os.name == "nt" and url.startswith(_BASE_CISCO + "/"):
                    os.startfile(url)
                    return self._json({"ok": True})
                return self._json({"ok": False, "error": "URL no permitida"})
            if ruta == "/api/guias/indexar":
                return self._json({"trabajo": lanzar(t_indexar_guias, body)})
            if ruta == "/api/guias/buscar":
                return self._json({"resultados": guias.buscar(GUIAS_DB, str(body.get("q", ""))[:500], 5)})
            if ruta == "/api/guias/abrir":
                if os.name == "nt":
                    os.makedirs(GUIAS, exist_ok=True)
                    os.startfile(GUIAS)
                return self._json({"ok": True})
            if ruta == "/api/wireshark/borrar":
                db.borrar_captura(int(body["id"]))
                return self._json({"ok": True})
            if ruta == "/api/wireshark/capturar":
                return self._json({"trabajo": lanzar(t_capturar, body, gpu=False)})
            if ruta == "/api/wireshark/bpf":
                tuyo = ws.compilar_bpf(str(body.get("filtro", "")).strip())
                if not tuyo["ok"]:
                    return self._json({"ok": False, "correcto": False, "error": tuyo["error"]})
                refs = [str(x) for x in (body.get("refs") or [])][:4]
                for ref in refs:
                    r = ws.compilar_bpf(ref)
                    if r["ok"] and ws.equivalentes_bpf(r["codigo"], tuyo["codigo"], refs + [str(body.get("filtro", ""))]):
                        return self._json({"ok": True, "correcto": True})
                return self._json({"ok": True, "correcto": False, "instrucciones": len(tuyo["codigo"]),
                                   "error": "Es un filtro válido, pero no captura lo mismo que se pide."})
            if ruta == "/api/wireshark/analizar":
                return self._json({"trabajo": lanzar(t_analizar_captura, body)})
            if ruta == "/api/leer_captura":
                return self._json({"trabajo": lanzar(t_leer_captura, body)})
            if ruta == "/api/simulacro/generar":
                return self._json({"trabajo": lanzar(t_generar_simulacro, body)})
            if ruta == "/api/subneteo/resultado":
                total = max(int(body.get("total", 0)), 0)
                buenas = min(max(float(body.get("buenas", 0)), 0), total)
                if total:
                    eid = db.guardar_examen({"titulo": str(body.get("titulo") or "Subneteo rápido")[:80], "tema": "ipv4", "nivel": "Básico",
                                             "preguntas": [], "subneteo": True,
                                             "segundos": int(body.get("segundos", 0))})
                    db.guardar_resultado_examen(eid, {"detalle": [], "buenas": buenas, "total": total,
                                                      "calificacion": round(10 * buenas / total, 1)})
                return self._json({"ok": True})
            if ruta == "/api/constructor/generar":
                return self._json({"trabajo": lanzar(t_generar_topologia, body)})
            if ruta == "/api/reiniciar":
                if hay_trabajo_activo():
                    return self._json({"ok": False, "error": "Hay un trabajo en curso; espera a que termine."})
                self._json({"ok": True})
                REINICIAR.set()
                threading.Thread(target=SERVIDOR.shutdown, daemon=True).start()
                return
            if ruta == "/api/cerrar":
                self._json({"ok": True})
                threading.Thread(target=apagar, daemon=True).start()
                return
            return self._json({"error": "ruta desconocida"}, 404)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


# --------------------------------------------------------------------------- #
# Arranque y cierre limpio
# --------------------------------------------------------------------------- #
_apagado = threading.Event()
REINICIAR = threading.Event()  # para cargar código nuevo sin cerrar la ventana


def liberar_vram():
    for m in list(MODELOS_USADOS):
        ollama.unload(m)


def apagar():
    if _apagado.is_set():
        return
    _apagado.set()
    liberar_vram()
    try:
        # con el SIEM instalado, suspendemos (savestate) para reanudar al instante la próxima vez (Elastic/Kibana vivos);
        # si no, apagado normal. En ambos casos la VM deja de gastar RAM/CPU.
        if vm.siem_instalado() and vm.corriendo() and not vm.espacio()["poco"]:
            if not vm.suspender():
                vm.apagar()
        else:
            vm.apagar()
    except Exception:  # noqa: BLE001
        pass
    db.cerrar()
    limpiar_tmp()
    if SERVIDOR is not None:
        threading.Thread(target=SERVIDOR.shutdown, daemon=True).start()


def vigilante():
    """Si cierras la ventana, ya no llegan latidos: la app se apaga sola y libera la VRAM."""
    while not _apagado.is_set():
        time.sleep(5)
        t = ULTIMO_LATIDO["t"]
        if t and time.time() - t > SIN_LATIDO_SEG and not hay_trabajo_activo():
            print("Ventana cerrada: apagando y liberando VRAM.")
            apagar()


def proteger_cierre_de_consola():
    """En Windows, cerrar la consola con la X también libera la VRAM (igual que tu asistente)."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    def manejador(evento):
        liberar_vram()
        return False

    proteger_cierre_de_consola.ref = manejador  # que no lo recoja el recolector de basura
    ctypes.windll.kernel32.SetConsoleCtrlHandler(manejador, True)


def abrir_ventana(url: str):
    """Abre la app en su propia ventana (modo app de Edge); si no, en el navegador normal."""
    if os.environ.get("LABCCNA_SIN_VENTANA"):
        return
    if os.name == "nt":
        for edge in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                     r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.isfile(edge):
                subprocess.Popen([edge, f"--app={url}", "--window-size=1400,900"], close_fds=True)
                return
    webbrowser.open(url)


def main():
    global SERVIDOR
    os.makedirs(DATOS, exist_ok=True)
    if os.path.exists(ERROR_RUTA):
        os.remove(ERROR_RUTA)
    limpiar_tmp()  # por si la vez anterior se cerró de golpe
    db.abrir(os.path.join(DATOS, "historial.db"))
    url = f"http://127.0.0.1:{PUERTO}/"
    # En Windows, SO_REUSEADDR deja que DOS NetLab escuchen el mismo puerto (y contesta el viejo): se apaga.
    ThreadingHTTPServer.allow_reuse_address = os.name != "nt"
    ThreadingHTTPServer.request_queue_size = 128  # la página pide ~20 archivos a la vez: con la cola de 5 se perdían conexiones
    ThreadingHTTPServer.daemon_threads = True
    intentos = 10 if os.environ.get("LABCCNA_SIN_VENTANA") else 1  # tras un reinicio, el puerto tarda un instante en soltarse
    for i in range(intentos):
        try:
            SERVIDOR = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
            break
        except OSError:
            if i + 1 < intentos:
                time.sleep(0.5)
                continue
            print("La app ya estaba abierta; abro la ventana.")
            abrir_ventana(url)
            return
    SERVIDOR.daemon_threads = True
    atexit.register(apagar)
    proteger_cierre_de_consola()
    threading.Thread(target=vigilante, daemon=True).start()
    if CONFIG.get("vm_auto_calentar", True):
        try:  # el SIEM se calienta solo mientras estudias otra cosa (no bloquea jobs ni /api/reiniciar)
            vm.calentar_en_fondo(bool(CONFIG.get("vm_auto_caliente", True)))
        except Exception:  # noqa: BLE001
            pass
    print(f"NetLab en {url}  (Ctrl+C para cerrar)")
    abrir_ventana(url)
    try:
        SERVIDOR.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if REINICIAR.is_set() and not _apagado.is_set():
            # Reinicio: no libera la VRAM ni abre otra ventana; la ventana actual se reconecta sola
            _apagado.set()
            db.cerrar()
            SERVIDOR.server_close()
            entorno = dict(os.environ, LABCCNA_SIN_VENTANA="1")
            subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__)], env=entorno, cwd=AQUI,
                             close_fds=True)
            os._exit(0)
        apagar()
        SERVIDOR.server_close()
        print("Cerrado. VRAM liberada.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        os.makedirs(DATOS, exist_ok=True)
        with open(ERROR_RUTA, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
