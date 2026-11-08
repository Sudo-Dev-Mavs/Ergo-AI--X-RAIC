"""Descarga localmente los modelos de MediaPipe que usa ErgoAI (no envía ninguna imagen)."""

from pathlib import Path
from urllib.request import urlretrieve

MODELOS = {
    # Pose del operador: ángulos para REBA.
    "pose_landmarker_heavy.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
    ),
    # Rostros: respaldo para difuminar caras en las tomas de cámara cuando no se detecta la pose.
    "blaze_face_short_range.tflite": (
        "https://storage.googleapis.com/mediapipe-models/face_detector/"
        "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
    ),
}


def main() -> None:
    raiz = Path(__file__).resolve().parents[1]
    for nombre, url in MODELOS.items():
        destino = raiz / "models" / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and destino.stat().st_size > 0:
            print(f"El modelo ya existe: {destino}")
            continue
        print(f"Descargando {nombre} a {destino}...")
        urlretrieve(url, destino)
        print("Modelo descargado correctamente.")


if __name__ == "__main__":
    main()
