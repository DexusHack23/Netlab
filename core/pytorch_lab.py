"""IA práctica con PyTorch en TU GPU: misiones en Python que NetLab corre en el entorno ia_env y califica con pruebas ocultas.
También: entrenar nanoGPT (Karpathy) desde NetLab."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS_IA = os.path.join(AQUI, "ia", "datos")
_SIN_VENTANA = {"creationflags": 0x08000000} if os.name == "nt" else {}


def python_ia() -> str | None:
    for p in (os.path.join(AQUI, "ia_env", "Scripts", "python.exe"), os.path.join(AQUI, "ia_env", "bin", "python")):
        if os.path.isfile(p):
            return p
    return None


ARNES = r'''
# ======================= pruebas ocultas de NetLab =======================
import traceback as _tb
def prueba(nombre):
    def deco(f):
        try:
            f()
            print("@@OK", nombre, flush=True)
        except Exception as _e:
            print("@@FAIL", nombre, "::", type(_e).__name__, str(_e)[:400].replace("\n", " "), flush=True)
        return f
    return deco
'''


def _correr(codigo: str, carpeta_tmp: str, timeout: int) -> dict:
    py = python_ia()
    if not py:
        return {"ok": False, "fase": "python", "fallo": "Falta el entorno de IA (ia_env). Corre los comandos de instalación de PyTorch."}
    os.makedirs(carpeta_tmp, exist_ok=True)
    d = tempfile.mkdtemp(prefix="py_", dir=carpeta_tmp)
    try:
        f = os.path.join(d, "main.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(codigo)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "NETLAB_DATOS": DATOS_IA}
        try:
            r = subprocess.run([py, "-X", "utf8", f], capture_output=True, timeout=timeout, cwd=d, env=env, **_SIN_VENTANA)
        except subprocess.TimeoutExpired:
            return {"ok": False, "fase": "correr", "fallo": f"Tardó más de {timeout} s (¿entrenamiento demasiado largo o ciclo infinito?)."}
        out = r.stdout.decode("utf-8", "replace").replace(d + os.sep, "").replace(f, "main.py")
        err = r.stderr.decode("utf-8", "replace").replace(f, "main.py")
        return {"ok": True, "codigo_salida": r.returncode, "stdout": out[-20000:], "stderr": err[-6000:]}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def correr(codigo: str, carpeta_tmp: str) -> dict:
    return _correr(codigo, carpeta_tmp, 300)


def calificar(m: dict, codigo: str, carpeta_tmp: str) -> dict:
    reglas = [msg for pat, msg in m.get("requiere", []) if not re.search(pat, codigo, re.M)]
    if re.search(r"raise NotImplementedError", codigo):
        reglas.append("Todavía hay funciones con `raise NotImplementedError`")
    r = _correr(codigo + "\n" + ARNES + "\n" + m["pruebas"], carpeta_tmp, m.get("tiempo", 300))
    if not r["ok"]:
        return {"aprobado": False, **r, "reglas": reglas}
    pruebas = []
    for linea in r["stdout"].splitlines():
        if linea.startswith("@@OK "):
            pruebas.append({"prueba": linea[5:].strip(), "ok": True})
        elif linea.startswith("@@FAIL "):
            nombre, _, det = linea[7:].partition("::")
            pruebas.append({"prueba": nombre.strip(), "ok": False, "detalle": det.strip()})
    if not pruebas:
        return {"aprobado": False, "fase": "correr", "fallo": (r["stderr"] or r["stdout"])[-3000:] or "El programa no llegó a las pruebas.", "reglas": reglas}
    salida = "\n".join(l for l in r["stdout"].splitlines() if not l.startswith("@@"))[-2000:]
    return {"aprobado": all(p["ok"] for p in pruebas) and not reglas, "pruebas": pruebas, "reglas": reglas, "stdout": salida,
            "avisos": r["stderr"][-1500:] if r["codigo_salida"] else ""}


def M(id, titulo, teoria, enunciado, inicial, solucion, pruebas, pistas, jefe=False, tiempo=300, requiere=()):
    return {"id": id, "titulo": titulo, "teoria": teoria.strip(), "enunciado": enunciado.strip(), "inicial": inicial.strip() + "\n",
            "solucion": solucion.strip() + "\n", "pruebas": pruebas.strip(), "pistas": list(pistas), "requiere": list(requiere),
            "prohibido": [], "modo": "python", "salida": "", "entrada": "", "jefe": jefe, "tiempo": tiempo}


CARGAR_MNIST = '''
import os, torch, torchvision
from torchvision import transforms
def datos_mnist():
    t = transforms.ToTensor()
    tr = torchvision.datasets.MNIST(os.environ["NETLAB_DATOS"], train=True, download=False, transform=t)
    te = torchvision.datasets.MNIST(os.environ["NETLAB_DATOS"], train=False, download=False, transform=t)
    return tr, te
'''

EVAL_MNIST = '''
def _exactitud(modelo):
    _, te = datos_mnist()
    dev = next(modelo.parameters()).device
    dl = torch.utils.data.DataLoader(te, batch_size=1000)
    modelo.eval(); bien = 0
    with torch.no_grad():
        for x, y in dl:
            bien += (modelo(x.to(dev)).argmax(1).cpu() == y).sum().item()
    return bien / len(te)
'''

NIVELES_TORCH = [
  {"nombre": "Tensores, GPU y autograd", "cap": "PyTorch básico", "misiones": [
    M("pt0_1", "Tensores en tu GPU",
      """Un **tensor** es un arreglo de n dimensiones (como en NumPy) que puede vivir en la GPU. `torch.cuda.is_available()` dice si
