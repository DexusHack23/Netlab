"use strict";
// ======================================================================
// NetLab — Procesadores: entrenador infinito (bits, complemento a dos, RISC-V, caché)
// y un simulador de ensamblador RISC-V (RV32I + mul) con retos que se califican solos.
// ======================================================================
const rnd = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
const hex = (n, d = 2) => "0x" + (n >>> 0).toString(16).toUpperCase().padStart(d, "0");
const bin = (n, d = 8) => (n >>> 0).toString(2).padStart(d, "0").slice(-d);
const REG_ABI = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7",
  "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"];

// ---------------------------------------------------------------- generadores (respuesta exacta, sin IA)
const R_OPS = { add: [0, 0], sub: [0, 0x20], sll: [1, 0], slt: [2, 0], xor: [4, 0], srl: [5, 0], or: [6, 0], and: [7, 0] };
const I_OPS = { addi: 0, slti: 2, xori: 4, ori: 6, andi: 7 };
const codR = (op, rd, rs1, rs2) => ((R_OPS[op][1] << 25) | (rs2 << 20) | (rs1 << 15) | (R_OPS[op][0] << 12) | (rd << 7) | 0x33) >>> 0;
const codI = (op, rd, rs1, imm) => (((imm & 0xfff) << 20) | (rs1 << 15) | (I_OPS[op] << 12) | (rd << 7) | 0x13) >>> 0;

