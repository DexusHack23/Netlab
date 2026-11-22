"use strict";
// Chequeo de estado de NetLab: pinta verde/rojo qué está listo.

async function pintarSalud() {
  const caja = $("#saludVista");
  caja.innerHTML = `<div class="tarjeta"><div class="trabajo"><div class="girar"></div><div>Revisando todo…</div></div></div>`;
  let r;
  try { r = await api("/api/salud"); } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }

  const pin = (ok) => `<span class="sal-pin ${ok ? "si" : "no"}">${ok ? "✓" : "✕"}</span>`;
  const fila = (ok, nombre, detalle) => `<div class="sal-fila">${pin(ok)}<span class="sal-n">${esc(nombre)}</span><span class="sal-d">${esc(detalle || "")}</span></div>`;

  // modelos
  const rolesHtml = Object.values(r.modelos.roles).map((x) =>
    fila(x.ok, x.etiqueta, x.pedido)).join("");
  const modelosHtml = `
    <div class="tarjeta">
      <h3 style="margin-top:0">🧠 Modelos de IA (Ollama)</h3>
      ${fila(r.modelos.ollama, "Ollama", r.modelos.ollama ? `${r.modelos.instalados.length} modelos instalados` : "No responde (¿Ollama está abierto?)")}
      ${rolesHtml}
    </div>`;

  // herramientas
  const he = r.herramientas;
  const herrHtml = `
    <div class="tarjeta">
      <h3 style="margin-top:0">🛠️ Compiladores y herramientas</h3>
      ${fila(he.rustc.ok, "Rust (rustc)", he.rustc.detalle)}
      ${fila(he.cargo.ok, "Cargo", he.cargo.detalle)}
      ${fila(he.java.ok, "Java (JDK)", he.java.detalle)}
      ${fila(he.sbt.ok, "sbt (Chisel)", he.sbt.detalle)}
      ${fila(he.python_ia.ok, "PyTorch (ia_env)", he.python_ia.detalle)}
      ${fila(he.tshark.ok, "Wireshark (tshark)", he.tshark.detalle)}
    </div>`;

  // máquina virtual
  const mq = r.maquina;
  const vmHtml = `
    <div class="tarjeta">
      <h3 style="margin-top:0">🖥️ Máquina virtual y SIEM</h3>
      ${fila(mq.virtualbox.ok, "VirtualBox", mq.virtualbox.detalle)}
      ${fila(mq.existe.ok, "VM Ubuntu", mq.existe.detalle)}
      ${fila(mq.corriendo.ok, "Encendida", mq.corriendo.detalle)}
      ${fila(mq.instantanea.ok, "Instantánea", mq.instantanea.detalle)}
      ${fila(mq.siem.ok, "SIEM instalado", mq.siem.detalle)}
      ${fila(mq.elasticsearch.ok, "Elasticsearch", mq.elasticsearch.detalle)}
      ${fila(mq.kibana.ok, "Kibana", mq.kibana.detalle)}
    </div>`;

  // mundos
  const mundosHtml = `
    <div class="tarjeta">
      <h3 style="margin-top:0">🗺️ Mundos (${r.resumen.mundos_listos}/${r.resumen.mundos_total} listos)</h3>
      <div class="sal-mundos">
        ${r.mundos.map((m) => `<div class="sal-mundo ${m.ok ? "" : "falla"}">
          <div class="sal-mundo-cab">${pin(m.ok)} <b>${m.icono} ${esc(m.nombre)}</b></div>
          <div class="sub">Motor: ${esc(m.dependencia)}</div>
          <div class="sal-partes">${m.partes.map((p) => `<span>${esc(p)}</span>`).join("")}</div>
        </div>`).join("")}
      </div>
    </div>`;

  const global = r.ok_global
    ? `<div class="tarjeta sal-ok"><b>✅ Todo en orden</b> · ${r.resumen.mundos_listos}/${r.resumen.mundos_total} mundos listos para jugar.</div>`
    : `<div class="tarjeta sal-aviso"><b>⚠️ Hay cosas por revisar</b> · ${r.resumen.mundos_listos}/${r.resumen.mundos_total} mundos listos. Mira abajo lo que está en rojo.</div>`;

  caja.innerHTML = `${global}
    <div class="acciones" style="margin:8px 0"><button class="primario" id="salRe">🔄 Volver a revisar</button></div>
    ${modelosHtml}${herrHtml}${vmHtml}${mundosHtml}`;
  $("#salRe").addEventListener("click", pintarSalud);
}
