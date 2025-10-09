import argparse 

# Crear el parser
parser = argparse.ArgumentParser(description="Consulta de datos de marcha desde InfluxDB")

# Definir los argumentos
parser.add_argument("--from_time", type=str, default="2024-01-01 00:00:00", help="Tiempo inicial")
parser.add_argument("--until", type=str, default="2024-01-01 23:59:59", help="Tiempo final")
parser.add_argument("--codigo", type=str, default="CODIGO_DEFAULT", help="Código del sujeto o token")
parser.add_argument("--lado", type=str, choices=["Right", "Left"], default="Right", help="Pie a procesar: Right o Left")

# Leer los argumentos desde la linea de comandos
args = parser.parse_args()

# Mostrar los valores recibidos o por defecto 
print(f"Desde: {args.from_time}")
print(f"Hasta: {args.until}")
print(f"Código: {args.codigo}")
print(f"Lado: {args.lado}")