hay GPU; `x.to("cuda")` lo manda allá. Las operaciones entre tensores deben estar en el mismo dispositivo. `@` es multiplicación de matrices.""",
      """1. `dispositivo()`: devuelve `"cuda"` si hay GPU, si no `"cpu"`.
2. `multiplicar(a, b)`: recibe dos listas de listas, las vuelve tensores float32 en `dispositivo()`, las multiplica (matrices) y
devuelve el resultado **en CPU** como tensor.""",
      """import torch

def dispositivo():
    raise NotImplementedError

def multiplicar(a, b):
    raise NotImplementedError

if __name__ == "__main__":
    print(dispositivo(), multiplicar([[1, 2]], [[3], [4]]))""",
      """import torch

def dispositivo():
    return "cuda" if torch.cuda.is_available() else "cpu"

def multiplicar(a, b):
    d = dispositivo()
    x = torch.tensor(a, dtype=torch.float32, device=d)
    y = torch.tensor(b, dtype=torch.float32, device=d)
    return (x @ y).cpu()

if __name__ == "__main__":
    print(dispositivo(), multiplicar([[1, 2]], [[3], [4]]))""",
      """@prueba("usa la GPU si existe")
def _():
    assert dispositivo() == ("cuda" if torch.cuda.is_available() else "cpu")
@prueba("producto de matrices")
def _():
    r = multiplicar([[1, 2], [3, 4]], [[5, 6], [7, 8]])
    assert torch.equal(r, torch.tensor([[19., 22.], [43., 50.]])), r
@prueba("regresa en CPU")
def _():
    assert multiplicar([[1.0]], [[2.0]]).device.type == "cpu"
""", ["`torch.tensor(a, dtype=torch.float32, device=d)`", "`(x @ y).cpu()`"]),
    M("pt0_2", "Autograd: derivadas automáticas",
      """El corazón de PyTorch: si un tensor tiene `requires_grad=True`, PyTorch recuerda las operaciones y `y.backward()` calcula
la derivada de `y` respecto a él en `x.grad`. Así se entrenan TODAS las redes neuronales: derivadas del error respecto a cada peso.""",
      """`derivada(x0)`: devuelve (como `float`) la derivada de `f(x) = x³ + 2x − 5` evaluada en `x0`, **usando autograd** (no la fórmula a mano).""",
      """import torch

def derivada(x0):
    raise NotImplementedError""",
      """import torch

def derivada(x0):
    x = torch.tensor(float(x0), requires_grad=True)
    y = x ** 3 + 2 * x - 5
    y.backward()
    return x.grad.item()""",
      """@prueba("en x=2 vale 14")
def _():
    assert abs(derivada(2) - 14) < 1e-5
