"""Chisel: diseño de hardware en Scala. Cada misión es un módulo que el alumno escribe; NetLab lo prueba con chiseltest
(simulador treadle, 100% Java: no necesita Verilator) usando el sbt y el Java que ya tienes. También muestra el Verilog generado."""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import threading

_CANDADO = threading.Lock()  # un solo proyecto sbt: una compilación a la vez

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROYECTO = os.path.join(AQUI, "chisel", "proyecto")
_SIN_VENTANA = {"creationflags": 0x08000000} if os.name == "nt" else {}

BUILD_SBT = """scalaVersion := "2.13.10"
val chiselVersion = "3.6.1"
libraryDependencies ++= Seq(
  "edu.berkeley.cs" %% "chisel3" % chiselVersion,
  "edu.berkeley.cs" %% "chiseltest" % "0.6.2" % "test"
)
addCompilerPlugin("edu.berkeley.cs" % "chisel3-plugin" % chiselVersion cross CrossVersion.full)
scalacOptions ++= Seq("-language:reflectiveCalls", "-deprecation", "-feature", "-Xcheckinit")
Test / parallelExecution := false
"""


def herramientas() -> dict:
    java_home = os.environ.get("JAVA_HOME", "")
    if not java_home or not os.path.isdir(java_home):
        cand = sorted(glob.glob(r"C:\Program Files\Eclipse Adoptium\jdk-17*")) + sorted(glob.glob(r"C:\Program Files\Eclipse Adoptium\jdk-*"))
        java_home = cand[-1] if cand else ""
    sbt = shutil.which("sbt") or shutil.which("sbt.bat")
    for c in (r"C:\Program Files (x86)\sbt\bin\sbt.bat", r"C:\Program Files\sbt\bin\sbt.bat"):
        if not sbt and os.path.isfile(c):
            sbt = c
    return {"java_home": java_home, "sbt": sbt}


def _preparar() -> None:
    os.makedirs(os.path.join(PROYECTO, "project"), exist_ok=True)
    for ruta, txt in ((os.path.join(PROYECTO, "build.sbt"), BUILD_SBT),
                      (os.path.join(PROYECTO, "project", "build.properties"), "sbt.version=1.10.2\n")):
        if not os.path.isfile(ruta) or open(ruta, encoding="utf-8").read() != txt:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(txt)
    for sub in ("src/main/scala", "src/test/scala"):
        d = os.path.join(PROYECTO, *sub.split("/"))
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)


def _sbt(tarea: str, timeout: int) -> tuple[int, str]:
    h = herramientas()
    if not h["sbt"] or not h["java_home"]:
        return 1, "No encontré sbt o Java 17. Instálalos con winget (EclipseAdoptium.Temurin.17.JDK y sbt.sbt) y reinicia NetLab."
    env = {**os.environ, "JAVA_HOME": h["java_home"], "PATH": os.path.join(h["java_home"], "bin") + os.pathsep + os.environ.get("PATH", ""),
           "SBT_OPTS": "-Xmx2G -Dfile.encoding=UTF-8"}
    cmd = [h["sbt"], "-batch", "-no-colors", tarea]  # el .bat se puede lanzar directo; con "cmd /c" se rompen las rutas con espacios
    try:
        r = subprocess.run(cmd, cwd=PROYECTO, capture_output=True, timeout=timeout, env=env, **_SIN_VENTANA)
    except subprocess.TimeoutExpired:
        return 124, "sbt tardó demasiado (la primera vez baja Chisel, ~200 MB: intenta otra vez)."
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def _escribir(codigo: str, prueba: str = "") -> None:
    _preparar()
    with open(os.path.join(PROYECTO, "src", "main", "scala", "Ejercicio.scala"), "w", encoding="utf-8") as f:
        f.write(codigo)
    if prueba:
        with open(os.path.join(PROYECTO, "src", "test", "scala", "PruebaNetlab.scala"), "w", encoding="utf-8") as f:
            f.write(prueba)


def _errores(salida: str) -> str:
    lineas = [l for l in salida.splitlines() if l.startswith("[error]") or "error:" in l.lower()]
    return "\n".join(lineas[:40]) or salida[-3000:]


