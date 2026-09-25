/* Revisor de licitaciones SEACE – versión web (todo se procesa en el navegador). */
"use strict";

const CATEGORIAS = ["Avena", "Arroz símil", "Arroz fortificado", "Vaso de Leche"];
const PATRONES = {
  "Arroz símil": [/\bsimil(es)?\b.{0,40}\barroz\b/, /\barroz\b.{0,40}\bsimil(es)?\b/],
  "Arroz fortificado": [/\barroz\b.{0,40}\bfortificad[oa]s?\b/],
  "Vaso de Leche": [/\bvaso\s+de\s+leche\b/, /\bp\.?\s?v\.?\s?l\.?\b/],
  "Avena": [/\bavena\b/],
};
const PALABRAS_PRODUCTO = {
  "Avena": ["avena"],
  "Arroz símil": ["simil", "arroz"],
  "Arroz fortificado": ["arroz"],
  "Vaso de Leche": ["leche", "avena", "hojuela", "cereal", "enriquecid", "fortificad", "mezcla"],
};
const URL_DIGESA = "https://consultas-digesa.minsa.gob.pe/ConsultaWebRS/Consultas/Consulta_Registro_Sanitario.aspx";

const COL = {
  descripcion: ["descripcion_objeto", "descripcion_de_objeto", "descripcion_del_item", "descripcion", "objeto_contractual", "sintesis", "item"],
  ganador: ["nombre_razon_social_ganador", "ganador", "postor_ganador", "razon_social_del_postor", "proveedor", "contratista", "adjudicatario", "razon_social", "postor"],
  ruc: ["ruc_ganador", "ruc_postor", "ruc_proveedor", "ruc_contratista", "ruc_adjudicatario", "ruc"],
  entidad: ["entidad_convocante", "nombre_o_sigla_de_la_entidad", "nombre_entidad", "entidad", "comprador"],
  nomenclatura: ["nomenclatura", "codigo_convocatoria", "nro_procedimiento", "proceso", "ocid"],
  monto: ["monto_adjudicado", "monto_contratado", "monto_total", "valor_adjudicado", "vr_ve_cuantia", "valor_referencial", "valor_estimado", "cuantia", "monto"],
  fechaBP: ["fecha_buena_pro", "fecha_de_buena_pro", "fecha_otorgamiento", "fecha_adjudicacion", "fecha_consentimiento"],
  fechaPub: ["fecha_y_hora_de_publicacion", "fecha_publicacion", "fecha_de_publicacion", "fecha_convocatoria"],
  fechaOfertas: ["fecha_presentacion", "presentacion_de_ofertas", "fecha_limite", "fin_presentacion"],
  moneda: ["moneda"],
  estado: ["estado_procedimiento", "estado", "situacion"],
  // DIGESA
  rsCodigo: ["registro_sanitario", "n_registro_sanitario", "nro_registro", "numero_registro", "codigo_registro", "registro"],
  rsProducto: ["nombre_producto", "producto", "descripcion_producto", "denominacion"],
  rsMarca: ["marca"],
  rsTitular: ["titular", "razon_social", "empresa", "fabricante", "solicitante"],
  rsRuc: ["ruc_titular", "ruc_empresa", "ruc"],
  rsVence: ["fecha_vencimiento", "vencimiento", "fecha_vigencia", "vigencia", "fecha_fin"],
  rsEstado: ["estado", "situacion"],
};

/* ---------- utilidades ---------- */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const normalizar = (t) => String(t ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
const clave = (t) => normalizar(t).replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
const digitos = (t) => String(t ?? "").replace(/\D/g, "");

function clasificar(texto) {
  const t = normalizar(texto);
  let cats = Object.keys(PATRONES).filter((c) => PATRONES[c].some((re) => re.test(t)));
  if (cats.includes("Arroz símil")) cats = cats.filter((c) => c !== "Arroz fortificado");
  return CATEGORIAS.filter((c) => cats.includes(c));
}

function productoRelacionado(cat, producto) {
  const t = normalizar(producto);
  const pal = PALABRAS_PRODUCTO[cat] || [];
  return cat === "Arroz símil" ? pal.every((p) => t.includes(p)) : pal.some((p) => t.includes(p));
}

function campo(fila, candidatos) {
  for (const c of candidatos) if (fila[c] !== undefined && String(fila[c]).trim()) return fila[c];
  for (const c of candidatos) {
    for (const k of Object.keys(fila)) {
      if (!c.includes("ruc") && k.startsWith("ruc")) continue;
      if (k.includes(c) && String(fila[k]).trim()) return fila[k];
    }
  }
  return "";
}

function aFecha(v) {
  if (v instanceof Date && !isNaN(v)) return new Date(v.getFullYear(), v.getMonth(), v.getDate());
  if (typeof v === "number" && v > 20000 && v < 80000) { // número de serie de Excel
    const d = new Date(Math.round((v - 25569) * 86400000));
    return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  }
  const s = String(v ?? "").trim().replace("T", " ").split(" ")[0];
  let m = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$/);
  if (m) return new Date(m[3].length === 2 ? 2000 + +m[3] : +m[3], +m[2] - 1, +m[1]);
  return null;
}

