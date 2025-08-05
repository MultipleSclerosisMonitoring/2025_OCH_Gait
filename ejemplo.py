import sys, os
import datetime
def calcular_distancia(x1,y1,x2,y2):
"""
Calcula la distancia euclidiana entre dos puntos (x1,y1) y (x2,y2).

Args:
    x1 (float): Coordenada x del primer punto 
    y1 (float): Coordenada y del primer punto
    x2 (float): Coordenada x del segundo punto 
    y2 (float): Coordenada y del segundo punto 

Returns: 
    float: Distancia entre los dos puntos.
"""
return ((x2 - x1)**2 + (y2 - y1)**2) ** 0.5