import sys, os
import datetime
def calcular_distancia(x1, y1, x2, y2):
    """
    Calcula la distancia euclidiana entre dos puntos.

    Args:
        x1 (float): Coordenada x del primer punto.
        y1 (float): Coordenada y del primer punto.
        x2 (float): Coordenada x del segundo punto.
        y2 (float): Coordenada y del segundo punto.

    Returns:
        float: Distancia entre los dos puntos.
    """
    return ((x2 - x1)**2 + (y2 - y1)**2) ** 0.5
def velocidad_media(distancia, tiempo):
    """
    Calcula la velocidad media.

    Args:
        distancia (float): Distancia recorrida en metros.
        tiempo (float): Tiempo en segundos.

    Returns:
        float: Velocidad media en m/s.
    """
    if tiempo == 0:
        return 0.0
    return distancia / tiempo