function aMonto(v) {
  if (typeof v === "number") return v;
  let s = String(v ?? "").replace(/[^\d,.\-]/g, "");
  if (!s) return null;
  if (s.includes(",") && s.includes(".")) {
    s = s.lastIndexOf(",") > s.lastIndexOf(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  } else if (s.includes(",")) {
    const partes = s.split(",");
    s = partes[partes.length - 1].length <= 2 ? s.replace(",", ".") : s.replace(/,/g, "");
  }
  const n = parseFloat(s);
  return isNaN(n) ? null : n;
}

const fmtFechaHora = (d) => (d ? d.toLocaleString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-");
const fmtFecha = (d) => (d ? d.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "-");
const fmtMonto = (n, mon) => (n == null ? "-" : `${!mon || /pen|sol|s\//i.test(mon) ? "S/" : mon} ${n.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function normalizarEmpresa(n) {
  return normalizar(n).replace(/,/g, " ")
    .replace(/\b(s\.?\s?a\.?\s?c\.?|s\.?\s?a\.?\s?a\.?|s\.?\s?a\.?|e\.?\s?i\.?\s?r\.?\s?l\.?|s\.?\s?r\.?\s?l\.?|s\.?\s?c\.?\s?r\.?\s?l\.?|sociedad anonima cerrada|sociedad anonima)\s*$/, "")
    .replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
}

/* ---------- lectura de archivos ---------- */
async function leerFilas(archivo) {
  const nombre = archivo.name.toLowerCase();
  const buf = await archivo.arrayBuffer();
  if (nombre.endsWith(".json")) return { ocds: JSON.parse(new TextDecoder().decode(buf)) };
  let libro;
  if (nombre.endsWith(".csv") || nombre.endsWith(".txt")) {
    let texto = new TextDecoder("utf-8").decode(buf);
    if (texto.includes("�")) texto = new TextDecoder("windows-1252").decode(buf);
    libro = XLSX.read(texto, { type: "string", cellDates: true, raw: true });
  } else {
    libro = XLSX.read(buf, { type: "array", cellDates: true });
  }
  const filas = [];
  for (const nombreHoja of libro.SheetNames) {
    const matriz = XLSX.utils.sheet_to_json(libro.Sheets[nombreHoja], { header: 1, raw: true, defval: "" });
    let enc = null;
    for (const fila of matriz) {
      if (!enc) {
        if (fila.filter((v) => String(v).trim()).length >= 3) enc = fila.map(clave);
        continue;
      }
      if (!fila.some((v) => String(v).trim())) continue;
      const o = {};
      enc.forEach((k, i) => { if (k && !(k in o)) o[k] = fila[i] ?? ""; });
      filas.push(o);
    }
  }
  return { filas };
}

function procesosDeOCDS(paquete) {
  const rels = [];
  (function recorrer(p) {
    if (Array.isArray(p)) return p.forEach(recorrer);
    if (!p || typeof p !== "object") return;
    if (Array.isArray(p.releases)) return recorrer(p.releases);
    if (Array.isArray(p.records)) return p.records.forEach((r) => recorrer(r.compiledRelease || r));
    if (p.ocid) rels.push(p);
  })(paquete);
  const salida = [];
  for (const r of rels) {
    const t = r.tender || {};
    const texto = [t.title, t.description, ...(t.items || []).map((i) => i.description)].join(" | ");
    const base = {
      nomenclatura: t.id || r.ocid, entidad: (r.buyer || {}).name || "", descripcion: t.description || t.title || "",
      texto, fechaPub: aFecha((t.tenderPeriod || {}).startDate || r.date), fechaOfertas: aFecha((t.tenderPeriod || {}).endDate),
      estado: t.status || "",
    };
    const awards = (r.awards || []).filter((a) => !a.status || ["active", "pending"].includes(a.status));
    if (!awards.length) {
      salida.push({ ...base, monto: aMonto((t.value || {}).amount), moneda: (t.value || {}).currency || "PEN" });
    }
    for (const a of awards) for (const s of a.suppliers || [{}]) {
      const id = digitos((s.identifier || {}).id || s.id);
      salida.push({ ...base, ganador: s.name || "", ruc: id.slice(-11), monto: aMonto((a.value || {}).amount),
        moneda: (a.value || {}).currency || "PEN", fechaBP: aFecha(a.date) });
    }
  }
  return salida;
}

function procesosDeFilas(filas) {
  return filas.map((f) => ({
    nomenclatura: String(campo(f, COL.nomenclatura)),
    entidad: String(campo(f, COL.entidad)),
    descripcion: String(campo(f, COL.descripcion)),
    texto: `${campo(f, COL.descripcion)} | ${campo(f, COL.entidad)}`,
    ganador: String(campo(f, COL.ganador)).trim(),
    ruc: digitos(campo(f, COL.ruc)).slice(-11),
    monto: aMonto(campo(f, COL.monto)),
    moneda: String(campo(f, COL.moneda)) || "PEN",
    fechaBP: aFecha(campo(f, COL.fechaBP)),
    fechaPub: aFecha(campo(f, COL.fechaPub)),
    fechaOfertas: aFecha(campo(f, COL.fechaOfertas)),
    estado: String(campo(f, COL.estado)),
  }));
}

/* ---------- registro sanitario ---------- */
class BaseRegistros {
  constructor() { this.porRuc = new Map(); this.porNombre = new Map(); this.total = 0; this.archivos = []; }
  agregar(filas, nombre) {
    for (const f of filas) {
      const codigo = String(campo(f, COL.rsCodigo)).trim();
      if (!codigo) continue;
      const ruc = digitos(campo(f, COL.rsRuc));
      const vence = aFecha(campo(f, COL.rsVence));
      const estado = String(campo(f, COL.rsEstado));
      const r = { codigo, producto: String(campo(f, COL.rsProducto)), marca: String(campo(f, COL.rsMarca)),
        titular: String(campo(f, COL.rsTitular)), ruc: ruc.length >= 11 ? ruc.slice(-11) : ruc, vence, estado };
      r.vigente = /cancel|vencid|suspend|anulad/i.test(estado) ? false : vence ? vence >= hoy() : null;
      if (r.ruc) (this.porRuc.get(r.ruc) || this.porRuc.set(r.ruc, []).get(r.ruc)).push(r);
      const k = normalizarEmpresa(r.titular);
      if (k) (this.porNombre.get(k) || this.porNombre.set(k, []).get(k)).push(r);
      this.total++;
    }
    this.archivos.push(nombre);
  }
  verificar(p) {
    if (!this.total) return { estado: "NO VERIFICADO", registros: [], relacionados: [],
      nota: "No se cargó una base de registros de DIGESA. Consulta el RUC en la página oficial de DIGESA (enlace abajo)." };
    const regs = (p.ruc && this.porRuc.get(p.ruc)) || this.porNombre.get(normalizarEmpresa(p.ganador)) || [];
    const rel = regs.filter((r) => productoRelacionado(p.categoria, r.producto));
    const notas = [];
    if (/^consorcio/i.test(normalizar(p.ganador))) notas.push("Ganador es un consorcio: verifique a cada empresa consorciada.");
    if (!regs.length) {
      notas.push("No hay registros a nombre del ganador. Puede ser distribuidor de un producto cuyo titular es otra empresa (revise la oferta).");
      return { estado: "SIN REGISTRO SANITARIO", registros: [], relacionados: [], nota: notas.join(" ") };
    }
    if (!rel.length) notas.push(`Tiene registros, pero ninguno parece de ${p.categoria.toLowerCase()}.`);
    if (rel.length && rel.every((r) => r.vigente === false)) notas.push("Todos los registros relacionados figuran vencidos o cancelados.");
    return { estado: "CON REGISTRO SANITARIO", registros: regs, relacionados: rel, nota: notas.join(" ") };
  }
}

function hoy() { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

/* ---------- revisión ---------- */
let REPORTE = null;

async function revisar(archivosSeace, archivosDigesa, desde, hasta, etiqueta) {
  const base = new BaseRegistros();
  const fuentes = [], avisos = [];
  for (const a of archivosDigesa) {
    try { const { filas } = await leerFilas(a); base.agregar(filas || [], a.name); }
    catch (e) { avisos.push(`No se pudo leer ${a.name}: ${e.message}`); }
  }
  let procesos = [];
  for (const a of archivosSeace) {
    try {
      const r = await leerFilas(a);
      const ps = r.ocds ? procesosDeOCDS(r.ocds) : procesosDeFilas(r.filas);
      procesos = procesos.concat(ps.map((p) => ({ ...p, fuente: a.name })));
      fuentes.push(`${a.name} (${ps.length} filas)`);
    } catch (e) { avisos.push(`No se pudo leer ${a.name}: ${e.message}`); }
  }

  const ganadores = [], proximas = [], vistos = new Set();
  for (const p of procesos) {
    const cats = clasificar(p.texto);
    if (!cats.length) continue;
    const adjudicado = p.ganador && !/desierto|nulo|cancelad/i.test(p.estado);
    if (adjudicado) {
      if (desde && p.fechaBP && p.fechaBP < desde) continue;
      if (hasta && p.fechaBP && p.fechaBP > hasta) continue;
    }
    if (!adjudicado) {
      // Un proceso pendiente se muestra una sola vez, con todos sus productos.
      const k = ["p", p.nomenclatura, p.entidad, p.descripcion].join("|");
      if (!vistos.has(k) && !/desierto|nulo|cancelad|adjudicad|consentid|contratad/i.test(p.estado)) {
        vistos.add(k);
        proximas.push({ ...p, categoria: cats.join(" · ") });
      }
      continue;
    }
    for (const categoria of cats) {
      const item = { ...p, categoria };
      const k = [categoria, p.nomenclatura, p.ruc || p.ganador, p.monto].join("|");
      if (vistos.has(k)) continue;
      vistos.add(k);
      item.verif = base.verificar(item);
      ganadores.push(item);
    }
  }
  if (!base.total) avisos.push("Sin base de registros de DIGESA: los ganadores quedan como NO VERIFICADO.");
  if (!procesos.length) avisos.push("No se cargó ningún archivo del SEACE.");
  const orden = (a, b) => (b.fechaBP || b.fechaPub || 0) - (a.fechaBP || a.fechaPub || 0);
  ganadores.sort(orden); proximas.sort(orden);
  REPORTE = { ganadores, proximas, fuentes, avisos, baseDigesa: base.archivos, desde, hasta, etiqueta, generado: new Date() };
  pintar();
}

/* ---------- interfaz ---------- */
const claseEstado = (e) => (e.startsWith("CON") ? "si" : e.startsWith("SIN") ? "no" : "nv");

function tarjetaGanador(g) {
  const v = g.verif;
  const regs = v.relacionados.length ? v.relacionados : v.registros;
  const total = v.totalRegistros || v.registros.length;
  const aviso = !v.relacionados.length && total ? `<p class="sub">La empresa tiene ${total} registros sanitarios, pero ninguno parece de ${esc(g.categoria.toLowerCase())}. ${total > regs.length ? `Se muestran ${regs.length}.` : ""}</p>` : "";
  const tabla = regs.length ? `
    <div class="tabla"><table><thead><tr><th>N.º registro</th><th>Producto</th><th>Marca</th><th>Titular</th><th>Vence</th><th>Estado</th></tr></thead><tbody>
    ${regs.map((r) => `<tr><td>${esc(r.codigo)}</td><td>${esc(r.producto)}</td><td>${esc(r.marca || "-")}</td><td>${esc(r.titular)}</td>
      <td>${fmtFecha(r.vence)}</td><td class="${r.vigente === false ? "rojo" : r.vigente ? "verde" : ""}">${esc(r.vigente === false ? (r.estado || "Vencido") : r.vigente ? "Vigente" : (r.estado || "-"))}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="vacio">No se encontraron registros sanitarios para este ganador.</p>`;
  return `<details class="item"><summary>
      <div><div class="nombre">${esc(g.ganador)}</div>
      <div class="sub">RUC ${esc(g.ruc || "-")} · ${esc(g.entidad)} · ${fmtMonto(g.monto, g.moneda)}${g.fechaBP ? " · B.P. " + fmtFecha(g.fechaBP) : ""}</div></div>
      <span class="badge ${claseEstado(v.estado)}">${esc(v.estado)}</span></summary>
    <div class="cuerpo"><dl>
      <dt>Procedimiento</dt><dd>${esc(g.nomenclatura || "-")}${g.url ? ` · <a href="${esc(g.url)}" target="_blank" rel="noopener">ver en el SEACE</a>` : ""}</dd>
      <dt>Entidad</dt><dd>${esc(g.entidad || "-")}</dd>
      <dt>Descripción</dt><dd>${esc(g.descripcion || "-")}</dd>
      <dt>Monto adjudicado</dt><dd>${fmtMonto(g.monto, g.moneda)}</dd>
      <dt>Fuente</dt><dd>${esc(g.fuente)}</dd></dl>
      <b>Registro sanitario</b>${aviso}${tabla}
      ${v.nota ? `<div class="nota">${esc(v.nota)}</div>` : ""}
      <p class="sub">Confirmar en DIGESA (pestaña "RUC"): <a href="${URL_DIGESA}" target="_blank" rel="noopener">consulta oficial de registro sanitario</a></p>
    </div></details>`;
}

function tarjetaProxima(p) {
  const cierre = p.fechaOfertas ? ` · cierra ${fmtFechaHora(p.fechaOfertas)}` : "";
  return `<details class="item"><summary>
      <div><div class="nombre">${esc(p.descripcion || p.nomenclatura)}</div>
      <div class="sub">${esc(p.entidad)}${p.monto != null ? " · " + fmtMonto(p.monto, p.moneda) : ""}${cierre}</div></div>
      <span class="badge nv">${esc(p.estado || p.categoria)}</span></summary>
    <div class="cuerpo"><dl>
      <dt>Producto</dt><dd>${esc(p.categoria)}</dd>
      <dt>Procedimiento</dt><dd>${esc(p.nomenclatura || "-")}${p.url ? ` · <a href="${esc(p.url)}" target="_blank" rel="noopener">ver en el SEACE</a>` : ""}</dd>
      <dt>Entidad</dt><dd>${esc(p.entidad || "-")}</dd>
      ${p.monto != null ? `<dt>Valor referencial</dt><dd>${fmtMonto(p.monto, p.moneda)}</dd>` : ""}
      <dt>Publicación</dt><dd>${fmtFechaHora(p.fechaPub)}</dd>
      ${p.fechaIniCot ? `<dt>Inicio de cotización</dt><dd>${fmtFechaHora(p.fechaIniCot)}</dd>` : ""}
      <dt>Cierre de cotización / ofertas</dt><dd>${fmtFechaHora(p.fechaOfertas)}</dd>
      <dt>Estado</dt><dd>${esc(p.estado || "Sin buena pro registrada")}</dd>
      <dt>Fuente</dt><dd>${esc(p.fuente)}</dd></dl></div></details>`;
}

function pintar(desplazar = true) {
  const R = REPORTE;
  const c = { si: 0, no: 0, nv: 0 };
  R.ganadores.forEach((g) => c[claseEstado(g.verif.estado)]++);
  const tabs = [...CATEGORIAS.map((cat) => ({ id: cat, titulo: cat, items: R.ganadores.filter((g) => g.categoria === cat), tipo: "g" })),
    { id: "proximas", titulo: "Próximas contrataciones", items: R.proximas, tipo: "p" }];
  $("#resultado").hidden = false;
  $("#resumen").innerHTML = `
    <div class="tarjeta"><b>${R.ganadores.length}</b><span>Ganadores</span></div>
    <div class="tarjeta"><b class="verde">${c.si}</b><span>Con registro sanitario</span></div>
    <div class="tarjeta"><b class="rojo">${c.no}</b><span>Sin registro sanitario</span></div>
    <div class="tarjeta"><b class="gris">${c.nv}</b><span>No verificado</span></div>
    <div class="tarjeta"><b class="azul">${R.proximas.length}</b><span>Próximas contrataciones</span></div>`;
  $("#actualizado").textContent = R.automatico ? `Revisión automática del ${fmtFechaHora(R.generado)} · ganadores de los últimos ${R.dias} días` : "";
  $("#fuentes").textContent = `Fuentes: ${R.fuentes.join("; ") || "ninguna"} · Base DIGESA: ${R.baseDigesa.join(", ") || "no cargada"}`;
  $("#avisos").innerHTML = R.avisos.map((a) => `<div>⚠ ${esc(a)}</div>`).join("");
  $("#avisos").hidden = !R.avisos.length;
  $("#tabs").innerHTML = tabs.map((t, i) => `<button type="button" role="tab" class="${i ? "" : "activo"}" data-i="${i}">${esc(t.titulo)} (${t.items.length})</button>`).join("");
  $("#paneles").innerHTML = tabs.map((t, i) => `<section class="panel-tab ${i ? "" : "activo"}" data-i="${i}">
    ${t.items.length ? t.items.map(t.tipo === "g" ? tarjetaGanador : tarjetaProxima).join("") : `<p class="vacio">Sin resultados.</p>`}</section>`).join("");
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#tabs button, .panel-tab").forEach((x) => x.classList.remove("activo"));
    b.classList.add("activo");
    document.querySelector(`.panel-tab[data-i="${b.dataset.i}"]`).classList.add("activo");
  }));
  if (desplazar) $("#resultado").scrollIntoView({ behavior: "smooth" });
}

/* ---------- PDF ---------- */
function descargarPDF() {
  const R = REPORTE;
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  const azul = [29, 63, 115];
  doc.setFontSize(15); doc.setTextColor(...azul);
  doc.text("Ganadores de licitaciones: avena, arroz símil, arroz fortificado y Vaso de Leche", 40, 45);
  doc.setFontSize(9); doc.setTextColor(60);
  const rango = R.desde || R.hasta ? `Buena pro: ${fmtFecha(R.desde)} al ${fmtFecha(R.hasta)} · ` : "";
  doc.text(`${rango}Generado: ${R.generado.toLocaleString("es-PE")}${R.etiqueta ? " · " + R.etiqueta : ""}`, 40, 62);
  doc.text(doc.splitTextToSize(`Fuentes: ${R.fuentes.join("; ") || "ninguna"} · Base DIGESA: ${R.baseDigesa.join(", ") || "no cargada"}`, 760), 40, 75);
  let y = 95;
  const colorEstado = (e) => (e.startsWith("CON") ? [31, 122, 58] : e.startsWith("SIN") ? [179, 38, 30] : [107, 107, 107]);

  for (const cat of CATEGORIAS) {
    const items = R.ganadores.filter((g) => g.categoria === cat);
    doc.autoTable({
      startY: y, head: [[{ content: `${cat} (${items.length})`, colSpan: 7, styles: { fillColor: azul, fontSize: 11 } }],
        ["Procedimiento", "Entidad", "Descripción", "Ganador / RUC", "Fecha B.P.", "Monto", "Registro sanitario"]],
      body: items.length ? items.map((g) => {
        const regs = g.verif.relacionados.length ? g.verif.relacionados : g.verif.registros;
        const det = regs.slice(0, 4).map((r) => `${r.codigo} - ${r.producto.length > 90 ? r.producto.slice(0, 89) + "…" : r.producto}${r.vence ? " (vence " + fmtFecha(r.vence) + ")" : ""}${r.vigente === false ? " [NO VIGENTE]" : ""}`).join("\n");
        return [g.nomenclatura, g.entidad, g.descripcion.slice(0, 250), `${g.ganador}\nRUC ${g.ruc || "-"}`, fmtFecha(g.fechaBP),
          fmtMonto(g.monto, g.moneda), [g.verif.estado, det, g.verif.nota].filter(Boolean).join("\n")];
      }) : [[{ content: "Sin ganadores en el periodo.", colSpan: 7 }]],
      styles: { fontSize: 7.5, cellPadding: 3, valign: "top" }, headStyles: { fillColor: [221, 228, 240], textColor: 20 },
      columnStyles: { 0: { cellWidth: 85 }, 1: { cellWidth: 110 }, 2: { cellWidth: 150 }, 3: { cellWidth: 120 }, 4: { cellWidth: 55 }, 5: { cellWidth: 70 } },
      didParseCell: (d) => { if (d.section === "body" && d.column.index === 6 && items.length) d.cell.styles.textColor = colorEstado(items[d.row.index].verif.estado); },
      margin: { left: 40, right: 40 },
    });
    y = doc.lastAutoTable.finalY + 16;
    if (y > 470 && cat !== CATEGORIAS[CATEGORIAS.length - 1]) { doc.addPage(); y = 40; }
  }
  if (y > 470) { doc.addPage(); y = 40; }
  doc.autoTable({
    startY: y, head: [[{ content: `Próximas contrataciones (${R.proximas.length})`, colSpan: 6, styles: { fillColor: azul, fontSize: 11 } }],
      ["Producto", "Procedimiento", "Entidad", "Descripción", "Valor referencial", "Publicación / cierre de cotización"]],
    body: R.proximas.length ? R.proximas.map((p) => [p.categoria, p.nomenclatura, p.entidad, p.descripcion.slice(0, 250), fmtMonto(p.monto, p.moneda),
      `${fmtFecha(p.fechaPub)} / ${fmtFechaHora(p.fechaOfertas)}`]) : [[{ content: "Sin procedimientos pendientes en los archivos cargados.", colSpan: 6 }]],
    styles: { fontSize: 7.5, cellPadding: 3, valign: "top" }, headStyles: { fillColor: [221, 228, 240], textColor: 20 },
    margin: { left: 40, right: 40 },
  });
  y = doc.lastAutoTable.finalY + 16;
  doc.setFontSize(7); doc.setTextColor(110);
  doc.text(doc.splitTextToSize("Nota: el registro sanitario se verifica cruzando el RUC o razón social del ganador con la base de DIGESA cargada. " +
    "Un ganador puede ofertar un producto cuyo titular del registro es otra empresa; confirme con la oferta y la consulta oficial de DIGESA.", 760), 40, Math.min(y, 560));
  const n = doc.getNumberOfPages();
  for (let i = 1; i <= n; i++) { doc.setPage(i); doc.setFontSize(7); doc.text(`Página ${i} de ${n}`, 800, 580, { align: "right" }); }
  const d = new Date();
  doc.save(`ganadores_${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}.pdf`);
}

/* ---------- eventos ---------- */
const valorFecha = (id) => ($(id).value ? aFecha($(id).value) : null);

$("#form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const seace = [...$("#seace").files], digesa = [...$("#digesa").files];
  if (!seace.length) { alert("Sube al menos un archivo descargado del SEACE (Excel o CSV)."); return; }
  await revisar(seace, digesa, valorFecha("#desde"), valorFecha("#hasta"), "");
});

