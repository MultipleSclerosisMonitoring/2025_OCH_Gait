import argparse

# Crear el parser
parser = argparse.ArgumentParser(description="Ejemplo de verbose con niveles")

# Agregar argumento verbose con valor por defecto 
parser.add_argument("--verbose", type=int, choices=[0,1,2,3], default=0, help="Nivel de detalle (0-3)")

# Leer argumentos
args = parser.parse_args()

# Mostrar mensajes según nivel
if args.verbose >= 1:
    print("Proceso iniciado")

if args.verbose >= 2:
    print("Leyendo datos...")

if args.verbose >= 3:
    print("Proceso finalizado")    