@prueba("en x=0 vale 2")
def _():
    assert abs(derivada(0) - 2) < 1e-5
@prueba("en x=-1.5 vale 8.75")
def _():
    assert abs(derivada(-1.5) - 8.75) < 1e-4
""", ["`x = torch.tensor(float(x0), requires_grad=True)`", "Arma `y`, llama `y.backward()` y regresa `x.grad.item()`."],
      requiere=[(r"backward\(", "Usa autograd: `.backward()`")]),
    M("pt0_3", "JEFE: tu primer entrenamiento",
      """Entrenar = repetir: predecir → medir error (pérdida) → `loss.backward()` → `optimizador.step()` → `optimizador.zero_grad()`.
`nn.Linear(1, 1)` es `y = w·x + b`; `nn.MSELoss()` es el error cuadrático medio; `torch.optim.SGD(modelo.parameters(), lr=...)` actualiza.""",
      """`entrenar(xs, ys)`: entrena un `nn.Linear(1, 1)` con esos datos y devuelve `(w, b)` como floats.
Los datos vienen de `y = 3x − 1` con un poco de ruido: debe aprender w ≈ 3 y b ≈ −1.""",
      """import torch
from torch import nn

def entrenar(xs, ys):
    raise NotImplementedError""",
      """import torch
from torch import nn

def entrenar(xs, ys):
    x = torch.tensor(xs, dtype=torch.float32).view(-1, 1)
    y = torch.tensor(ys, dtype=torch.float32).view(-1, 1)
    modelo = nn.Linear(1, 1)
    opt = torch.optim.SGD(modelo.parameters(), lr=0.05)
    perdida = nn.MSELoss()
    for _ in range(2000):
        opt.zero_grad()
        l = perdida(modelo(x), y)
        l.backward()
        opt.step()
    return modelo.weight.item(), modelo.bias.item()""",
      """@prueba("aprende w≈3 y b≈-1")
def _():
    g = torch.Generator().manual_seed(0)
    x = torch.linspace(-2, 2, 200)
    y = 3 * x - 1 + 0.05 * torch.randn(200, generator=g)
    w, b = entrenar(x.tolist(), y.tolist())
    assert abs(w - 3) < 0.05 and abs(b + 1) < 0.05, (w, b)
""", ["Convierte a tensores de forma (N, 1) con `.view(-1, 1)`.", "Ciclo: `opt.zero_grad()`, `l = perdida(modelo(x), y)`, `l.backward()`, `opt.step()`."],
      jefe=True, requiere=[(r"\.step\(\)", "Usa un optimizador (`.step()`)")]),
  ]},
  {"nombre": "Redes neuronales", "cap": "Backprop y visión (MNIST)", "misiones": [
    M("pt1_1", "Backpropagation a mano (XOR)",
      """El perceptrón no puede aprender XOR. Con una **capa oculta** sí. Aquí lo haces sin autograd, con NumPy: propagas hacia adelante,