/* ---------- datos automáticos (GitHub Actions, cada día) ---------- */
function aFechaISO(v) {
  if (!v) return null;
  const m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0)) : null;
}

async function cargarAutomatico() {
  let d;
  try {
    const r = await fetch(`datos/ultimo.json?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) return;
    d = await r.json();
  } catch { return; }
  const reg = (x) => ({ ...x, vence: aFechaISO(x.fecha_vencimiento) });
  REPORTE = {
    automatico: true, dias: d.dias, fuentes: d.fuentes || [], avisos: d.avisos || [], baseDigesa: d.baseDigesa || [],
    desde: aFechaISO(d.desde), hasta: aFechaISO(d.hasta), etiqueta: "Revisión automática", generado: aFechaISO(d.generado) || new Date(),
    ganadores: (d.ganadores || []).map((g) => ({ ...g, fechaBP: aFechaISO(g.fechaBP),
      verif: { ...g.verif, registros: g.verif.registros.map(reg), relacionados: g.verif.relacionados.map(reg) } })),
    proximas: (d.proximas || []).map((p) => ({ ...p, fechaPub: aFechaISO(p.fechaPub), fechaIniCot: aFechaISO(p.fechaIniCot),
      fechaOfertas: aFechaISO(p.fechaOfertas) })),
  };
  pintar(false);
}

$("#demo").addEventListener("click", async () => {
  const bajar = async (n) => new File([await (await fetch(`demo/${n}`)).blob()], n);
  await revisar([await bajar("demo_buena_pro.csv")], [await bajar("demo_registros_digesa.csv")], null, null, "DATOS DE DEMOSTRACIÓN FICTICIOS");
});

$("#pdf").addEventListener("click", descargarPDF);

$("#volver").addEventListener("click", () => cargarAutomatico());
cargarAutomatico();