const GEN_CPU = {
  dec_bin: () => { const n = rnd(1, 255); return { q: `Convierte ${n} (decimal) a binario de 8 bits.`, r: bin(n), e: `Restas potencias de 2 de mayor a menor (128, 64, 32…): ${n} = ${bin(n).split("").map((b, i) => b === "1" ? 2 ** (7 - i) : 0).filter(Boolean).join(" + ")} → ${bin(n)}.` }; },
  bin_dec: () => { const n = rnd(1, 255); return { q: `¿Cuánto vale ${bin(n)} en decimal?`, r: String(n), e: `Suma los pesos de los 1: ${bin(n).split("").map((b, i) => b === "1" ? 2 ** (7 - i) : 0).filter(Boolean).join(" + ")} = ${n}.` }; },
  dec_hex: () => { const n = rnd(16, 65535); return { q: `Convierte ${n} a hexadecimal (con 0x).`, r: hex(n, 1), e: `Divide entre 16 y lee los residuos al revés: ${n} = ${hex(n, 1)}.` }; },
  hex_bin: () => { const n = rnd(1, 255); return { q: `Convierte ${hex(n)} a binario (8 bits).`, r: bin(n), e: `Cada dígito hex son 4 bits: ${hex(n).slice(2).split("").map((d) => `${d}=${bin(parseInt(d, 16), 4)}`).join(", ")} → ${bin(n)}.` }; },
  c2_valor: () => { const n = rnd(128, 255); return { q: `En complemento a dos de 8 bits, ¿qué número es ${bin(n)}?`, r: String(n - 256), e: `El bit 7 está prendido → es negativo: ${n} − 256 = ${n - 256}. (O invierte y suma 1: ${bin((~n + 1) & 255)} = ${256 - n}, con signo menos.)` }; },
  c2_codifica: () => { const n = -rnd(1, 128); return { q: `Escribe ${n} en complemento a dos de 8 bits.`, r: bin(n & 255), e: `${-n} = ${bin(-n)}; inviertes los bits → ${bin(~(-n) & 255)}; sumas 1 → ${bin(n & 255)}.` }; },
  bits: () => { const a = rnd(0, 255), b = rnd(0, 255), op = ["AND", "OR", "XOR"][rnd(0, 2)]; const r = op === "AND" ? a & b : op === "OR" ? a | b : a ^ b;
    return { q: `${hex(a)} ${op} ${hex(b)} = ? (en hex)`, r: hex(r), e: `${bin(a)}\n${bin(b)} ${op}\n${bin(r)} = ${hex(r)}` }; },
  shift: () => { const a = rnd(1, 255), k = rnd(1, 4), izq = Math.random() < 0.5; const r = izq ? (a << k) & 255 : a >> k;
    return { q: `En 8 bits: ${bin(a)} ${izq ? "<<" : ">>"} ${k} = ? (binario)`, r: bin(r), e: `${izq ? "Corres a la izquierda (entran ceros a la derecha; ×" + 2 ** k + " si no se sale nada)" : "Corres a la derecha (÷" + 2 ** k + " entero)"}: ${bin(r)}.` }; },
  suma_flags: () => { const a = rnd(0, 255), b = rnd(0, 255), s = (a + b) & 255, c = a + b > 255 ? 1 : 0, sa = a > 127 ? a - 256 : a, sb = b > 127 ? b - 256 : b, ss = s > 127 ? s - 256 : s, v = sa + sb !== ss ? 1 : 0;
    return { q: `Suma de 8 bits ${hex(a)} + ${hex(b)}. Escribe: resultado(hex) C V  (ej. 0x1F 0 1)`, r: `${hex(s)} ${c} ${v}`, e: `${a} + ${b} = ${a + b}${c ? " (se pasa de 255 → C=1)" : ""}. Con signo: ${sa} + ${sb} = ${sa + sb}${v ? `, que no cabe en −128..127 → V=1` : " (cabe → V=0)"}.` }; },
  rv_cod_i: () => { const rd = rnd(1, 31), rs = rnd(0, 31), imm = rnd(-2048, 2047), op = Object.keys(I_OPS)[rnd(0, 4)]; const c = codI(op, rd, rs, imm);
    return { q: `Codifica en hex: ${op} x${rd}, x${rs}, ${imm}`, r: hex(c, 8), e: `Tipo I: imm[11:0]=${bin(imm & 0xfff, 12)} | rs1=${bin(rs, 5)} | funct3=${bin(I_OPS[op], 3)} | rd=${bin(rd, 5)} | opcode=0010011 → ${hex(c, 8)}` }; },
  rv_cod_r: () => { const rd = rnd(1, 31), r1 = rnd(0, 31), r2 = rnd(0, 31), op = Object.keys(R_OPS)[rnd(0, 7)]; const c = codR(op, rd, r1, r2);
    return { q: `Codifica en hex: ${op} x${rd}, x${r1}, x${r2}`, r: hex(c, 8), e: `Tipo R: funct7=${bin(R_OPS[op][1], 7)} | rs2=${bin(r2, 5)} | rs1=${bin(r1, 5)} | funct3=${bin(R_OPS[op][0], 3)} | rd=${bin(rd, 5)} | opcode=0110011 → ${hex(c, 8)}` }; },
  rv_dec: () => { const rd = rnd(1, 31), r1 = rnd(0, 31), r2 = rnd(0, 31), op = Object.keys(R_OPS)[rnd(0, 7)]; const c = codR(op, rd, r1, r2);
    return { q: `Decodifica ${hex(c, 8)} (formato: op xD, xS1, xS2)`, r: `${op} x${rd}, x${r1}, x${r2}`, e: `opcode 0x33 = tipo R. rd=bits 11-7 → ${rd}; funct3=${R_OPS[op][0]}; rs1=${r1}; rs2=${r2}; funct7=${hex(R_OPS[op][1])} → ${op}.` }; },
  rv_imm: () => { const imm = rnd(-2048, 2047), c = codI("addi", rnd(1, 31), rnd(0, 31), imm);
    return { q: `¿Qué inmediato (decimal, con signo) trae la instrucción addi ${hex(c, 8)}?`, r: String(imm), e: `Los bits 31-20 son ${bin(c >>> 20, 12)}. ${imm < 0 ? `El bit 11 es 1 → negativo: ${(c >>> 20)} − 4096 = ${imm}.` : `Positivo: ${imm}.`}` }; },
  endian: () => { const n = (rnd(0, 0xffff) << 16 | rnd(0, 0xffff)) >>> 0; const b = [n & 255, n >>> 8 & 255, n >>> 16 & 255, n >>> 24];
    return { q: `¿Cómo queda ${hex(n, 8)} en memoria en little endian? (4 bytes en hex separados por espacio, de la dirección baja a la alta)`, r: b.map((x) => hex(x)).join(" "), e: `Little endian guarda primero el byte MENOS significativo: ${b.map((x) => hex(x)).join(" ")}. (En la red, big endian, sería al revés.)` }; },
  cache: () => { const lineas = 2 ** rnd(2, 6), bloque = 2 ** rnd(2, 6), d = rnd(0, 65535); const off = d % bloque, idx = Math.floor(d / bloque) % lineas, tag = Math.floor(d / bloque / lineas);
    return { q: `Caché de mapeo directo: ${lineas} líneas, bloques de ${bloque} bytes. Dirección ${d}. Escribe: etiqueta índice desplazamiento`, r: `${tag} ${idx} ${off}`,
      e: `desplazamiento = ${d} mod ${bloque} = ${off}; bloque = ${d} ÷ ${bloque} = ${Math.floor(d / bloque)}; índice = ${Math.floor(d / bloque)} mod ${lineas} = ${idx}; etiqueta = ${Math.floor(d / bloque)} ÷ ${lineas} = ${tag}.` }; },
};
const TEMAS_CPU = { "Todo mezclado": Object.keys(GEN_CPU), "Binario y hex": ["dec_bin", "bin_dec", "dec_hex", "hex_bin"], "Complemento a dos y banderas": ["c2_valor", "c2_codifica", "suma_flags"],
  "Operaciones de bits": ["bits", "shift"], "RISC-V": ["rv_cod_i", "rv_cod_r", "rv_dec", "rv_imm"], "Memoria (endianness y caché)": ["endian", "cache"] };
