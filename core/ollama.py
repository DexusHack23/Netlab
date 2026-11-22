"""Cliente mínimo de Ollama (solo biblioteca estándar) con liberación de VRAM."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
KEEP_ALIVE = "2m"  # cuánto se queda el modelo en VRAM tras usarlo (la app lo ajusta por rol)
IDIOMA = "es"  # idioma del alumno; con "en" todo lo que escribe la IA sale en inglés
_EN = ("\n\nIMPORTANT: the student studies in ENGLISH. Write ALL natural-language text (titles, explanations, questions, "
       "options, tasks, hints, feedback) in clear English, even if other instructions say Spanish. Keep JSON keys, IOS/Linux "
       "commands and filters exactly as specified.")


class OllamaError(RuntimeError):
    pass


def _post(path: str, body: dict, timeout: float = 900) -> dict:
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise OllamaError(f"Ollama respondió {e.code}: {detail[:300]}") from None
    except urllib.error.URLError as e:
        raise OllamaError("No pude conectar con Ollama. ¿Está abierto? (ollama serve)") from e


def _get(path: str, timeout: float = 5) -> dict:
    try:
        with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def list_models() -> list[str]:
    return sorted(m["name"] for m in _get("/api/tags").get("models", []))


def loaded_models() -> list[str]:
    return [m["name"] for m in _get("/api/ps").get("models", [])]


def loaded_detail() -> list[dict]:
    """Modelos cargados con cuánto ocupan y cuánto está en la GPU (si no cabe, va lento)."""
    out = []
    for m in _get("/api/ps").get("models", []):
        size, vram = m.get("size", 0), m.get("size_vram", 0)
        out.append({"modelo": m["name"], "gb": round(size / 1e9, 1), "gb_gpu": round(vram / 1e9, 1),
                    "pct_gpu": round(100 * vram / size) if size else 0, "contexto": m.get("context_length")})
    return out


ULTIMA_LLAMADA: dict = {}
HISTORIAL_LLAMADAS: list[dict] = []  # solo en memoria, para diagnosticar


def diagnostico(model: str) -> dict:
    """Mide la velocidad real: texto libre y JSON con esquema."""
    res = {}
    for nombre, extra in (("libre", {}), ("json", {"format": {"type": "object", "properties": {
            "a": {"type": "string"}, "b": {"type": "array", "items": {"type": "string"}}}, "required": ["a", "b"]}})):
        body = {"model": model, "stream": False, "keep_alive": "2m",
                "messages": [{"role": "user", "content": "Da 3 comandos IOS para crear la VLAN 10 y explícalos en 1 línea."}],
                "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 800}, **extra}
        if model.startswith("gpt-oss"):
            body["think"] = "low"
        elif model.startswith("qwen3") and "instruct" not in model:
            body["think"] = False
        d = _post("/api/chat", body, timeout=300)
        res[nombre] = {"tokens": d.get("eval_count"),
                       "tok_s": round(d.get("eval_count", 0) / (d.get("eval_duration", 1) / 1e9), 1),
                       "carga_s": round(d.get("load_duration", 0) / 1e9, 1),
                       "total_s": round(d.get("total_duration", 0) / 1e9, 1),
                       "pensamiento_chars": len((d.get("message") or {}).get("thinking") or ""),
                       "respuesta_chars": len((d.get("message") or {}).get("content") or "")}
    res["gpu"] = loaded_detail()
    return res


def unload(model: str) -> None:
    try:
        _post("/api/generate", {"model": model, "keep_alive": 0}, timeout=15)
    except OllamaError:
        pass


def unload_all() -> None:
    for m in loaded_models():
        unload(m)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


# Algunos modelos locales (sobre todo los de origen chino, tipo qwen) filtran caracteres chinos/japoneses/coreanos.
_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿豈-﫿＀-￯]")


def _cjk_n(s: str) -> int:
    return len(_CJK.findall(s or ""))


def chat(model: str, messages: list[dict], *, schema: dict | None = None, temperature: float = 0.4,
         keep_alive: str | None = None, num_ctx: int = 8192, num_predict: int = 6000, idioma_fijo: bool = False) -> str:
    if IDIOMA == "en" and not idioma_fijo and messages and messages[0].get("role") == "system":
        messages = [{**messages[0], "content": messages[0]["content"] + _EN}] + messages[1:]
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive or KEEP_ALIVE,
        # tope de tokens: si el modelo se cicla (pasa con JSON forzado) no se queda minutos generando
        "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict},
    }
    if schema is not None:
        body["format"] = schema
    # Los modelos con razonamiento (qwen3, gpt-oss) piensan menos = responden más rápido.
    if model.startswith("gpt-oss"):
        body["think"] = "low"
    elif (model.startswith("qwen3") and "instruct" not in model) or model.startswith(("gemma", "deepseek")):
        # Probado en tu PC: con JSON forzado, gemma4 se gastaba todo el tope de tokens pensando y
        # devolvía la respuesta vacía. Sin razonamiento responde en segundos y el verificador cuida lo demás.
        body["think"] = False
    try:
        data = _post("/api/chat", body)
    except OllamaError as e:
        if "think" in str(e).lower() and "think" in body:  # modelo o versión de Ollama sin 'think'
            body.pop("think")
            data = _post("/api/chat", body)
        else:
            raise
    msg = data.get("message") or {}
    if not (msg.get("content") or "").strip() and (msg.get("thinking") or "").strip() and body.get("think") is not False:
        # Se le acabaron los tokens pensando: una vez más, sin pensar
        body["think"] = False
        try:
            data = _post("/api/chat", body)
        except OllamaError:
            pass
    ULTIMA_LLAMADA.update(modelo=model, tokens=data.get("eval_count"),
                          segundos=round(data.get("total_duration", 0) / 1e9, 1),
                          tok_s=round(data.get("eval_count", 0) / max(data.get("eval_duration", 1) / 1e9, 1e-9), 1),
                          pensamiento=len((data.get("message") or {}).get("thinking") or ""),
                          respuesta=len((data.get("message") or {}).get("content") or ""),
                          fin=data.get("done_reason"), think=body.get("think", "(no enviado)"),
                          inicio=((data.get("message") or {}).get("content") or "")[:200])
    HISTORIAL_LLAMADAS.append(dict(ULTIMA_LLAMADA))
    del HISTORIAL_LLAMADAS[:-20]
    contenido = _strip_think(data.get("message", {}).get("content", ""))
    # guardia de idioma: si el modelo filtró chino/japonés/coreano, reintenta una vez exigiendo el idioma
    if _cjk_n(contenido) > 3 and messages and messages[0].get("role") == "system":
        idi = "English" if IDIOMA == "en" else "español de México"
        refuerzo = (f" CRITICAL: respond EXCLUSIVELY in {idi}. Do NOT output a single Chinese, Japanese or Korean "
                    "character anywhere in the response.")
        body["messages"] = [{**messages[0], "content": messages[0]["content"] + refuerzo}] + messages[1:]
        try:
            d2 = _post("/api/chat", body)
            c2 = _strip_think((d2.get("message") or {}).get("content", ""))
            if c2 and _cjk_n(c2) < _cjk_n(contenido):
                contenido = c2
        except OllamaError:
            pass
    return contenido


def chat_json(model: str, messages: list[dict], schema: dict, **kw) -> dict:
    """Pide JSON con esquema; si el modelo se sale del formato, intenta rescatarlo una vez."""
    last = ""
    for intento in range(2):
        txt = chat(model, messages, schema=schema, **kw)
        last = txt
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", txt, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        messages = messages + [
            {"role": "assistant", "content": txt[:2000]},
            {"role": "user", "content": "Eso no es JSON válido. Responde SOLO con el JSON pedido."},
        ]
    raise OllamaError(f"El modelo no devolvió JSON válido. Inicio de la respuesta: {last[:200]!r}")
