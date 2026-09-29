# Versionado de datos con DVC

## Por qué

Hoy los datos no están en Git (por tamaño) y el versionado se apoya en los checksums que el
propio pipeline registra: `source_md5` en el `.meta.json` de Bronze y `file_md5` en
`dataset_lines` de DuckDB. Eso permite **auditar** qué se ingirió, pero no permite
**reproducir** una versión antigua de Silver si la fuente cambió.

DVC añade un `.dvc` por fichero de datos: el fichero real va fuera (S3, GDrive, etc.) y en Git
se versiona solo su hash y sus metadatos.

## Instalación

```bash
pip install dvc
dvc init
```

## Configurar el remoto

```bash
# Opción A: S3 (recomendado para datos)
dvc remote add -d s3store s3://mi-bucket/sipat-etl
aws configure

# Opción B: disco local compartido
dvc remote add -d local /mnt/datos/sipat-etl
```

`.dvc/config` (sin credenciales) queda versionado; las claves van en variables de entorno
o en `~/.aws/credentials`, nunca en el repositorio.

## Versionar las capas

```bash
# Bronze: se versiona solo cuando la fuente cambia (el pipeline ya lo detecta)
dvc add data/bronze/onsv/onsv_1.0.parquet

# Silver y Gold: se versionan en cada entrega
dvc add data/silver/onsv_silver_1.0.parquet
dvc add data/gold/onsv_model_ready_1.0.parquet
```

Como los nombres llevan la versión (`_1.0.parquet`), DVC versiona por **contenido**: si el
contenido no cambió, `dvc add` no crea una entrada nueva.

## Integración con el pipeline

Añadir a `.gitignore` las rutas de datos y dejar que DVC las gestione:

```gitignore
data/bronze/**
data/silver/**
data/gold/**
!data/**/.gitignore
```

Y en el flujo, versionar solo cuando el gate pasa (evita versionar datos que se van a descartar):

```python
# src/orchestration/flow.py, tras build_gold con gate PASSED
if gate_result["status"] in ("PASSED", "WARNING"):
    subprocess.run(["dvc", "add", "-f", silver["path"]], check=False)
```

## Convivencia con los checksums ya existentes

DVC usa MD5 por defecto, y `register_bronze` ya calcula `source_md5`. Ambos coinciden, así que
se puede **verificar la coherencia**:

```bash
dvc status -c     # comprueba que el hash en .dvc coincide con el fichero
```

Si divergen, significa que alguien modificó un Parquet a mano: exactamente el caso que
`data/bronze` inmutable y la comprobación de `source_md5` ya intentan detectar.

## Alternativa: lakehouse

Si los datos crecen mucho (más de unos cientos de GB), DVC con Git se queda corto. El orden
natural de escalado es:

1. **Parquet particionado** por `fecha` en Bronze → no reescribir el histórico.
2. **Delta Lake / Iceberg** sobre object storage → `MERGE`, `DELETE` y time travel.
3. **DuckDB** sigue sirviendo como motor de consulta local sobre esos Parquet.

La ruta de migración está descrita en la sección 10 del informe técnico.