def calificar(m: dict, codigo: str, carpeta_tmp: str = "") -> dict:
    with _CANDADO:
        _escribir(codigo, PREAMBULO_TEST + m["pruebas"])
        code, out = _sbt("testOnly PruebaNetlab", 900)
        shutil.rmtree(os.path.join(PROYECTO, "test_run_dir"), ignore_errors=True)  # chiseltest deja archivos de la simulación
    if code and ("Compilation failed" in out or ("[error]" in out and "Tests:" not in out)):
        return {"aprobado": False, "fase": "compilar", "fallo": _errores(out), "reglas": []}
    pruebas = []
    for mm in re.finditer(r"^\[info\] - (.+?)(?: \*\*\* FAILED \*\*\*)?(?: \(\d+ .*?\))?$", out, re.M):
        nombre = mm.group(1).strip()
        pruebas.append({"prueba": nombre, "ok": "*** FAILED ***" not in mm.group(0)})
    fallos = re.findall(r"^\[info\]   (.+)$", out, re.M)
    for p in pruebas:
        if not p["ok"] and fallos:
            p["detalle"] = "\n".join(fallos[:6])[:800]
    if not pruebas:
        return {"aprobado": False, "fase": "correr", "fallo": _errores(out), "reglas": []}
    return {"aprobado": all(p["ok"] for p in pruebas) and code == 0, "pruebas": pruebas, "reglas": []}


def verilog(codigo: str, modulo: str) -> dict:
    """Genera el Verilog del módulo (lo que de verdad va a un chip / FPGA)."""
    if not re.fullmatch(r"[A-Za-z_]\w*", modulo or ""):
        return {"ok": False, "fallo": "Nombre de módulo inválido."}
    gen = (codigo + f"""

object NetlabVerilog extends App {{
  println("@@VERILOG@@")
  println((new chisel3.stage.ChiselStage).emitVerilog(new {modulo}))
}}
""")
    with _CANDADO:
        _escribir(gen)
        code, out = _sbt("runMain NetlabVerilog", 900)
    if "@@VERILOG@@" not in out:
        return {"ok": False, "fallo": _errores(out)}
    v = out.split("@@VERILOG@@", 1)[1]
    v = "\n".join(l for l in v.splitlines() if not l.startswith("[")).strip()
    return {"ok": True, "verilog": v[:20000]}


PREAMBULO_TEST = """import chisel3._
import chiseltest._
import org.scalatest.flatspec.AnyFlatSpec

"""


def M(id, titulo, teoria, enunciado, inicial, solucion, pruebas, pistas, modulo, jefe=False):
    return {"id": id, "titulo": titulo, "teoria": teoria.strip(), "enunciado": enunciado.strip(), "inicial": inicial.strip() + "\n",
            "solucion": solucion.strip() + "\n", "pruebas": pruebas.strip() + "\n", "pistas": list(pistas), "requiere": [], "prohibido": [],
            "modo": "chisel", "modulo": modulo, "salida": "", "entrada": "", "jefe": jefe}


