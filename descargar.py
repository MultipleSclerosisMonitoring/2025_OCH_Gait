import argparse

# Crear el parser
parser = argparse.ArgumentParser(description="Controlar si se guarda la descarga")

# Argumento booleano (manual)
parser.add_argument("--guardar", action='store_true', help="Si se incluye, se guarda el archivo")

# Leer argumentos
args = parser.parse_args()

# Evaluar el valor de guardar
if args.guardar:
    print("Descarga guardada correctamente")
else: print("Descarga descartada")
