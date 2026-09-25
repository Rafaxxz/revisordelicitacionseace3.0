# Revisor diario de licitaciones SEACE

Revisa las licitaciones del SEACE para **avena**, **arroz símil**, **arroz fortificado** y el **Programa del Vaso de Leche**. Para cada procedimiento lista a los **ganadores (buena pro)** y verifica si tienen **registro sanitario de DIGESA**. Los resultados se ven en una página web con **pestañas por producto**. Cada ganador es una **pestaña desplegable** que muestra el detalle de su registro sanitario. El reporte completo se puede **descargar en PDF**.

## Página web (sin instalar nada)

**https://rafaxxz.github.io/revisordelicitacionseace3.0/**

1. Descarga del [buscador del SEACE](https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml) (o de OECE/CONOSCE) el Excel con los procesos de avena, arroz o vaso de leche.
2. Súbelo en la página y pulsa **Revisar**: verás los ganadores por producto (cada uno en un desplegable con su registro sanitario) y las **próximas contrataciones** (procesos aún sin buena pro).
3. Pulsa **Descargar PDF**.

Todo se procesa en el navegador. El SEACE y el OECE bloquean las conexiones desde fuera del Perú (también desde los servidores de GitHub), por eso el archivo se descarga desde tu PC. La página se publica sola desde la carpeta `web/` con el workflow `.github/workflows/pagina.yml`.

## Versión Python (opcional)

### Instalación (una sola vez)

Necesitas Python 3.10 o superior.

```bash
pip install -r requirements.txt
```

En Windows puedes hacer doble clic en `iniciar_web.bat`: instala las dependencias y abre el revisor.

## Uso

### Página web

```bash
python -m revisor web
```

Abre http://127.0.0.1:5000, elige la fecha de buena pro y pulsa **Revisar**. Luego pulsa **Descargar PDF**.

Para probar el sistema sin conexión, marca **Usar datos de demostración**. Esos datos son ficticios.

### Consola (para correrlo todos los días)

```bash
python -m revisor --ayer                  # ganadores de ayer + PDF en reportes/
python -m revisor --fecha 2026-09-24      # un día concreto
python -m revisor --desde 2026-09-01      # desde una fecha hasta hoy
python -m revisor --demo                  # datos de demostración
```

Para automatizarlo, programa `revision_diaria.bat` en el *Programador de tareas* de Windows. En Linux o Mac usa cron: `0 8 * * * cd /ruta && python -m revisor --ayer`.

## De dónde salen los datos

### 1. Ganadores (SEACE / OECE)

- **En línea:** el revisor consulta el portal *Contrataciones Abiertas* del OECE (ex OSCE), que publica los datos del SEACE en formato OCDS. Si el OECE cambia la dirección de su API, ajústala con la variable de entorno `OECE_API_URL`.
- **Archivos:** si la consulta en línea falla, descarga el reporte de buena pro desde el SEACE, CONOSCE o el portal de datos abiertos. Súbelo en la página o guárdalo en `data/seace/`. Se aceptan:
  - CSV y XLSX: las columnas se detectan por nombre (entidad, descripción, RUC y razón social del ganador, monto, fecha de buena pro).
  - JSON OCDS.

### 2. Registro sanitario (DIGESA)

Descarga la relación de registros sanitarios de alimentos industrializados de DIGESA (CSV o XLSX). Guárdala en `data/digesa/` o súbela en la página.

El revisor cruza cada ganador **por RUC** y, si no tiene RUC, **por razón social**. Luego marca uno de estos estados:

| Estado | Significado |
|---|---|
| CON REGISTRO SANITARIO | La empresa es titular de registros. Se muestran los relacionados con el producto (avena, arroz, leche…), con su vencimiento. |
| SIN REGISTRO SANITARIO | No hay registros a nombre del ganador. |
| NO VERIFICADO | No se cargó la base de DIGESA. |

> **Importante:** un ganador puede ofertar un producto cuyo registro sanitario pertenece a otra empresa (por ejemplo, un distribuidor o un consorcio). Por eso "SIN REGISTRO" es una alerta para revisar la oferta, no una conclusión definitiva. Confirma siempre en la consulta oficial de DIGESA.

## Estructura

```
revisor/
  categorias.py          reglas para detectar avena, arroz símil, arroz fortificado y Vaso de Leche
  sources/oece.py        consulta en línea al OECE (OCDS)
  sources/archivo.py     importación de CSV / XLSX / JSON
  registro_sanitario.py  cruce con la base de DIGESA
  revisor.py             orquestación
  pdf.py                 reporte PDF
  app.py + templates/    página web
data/demo/               datos ficticios de prueba
tests/                   pruebas (python -m pytest)
```
