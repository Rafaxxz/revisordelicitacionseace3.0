# Prompt para terminar el robot de licitaciones (prod2) en la PC

Copia todo lo que está dentro del bloque y pégalo en tu agente de IA (Claude Code u otro) abierto en la carpeta del proyecto.

```text
Estás en el repositorio "revisordelicitacionseace3.0" (Python). Corres en una PC en Perú, con Chrome, así que SÍ tienes acceso a prod2.seace.gob.pe (desde fuera del Perú responde 403). Tu tarea es terminar y dejar funcionando el robot que revisa las licitaciones grandes del SEACE.

CONTEXTO
- revisor/sources/prod2.py: robot con Playwright (clase RobotSEACE y función recolectar). Se escribió SIN ver el HTML real de prod2, guiándose solo por capturas de pantalla, y se probó contra una réplica local (tests/test_prod2_robot.py). Es muy probable que algunos selectores no coincidan con la página real.
- revisor/buenapro.py: lee el PDF "Reporte de otorgamiento de buena pro" que viene dentro del ZIP "Documentos de Otorgamiento de Buena Pro". Está probado (tests/test_buenapro.py).
- revisor/prod2_local.py: el programa principal (python -m revisor.prod2_local). Abre Chrome visible, llama a recolectar(), luego enriquecer() (DIGESA + contactos del OECE) y escribir() (PDF + JSON en reportes/).
- revisor/sources/prod6.py (categorias_de): filtro de productos (avena, arroz símil, arroz fortificado, Vaso de Leche; excluye heno, forraje, servicios y útiles).

FLUJO MANUAL QUE EL ROBOT DEBE REPETIR
1. Abrir https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml
2. Pestaña "Buscador de Procedimientos de Selección". Llenar "Descripción del Objeto" (avena, arroz, simil, vaso de leche, leche, hojuela). "Año de la Convocatoria" = año actual. Opcional: "Objeto de Contratación" = Bien. Clic en "Buscar". La página tiene reCAPTCHA (insignia abajo a la derecha).
3. Tabla de resultados con columnas: N°, Nombre o Sigla de la Entidad, Fecha y Hora de Publicacion, Nomenclatura, Reiniciado Desde, Objeto de Contratación, Descripción de Objeto, Código SNIP, Código Unico de Inversion, VR/VE/Cuantía, Moneda, Versión SEACE, Acciones. En "Acciones" hay 2 íconos: reloj (historial) y ficha. La ficha abre fichaSeleccion.xhtml?id=<uuid>&ptoRetorno=LOCAL. La tabla está paginada.
4. En la ficha: sección "Ver documentos por Etapa" → tabla "Lista de Documentos" (Nro., Etapa, Documento, Archivo, Fecha y Hora de publicación, Acciones), paginada de 5 en 5. La fila con Etapa "Adjudicación" y Documento "Documentos de Otorgamiento de Buena Pro" tiene un ícono ZIP en "Archivo". Al descargarlo trae "0Acta de otorgamiento de buena pro.pdf" y "1Reporte de otorgamiento de buena pro.pdf".
5. El reporte lista por ítem: "Nombre o Razón Social" con formato RUC-NOMBRE (ej. 10428536890-TICONA MENDEZ NESTOR FAUSTO), "Integrante del Consorcio", "Cantidad Adjudicada" y "Monto Adjudicado".

LO QUE DEBES HACER
1. Instalar: pip install -r requirements.txt  y  python -m playwright install chromium
2. Ejecutar las pruebas: python -m pytest -q  (deben pasar todas antes y después de tus cambios).
3. Abrir prod2 con Playwright en modo visible (headless=False, channel="chrome"). Guardar el HTML real de: el buscador, la tabla de resultados después de buscar "avena", una ficha y la lista de documentos. Guárdalos en tests/datos/prod2_real/ para usarlos como referencia.
4. Con ese HTML real, corregir los selectores de RobotSEACE en revisor/sources/prod2.py:
   - _input_de_fila / buscar: campo "Descripción del Objeto" y botón "Buscar" (probablemente componentes PrimeFaces/JSF; puede que el botón sea un <button> con un <span> "Buscar").
   - _tabla_resultados / leer_resultados: la tabla y sus columnas.
   - siguiente_pagina: el paginador de resultados.
   - abrir_ficha: el ícono de ficha en "Acciones" (confirmar si abre en la misma pestaña o en otra, y si conviene guardar la URL fichaSeleccion.xhtml?id=... e ir directo).
   - documentos_buena_pro: la fila "Documentos de Otorgamiento de Buena Pro" y la descarga del ZIP (paginación de 5 en 5 de la lista de documentos).
   - Después de ver una ficha, recolectar() vuelve a buscar para regresar a los resultados. Si el SEACE permite ir directo a la URL de la ficha, simplifícalo: primero junta todas las URLs de las fichas y luego visítalas.
5. reCAPTCHA: si aparece un desafío, el robot debe pausar y pedir al usuario que lo resuelva en la ventana (ya existe esa pausa en buscar()). NO intentes saltarte ni resolver el captcha de forma automática ni uses servicios para resolverlo.
6. Probar con: python -m revisor.prod2_local --dias 60. Debe listar ganadores reales con RUC y monto, y generar reportes/ganadores_FECHA.pdf y .json. Verifica al menos 2 ganadores comparándolos a mano con el PDF del SEACE.
7. Si el "Reporte de otorgamiento de buena pro" real no se lee bien, guarda uno en tests/datos/ y ajusta revisor/buenapro.py con una prueba nueva que lo use.
8. Actualizar tests/test_prod2_robot.py para que la réplica se parezca al HTML real, y que todas las pruebas pasen.
9. Sé respetuoso con el servidor: pausas de 1 a 2 segundos entre acciones y usa el caché (reportes/prod2_cache.json) para no descargar dos veces lo mismo.
10. Haz commit en la rama claude/stoic-edison-bldhb4 con un mensaje claro y push.

REGLAS
- No borres la revisión automática diaria (.github/workflows/pagina.yml, revisor/publicar.py, revisor/sources/prod6.py) ni la página web (web/).
- No guardes DNI de socios ni representantes.
- Si algo no se puede hacer, explícalo y deja el robot guardando capturas + HTML en reportes/diagnostico/ en el paso que falla.
```