NIVELES_CHISEL = [
  {"nombre": "Lógica combinacional", "cap": "Digital Design with Chisel, cap. 2-5", "misiones": [
    M("ch0_1", "Compuertas lógicas",
      """En Chisel describes **hardware**, no un programa: cada `:=` es un cable conectado para siempre. Un módulo tiene una `io` con
entradas (`Input`) y salidas (`Output`). `Bool()` es un bit. Operadores: `&` (AND), `|` (OR), `^` (XOR), `~` (NOT).""",
      """Completa `Compuertas`: con las entradas `a` y `b`, conecta las salidas `y` (AND), `o` (OR) y `x` (XOR).""",
      """import chisel3._

class Compuertas extends Module {
  val io = IO(new Bundle {
    val a = Input(Bool())
    val b = Input(Bool())
    val y = Output(Bool())
    val o = Output(Bool())
    val x = Output(Bool())
  })
  io.y := false.B
  io.o := false.B
  io.x := false.B
}""",
      """import chisel3._

class Compuertas extends Module {
  val io = IO(new Bundle {
    val a = Input(Bool())
    val b = Input(Bool())
    val y = Output(Bool())
    val o = Output(Bool())
    val x = Output(Bool())
  })
  io.y := io.a & io.b
  io.o := io.a | io.b
  io.x := io.a ^ io.b
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Compuertas" should "cumplir la tabla de verdad" in {
    test(new Compuertas) { c =>
      for (a <- Seq(false, true); b <- Seq(false, true)) {
        c.io.a.poke(a.B); c.io.b.poke(b.B)
        c.io.y.expect((a && b).B); c.io.o.expect((a || b).B); c.io.x.expect((a ^ b).B)
      }
    }
  }
}""", ["`io.y := io.a & io.b`", "OR es `|` y XOR es `^`."], "Compuertas"),
    M("ch0_2", "Sumador completo",
      """El mismo sumador completo que hiciste en Rust, ahora como hardware real: `suma = a ⊕ b ⊕ cin`, `cout = (a·b) + (cin·(a⊕b))`.
Encadenando 8 tienes un sumador de 8 bits como el de la ALU de un procesador.""",
      """Completa `SumadorCompleto` con entradas `a`, `b`, `cin` (Bool) y salidas `s` y `cout`.""",
      """import chisel3._

class SumadorCompleto extends Module {
  val io = IO(new Bundle {
    val a = Input(Bool())
    val b = Input(Bool())
    val cin = Input(Bool())
    val s = Output(Bool())
    val cout = Output(Bool())
  })
  io.s := false.B
  io.cout := false.B
}""",
      """import chisel3._

class SumadorCompleto extends Module {
  val io = IO(new Bundle {
    val a = Input(Bool())
    val b = Input(Bool())
    val cin = Input(Bool())
    val s = Output(Bool())
    val cout = Output(Bool())
  })
  io.s := io.a ^ io.b ^ io.cin
  io.cout := (io.a & io.b) | (io.cin & (io.a ^ io.b))
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "SumadorCompleto" should "sumar los 8 casos" in {
    test(new SumadorCompleto) { c =>
      for (a <- 0 to 1; b <- 0 to 1; ci <- 0 to 1) {
        c.io.a.poke((a == 1).B); c.io.b.poke((b == 1).B); c.io.cin.poke((ci == 1).B)
        val t = a + b + ci
        c.io.s.expect((t % 2 == 1).B); c.io.cout.expect((t >= 2).B)
      }
    }
  }
}""", ["`io.s := io.a ^ io.b ^ io.cin`", "`io.cout := (io.a & io.b) | (io.cin & (io.a ^ io.b))`"], "SumadorCompleto"),
    M("ch0_3", "Multiplexor 4 a 1",
      """Un **multiplexor** elige una de varias entradas según un selector: es como un `match` en hardware. Con `UInt(8.W)` tienes
números de 8 bits. `switch(io.sel) { is(0.U) { ... } }` o `MuxLookup` lo hacen. Toda salida necesita un valor por defecto.""",
      """`Mux4`: entradas `a, b, c, d` (8 bits) y `sel` (2 bits); `y` = la entrada elegida (0→a, 1→b, 2→c, 3→d).""",
      """import chisel3._
import chisel3.util._

class Mux4 extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(8.W))
    val b = Input(UInt(8.W))
    val c = Input(UInt(8.W))
    val d = Input(UInt(8.W))
    val sel = Input(UInt(2.W))
    val y = Output(UInt(8.W))
  })
  io.y := 0.U
}""",
      """import chisel3._
import chisel3.util._

class Mux4 extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(8.W))
    val b = Input(UInt(8.W))
    val c = Input(UInt(8.W))
    val d = Input(UInt(8.W))
    val sel = Input(UInt(2.W))
    val y = Output(UInt(8.W))
  })
  io.y := io.a
  switch(io.sel) {
    is(1.U) { io.y := io.b }
    is(2.U) { io.y := io.c }
    is(3.U) { io.y := io.d }
  }
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Mux4" should "elegir la entrada correcta" in {
    test(new Mux4) { c =>
      c.io.a.poke(11.U); c.io.b.poke(22.U); c.io.c.poke(33.U); c.io.d.poke(44.U)
      for ((s, v) <- Seq(0 -> 11, 1 -> 22, 2 -> 33, 3 -> 44)) { c.io.sel.poke(s.U); c.io.y.expect(v.U) }
    }
  }
}""", ["Valor por defecto `io.y := io.a` y luego `switch(io.sel) { is(1.U) { io.y := io.b } ... }`.", "Necesitas `import chisel3.util._` para `switch`."], "Mux4"),
  ]},
  {"nombre": "Lógica secuencial", "cap": "Registros, contadores y la ALU", "misiones": [
    M("ch1_1", "Contador con enable",
      """Un **registro** (`RegInit(0.U(4.W))`) guarda un valor y cambia solo en el flanco del reloj: así nace la memoria. Un contador es
un registro que se suma a sí mismo. En 4 bits, después de 15 vuelve a 0 (se desborda, como el u8 de Rust en modo release).""",
      """`Contador`: si `en` está en 1, el registro de 4 bits sube 1 en cada ciclo de reloj; `cuenta` muestra su valor.""",
      """import chisel3._

class Contador extends Module {
  val io = IO(new Bundle {
    val en = Input(Bool())
    val cuenta = Output(UInt(4.W))
  })
  io.cuenta := 0.U
}""",
      """import chisel3._

class Contador extends Module {
  val io = IO(new Bundle {
    val en = Input(Bool())
    val cuenta = Output(UInt(4.W))
  })
  val r = RegInit(0.U(4.W))
  when(io.en) { r := r + 1.U }
  io.cuenta := r
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Contador" should "contar solo con enable y dar la vuelta" in {
    test(new Contador) { c =>
      c.io.en.poke(false.B); c.clock.step(3); c.io.cuenta.expect(0.U)
      c.io.en.poke(true.B)
      for (i <- 1 to 17) { c.clock.step(); c.io.cuenta.expect((i % 16).U) }
    }
  }
}""", ["`val r = RegInit(0.U(4.W))`", "`when(io.en) { r := r + 1.U }` y `io.cuenta := r`."], "Contador"),
    M("ch1_2", "Registro de desplazamiento",
      """Un **registro de desplazamiento** mueve los bits un lugar en cada ciclo: así funcionan los puertos serie (UART, SPI) que convierten
bits sueltos en bytes. `Cat(a, b)` concatena bits; `r(6, 0)` toma los bits 6 a 0.""",
      """`Serie8`: en cada ciclo entra el bit `din` por la derecha (LSB) y todo se recorre a la izquierda. `q` muestra los 8 bits.""",
      """import chisel3._
import chisel3.util._

class Serie8 extends Module {
  val io = IO(new Bundle {
    val din = Input(Bool())
    val q = Output(UInt(8.W))
  })
  io.q := 0.U
}""",
      """import chisel3._
import chisel3.util._

class Serie8 extends Module {
  val io = IO(new Bundle {
    val din = Input(Bool())
    val q = Output(UInt(8.W))
  })
  val r = RegInit(0.U(8.W))
  r := Cat(r(6, 0), io.din)
  io.q := r
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Serie8" should "armar el byte 0xA5 bit por bit" in {
    test(new Serie8) { c =>
      for (b <- Seq(1, 0, 1, 0, 0, 1, 0, 1)) { c.io.din.poke((b == 1).B); c.clock.step() }
      c.io.q.expect(0xA5.U)
    }
  }
}""", ["Registro de 8 bits que empieza en 0.", "`r := Cat(r(6, 0), io.din)`"], "Serie8"),
    M("ch1_3", "JEFE: ALU de 8 bits",
      """La **ALU** es el corazón del procesador. Recibe dos operandos y un código de operación, y además levanta banderas: `zero`
cuando el resultado es 0 (así se implementa `if a == b` en ensamblador: restar y ver zero). Es la misma ALU que hiciste en Rust, ahora en silicio.""",
      """`Alu`: `op` de 3 bits: 0 suma, 1 resta, 2 AND, 3 OR, 4 XOR, 5 corrimiento a la izquierda 1 (`a << 1`, 8 bits). Otros → 0.
`y` (8 bits) es el resultado y `zero` vale 1 si `y` es 0.""",
      """import chisel3._
import chisel3.util._

class Alu extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(8.W))
    val b = Input(UInt(8.W))
    val op = Input(UInt(3.W))
    val y = Output(UInt(8.W))
    val zero = Output(Bool())
  })
  io.y := 0.U
  io.zero := false.B
}""",
      """import chisel3._
import chisel3.util._

class Alu extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(8.W))
    val b = Input(UInt(8.W))
    val op = Input(UInt(3.W))
    val y = Output(UInt(8.W))
    val zero = Output(Bool())
  })
  val r = WireDefault(0.U(8.W))
  switch(io.op) {
    is(0.U) { r := io.a + io.b }
    is(1.U) { r := io.a - io.b }
    is(2.U) { r := io.a & io.b }
    is(3.U) { r := io.a | io.b }
    is(4.U) { r := io.a ^ io.b }
    is(5.U) { r := (io.a << 1)(7, 0) }
  }
  io.y := r
  io.zero := r === 0.U
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Alu" should "hacer las 6 operaciones y la bandera zero" in {
    test(new Alu) { c =>
      val rnd = new scala.util.Random(7)
      for (_ <- 0 until 60) {
        val a = rnd.nextInt(256); val b = rnd.nextInt(256); val op = rnd.nextInt(8)
        val esp = op match {
          case 0 => (a + b) & 255; case 1 => (a - b) & 255; case 2 => a & b; case 3 => a | b
          case 4 => a ^ b; case 5 => (a << 1) & 255; case _ => 0 }
        c.io.a.poke(a.U); c.io.b.poke(b.U); c.io.op.poke(op.U)
        c.io.y.expect(esp.U); c.io.zero.expect((esp == 0).B)
      }
      c.io.a.poke(7.U); c.io.b.poke(7.U); c.io.op.poke(1.U); c.io.zero.expect(true.B)
    }
  }
}""", ["Un `WireDefault(0.U(8.W))` y un `switch(io.op)` que lo asigne.", "Para el corrimiento recorta a 8 bits: `(io.a << 1)(7, 0)`; `zero` es `r === 0.U`."], "Alu", jefe=True),
  ]},
  {"nombre": "Máquinas de estado", "cap": "FSM y protocolos", "misiones": [
    M("ch2_1", "JEFE: detector de secuencia",
      """Una **máquina de estados (FSM)** recuerda en qué paso va. Así funcionan los controladores de protocolos y los IDS en hardware:
buscan patrones en un flujo de bits. `ChiselEnum` define estados; un registro guarda el actual y `switch` decide el siguiente.""",
      """`Detector101`: entra un bit `din` por ciclo. `hallado` debe valer 1 en el ciclo en que el registro de estado indica que los últimos
tres bits recibidos fueron `1, 0, 1` (con traslape: `10101` lo detecta dos veces).""",
      """import chisel3._
import chisel3.util._

class Detector101 extends Module {
  val io = IO(new Bundle {
    val din = Input(Bool())
    val hallado = Output(Bool())
  })
  io.hallado := false.B
}""",
      """import chisel3._
import chisel3.util._

class Detector101 extends Module {
  val io = IO(new Bundle {
    val din = Input(Bool())
    val hallado = Output(Bool())
  })
  object E extends ChiselEnum { val nada, uno, unoCero, ok = Value }
  val e = RegInit(E.nada)
  switch(e) {
    is(E.nada)    { e := Mux(io.din, E.uno, E.nada) }
    is(E.uno)     { e := Mux(io.din, E.uno, E.unoCero) }
    is(E.unoCero) { e := Mux(io.din, E.ok, E.nada) }
    is(E.ok)      { e := Mux(io.din, E.uno, E.unoCero) }
  }
  io.hallado := e === E.ok
}""",
      """class PruebaNetlab extends AnyFlatSpec with ChiselScalatestTester {
  "Detector101" should "encontrar 101 con traslape" in {
    test(new Detector101) { c =>
      val bits = Seq(0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1)
      var ult = List[Int]()
      for (b <- bits) {
        c.io.din.poke((b == 1).B); c.clock.step()
        ult = (ult :+ b).takeRight(3)
        c.io.hallado.expect((ult == List(1, 0, 1)).B)
      }
    }
  }
}""", ["Cuatro estados: nada, vi '1', vi '10', vi '101' (hallado).", "Desde 'hallado', un 1 te deja en 'vi 1' y un 0 en 'vi 10' (eso da el traslape)."], "Detector101", jefe=True),
  ]},
]
