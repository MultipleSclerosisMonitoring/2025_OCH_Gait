# Paso 0: Estructura. inima con argparse

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
def build_parser():
    p = argparse.ArgumentParser(
        description="Consulta MOCK: genera datos y calcula features sin conectar a Influx"
    )
    p.add_argument('-f','--from_time',required=True,
                   help='Inicio ventana: "YYYY-MM-DD HH:MM:SS" o ISO "YYYY-MM-DDTHH:MM:SSZ"')
    p.add_argument('-u','--until',required=True,
                   help='Fin ventana (mismo formato que --from_time)')
    p.add_argument('-q','--token',required=True, help='Identificador de episodio (query token)')
    p.add_argument('-l','--side', choices=['Left','Right'], required=True, help='Lado del sensor')
    p.add_argument('--fs',type=float, default=50.0, help='Frecuencia de muestreo simulada (Hz)')
    p.add_argument('-v','--verbose',type=int, default=0, choices=[0,1,2], help='Nivel de detalle')
    
    # Paso 4: Exportar CSV y guardar features a fichero
    p.add_argument('--export', metavar='CSV', help='Guardar los datos simulados a CSV')
    p.add_argument('--features', metavar='CSV', help='Guardar features (append) a CSV')

    return p

# Paso 1: Parsear fechas bien (UTC si viene con Z)

from datetime import datetime, timezone

def parse_time(s:str) -> datetime:
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1]
        dt = datetime.fromisoformat(s.replace('T',' ')).replace(tzinfo=timezone.utc)
        return dt
    try:
        dt = datetime.fromisoformat(s.replace('T',' '))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S",):
        try: 
            return datetime.strptime(s,fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError (f"Formato de fecha no soportado: {s!r}")
    
# Paso 2: Simular datos (como si fueran de Influx)

import math
from dataclasses import dataclass
import numpy as np 
import pandas as pd

@dataclass
class MockQuery:
    token: str
    side:str    #"Left" / "Right"
    start: datetime
    end: datetime
    fs: float = 50.0

    def simulate(self) -> pd.DataFrame:
        if self.end <= self.start:
            raise ValueError("'until' debe ser posterior a 'from_time'")
        n = int((self.end - self.start).total_seconds()*self.fs)
        t = np.arange(n) / self.fs

        f_step = 1.6    #Hz aprox caminando
        phase = 0.0 if self.side.lower().startswith('l') else math.pi/6

        ax = 0.2*np.sin(2*np.pi*f_step*t + phase) + 0.05*np.random.randn(n)
        ay = 0.15*np.sin(2*np.pi*f_step*t + phase/2) + 0.05*np.random.randn(n)
        az = 1.0 + 0.25*np.abs(np.sin(2*np.pi*f_step*t + phase)) + 0.05*np.random.randn(n)
        gx = 0.5*np.sin(2*np.pi*f_step*t + phase) + 0.05*np.random.randn(n)
        gy = 0.35*np.sin(2*np.pi*2*f_step*t + phase) + 0.05*np.random.randn(n)
        gz = 0.2*np.sin(2*np.pi*0.75*f_step*t + phase) + 0.05*np.random.randn(n)

        idx = pd.date_range(self.start, periods=n, freq=pd.Timedelta(seconds=1/self.fs), tz=timezone.utc)
        return pd.DataFrame({
            'time': idx,'ax':ax, 'ay':ay, 'az': az,
            'gx':gx, 'gy': gy, 'gz': gz,
            'token': self.token, 'side': self.side
        })

# Paso 3: Calcular features utiles

def compute_features(df: pd.DataFrame) -> dict:
    if df.empty:
        return{'duration_s':0, 
               'cadence_spm':0, 
               'acc_mean':np.nan, 
               'acc_std':np.nan, 
               'gyr_mean':np.nan, 
               'gyr_std':np.nan
               }
    
    acc_mag = np.sqrt(df['ax']**2 + df['ay']**2 + df['az']**2)
    gyr_mag = np.sqrt(df['gx']**2 + df['gy']**2 + df['gz']**2)
    duration_s = (df['time'].iloc[-1] - df['time'].iloc[0]).total_seconds()

    thr = acc_mag.mean() + 0.6*acc_mag.std()
    peaks = (acc_mag.shift(1) < thr) & (acc_mag >= thr)
    n_steps = int(peaks.sum())
    cadence_spm = 60.0 * n_steps / duration_s if duration_s > 0 else 0.0

    return {
        'duration_s': round(float(duration_s),3),
        'cadence_spm': round(float(cadence_spm),3),
        'acc_mean': round(float(acc_mag.mean()),3),
        'acc_std': round(float(acc_mag.std()),3),
        'gyr_mean': round(float(gyr_mag.mean()),3),
        'gyr_std': round(float(gyr_mag.std()),3),
    }

def main ():
    args = build_parser().parse_args()
    start = parse_time(args.from_time)
    end = parse_time(args.until)

    q = MockQuery(args.token, args.side, start, end, args.fs)
    df = q.simulate()

# Paso 4: Exportar CSV  y guardar features a fihchero
    import os
    if args.export:
        df.to_csv(args.export, index=False)
        if args.verbose:
            print(f"[i] Datos exportados a: {args.export}")

    feats = compute_features(df)
    if args.features:
        mode = 'a'if os.path.exists(args.features) else 'w'
        header = not os.path.exists(args.features)
        row = {'token': args.token, 'side': args.side,**feats}
        pd.DataFrame([row]).to_csv(args.features, mode=mode, header=header,index=False)
        if args.verbose:
            print(f"[i] Features añadidas a: {args.features}")
    else:
        print(json.dumps(feats, ensure_ascii=False, indent=2))

    if args.verbose >= 2:
        print ("[i] Primeras filas: \n", df.head().to_string(index=False))

    if args.verbose:
        print("[i] Args OK:", args)
        print(f"[i] Ventana UTC: {start.isoformat()} -> {end.isoformat()}")
    
    import json
    feats = compute_features(df)
    print(json.dumps(feats, ensure_ascii=False, indent=2))
    
    return 0

if __name__=="__main__":
    raise SystemExit(main())
