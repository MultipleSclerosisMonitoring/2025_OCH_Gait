import argparse 
from datetime import datetime

# Crear el parser
parser = argparse.ArgumentParser(description="Comparar dos fechas")

# Definir los argumentos
parser.add_argument("--desde", type=str, default="2024-01-01 00:00:00", help="Fecha de inicio")
parser.add_argument("--hasta", type=str, default="2024-01-01 23:59:59", help="Fecha final")

# Leer argumentos
args = parser.parse_args()

# Convertir las fechas de texto a datetime
formato = "%Y-%m-%d %H:%M:%S"
fecha_desde = datetime.strptime(args.desde, formato)
fecha_hasta = datetime.strptime(args.hasta, formato)

# Comparar las fechas
if fecha_hasta > fecha_desde:
    print("Fechas válidas: la final es posterior a la inicial")
else: 
    print("Error: la fecha final debe ser posterior a la inicial")
    