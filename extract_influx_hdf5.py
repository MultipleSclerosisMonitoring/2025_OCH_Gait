#!/usr/bin/env python3
"""
Extrae datos de InfluxDB y (de momento) solo consulta cuántos registros hay
para cada pie en un intervalo de tiempo.

Más adelante guardaremos los datos en HDF5 con la estructura:
  /<referencia>/<YYYYMMDDTHHMMSS>-<YYYYMMDDTHHMMSS>/<pie>
"""

import argparse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml
from influxdb_client import InfluxDBClient


# ------------------------------
# Paso 1: leer argumentos
# ------------------------------
def get_args():
    p = argparse.ArgumentParser(
        description="Extrae datos de InfluxDB y guarda por pie en HDF5."
    )
    p.add_argument(
        "-f", "--from_time", required=True,
        help='Inicio (ej: "2025-07-01 15:59:14")'
    )
    p.add_argument(
        "-u", "--until", required=True,
        help='Fin (ej: "2025-07-01 16:05:18")'
    )
    p.add_argument(
        "-q", "--reference", required=True,
        help='Referencia (ej: "TESTPATIENT-98")'
    )
    p.add_argument(
        "--feet", nargs="+", default=["Left", "Right"],
        help='Pies a extraer (por defecto Left Right)'
    )
    p.add_argument(
        "-o", "--output", default="salida.h5",
        help="Fichero HDF5 de salida (por defecto salida.h5)"
    )
    p.add_argument(
        "--from-tz", default="Europe/Madrid",
        help="Zona horaria de las fechas de entrada"
    )
    p.add_argument(
        "--ref-tag", default="reference",
        help="Nombre del tag en InfluxDB para la referencia"
    )
    p.add_argument(
        "--foot-tag", default="foot",
        help="Nombre del tag en InfluxDB para el pie (Left/Right)"
    )
    return p.parse_args()


# ------------------------------
# Paso 2: leer .config.yaml
# ------------------------------
def load_config(config_path=None):
    """
    Lee .config.yaml y devuelve un dict con:
      cfg["influxdb"] = {url, org, bucket, token}
      cfg["Location"]["zoneInfo"] (opcional)
    """
    cfg_file = Path(config_path or ".config.yaml")
    if not cfg_file.exists():
        raise FileNotFoundError(
            f"No encuentro {cfg_file.resolve()}. Colócalo en la raíz del proyecto."
        )

    with cfg_file.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    needed = ["url", "org", "bucket", "token"]
    miss = [k for k in needed if k not in (cfg.get("influxdb") or {})]
    if miss:
        raise ValueError(
            f"Faltan campos en 'influxdb': {miss}. Revisa {cfg_file}."
        )

    return cfg


# ------------------------------
# Paso 3: manejar fechas
# ------------------------------
def process_date(dt_str, tz_name):
    """
    Recibe una fecha/hora en texto (local) y la zona horaria.
    Devuelve:
      - la misma fecha convertida a UTC en formato RFC3339 (para InfluxDB)
      - una cadena compacta YYYYMMDDTHHMMSS (para el nombre en HDF5)
    """
    s = dt_str.strip().replace("T", " ")
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    dt_local = dt.replace(tzinfo=ZoneInfo(tz_name))

    # Para InfluxDB → UTC RFC3339
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
    utc_rfc3339 = dt_utc.isoformat().replace("+00:00", "Z")

    # Para el HDF5 → nombre compacto en local
    key_str = dt_local.strftime("%Y%m%dT%H%M%S")

    return utc_rfc3339, key_str


# ------------------------------
# Paso 4: construir consulta Flux
# ------------------------------
def make_flux_query(bucket, start_iso, stop_iso, ref_tag, reference, foot_tag, foot):
    """
    Construye la consulta Flux para un pie concreto.
    Filtra por:
      - rango de tiempo [start_iso, stop_iso]
      - referencia (tag ref_tag == reference)
      - pie (tag foot_tag == foot)
    """
    query = f'''
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["{ref_tag}"] == "{reference}")
  |> filter(fn: (r) => r["{foot_tag}"] == "{foot}")
'''
    return query


# ------------------------------
# Programa principal
# ------------------------------
def main():
    args = get_args()
    cfg = load_config()

    # Zona horaria: primero miramos YAML, si no está, usamos la que se pasó por argumento
    tz = (cfg.get("Location") or {}).get("zoneInfo", args.from_tz)

    # Convertimos las dos fechas (local → UTC + nombre HDF5)
    start_iso, start_key = process_date(args.from_time, tz)
    stop_iso,  stop_key  = process_date(args.until, tz)

    # Ruta base que luego usaremos en el HDF5
    hdf5_base = f"/{args.reference}/{start_key}-{stop_key}"

    # ---------- CONEXIÓN A INFLUX ----------
    inf_cfg = cfg["influxdb"]
    client = InfluxDBClient(
    url=inf_cfg["url"],
    token=inf_cfg["token"],
    org=inf_cfg["org"],
    verify_ssl=False,  # Ajustar según el entorno (certificados SSL)
)


    query_api = client.query_api()

    print("Zona local usada:", tz)
    print("Inicio local:", args.from_time, "→ UTC (InfluxDB):", start_iso)
    print("Fin local:   ", args.until,     "→ UTC (InfluxDB):", stop_iso)
    print("Ruta base HDF5 (sin pie aún):", hdf5_base + "/<Foot>")
    print()

    # ---------- CONSULTA POR CADA PIE ----------
    for foot in args.feet:
        flux = make_flux_query(
            bucket=inf_cfg["bucket"],
            start_iso=start_iso,
            stop_iso=stop_iso,
            ref_tag=args.ref_tag,
            reference=args.reference,
            foot_tag=args.foot_tag,
            foot=foot,
        )

        print(f"=== Pie: {foot} ===")
        print("Flux query enviada a Influx:")
        print(flux)
        
        tables = query_api.query(flux)


        # Contar cuántos registros hay
        n_registros = sum(len(t.records) for t in tables)
        print(f"Registros obtenidos de InfluxDB: {n_registros}")
        if n_registros == 0:
            print("⚠️ No hay datos para este pie con esos filtros.")
        print()


if __name__ == "__main__":
    main()



