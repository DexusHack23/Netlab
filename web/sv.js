"use strict";
// ======================================================================
// NetLab — Mundo SystemVerilog (diseño digital y verificación de hardware).
// Misma mecánica de teoría + examen + jefe que Linux/Wireshark (pintarRuta2),
// sin laboratorio calificado en la app: la práctica se hace en EDA Playground
// o con Verilator. La teoría sale del RAG (IEEE 1800-2023 y el manual de Verilator).
// ======================================================================
const RUTA_SV = [
  { nombre: "Básico", icono: "🌱", temas: [
    { id: "sv_tipos", nombre: "Tipos, señales y vectores" },
    { id: "sv_combinacional", nombre: "Lógica combinacional" },
    { id: "sv_secuencial", nombre: "Lógica secuencial" },
  ] },
  { nombre: "Intermedio", icono: "⚙️", temas: [
    { id: "sv_fsm", nombre: "Máquinas de estado (FSM)" },
    { id: "sv_jerarquia", nombre: "Módulos, parámetros e interfaces" },
    { id: "sv_paquetes", nombre: "Tareas, funciones y paquetes" },
  ] },
  { nombre: "Avanzado", icono: "🔥", temas: [
    { id: "sv_testbench", nombre: "Testbenches y estímulos" },
    { id: "sv_oop", nombre: "Clases y aleatorización" },
    { id: "sv_cobertura", nombre: "Cobertura funcional" },
  ] },
  { nombre: "Experto", icono: "👑", temas: [
    { id: "sv_sva", nombre: "Aserciones (SVA)" },
    { id: "sv_verilator", nombre: "Simulación con Verilator" },
  ] },
];

async function pintarRutaSV() {
  const prog = await progresoGeneral();
  const niveles = RUTA_SV.map((n) => ({ ...n, temas: n.temas.map((t) => ({ ...t, detalle: "teoría + examen" })) }));
  const total = RUTA_SV.reduce((s, n) => s + n.temas.length, 0);
  const dominados = niveles.flatMap((n) => n.temas).filter((t) => (prog[t.id]?.mejor_examen || 0) >= 8).length;
  $("#svRuta").innerHTML = `<div class="tarjeta lx-resumen">
      <div><b>${dominados}/${total}</b> temas dominados · diseño RTL y verificación con SystemVerilog</div>
      <div class="acciones"><button id="svPlayground">🌐 EDA Playground (practicar)</button>
        <button id="svExamen">📝 Examen general</button></div></div><div id="svRutaCaja"></div>`;
  $("#svPlayground").addEventListener("click", () => window.open("https://www.edaplayground.com/", "_blank"));
  $("#svExamen").addEventListener("click", () => irExamenMundo("sv"));
  pintarRuta2({ caja: $("#svRutaCaja"), pref: "sv", dominio: "sv", titulo: "SystemVerilog: diseño digital y verificación",
    cert: "IEEE 1800-2023 (SystemVerilog) y simulación con Verilator", niveles, onPractica: () => {} }, prog);
}