calculas el error y aplicas la **regla de la cadena** capa por capa (eso es backpropagation). Sigmoide: σ(z)=1/(1+e^−z), σ'=σ(1−σ).""",
      """`entrenar_xor()`: red 2 → 4 (sigmoide) → 1 (sigmoide) entrenada con descenso de gradiente sobre la tabla XOR **sin PyTorch**.
Devuelve una función `predecir(x)` que recibe `[a, b]` y regresa un número entre 0 y 1.""",
      """import numpy as np

def entrenar_xor():
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    Y = np.array([[0], [1], [1], [0]], dtype=float)
    raise NotImplementedError""",
      """import numpy as np

def entrenar_xor():
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    Y = np.array([[0], [1], [1], [0]], dtype=float)
    rng = np.random.default_rng(1)
    W1, b1 = rng.normal(0, 1, (2, 4)), np.zeros(4)
    W2, b2 = rng.normal(0, 1, (4, 1)), np.zeros(1)
    s = lambda z: 1 / (1 + np.exp(-z))
    for _ in range(20000):
        h = s(X @ W1 + b1)
        o = s(h @ W2 + b2)
        d2 = (o - Y) * o * (1 - o)
        d1 = (d2 @ W2.T) * h * (1 - h)
        W2 -= 1.0 * h.T @ d2; b2 -= 1.0 * d2.sum(0)
        W1 -= 1.0 * X.T @ d1; b1 -= 1.0 * d1.sum(0)
    return lambda x: float(s(s(np.array(x, dtype=float) @ W1 + b1) @ W2 + b2)[0])""",
      """@prueba("aprende XOR")
def _():
    p = entrenar_xor()
    for x, y in (([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)):
        assert abs(p(x) - y) < 0.2, (x, p(x))
@prueba("sin PyTorch")
def _():
    import inspect, sys
    assert "torch" not in inspect.getsource(entrenar_xor)
""", ["Adelante: `h = σ(X@W1+b1)`, `o = σ(h@W2+b2)`.", "Atrás: `d2 = (o−Y)·o·(1−o)`, `d1 = (d2@W2.T)·h·(1−h)`; resta `lr·h.T@d2` y `lr·X.T@d1`."]),
    M("pt1_2", "MNIST: reconocer dígitos en tu GPU",
      """MNIST: 70 000 imágenes de dígitos escritos a mano (28×28). Una red densa (MLP) llega a ~98%. `DataLoader` arma lotes;
`nn.CrossEntropyLoss` es la pérdida para clasificar; `Adam` suele entrenar más rápido que SGD. La función `datos_mnist()` ya te da los datos.""",
      """`entrenar()`: crea y entrena en la GPU un MLP (`nn.Flatten`, `nn.Linear`, `nn.ReLU`…) y devuelve el modelo.
Debe lograr **≥ 97 %** en el conjunto de prueba (que tú no ves). Tiempo máximo: 5 min.""",
      CARGAR_MNIST + """
from torch import nn

def entrenar():
    tr, _ = datos_mnist()
    raise NotImplementedError""",
      CARGAR_MNIST + """
from torch import nn

def entrenar():
    tr, _ = datos_mnist()
    d = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = nn.Sequential(nn.Flatten(), nn.Linear(784, 256), nn.ReLU(), nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, 10)).to(d)
    opt = torch.optim.Adam(modelo.parameters(), lr=1e-3)
    f = nn.CrossEntropyLoss()
    dl = torch.utils.data.DataLoader(tr, batch_size=128, shuffle=True)
    for ep in range(4):
        modelo.train()
        for x, y in dl:
            x, y = x.to(d), y.to(d)
            opt.zero_grad(); l = f(modelo(x), y); l.backward(); opt.step()
        print("época", ep + 1, "pérdida", round(l.item(), 4))
    return modelo""",
      EVAL_MNIST + """
@prueba("≥ 97% en prueba")
def _():
    a = _exactitud(entrenar())
    print("exactitud:", round(100 * a, 2), "%")
    assert a >= 0.97, f"{100*a:.2f}%"
""", ["`nn.Sequential(nn.Flatten(), nn.Linear(784, 256), nn.ReLU(), …, nn.Linear(…, 10)).to(d)`", "3-5 épocas con `Adam(lr=1e-3)` y lotes de 128 bastan."], tiempo=420),
    M("pt1_3", "JEFE: red convolucional",
      """Las **convoluciones** (`nn.Conv2d`) recorren la imagen con filtros pequeños que detectan bordes y formas; con `MaxPool2d`
reducen tamaño. Por eso dominan visión por computadora (y tu tesis de baches). Una CNN chica pasa de 99 % en MNIST.""",
      """`entrenar()`: una CNN (al menos una `nn.Conv2d`) que logre **≥ 98.5 %** en prueba, en la GPU.""",
      CARGAR_MNIST + """
from torch import nn

def entrenar():
    tr, _ = datos_mnist()
    raise NotImplementedError""",
      CARGAR_MNIST + """
from torch import nn

def entrenar():
    tr, _ = datos_mnist()
    d = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = nn.Sequential(nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                           nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                           nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Linear(128, 10)).to(d)
    opt = torch.optim.Adam(modelo.parameters(), lr=1e-3)
    f = nn.CrossEntropyLoss()
    dl = torch.utils.data.DataLoader(tr, batch_size=128, shuffle=True)
    for ep in range(3):
        modelo.train()
        for x, y in dl:
            x, y = x.to(d), y.to(d)
            opt.zero_grad(); l = f(modelo(x), y); l.backward(); opt.step()
        print("época", ep + 1, "pérdida", round(l.item(), 4))
    return modelo""",
      EVAL_MNIST + """
@prueba("≥ 98.5% en prueba")
def _():
    a = _exactitud(entrenar())
    print("exactitud:", round(100 * a, 2), "%")
    assert a >= 0.985, f"{100*a:.2f}%"
""", ["Conv2d(1, 32, 3, padding=1) → ReLU → MaxPool2d(2), dos veces; luego Flatten y Linear.", "Tras dos MaxPool la imagen queda de 7×7."],
      jefe=True, tiempo=480, requiere=[(r"Conv2d", "Usa al menos una `nn.Conv2d`")]),
  ]},
  {"nombre": "IA para ciberseguridad", "cap": "Detección de intrusiones", "misiones": [
    M("pt2_1", "JEFE: detector de intrusiones",
      """En un SOC no basta la *exactitud*: si 99 % del tráfico es normal, decir "todo normal" da 99 % y no sirve. Se mide
**precisión** (de lo que marcaste como ataque, cuánto sí era) y **recall** (de los ataques reales, cuántos atrapaste).
Las características de cada conexión: duración, bytes enviados/recibidos, paquetes, puertos distintos, % de SYN, fallos de login.""",
      """`entrenar(X, y)`: recibe un tensor `X` (N×7, características de conexiones) y `y` (0 normal / 1 ataque) y devuelve una función
`predecir(X)` que regresa un tensor de 0/1. En datos nuevos debe lograr **precisión ≥ 0.90** y **recall ≥ 0.90** (los ataques son solo ~8 %).""",
      """import torch
from torch import nn

def entrenar(X, y):
    raise NotImplementedError""",
      """import torch
from torch import nn

def entrenar(X, y):
    media, desv = X.mean(0), X.std(0) + 1e-6
    modelo = nn.Sequential(nn.Linear(X.shape[1], 32), nn.ReLU(), nn.Linear(32, 1))
    opt = torch.optim.Adam(modelo.parameters(), lr=1e-2)
    f = nn.BCEWithLogitsLoss()
    Xn = (X - media) / desv
    for _ in range(1000):
        opt.zero_grad(); l = f(modelo(Xn).squeeze(1), y.float()); l.backward(); opt.step()
    return lambda Z: (torch.sigmoid(modelo((Z - media) / desv).squeeze(1)) > 0.5).long()""",
      """def _trafico(n, semilla):
    g = torch.Generator().manual_seed(semilla)
    ataque = (torch.rand(n, generator=g) < 0.08).long()
    r = lambda: torch.randn(n, generator=g)
    a = ataque.float()
    X = torch.stack([
        (2 + r()).abs() * (1 - 0.3 * a),            # duración
        (8 + r()) + 0.8 * a * r().abs(),            # log(bytes enviados)
        (9 + r()) - 0.9 * a,                        # log(bytes recibidos)
        (20 + 8 * r()).abs() + 9 * a,               # paquetes
        (1 + r().abs()) + 2.2 * a * (0.5 + r().abs()),  # puertos distintos
        (0.1 + 0.08 * r()).abs() + 0.12 * a,        # % de SYN
        (0.5 * r()).abs() + 0.8 * a * r().abs(),    # fallos de login
    ], 1)
    return X, ataque
@prueba("precisión ≥ 0.90 y recall ≥ 0.90")
def _():
    X, y = _trafico(6000, 1)
    p = entrenar(X, y)
    Xt, yt = _trafico(4000, 2)
    pr = p(Xt)
    tp = ((pr == 1) & (yt == 1)).sum().item(); fp = ((pr == 1) & (yt == 0)).sum().item(); fn = ((pr == 0) & (yt == 1)).sum().item()
    prec, rec = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    print(f"precisión {prec:.3f} · recall {rec:.3f} · falsos positivos {fp}")
    assert prec >= 0.90 and rec >= 0.90, (round(prec, 3), round(rec, 3))
""", ["Normaliza las columnas (resta la media y divide entre la desviación): sus escalas son muy distintas.",
      "Si te sale mucho falso positivo o mucho ataque perdido, mueve el umbral (0.5) o entrena más pasos; `pos_weight` sube el recall pero baja la precisión."], jefe=True),
  ]},
  {"nombre": "Transformers", "cap": "Atención y mini GPT", "misiones": [
    M("pt3_1", "Atención escalada",
      """La pieza clave de GPT: **Atención(Q, K, V) = softmax(Q·Kᵀ / √d) · V**. Cada token mira a los demás (Q·Kᵀ = qué tan
relevantes son) y mezcla sus valores V. Con **máscara causal**, un token no puede ver los que vienen después (así se predice la siguiente palabra).""",
      """`atencion(Q, K, V, causal=False)`: tensores de forma (lote, tokens, d). Implementa la fórmula **sin** usar
`scaled_dot_product_attention` (la prueba compara contra ella). Si `causal`, pon −∞ arriba de la diagonal antes del softmax.""",
      """import math, torch

def atencion(Q, K, V, causal=False):
    raise NotImplementedError""",
      """import math, torch

def atencion(Q, K, V, causal=False):
    s = Q @ K.transpose(-2, -1) / math.sqrt(Q.shape[-1])
    if causal:
        n = s.shape[-1]
        s = s.masked_fill(torch.triu(torch.ones(n, n, dtype=torch.bool, device=s.device), 1), float("-inf"))
    return torch.softmax(s, -1) @ V""",
      """import torch.nn.functional as F
_g = torch.Generator().manual_seed(0)
_Q, _K, _V = (torch.randn(2, 5, 8, generator=_g) for _ in range(3))
@prueba("igual a la de PyTorch")
def _():
    assert torch.allclose(atencion(_Q, _K, _V), F.scaled_dot_product_attention(_Q, _K, _V), atol=1e-5)
@prueba("máscara causal correcta")
def _():
    assert torch.allclose(atencion(_Q, _K, _V, True), F.scaled_dot_product_attention(_Q, _K, _V, is_causal=True), atol=1e-5)
@prueba("lo implementaste tú")
def _():
    import inspect
    assert "scaled_dot_product_attention" not in inspect.getsource(atencion)
""", ["`s = Q @ K.transpose(-2, -1) / math.sqrt(d)`", "Máscara: `torch.triu(torch.ones(n, n, dtype=torch.bool), 1)` y `masked_fill(…, -inf)`."]),
    M("pt3_2", "JEFE: mini GPT de caracteres",
      """Un GPT es: embeddings de tokens + posiciones → bloques de (atención causal + MLP) → probabilidad del siguiente token.
Aquí entrenas uno chiquito sobre un texto corto, carácter por carácter. Puedes usar `nn.TransformerEncoderLayer` con máscara causal
o tu propia atención. Es exactamente lo que hace nanoGPT, en miniatura.""",
      """`entrenar(texto)`: entrena un modelo de lenguaje de caracteres y devuelve `siguiente(contexto)` que, dado un string,
regresa el carácter más probable que sigue. Con el texto de prueba (repetitivo) debe atinar **≥ 95 %** de las predicciones.""",
      """import torch
from torch import nn

def entrenar(texto):
    raise NotImplementedError""",
      """import torch
from torch import nn

def entrenar(texto):
    d = "cuda" if torch.cuda.is_available() else "cpu"
    chars = sorted(set(texto)); stoi = {c: i for i, c in enumerate(chars)}
    datos = torch.tensor([stoi[c] for c in texto], device=d)
    T, E = 32, 64
    class GPT(nn.Module):
        def __init__(s):
            super().__init__()
            s.tok = nn.Embedding(len(chars), E); s.pos = nn.Embedding(T, E)
            capa = nn.TransformerEncoderLayer(E, 4, 4 * E, dropout=0.0, batch_first=True)
            s.bloques = nn.TransformerEncoder(capa, 2); s.cab = nn.Linear(E, len(chars))
        def forward(s, x):
            n = x.shape[1]
            m = torch.triu(torch.ones(n, n, dtype=torch.bool, device=x.device), 1)
            h = s.tok(x) + s.pos(torch.arange(n, device=x.device))
            return s.cab(s.bloques(h, mask=m))
    modelo = GPT().to(d)
    opt = torch.optim.AdamW(modelo.parameters(), lr=3e-3)
    for paso in range(600):
        ix = torch.randint(0, len(datos) - T - 1, (64,), device=d)
        x = torch.stack([datos[i:i + T] for i in ix]); y = torch.stack([datos[i + 1:i + T + 1] for i in ix])
        l = nn.functional.cross_entropy(modelo(x).reshape(-1, len(chars)), y.reshape(-1))
        opt.zero_grad(); l.backward(); opt.step()
    modelo.eval()
    def siguiente(ctx):
        x = torch.tensor([[stoi[c] for c in ctx[-T:]]], device=d)
        with torch.no_grad():
            return chars[modelo(x)[0, -1].argmax().item()]
    return siguiente""",
      """@prueba("predice el siguiente carácter (≥95%)")
def _():
    texto = "el analista revisa la alerta, bloquea la ip y documenta el incidente. " * 60
    sig = entrenar(texto)
    bien = sum(sig(texto[i - 20:i]) == texto[i] for i in range(200, 700))
    print("aciertos:", bien, "/ 500")
    assert bien >= 475, bien
""", ["Embeddings de token + posición, `nn.TransformerEncoderLayer(..., batch_first=True)` y una capa lineal final.",
      "La máscara causal es la misma de la misión de atención; entrena con pares (x, x desplazado un carácter)."], jefe=True, tiempo=420),
  ]},
]


