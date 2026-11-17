"""Escritura en el repositorio de GitHub.

Hace un unico commit con todos los archivos cambiados, para que Netlify
despliegue una sola vez por ciclo en vez de una por archivo.
"""
from __future__ import annotations

import base64
import io

import requests
from PIL import Image

API = "https://api.github.com"


class Repositorio:
    def __init__(self, token: str, propietario: str, nombre: str, rama: str = "main"):
        self.propietario = propietario
        self.nombre = nombre
        self.rama = rama
        self.s = requests.Session()
        self.s.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    @property
    def _base(self) -> str:
        return f"{API}/repos/{self.propietario}/{self.nombre}"

    # ---------- lectura ----------

    def leer_texto(self, ruta: str) -> str | None:
        r = self.s.get(f"{self._base}/contents/{ruta}", params={"ref": self.rama}, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        contenido = r.json().get("content", "")
        return base64.b64decode(contenido).decode("utf-8")

    # ---------- escritura ----------

    def commit(self, archivos: dict[str, bytes | str], mensaje: str) -> str | None:
        """archivos: {ruta_en_repo: contenido}. Devuelve el sha del commit."""
        if not archivos:
            return None

        ref = self.s.get(f"{self._base}/git/ref/heads/{self.rama}", timeout=30)
        ref.raise_for_status()
        sha_padre = ref.json()["object"]["sha"]

        commit_padre = self.s.get(f"{self._base}/git/commits/{sha_padre}", timeout=30)
        commit_padre.raise_for_status()
        sha_arbol_base = commit_padre.json()["tree"]["sha"]

        entradas = []
        for ruta, contenido in archivos.items():
            if isinstance(contenido, bytes):
                blob = self.s.post(
                    f"{self._base}/git/blobs",
                    json={"content": base64.b64encode(contenido).decode("ascii"), "encoding": "base64"},
                    timeout=60,
                )
            else:
                blob = self.s.post(
                    f"{self._base}/git/blobs",
                    json={"content": contenido, "encoding": "utf-8"},
                    timeout=60,
                )
            blob.raise_for_status()
            entradas.append(
                {"path": ruta, "mode": "100644", "type": "blob", "sha": blob.json()["sha"]}
            )

        arbol = self.s.post(
            f"{self._base}/git/trees",
            json={"base_tree": sha_arbol_base, "tree": entradas},
            timeout=60,
        )
        arbol.raise_for_status()

        nuevo = self.s.post(
            f"{self._base}/git/commits",
            json={"message": mensaje, "tree": arbol.json()["sha"], "parents": [sha_padre]},
            timeout=60,
        )
        nuevo.raise_for_status()
        sha_nuevo = nuevo.json()["sha"]

        actualizar = self.s.patch(
            f"{self._base}/git/refs/heads/{self.rama}", json={"sha": sha_nuevo}, timeout=30
        )
        actualizar.raise_for_status()
        return sha_nuevo


def descargar_imagen(url: str, ancho_max: int = 1200, calidad: int = 82) -> bytes | None:
    """Descarga la foto de Telegram y la deja lista para la web."""
    try:
        r = requests.get(url, timeout=45)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        if img.mode in ("RGBA", "LA", "P"):
            fondo = Image.new("RGB", img.size, (255, 255, 255))
            img = img.convert("RGBA")
            fondo.paste(img, mask=img.split()[-1])
            img = fondo
        else:
            img = img.convert("RGB")
        if img.width > ancho_max:
            alto = round(img.height * ancho_max / img.width)
            img = img.resize((ancho_max, alto), Image.LANCZOS)
        salida = io.BytesIO()
        img.save(salida, format="JPEG", quality=calidad, optimize=True, progressive=True)
        return salida.getvalue()
    except Exception:
        return None