const normCpu = (s) => String(s).trim().toLowerCase().replace(/\s+/g, " ").replace(/0x0*([0-9a-f])/g, "0x$1").replace(/,\s*/g, ", ");

const CPUQ = { lista: [], i: 0, buenas: 0 };
function pintarEntrenadorCpu() {
  const v = $("#acVista_cpu");
  v.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button data-ac-mapa>← Mapa</button>
      <button class="primario btn-teofondo" id="cpuTeoFondo">📖 Teoría a fondo del tema</button><button id="cpuTeoLec">📚 Lecciones y exámenes</button></div>
    <div id="cpuTeoFondoCaja" hidden></div>
    <div class="tarjeta"><h2 style="margin-top:0">♾️ Entrenador de bits y RISC-V</h2>
      <p class="sub">Infinito y con respuesta exacta (sin IA). Rondas de 10; con 8 o más ganas estrellas del día.</p>
      <div class="fila"><label>Tema<select id="cpuTema">${Object.keys(TEMAS_CPU).map((t) => `<option>${esc(t)}</option>`).join("")}</select></label></div>
      <div class="acciones"><button class="primario" id="cpuEmpezar">Empezar ronda</button></div></div><div id="cpuRonda"></div>`;
  $("[data-ac-mapa]", v).addEventListener("click", () => cargarAcademia("cpu"));
  $("#cpuTeoFondo").addEventListener("click", (ev) => {
    const caja = $("#cpuTeoFondoCaja"), t = $("#cpuTema").value;
    if (caja.dataset.tema !== t) { caja.innerHTML = ""; delete caja.dataset.listo; caja.dataset.tema = t; }
    teoriaAFondo(ev.target, caja, { clave: `cpu:${t}`, mundo: "cpu", titulo: t,
      contexto: `Entrenador de arquitectura de computadoras, tema "${t}" (ejercicios del tipo: ${TEMAS_CPU[t].join(", ")}). Explica el método para resolverlos a mano, paso a paso, con ejemplos resueltos y errores típicos.` });
  });
  $("#cpuTeoLec").addEventListener("click", () => irTeoria("cpu", null));
  $("#cpuEmpezar").addEventListener("click", () => {
    const g = TEMAS_CPU[$("#cpuTema").value];
    Object.assign(CPUQ, { lista: Array.from({ length: 10 }, () => GEN_CPU[g[rnd(0, g.length - 1)]]()), i: 0, buenas: 0 });
    preguntaCpu();
  });
}
function preguntaCpu() {
  const c = $("#cpuRonda"), q = CPUQ.lista[CPUQ.i];
  if (!q) return finRondaCpu();
  c.innerHTML = `<div class="tarjeta"><div class="sub">Pregunta ${CPUQ.i + 1}/10 · ✅ ${CPUQ.buenas}</div><h3>${esc(q.q)}</h3>
    <div class="fila-filtro"><input class="mono" id="cpuIn" autocomplete="off" spellcheck="false"><button class="primario" id="cpuOk">Comprobar</button></div><div id="cpuExp"></div></div>`;
  const ir = () => {
    const ok = normCpu($("#cpuIn").value) === normCpu(q.r);
    if (ok) CPUQ.buenas++;
    $("#cpuExp").innerHTML = `<div class="${ok ? "ok-txt" : "error"}"><b>${ok ? "✓ Correcto" : `✗ Era: ${esc(q.r)}`}</b></div><pre class="ac-pre">${esc(q.e)}</pre>
      <div class="acciones"><button class="primario" id="cpuSig">Siguiente →</button></div>`;
    $("#cpuOk").disabled = true; $("#cpuIn").disabled = true;
    $("#cpuSig").addEventListener("click", () => { CPUQ.i++; preguntaCpu(); });
    $("#cpuSig").focus();
  };
  $("#cpuOk").addEventListener("click", ir);
  $("#cpuIn").addEventListener("keydown", (e) => { if (e.key === "Enter") ir(); });
  $("#cpuIn").focus();
}
async function finRondaCpu() {
  const b = CPUQ.buenas, est = b >= 10 ? 3 : b >= 9 ? 2 : b >= 8 ? 1 : 0;
  if (est) {
    const hoy = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    await api("/api/academia/resultado", { id: `cpue_${hoy}`, estrellas: est }).catch(() => {});
    refrescarJugador(true);
  }
  $("#cpuRonda").innerHTML = `<div class="tarjeta ${est ? "ac-ok" : ""}"><h3 style="margin-top:0">${b}/10 ${est ? "★".repeat(est) : ""}</h3>
    <p class="sub">${est ? "¡Bien! Las estrellas del día se guardan (cuenta tu mejor ronda de hoy)." : "Necesitas 8/10 para estrellas. Otra ronda."}</p>
    <div class="acciones"><button class="primario" id="cpuOtra">Otra ronda</button></div></div>`;
  $("#cpuOtra").addEventListener("click", () => $("#cpuEmpezar").click());
}

// ---------------------------------------------------------------- simulador RISC-V
function regNum(t) {
  t = t.trim().toLowerCase();
  if (/^x\d+$/.test(t) && +t.slice(1) < 32) return +t.slice(1);
  if (t === "fp") return 8;
  const i = REG_ABI.indexOf(t);
  if (i < 0) throw new Error(`registro desconocido: ${t}`);
  return i;
}
function ensamblar(src) {
  const lineas = src.split("\n").map((l) => l.replace(/[#;].*$/, "").trim());
  const etiquetas = {}, prog = [];
  for (const [n, l0] of lineas.entries()) {
    let l = l0;
    const m = l.match(/^([A-Za-z_.][\w.]*):\s*(.*)$/);
    if (m) { etiquetas[m[1]] = prog.length * 4; l = m[2]; }
    if (!l) continue;
    const [op, ...resto] = l.split(/\s+/);
    const args = resto.join(" ").split(",").map((a) => a.trim()).filter(Boolean);
    prog.push({ op: op.toLowerCase(), args, linea: n + 1, txt: l });
  }
  const num = (t, pc) => {
    if (t in etiquetas) return etiquetas[t] - pc;
    const v = Number(t);
    if (Number.isNaN(v)) throw new Error(`no entiendo "${t}"`);
    return v;
  };
  // expande pseudoinstrucciones
  return prog.map((ins, k) => {
    const pc = k * 4, a = ins.args;
    try {
      switch (ins.op) {
        case "li": return { ...ins, op: "li", rd: regNum(a[0]), imm: Number(a[1]) | 0 };
        case "mv": return { ...ins, op: "addi", rd: regNum(a[0]), rs1: regNum(a[1]), imm: 0 };
        case "nop": return { ...ins, op: "addi", rd: 0, rs1: 0, imm: 0 };
        case "j": return { ...ins, op: "jal", rd: 0, imm: num(a[0], pc) };
        case "ret": return { ...ins, op: "jalr", rd: 0, rs1: 1, imm: 0 };
        case "beqz": return { ...ins, op: "beq", rs1: regNum(a[0]), rs2: 0, imm: num(a[1], pc) };
        case "bnez": return { ...ins, op: "bne", rs1: regNum(a[0]), rs2: 0, imm: num(a[1], pc) };
        case "lw": case "sw": case "lb": case "lbu": case "sb": {
          const m = a[1].match(/^(-?\w+)?\((\w+)\)$/);
          if (!m) throw new Error("formato: lw rd, offset(rs)");
          return ins.op[0] === "s" ? { ...ins, rs2: regNum(a[0]), rs1: regNum(m[2]), imm: Number(m[1] || 0) } : { ...ins, rd: regNum(a[0]), rs1: regNum(m[2]), imm: Number(m[1] || 0) };
        }
        case "jal": return a.length === 1 ? { ...ins, rd: 1, imm: num(a[0], pc) } : { ...ins, rd: regNum(a[0]), imm: num(a[1], pc) };
        case "jalr": return { ...ins, rd: regNum(a[0]), rs1: regNum(a[1] || "ra"), imm: Number(a[2] || 0) };
        case "lui": return { ...ins, rd: regNum(a[0]), imm: Number(a[1]) };
        case "beq": case "bne": case "blt": case "bge": case "bltu": case "bgeu": return { ...ins, rs1: regNum(a[0]), rs2: regNum(a[1]), imm: num(a[2], pc) };
        case "ecall": case "ebreak": return ins;
        default:
          if (ins.op in R_OPS || ["sra", "sltu", "mul", "div", "rem"].includes(ins.op)) return { ...ins, rd: regNum(a[0]), rs1: regNum(a[1]), rs2: regNum(a[2]) };
          if (ins.op in I_OPS || ["slli", "srli", "srai", "sltiu"].includes(ins.op)) return { ...ins, rd: regNum(a[0]), rs1: regNum(a[1]), imm: Number(a[2]) | 0 };
          throw new Error(`instrucción desconocida: ${ins.op}`);
      }
    } catch (e) { throw new Error(`línea ${ins.linea} (${ins.txt}): ${e.message}`); }
  });
}
function ejecutarRv(prog, x0 = {}, mem0 = []) {
  const x = new Int32Array(32), mem = new Uint8Array(4096);
  x[2] = 4096;  // sp
  for (const [r, v] of Object.entries(x0)) x[regNum(r)] = v;
  for (const [dir, bytes] of mem0) mem.set(bytes, dir);
  const lw = (d) => { if (d < 0 || d + 3 >= 4096 || d % 4) throw new Error(`lw a dirección inválida ${d}`); return mem[d] | mem[d + 1] << 8 | mem[d + 2] << 16 | mem[d + 3] << 24; };
  const sw = (d, v) => { if (d < 0 || d + 3 >= 4096 || d % 4) throw new Error(`sw a dirección inválida ${d}`); mem[d] = v; mem[d + 1] = v >> 8; mem[d + 2] = v >> 16; mem[d + 3] = v >> 24; };
  let pc = 0, pasos = 0;
  while (pc >= 0 && pc / 4 < prog.length) {
    if (++pasos > 200000) throw new Error("más de 200 000 instrucciones: ¿un ciclo infinito?");
    const i = prog[pc / 4], u = (r) => x[r] >>> 0;
    let sig = pc + 4;
    switch (i.op) {
      case "add": x[i.rd] = x[i.rs1] + x[i.rs2]; break;
      case "sub": x[i.rd] = x[i.rs1] - x[i.rs2]; break;
      case "and": x[i.rd] = x[i.rs1] & x[i.rs2]; break;
      case "or": x[i.rd] = x[i.rs1] | x[i.rs2]; break;
      case "xor": x[i.rd] = x[i.rs1] ^ x[i.rs2]; break;
      case "sll": x[i.rd] = x[i.rs1] << (x[i.rs2] & 31); break;
      case "srl": x[i.rd] = u(i.rs1) >>> (x[i.rs2] & 31); break;
      case "sra": x[i.rd] = x[i.rs1] >> (x[i.rs2] & 31); break;
      case "slt": x[i.rd] = x[i.rs1] < x[i.rs2] ? 1 : 0; break;
      case "sltu": x[i.rd] = u(i.rs1) < u(i.rs2) ? 1 : 0; break;
      case "mul": x[i.rd] = Math.imul(x[i.rs1], x[i.rs2]); break;
      case "div": x[i.rd] = x[i.rs2] ? (x[i.rs1] / x[i.rs2]) | 0 : -1; break;
      case "rem": x[i.rd] = x[i.rs2] ? x[i.rs1] % x[i.rs2] : x[i.rs1]; break;
      case "addi": x[i.rd] = x[i.rs1] + i.imm; break;
      case "andi": x[i.rd] = x[i.rs1] & i.imm; break;
      case "ori": x[i.rd] = x[i.rs1] | i.imm; break;
      case "xori": x[i.rd] = x[i.rs1] ^ i.imm; break;
      case "slti": x[i.rd] = x[i.rs1] < i.imm ? 1 : 0; break;
      case "sltiu": x[i.rd] = u(i.rs1) < (i.imm >>> 0) ? 1 : 0; break;
      case "slli": x[i.rd] = x[i.rs1] << (i.imm & 31); break;
      case "srli": x[i.rd] = u(i.rs1) >>> (i.imm & 31); break;
      case "srai": x[i.rd] = x[i.rs1] >> (i.imm & 31); break;
      case "li": x[i.rd] = i.imm; break;
      case "lui": x[i.rd] = i.imm << 12; break;
      case "lw": x[i.rd] = lw(x[i.rs1] + i.imm); break;
      case "sw": sw(x[i.rs1] + i.imm, x[i.rs2]); break;
      case "lb": x[i.rd] = (mem[(x[i.rs1] + i.imm) & 4095] << 24) >> 24; break;
      case "lbu": x[i.rd] = mem[(x[i.rs1] + i.imm) & 4095]; break;
      case "sb": mem[(x[i.rs1] + i.imm) & 4095] = x[i.rs2]; break;
      case "beq": if (x[i.rs1] === x[i.rs2]) sig = pc + i.imm; break;
      case "bne": if (x[i.rs1] !== x[i.rs2]) sig = pc + i.imm; break;
      case "blt": if (x[i.rs1] < x[i.rs2]) sig = pc + i.imm; break;
      case "bge": if (x[i.rs1] >= x[i.rs2]) sig = pc + i.imm; break;
      case "bltu": if (u(i.rs1) < u(i.rs2)) sig = pc + i.imm; break;
      case "bgeu": if (u(i.rs1) >= u(i.rs2)) sig = pc + i.imm; break;
      case "jal": x[i.rd] = pc + 4; sig = pc + i.imm; break;
      case "jalr": { const t = (x[i.rs1] + i.imm) & ~1; x[i.rd] = pc + 4; sig = t; break; }
      case "ecall": case "ebreak": sig = -1; break;
      default: throw new Error(`no implementada: ${i.op}`);
    }
    x[0] = 0;
    pc = sig;
  }
  return { x, mem, pasos };
}

const RETOS_RV = [
  { id: "suma", titulo: "Suma tres números", enun: "Recibes números en a0, a1 y a2. Deja su suma en a0.", ini: "# a0 = a0 + a1 + a2\n",
    caso: () => { const a = [rnd(-500, 500), rnd(-500, 500), rnd(-500, 500)]; return { x: { a0: a[0], a1: a[1], a2: a[2] }, esp: a[0] + a[1] + a[2] }; } },
  { id: "gauss", titulo: "Suma de 1 a n", enun: "En a0 viene n (0 a 1000). Deja en a0 la suma 1 + 2 + … + n usando un ciclo.", ini: "# usa un ciclo con blt/bne\n",
    caso: () => { const n = rnd(0, 1000); return { x: { a0: n }, esp: n * (n + 1) / 2 }; } },
  { id: "max", titulo: "Máximo de un arreglo", enun: "a0 apunta a un arreglo de enteros de 32 bits en memoria y a1 trae cuántos son (≥1). Deja el mayor en a0.", ini: "# lw t0, 0(a0) lee el primero; avanza de 4 en 4\n",
    caso: () => { const v = Array.from({ length: rnd(1, 12) }, () => rnd(-1000, 1000)); const b = []; v.forEach((n) => b.push(n & 255, n >> 8 & 255, n >> 16 & 255, n >> 24 & 255));
      return { x: { a0: 256, a1: v.length }, mem: [[256, b]], esp: Math.max(...v) }; } },
  { id: "popcount", titulo: "Cuenta los bits en 1", enun: "En a0 viene un número de 32 bits. Deja en a0 cuántos bits en 1 tiene (como contar_unos de Rust).", ini: "# pista: andi t0, a0, 1 y srli\n",
    caso: () => { const n = (rnd(0, 0xffff) << 16 | rnd(0, 0xffff)) | 0; let c = 0, k = n >>> 0; while (k) { c += k & 1; k >>>= 1; } return { x: { a0: n }, esp: c }; } },
  { id: "fib", titulo: "Fibonacci", enun: "En a0 viene n (0 a 40). Deja fib(n) en a0 (fib(0)=0, fib(1)=1).", ini: "",
    caso: () => { const n = rnd(0, 40); let a = 0, b = 1; for (let i = 0; i < n; i++) [a, b] = [b, a + b]; return { x: { a0: n }, esp: a }; } },
  { id: "bswap", titulo: "Big ↔ little endian", enun: "En a0 viene un número de 32 bits. Invierte el orden de sus 4 bytes (lo que hace ntohl). Deja el resultado en a0.", ini: "# andi, slli, srli y or\n",
    caso: () => { const n = (rnd(0, 0xffff) << 16 | rnd(0, 0xffff)) >>> 0; const r = ((n & 255) << 24 | (n >>> 8 & 255) << 16 | (n >>> 16 & 255) << 8 | n >>> 24) | 0; return { x: { a0: n | 0 }, esp: r }; } },
  { id: "strlen", titulo: "strlen", enun: "a0 apunta a un texto terminado en byte 0. Deja su longitud en a0 (lbu lee un byte).", ini: "",
    caso: () => { const t = Array.from({ length: rnd(0, 40) }, () => rnd(33, 126)); return { x: { a0: 512 }, mem: [[512, [...t, 0]]], esp: t.length }; } },
  { id: "fact", titulo: "Factorial (con mul)", enun: "En a0 viene n (0 a 12). Deja n! en a0. Puedes usar mul (extensión M).", ini: "",
    caso: () => { const n = rnd(0, 12); let f = 1; for (let i = 2; i <= n; i++) f *= i; return { x: { a0: n }, esp: f | 0 }; } },
];

function pintarSimuladorRv(retoId) {
  const v = $("#acVista_cpu"), r = RETOS_RV.find((x) => x.id === retoId) || null;
  const clave = `rv_${r ? r.id : "libre"}`;
  let guardado = null; try { guardado = localStorage.getItem(clave); } catch {}
  v.innerHTML = `<div class="acciones" style="margin-bottom:10px"><button data-ac-mapa>← Mapa</button>
      <button class="primario btn-teofondo" id="rvTeoFondo">📖 Teoría a fondo</button><button id="rvTeoLec">📚 Lecciones y exámenes</button></div>
    <div id="rvTeoFondoCaja" hidden></div>
    <div class="ac-layout"><div class="ac-izq">
      <div class="tarjeta"><h2 style="margin-top:0">🖥️ Simulador RISC-V</h2>
        <p class="sub">RV32I + mul/div. Registros por número (x10) o nombre (a0, t0, sp…). Pseudo: li, mv, j, ret, nop, beqz, bnez. Termina al llegar al final o con ecall.</p>
        <div class="r-misiones">${RETOS_RV.map((x) => `<button class="chico ${r && r.id === x.id ? "primario" : ""}" data-rv="${x.id}">${esc(x.titulo)} ${estrellasAc("asm_" + x.id) ? "★".repeat(estrellasAc("asm_" + x.id)) : ""}</button>`).join("")}</div>
        ${r ? `<h3>${esc(r.titulo)}</h3><div class="lx-objetivo">🎯 ${esc(r.enun)}</div>` : '<p class="sub">Elige un reto o escribe libremente.</p>'}
      </div>
      <div class="tarjeta"><h3 style="margin-top:0">Registros</h3><div id="rvRegs" class="rv-regs"></div></div>
    </div><div class="ac-der">
      <div class="tarjeta ac-editor-tarjeta"><div class="ac-editor-cab"><b>programa.s</b><span class="sub">Ctrl+Enter = ${r ? "calificar" : "ejecutar"}</span></div>
        <textarea class="ac-editor" id="rvSrc" spellcheck="false">${esc(guardado || (r ? r.ini : "li a0, 5\nli a1, 7\nadd a0, a0, a1   # a0 = 12\n"))}</textarea>
        <div class="acciones">${r ? '<button class="primario" id="rvCal">✅ Calificar (5 casos al azar)</button>' : ""}<button id="rvRun">▶ Ejecutar</button></div></div>
      <div id="rvRes"></div></div></div>`;
  $("[data-ac-mapa]", v).addEventListener("click", () => cargarAcademia("cpu"));
  $$("[data-rv]", v).forEach((b) => b.addEventListener("click", () => pintarSimuladorRv(b.dataset.rv)));
  $("#rvTeoFondo").addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#rvTeoFondoCaja"), {
    clave: `rv:${r ? r.id : "libre"}`, mundo: "cpu", titulo: r ? `RISC-V: ${r.titulo}` : "Ensamblador RISC-V (RV32I)",
    contexto: `Programación en ensamblador RISC-V RV32I + M: registros y su nombre ABI (a0–a7, t0–t6, s0–s11, sp, ra), instrucciones aritméticas, de carga/almacenamiento, saltos y ramas, pseudoinstrucciones (li, mv, j, ret, beqz), convención de llamadas y cómo traducir if/while/for a ensamblador.${r ? ` Reto: ${r.enun}` : ""}` }));
  $("#rvTeoLec").addEventListener("click", () => irTeoria("cpu", null));
  const src = $("#rvSrc");
  src.addEventListener("input", () => { try { localStorage.setItem(clave, src.value); } catch {} });
  src.addEventListener("keydown", (e) => { if (e.key === "Tab") { e.preventDefault(); src.setRangeText("    ", src.selectionStart, src.selectionEnd, "end"); } if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); (r ? calificarRv : correrRv)(); } });
  const regs = (x) => { $("#rvRegs").innerHTML = REG_ABI.map((n, i) => `<div><span class="sub">x${i} ${n}</span><b>${x ? x[i] : 0}</b></div>`).join(""); };
  regs(null);
  function correrRv() {
    try {
      const prog = ensamblar(src.value), c = r ? r.caso() : { x: {} }, res = ejecutarRv(prog, c.x, c.mem || []);
      regs(res.x);
      $("#rvRes").innerHTML = `<div class="tarjeta"><b>▶ Terminó</b> en ${res.pasos} instrucciones${r ? `. Con la entrada ${esc(JSON.stringify(c.x))} se esperaba a0 = ${c.esp} y quedó ${res.x[10]}.` : "."}</div>`;
    } catch (e) { $("#rvRes").innerHTML = `<div class="tarjeta ac-error"><b>✗</b> ${esc(e.message)}</div>`; }
  }
  async function calificarRv() {
    let prog;
    try { prog = ensamblar(src.value); } catch (e) { $("#rvRes").innerHTML = `<div class="tarjeta ac-error"><b>✗</b> ${esc(e.message)}</div>`; return; }
    const filas = [];
    for (let k = 0; k < 5; k++) {
      const c = r.caso();
      try { const res = ejecutarRv(prog, c.x, c.mem || []); filas.push({ ok: res.x[10] === c.esp, txt: `${JSON.stringify(c.x)} → a0 = ${res.x[10]} (esperado ${c.esp})` }); if (k === 4) regs(res.x); }
      catch (e) { filas.push({ ok: false, txt: e.message }); }
    }
    const ok = filas.every((f) => f.ok);
    if (ok) {
      const prev = estrellasAc("asm_" + r.id);
      await api("/api/academia/resultado", { id: "asm_" + r.id, estrellas: 3, codigo: src.value }).catch(() => {});
      AC.datos.progreso["asm_" + r.id] = { estrellas: 3 };
      if (!prev) celebrar("✅ ¡Programa correcto! ★★★", "logro");
      refrescarJugador(true);
    }
    $("#rvRes").innerHTML = `<div class="tarjeta ${ok ? "ac-ok" : "ac-error"}"><b>${ok ? "✅ Pasa los 5 casos" : "✗ Falla algún caso"}</b>
      ${filas.map((f) => `<div class="ac-prueba ${f.ok ? "ok" : "mal"}">${f.ok ? "✓" : "✗"} ${esc(f.txt)}</div>`).join("")}</div>`;
  }
  $("#rvRun").addEventListener("click", correrRv);
  $("#rvCal")?.addEventListener("click", calificarRv);
}