# ---------------------------------------------------------------- nanoGPT (Karpathy) desde NetLab
def nanogpt_dir() -> str:
    return os.path.join(AQUI, "ia", "nanoGPT")


def entrenar_nanogpt(progreso, iteraciones: int = 1500) -> dict:
    py, d = python_ia(), nanogpt_dir()
    if not py or not os.path.isdir(d):
        raise RuntimeError("Falta ia_env o la carpeta ia\\nanoGPT.")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    datos = os.path.join(d, "data", "shakespeare_char")
    if not os.path.isfile(os.path.join(datos, "train.bin")):
        progreso("Preparando el texto de Shakespeare (se baja una vez, 1 MB)…")
        r = subprocess.run([py, "prepare.py"], cwd=datos, capture_output=True, env=env, timeout=300, **_SIN_VENTANA)
        if r.returncode:
            raise RuntimeError("prepare.py falló: " + r.stderr.decode("utf-8", "replace")[-500:])
    salida = os.path.join(d, "out-netlab")
    cmd = [py, "train.py", "config/train_shakespeare_char.py", f"--max_iters={iteraciones}", "--lr_decay_iters=" + str(iteraciones),
           "--compile=False", "--eval_interval=250", "--eval_iters=50", "--log_interval=50", f"--out_dir={salida}",
           "--always_save_checkpoint=False"]
    p = subprocess.Popen(cmd, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, **_SIN_VENTANA)
    perdidas = []
    for linea in iter(p.stdout.readline, b""):
        t = linea.decode("utf-8", "replace").strip()
        m = re.match(r"step (\d+): train loss ([\d.]+), val loss ([\d.]+)", t)
        if m:
            perdidas.append({"paso": int(m.group(1)), "train": float(m.group(2)), "val": float(m.group(3))})
        if t.startswith(("iter", "step")):
            progreso(f"nanoGPT · {t[:90]}")
    p.wait()
    if p.returncode:
        raise RuntimeError("El entrenamiento falló (revisa que la GPU esté libre).")
    progreso("Generando texto con tu modelo…")
    r = subprocess.run([py, "sample.py", f"--out_dir={salida}", "--num_samples=1", "--max_new_tokens=500", "--compile=False"],
                       cwd=d, capture_output=True, env=env, timeout=300, **_SIN_VENTANA)
    texto = r.stdout.decode("utf-8", "replace")
    texto = texto.split("---------------")[0].strip()[-1500:] if texto else r.stderr.decode("utf-8", "replace")[-500:]
    return {"perdidas": perdidas, "muestra": texto}
