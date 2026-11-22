"""Historial en SQLite (un solo archivo: datos/historial.db). Es lo único que la app guarda."""
from __future__ import annotations

import datetime
import json
import re
import sqlite3
import threading

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def abrir(ruta: str) -> None:
    global _conn
    _conn = sqlite3.connect(ruta, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript("""
    PRAGMA journal_mode=DELETE;
    CREATE TABLE IF NOT EXISTS practicas(
        id INTEGER PRIMARY KEY, fecha TEXT, tema TEXT, nivel TEXT, titulo TEXT,
        datos TEXT, mejor REAL);
    CREATE TABLE IF NOT EXISTS intentos(
        id INTEGER PRIMARY KEY, practica_id INTEGER, fecha TEXT, calificacion REAL, datos TEXT);
    CREATE TABLE IF NOT EXISTS examenes(
        id INTEGER PRIMARY KEY, fecha TEXT, tema TEXT, nivel TEXT, titulo TEXT,
        datos TEXT, calificacion REAL, resultado TEXT);
    CREATE TABLE IF NOT EXISTS repaso(
        id INTEGER PRIMARY KEY, clave TEXT UNIQUE, area TEXT, tipo TEXT, datos TEXT, caja INTEGER DEFAULT 0,
        proxima TEXT, aciertos INTEGER DEFAULT 0, fallos INTEGER DEFAULT 0, creado TEXT, ultimo TEXT);
    CREATE TABLE IF NOT EXISTS mision_dia(fecha TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS rvb(
        id INTEGER PRIMARY KEY, fecha TEXT, modo TEXT, dificultad TEXT, puntos INTEGER, gano INTEGER, detalle TEXT);
    CREATE TABLE IF NOT EXISTS retos(
        id INTEGER PRIMARY KEY, fecha TEXT, curso TEXT, nivel INTEGER, titulo TEXT, datos TEXT);
    CREATE TABLE IF NOT EXISTS academia(
        mision TEXT PRIMARY KEY, curso TEXT, fecha TEXT, estrellas INTEGER, intentos INTEGER, codigo TEXT);
    CREATE TABLE IF NOT EXISTS linux(
        mision TEXT PRIMARY KEY, fecha TEXT, estrellas INTEGER, intentos INTEGER);
    CREATE TABLE IF NOT EXISTS lecciones(
        id INTEGER PRIMARY KEY, fecha TEXT, tema TEXT, idioma TEXT, titulo TEXT, datos TEXT);
    CREATE TABLE IF NOT EXISTS capturas(
        id INTEGER PRIMARY KEY, fecha TEXT, escenario TEXT, nivel TEXT, titulo TEXT, semilla INTEGER,
        datos TEXT, calificacion REAL, resultado TEXT);
    CREATE TABLE IF NOT EXISTS teoria_cache(clave TEXT PRIMARY KEY, fecha TEXT, datos TEXT);
    CREATE TABLE IF NOT EXISTS indice(item TEXT PRIMARY KEY, estado TEXT, notas TEXT, fecha TEXT);
    """)
    for alter in ("ALTER TABLE lecciones ADD COLUMN leida INTEGER DEFAULT 0",):
        try:
            _conn.execute(alter)
        except sqlite3.OperationalError:
            pass  # ya existe
    _conn.commit()


def cerrar() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def _ahora() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _q(sql: str, args=(), one=False, commit=False):
    with _lock:
        cur = _conn.execute(sql, args)
        if commit:
            _conn.commit()
            return cur.lastrowid
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


# ---- prácticas -------------------------------------------------------------- #
def guardar_practica(p: dict) -> int:
    return _q("INSERT INTO practicas(fecha,tema,nivel,titulo,datos,mejor) VALUES(?,?,?,?,?,NULL)",
              (_ahora(), p.get("tema", ""), p.get("nivel", ""), p.get("titulo", ""),
               json.dumps(p, ensure_ascii=False)), commit=True)


def practica(pid: int) -> dict | None:
    r = _q("SELECT * FROM practicas WHERE id=?", (pid,), one=True)
    if not r:
        return None
    p = json.loads(r["datos"])
    p["id"] = r["id"]
    p["mejor"] = r["mejor"]
    p["fecha"] = r["fecha"]
    return p


def guardar_intento(pid: int, calif: float, datos: dict) -> None:
    _q("INSERT INTO intentos(practica_id,fecha,calificacion,datos) VALUES(?,?,?,?)",
       (pid, _ahora(), calif, json.dumps(datos, ensure_ascii=False)), commit=True)
    _q("UPDATE practicas SET mejor = MAX(COALESCE(mejor,0), ?) WHERE id=?", (calif, pid), commit=True)


def borrar_practica(pid: int) -> None:
    _q("DELETE FROM intentos WHERE practica_id=?", (pid,), commit=True)
    _q("DELETE FROM practicas WHERE id=?", (pid,), commit=True)


# ---- exámenes --------------------------------------------------------------- #
# A qué MUNDO pertenece un examen (para XP, misión del día e historial). Antes todo caía en CCNA.
MUNDO_EXAMEN_SQL = (
    "CASE WHEN COALESCE(json_extract(datos,'$.dominio'), 'ccna') NOT IN ('ccna', '') THEN json_extract(datos,'$.dominio')"
    " WHEN tema = 'linux' OR tema LIKE 'lx\\_%' ESCAPE '\\' OR tema LIKE 'jefe\\_lx\\_%' ESCAPE '\\' THEN 'linux'"
    " WHEN tema = 'wireshark' OR tema LIKE 'ws\\_%' ESCAPE '\\' OR tema LIKE 'jefe\\_ws\\_%' ESCAPE '\\' THEN 'wireshark'"
    " WHEN tema = 'retos' AND json_extract(datos,'$.reto') IN ('linux','wireshark') THEN json_extract(datos,'$.reto')"
    " ELSE 'ccna' END")


def mundo_de_tema(tema: str) -> str:
    """Mundo a partir del id del tema (lx_*, ws_*, jefe_lx_*, jefe_ws_*)."""
    t = tema or ""
    if t == "linux" or t.startswith(("lx_", "jefe_lx_")):
        return "linux"
    if t == "wireshark" or t.startswith(("ws_", "jefe_ws_")):
        return "wireshark"
    return "ccna"


def guardar_examen(e: dict) -> int:
    return _q("INSERT INTO examenes(fecha,tema,nivel,titulo,datos) VALUES(?,?,?,?,?)",
              (_ahora(), e.get("tema", ""), e.get("nivel", ""), e.get("titulo", ""),
               json.dumps(e, ensure_ascii=False)), commit=True)


def examen(eid: int) -> dict | None:
    r = _q("SELECT * FROM examenes WHERE id=?", (eid,), one=True)
    if not r:
        return None
    e = json.loads(r["datos"])
    e["id"] = r["id"]
    e["calificacion"] = r["calificacion"]
    e["resultado"] = json.loads(r["resultado"]) if r["resultado"] else None
    return e


def guardar_resultado_examen(eid: int, res: dict) -> None:
    # al repetir un examen se queda tu mejor nota (el detalle es el del último intento)
    _q("UPDATE examenes SET calificacion=MAX(COALESCE(calificacion,0),?), resultado=? WHERE id=?",
       (res["calificacion"], json.dumps(res, ensure_ascii=False), eid), commit=True)


# ---- misiones de Linux ------------------------------------------------------- #
def guardar_mision(mision: str, estrellas: int) -> dict:
    r = _q("SELECT estrellas, intentos FROM linux WHERE mision=?", (mision,), one=True)
    antes = r["estrellas"] if r else 0
    if r:
        _q("UPDATE linux SET estrellas=MAX(estrellas,?), intentos=intentos+1, fecha=? WHERE mision=?",
           (estrellas, _ahora(), mision), commit=True)
    else:
        _q("INSERT INTO linux(mision,fecha,estrellas,intentos) VALUES(?,?,?,1)", (mision, _ahora(), estrellas), commit=True)
    return {"antes": antes, "ahora": max(antes, estrellas)}


def guardar_rvb(modo: str, dif: str, puntos: int, gano: bool, detalle: str) -> None:
    _q("INSERT INTO rvb(fecha,modo,dificultad,puntos,gano,detalle) VALUES(?,?,?,?,?,?)",
       (_ahora(), modo, dif, puntos, int(gano), detalle), commit=True)


def misiones() -> dict[str, int]:
    return {r["mision"]: r["estrellas"] for r in _q("SELECT mision, estrellas FROM linux")}


# ---- academia (Rust / IA / Procesadores) ----------------------------------- #
def guardar_academia(mision: str, curso: str, estrellas: int, codigo: str) -> dict:
    r = _q("SELECT estrellas FROM academia WHERE mision=?", (mision,), one=True)
    antes = r["estrellas"] if r else 0
    if r:
        _q("UPDATE academia SET estrellas=MAX(estrellas,?), intentos=intentos+1, fecha=?, codigo=? WHERE mision=?",
           (estrellas, _ahora(), codigo, mision), commit=True)
    else:
        _q("INSERT INTO academia(mision,curso,fecha,estrellas,intentos,codigo) VALUES(?,?,?,?,1,?)",
           (mision, curso, _ahora(), estrellas, codigo), commit=True)
    return {"antes": antes, "ahora": max(antes, estrellas)}


def guardar_reto(curso: str, nivel: int, r: dict) -> int:
    return _q("INSERT INTO retos(fecha,curso,nivel,titulo,datos) VALUES(?,?,?,?,?)",
              (_ahora(), curso, nivel, r.get("titulo", ""), json.dumps(r, ensure_ascii=False)), commit=True)


def reto(rid: int) -> dict | None:
    r = _q("SELECT * FROM retos WHERE id=?", (rid,), one=True)
    return {**json.loads(r["datos"]), "id": f"g{r['id']}", "curso": r["curso"], "nivel": r["nivel"]} if r else None


def retos(curso: str) -> list[dict]:
    return [{"id": f"g{r['id']}", "titulo": r["titulo"], "nivel": r["nivel"], "fecha": r["fecha"]}
            for r in _q("SELECT id, titulo, nivel, fecha FROM retos WHERE curso=? ORDER BY id DESC LIMIT 40", (curso,))]


def academia() -> dict[str, dict]:
    return {r["mision"]: {"estrellas": r["estrellas"], "codigo": r["codigo"]} for r in _q("SELECT mision, estrellas, codigo FROM academia")}


# ---- lecciones de teoría ----------------------------------------------------- #
def guardar_leccion(l: dict) -> int:
    return _q("INSERT INTO lecciones(fecha,tema,idioma,titulo,datos) VALUES(?,?,?,?,?)",
              (_ahora(), l["tema"], l["idioma"], l.get("titulo", ""), json.dumps(l, ensure_ascii=False)), commit=True)


def leccion(lid: int) -> dict | None:
    r = _q("SELECT * FROM lecciones WHERE id=?", (lid,), one=True)
    if not r:
        return None
    l = json.loads(r["datos"])
    l.update(id=r["id"], fecha=r["fecha"], leida=bool(r["leida"]))
    return l


def teoria_cache(clave: str) -> dict | None:
    """Teoría a fondo de una misión ya generada (se genera una vez y se reutiliza)."""
    r = _q("SELECT datos FROM teoria_cache WHERE clave=?", (clave,), one=True)
    return json.loads(r["datos"]) if r else None


def guardar_teoria_cache(clave: str, datos: dict) -> None:
    _q("INSERT OR REPLACE INTO teoria_cache(clave, fecha, datos) VALUES(?,?,?)",
       (clave, _ahora(), json.dumps(datos, ensure_ascii=False)), commit=True)


def lecciones() -> list[dict]:
    return [dict(r) for r in _q("SELECT id, fecha, tema, idioma, titulo, leida, COALESCE(json_extract(datos,'$.version'), 1) AS version "
                                "FROM lecciones ORDER BY id DESC")]


def actualizar_leccion(lid: int, l: dict) -> None:
    """Reemplaza el contenido de una lección (p. ej. al pasarla al formato nuevo) conservando su id, fecha y si ya la leíste."""
    l = {k: v for k, v in l.items() if k not in ("id", "fecha", "leida")}
    _q("UPDATE lecciones SET titulo=?, datos=? WHERE id=?", (l.get("titulo", ""), json.dumps(l, ensure_ascii=False), lid), commit=True)


def marcar_leida(lid: int) -> bool:
    r = _q("SELECT leida FROM lecciones WHERE id=?", (lid,), one=True)
    if not r or r["leida"]:
        return False
    _q("UPDATE lecciones SET leida=1, fecha=? WHERE id=?", (_ahora(), lid), commit=True)
    return True


def borrar_leccion(lid: int) -> None:
    _q("DELETE FROM lecciones WHERE id=?", (lid,), commit=True)


# ---- capturas de Wireshark (solo la semilla: el .pcap se regenera igual cuando hace falta) ---- #
def guardar_captura(c: dict) -> int:
    datos = {k: c[k] for k in ("preguntas", "filtros", "temas", "paquetes", "validada")}
    return _q("INSERT INTO capturas(fecha,escenario,nivel,titulo,semilla,datos) VALUES(?,?,?,?,?,?)",
              (_ahora(), c["escenario"], c["nivel"], c["titulo"], c["semilla"],
               json.dumps(datos, ensure_ascii=False)), commit=True)


def captura(cid: int) -> dict | None:
    r = _q("SELECT * FROM capturas WHERE id=?", (cid,), one=True)
    if not r:
        return None
    c = json.loads(r["datos"])
    c.update({k: r[k] for k in ("id", "fecha", "escenario", "nivel", "titulo", "semilla", "calificacion")})
    c["resultado"] = json.loads(r["resultado"]) if r["resultado"] else None
    return c


def guardar_resultado_captura(cid: int, res: dict) -> None:
    _q("UPDATE capturas SET calificacion=MAX(COALESCE(calificacion,0),?), resultado=? WHERE id=?",
       (res["calificacion"], json.dumps(res, ensure_ascii=False), cid), commit=True)


def borrar_captura(cid: int) -> None:
    _q("DELETE FROM capturas WHERE id=?", (cid,), commit=True)


def progreso_wireshark() -> dict[str, dict]:
    return {r["escenario"]: {"mejor": r["m"] or 0, "intentos": r["n"]}
            for r in _q("SELECT escenario, MAX(calificacion) AS m, COUNT(*) AS n FROM capturas GROUP BY escenario")}


# ---- historial y progreso --------------------------------------------------- #
def historial(limite: int = 200) -> list[dict]:
    p = _q("SELECT id, fecha, tema, nivel, titulo, mejor AS calificacion, 'practica' AS clase,"
           " (SELECT COUNT(*) FROM intentos i WHERE i.practica_id=practicas.id) AS intentos"
           " FROM practicas")
    e = _q("SELECT id, fecha, tema, nivel, titulo, calificacion, 'examen' AS clase, 0 AS intentos, "
           + MUNDO_EXAMEN_SQL + " AS mundo FROM examenes")
    w = _q("SELECT id, fecha, 'wireshark' AS tema, nivel, titulo, calificacion, 'wireshark' AS clase,"
           " 0 AS intentos FROM capturas")
    rv = _q("SELECT id, fecha, 'rvb' AS tema, dificultad AS nivel, 'Red vs Blue (' || modo || ')' AS titulo,"
            " ROUND(puntos / 100.0, 1) AS calificacion, 'rvb' AS clase, 0 AS intentos FROM rvb")
    filas = [dict(r) for r in p] + [dict(r) for r in e] + [dict(r) for r in w] + [dict(r) for r in rv]
    filas.sort(key=lambda r: r["fecha"], reverse=True)
    return filas[:limite]


def progreso() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in _q("SELECT tema, MAX(mejor) AS m, COUNT(*) AS n FROM practicas GROUP BY tema"):
        out.setdefault(r["tema"], {"mejor": 0, "practicas": 0, "examenes": 0})
        out[r["tema"]]["practicas"] = r["n"]
        out[r["tema"]]["mejor_practica"] = r["m"]
    for r in _q("SELECT tema, MAX(calificacion) AS m, COUNT(calificacion) AS n FROM examenes GROUP BY tema"):
        out.setdefault(r["tema"], {"mejor": 0, "practicas": 0, "examenes": 0})
        out[r["tema"]]["examenes"] = r["n"]
        out[r["tema"]]["mejor_examen"] = r["m"]
    for v in out.values():
        notas = [x for x in (v.get("mejor_practica"), v.get("mejor_examen")) if x is not None]
        # Para dominar un tema de laboratorio cuenta lo mejor de práctica y examen por igual
        v["mejor"] = round(sum(notas) / len(notas), 1) if notas else 0
    return out


# ---- datos para el modo juego (XP, niveles, logros) -------------------------- #
def para_juego() -> dict:
    pr = [dict(r) for r in _q("SELECT fecha, tema, mejor, json_extract(datos,'$.modo') AS modo FROM practicas")]
    ex = [dict(r) for r in _q("SELECT fecha, tema, calificacion, json_extract(datos,'$.simulacro') AS simulacro, "
                               "json_extract(datos,'$.subneteo') AS subneteo, " + MUNDO_EXAMEN_SQL + " AS mundo FROM examenes")]
    ws = [dict(r) for r in _q("SELECT fecha, escenario, calificacion FROM capturas")]
    lx = [dict(r) for r in _q("SELECT fecha, mision, estrellas FROM linux")]
    le = [dict(r) for r in _q("SELECT fecha FROM lecciones WHERE leida = 1")]  # solo cuenta lo que de verdad leíste
    rv = [dict(r) for r in _q("SELECT fecha, modo, dificultad, puntos, gano FROM rvb")]
    rp = [dict(r) for r in _q("SELECT ultimo AS fecha, aciertos, caja FROM repaso")]
    md = [dict(r) for r in _q("SELECT fecha FROM mision_dia")]
    ac = [dict(r) for r in _q("SELECT fecha, curso, mision, estrellas FROM academia")]
    ix = [dict(r) for r in _q("SELECT fecha, item, estado FROM indice WHERE estado = 'hecha'")]
    return {"academia": ac, "practicas": pr, "examenes": ex, "capturas": ws, "linux": lx, "lecciones": le, "rvb": rv, "repaso": rp, "mision_dia": md,
            "indice": ix}


# ---- mapa de MITRE ATT&CK: qué técnicas ya DETECTASTE/CONTUVISTE en NetLab ------- #
def evidencia_mitre() -> dict:
    """Jugadas de Red vs Blue que bloqueaste (en Linux: partidas ganadas), casos SOC resueltos y capturas de Wireshark."""
    rvb = set()
    for r in _q("SELECT modo, gano, detalle FROM rvb"):
        det = r["detalle"] or ""
        for acc, res in re.findall(r'"accion":\s*"(\w+)",\s*"resultado":\s*"(\w+)"', det):
            if res == "bloqueado" or (r["modo"] == "linux" and r["gano"]):
                rvb.add(f"{r['modo']}:{acc}")
    soc = sorted({m.group(1) for r in _q("SELECT mision FROM academia WHERE curso='soc' AND estrellas >= 2")
                  for m in [re.match(r"soc_([a-z0-9]+)_\d{8}$", r["mision"])] if m})
    ws = sorted({r["escenario"] for r in _q("SELECT escenario FROM capturas WHERE calificacion >= 7")})
    return {"rvb": sorted(rvb), "soc": soc, "ws": ws}


# ---- mundo índice (TryHackMe / HTB / labs locales): solo tu avance y tus notas ------- #
def indice() -> dict:
    return {r["item"]: {"estado": r["estado"], "notas": r["notas"] or "", "fecha": r["fecha"]} for r in _q("SELECT * FROM indice")}


def guardar_indice(item: str, estado: str | None, notas: str | None) -> dict:
    r = _q("SELECT estado, notas FROM indice WHERE item=?", (item,), one=True)
    est = estado if estado is not None else (r["estado"] if r else "pendiente")
    nts = notas if notas is not None else (r["notas"] if r else "")
    if est == "pendiente" and not nts:
        _q("DELETE FROM indice WHERE item=?", (item,), commit=True)
    else:
        _q("INSERT INTO indice(item,estado,notas,fecha) VALUES(?,?,?,?) ON CONFLICT(item) DO UPDATE SET estado=excluded.estado,"
           " notas=excluded.notas, fecha=excluded.fecha", (item, est, nts, _ahora()), commit=True)
    return {"item": item, "estado": est, "notas": nts}


# ---- cuaderno de errores (repaso espaciado tipo Leitner) --------------------- #
INTERVALOS = [1, 2, 4, 8, 16, 32, 60]  # días según la caja


def _hoy() -> str:
    return datetime.date.today().isoformat()


def agregar_repaso(clave: str, area: str, tipo: str, datos: dict) -> None:
    """Una pregunta que fallaste entra (o vuelve a la caja 0) y se repasa mañana."""
    manana = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    r = _q("SELECT id FROM repaso WHERE clave=?", (clave,), one=True)
    if r:
        _q("UPDATE repaso SET caja=0, proxima=?, fallos=fallos+1 WHERE id=?", (manana, r["id"]), commit=True)
    else:
        _q("INSERT INTO repaso(clave,area,tipo,datos,caja,proxima,creado) VALUES(?,?,?,?,0,?,?)",
           (clave[:300], area, tipo, json.dumps(datos, ensure_ascii=False), manana, _ahora()), commit=True)


def repasos_pendientes(limite: int = 30) -> list[dict]:
    filas = _q("SELECT * FROM repaso WHERE proxima <= ? ORDER BY caja, proxima LIMIT ?", (_hoy(), limite))
    return [{**{k: r[k] for k in ("id", "area", "tipo", "caja", "aciertos", "fallos")}, "datos": json.loads(r["datos"])} for r in filas]


def responder_repaso(rid: int, bien: bool) -> dict:
    r = _q("SELECT caja FROM repaso WHERE id=?", (rid,), one=True)
    if not r:
        return {}
    caja = min(r["caja"] + 1, len(INTERVALOS) - 1) if bien else 0
    prox = (datetime.date.today() + datetime.timedelta(days=INTERVALOS[caja])).isoformat()
    _q(f"UPDATE repaso SET caja=?, proxima=?, {'aciertos=aciertos+1' if bien else 'fallos=fallos+1'}, ultimo=? WHERE id=?",
       (caja, prox, _ahora(), rid), commit=True)
    return {"caja": caja, "proxima": prox}


def resumen_repaso() -> dict:
    t = _q("SELECT COUNT(*) n, SUM(proxima <= ?) pend, SUM(caja >= 4) dom FROM repaso", (_hoy(),), one=True)
    hoy = _q("SELECT COUNT(*) n FROM repaso WHERE ultimo LIKE ?", (_hoy() + "%",), one=True)
    return {"total": t["n"] or 0, "pendientes": t["pend"] or 0, "dominadas": t["dom"] or 0, "hechos_hoy": hoy["n"] or 0}


def actividad_de_hoy() -> dict:
    h = _hoy() + "%"
    c = lambda sql: (_q(sql, (h,), one=True) or {"n": 0})["n"]  # noqa: E731
    return {
        # solo exámenes de CCNA (antes un examen de Linux/Wireshark marcaba la tarea de CCNA)
        "examenes": c("SELECT COUNT(*) n FROM examenes WHERE fecha LIKE ? AND calificacion IS NOT NULL AND json_extract(datos,'$.subneteo') IS NULL AND tema != 'retos'"
                      " AND " + MUNDO_EXAMEN_SQL + " = 'ccna'"),
        "examenes_linux": c("SELECT COUNT(*) n FROM examenes WHERE fecha LIKE ? AND calificacion IS NOT NULL AND tema != 'retos'"
                            " AND " + MUNDO_EXAMEN_SQL + " = 'linux'"),
        "examenes_wireshark": c("SELECT COUNT(*) n FROM examenes WHERE fecha LIKE ? AND calificacion IS NOT NULL AND tema != 'retos'"
                                " AND " + MUNDO_EXAMEN_SQL + " = 'wireshark'"),
        "practicas": c("SELECT COUNT(*) n FROM intentos WHERE fecha LIKE ?"),
        "subneteo": c("SELECT COUNT(*) n FROM examenes WHERE fecha LIKE ? AND json_extract(datos,'$.subneteo')"),
        "retos": c("SELECT COUNT(*) n FROM examenes WHERE fecha LIKE ? AND tema = 'retos'"),
        "wireshark": c("SELECT COUNT(*) n FROM capturas WHERE fecha LIKE ? AND calificacion IS NOT NULL"),
        "linux": c("SELECT COUNT(*) n FROM linux WHERE fecha LIKE ?"),
        "rvb": c("SELECT COUNT(*) n FROM rvb WHERE fecha LIKE ?"),
        "lecciones": c("SELECT COUNT(*) n FROM lecciones WHERE fecha LIKE ? AND leida = 1"),
    }


def marcar_mision_dia() -> bool:
    if _q("SELECT fecha FROM mision_dia WHERE fecha=?", (_hoy(),), one=True):
        return False
    _q("INSERT INTO mision_dia(fecha) VALUES(?)", (_hoy(),), commit=True)
    return True
