"""MundoPromos · publicador automatico.

Lee los canales de Telegram cada X minutos, convierte lo nuevo en entradas
de blog y lo publica en la web haciendo commit en GitHub.

Variables de entorno necesarias:
  ANTHROPIC_API_KEY   clave de la API de Claude
  GITHUB_TOKEN        token con permiso de escritura en el repo
  GITHUB_PROPIETARIO  por ejemplo lostruke1-blip
  GITHUB_REPO         por ejemplo mundopromos

Opcionales:
  CANALES             separados por coma (por defecto los dos de MundoPromos)
  INTERVALO_MIN       minutos entre revisiones (por defecto 15)
  SITIO               por defecto https://mundopromos.com
  MODELO_REDACTOR     por defecto claude-haiku-5-5
  MAX_POR_CICLO       tope de promos nuevas por vuelta (por defecto 8)
  SOLO_UNA_VEZ        "1" para ejecutar un ciclo y salir
  IMPORTAR_HISTORICO  numero de publicaciones antiguas a importar al arrancar
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone

import canales
from generador import RUTA_PLANTILLAS, Generador
from redactor import FALLO, MAX_IMAGENES, Redactor, generar_slug
from repositorio import Repositorio, descargar_imagen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mundopromos")

RUTA_DATOS = "promos/datos.json"
RUTA_HUELLA = "promos/plantillas.txt"

# Se sube cuando el redactor aprende algo nuevo. Lo que se descarto con una
# version anterior se vuelve a mirar una vez: las publicaciones de solo foto
# se tiraban cuando el redactor todavia no sabia leer imagenes.
VERSION_REDACTOR = 2

# Huecos de la portada que rellena el bot. Cada uno dice que promos lleva
# y cuantas caben. Si un hueco no existe en index.html, se ignora.
BLOQUES = [
    {
        "nombre": "ultimas",
        "cuantas": 6,
        "filtro": lambda p: True,
    },
    {
        "nombre": "cupones",
        "cuantas": 6,
        "filtro": lambda p: p.get("categoria") in ("cupon", "chollo")
        or p.get("canal") == "OfertasSupermercadosES",
    },
    {
        # Solo el canal grande de muestras. Lo del canal de supermercados
        # tiene su propia pestana y aqui no pinta nada.
        "nombre": "muestras",
        "cuantas": 9,
        "filtro": lambda p: p.get("canal") == "Mundopromosapp",
    },
]


def entorno(clave: str, por_defecto=None, obligatoria=False):
    valor = os.environ.get(clave, por_defecto)
    if obligatoria and not valor:
        raise SystemExit(f"Falta la variable de entorno {clave}")
    return valor


class Publicador:
    def __init__(self):
        self.sitio = entorno("SITIO", "https://mundopromos.com")
        self.canales = [
            c.strip()
            for c in entorno("CANALES", "Mundopromosapp,OfertasSupermercadosES").split(",")
            if c.strip()
        ]
        self.max_por_ciclo = int(entorno("MAX_POR_CICLO", "8"))
        self.repo = Repositorio(
            token=entorno("GITHUB_TOKEN", obligatoria=True),
            propietario=entorno("GITHUB_PROPIETARIO", obligatoria=True),
            nombre=entorno("GITHUB_REPO", obligatoria=True),
        )
        self.redactor = Redactor()
        self.generador = Generador(self.sitio, entorno("API_COMENTARIOS", ""))

    # ---------- estado ----------

    def cargar_promos(self) -> list[dict]:
        crudo = self.repo.leer_texto(RUTA_DATOS)
        if not crudo:
            return []
        try:
            return json.loads(crudo).get("promos", [])
        except json.JSONDecodeError:
            log.warning("datos.json ilegible, empiezo de cero")
            return []

    # ---------- publicacion ----------

    def _crear_entrada(self, pub: canales.Publicacion) -> tuple[dict, dict] | None:
        """Devuelve (entrada, archivos_binarios) o None si no se publica."""
        if pub.reenviada:
            return None

        # Las fotos se bajan antes de redactar: el modelo las lee para sacar
        # importes, fechas y condiciones, que muchas veces solo estan ahi.
        fotos = [d for d in (descargar_imagen(u) for u in pub.fotos[:MAX_IMAGENES]) if d]

        if not fotos and len((pub.texto or "").strip()) < 25:
            log.info("  %s sin texto ni foto aprovechable", pub.id)
            return None

        redactado = self.redactor.redactar(pub.texto, pub.canal, pub.enlaces, fotos)
        if redactado is FALLO:
            return FALLO
        if not redactado:
            log.info("  %s descartada por el redactor", pub.id)
            return None

        slug = generar_slug(redactado["titulo"], pub.numero)

        binarios: dict[str, bytes] = {}
        ruta_imagen = None
        if fotos:
            ruta_imagen = f"/img/promos/{slug}.jpg"
            binarios[f"img/promos/{slug}.jpg"] = fotos[0]

        entrada = {
            "id": pub.id,
            "canal": pub.canal,
            "numero": pub.numero,
            "fecha": pub.fecha,
            "actualizado": datetime.now(timezone.utc).isoformat(),
            "slug": slug,
            "titulo": redactado["titulo"],
            "titulo_seo": redactado["titulo_seo"],
            "descripcion": redactado["descripcion"],
            "resumen": redactado["resumen"],
            "cuerpo_html": redactado["cuerpo_html"],
            "categoria": redactado["categoria"],
            "marca": redactado.get("marca"),
            "imagen": ruta_imagen,
            "enlace": pub.enlace_principal,
            "enlaces_extra": pub.enlaces[1:3],
            "estado": "agotada" if pub.agotada else "activa",
        }
        return entrada, binarios

    def _inyectar_en_portada(self, promos: list[dict]) -> dict[str, str]:
        """Rellena cada hueco de index.html con las promos que le tocan."""
        portada = self.repo.leer_texto("index.html")
        if not portada:
            return {}

        original = portada
        activas = [p for p in promos if p.get("estado") != "agotada"]

        # El contador de la cabecera
        marca_i, marca_f = "<!--CUENTA:INICIO-->", "<!--CUENTA:FIN-->"
        if marca_i in portada and marca_f in portada:
            cuantas = len(activas)
            texto = (
                "Actualizado a diario"
                if cuantas < 3
                else f"{cuantas} promociones activas ahora mismo"
            )
            i = portada.index(marca_i) + len(marca_i)
            f = portada.index(marca_f)
            if f > i:
                portada = portada[:i] + texto + portada[f:]

        for bloque in BLOQUES:
            marca_inicio = f"<!--{bloque['nombre'].upper()}:INICIO-->"
            marca_fin = f"<!--{bloque['nombre'].upper()}:FIN-->"
            if marca_inicio not in portada or marca_fin not in portada:
                continue
            inicio = portada.index(marca_inicio) + len(marca_inicio)
            fin = portada.index(marca_fin)
            if fin < inicio:
                log.warning("Marcadores de %s al reves, lo salto", bloque["nombre"])
                continue
            elegidas = [p for p in activas if bloque["filtro"](p)]
            if not elegidas:
                continue
            contenido = self.generador.tarjetas_inicio(elegidas, bloque["cuantas"])
            portada = portada[:inicio] + "\n      " + contenido + "\n      " + portada[fin:]

        return {} if portada == original else {"index.html": portada}

    def _huella_plantillas(self) -> str:
        """Resumen de las plantillas con las que se generan las paginas.

        Si cambia, hay que rehacer todas las paginas aunque no haya ninguna
        promo nueva. Sin esto, un retoque en el disenyo se quedaba esperando
        a que alguien publicara algo en Telegram.
        """
        trozos = []
        for archivo in sorted(RUTA_PLANTILLAS.iterdir()):
            if archivo.is_file():
                trozos.append(archivo.name.encode())
                trozos.append(archivo.read_bytes())
        trozos.append(self.sitio.encode())
        trozos.append(self.generador.api_comentarios.encode())
        return hashlib.sha256(b"|".join(trozos)).hexdigest()[:16]

    def _estaticos_desfasados(self, promos: list[dict]) -> dict[str, str]:
        """Lo que hay que rehacer aunque no haya promos nuevas."""
        huella = self._huella_plantillas()
        guardada = (self.repo.leer_texto(RUTA_HUELLA) or "").strip()

        if guardada != huella:
            log.info("Las plantillas han cambiado, rehago todas las paginas")
            archivos: dict[str, str] = dict(self.generador.construir(promos))
            archivos[RUTA_HUELLA] = huella + "\n"
            return archivos

        # Mismas plantillas: solo comprobamos los archivos sueltos
        generados = self.generador.construir(promos)
        desfasados = {}
        for ruta in ("comentarios.js", "promos.css", "instagram.js", "lupa.js"):
            if ruta in generados and self.repo.leer_texto(ruta) != generados[ruta]:
                desfasados[ruta] = generados[ruta]
        return desfasados

    def ciclo(self, historico: int = 0) -> int:
        promos = self.cargar_promos()
        conocidas = {p["id"]: p for p in promos}
        nuevas, binarios, cambios = [], {}, 0

        for canal in self.canales:
            try:
                if historico:
                    publicaciones = canales.leer_historico(canal, maximo=historico)
                else:
                    publicaciones = canales.leer_recientes(canal)
            except Exception as e:  # noqa: BLE001
                log.error("No pude leer @%s: %s", canal, e)
                continue

            log.info("@%s: %d publicaciones leidas", canal, len(publicaciones))

            # 1. marcar como agotadas las que Aaron ha editado
            for pub in publicaciones:
                existente = conocidas.get(pub.id)
                if existente and pub.agotada and existente.get("estado") != "agotada":
                    existente["estado"] = "agotada"
                    existente["actualizado"] = datetime.now(timezone.utc).isoformat()
                    cambios += 1
                    log.info("  %s marcada como agotada", pub.id)

            # 2. publicar las nuevas, de la mas antigua a la mas reciente
            def toca_mirarla(pub) -> bool:
                guardada = conocidas.get(pub.id)
                if guardada is None:
                    return True
                # Las descartadas por un redactor mas tonto, otra oportunidad
                return bool(guardada.get("descartada")) and (
                    guardada.get("version", 1) < VERSION_REDACTOR
                )

            candidatas = [p for p in publicaciones if toca_mirarla(p)]
            repescadas = sum(1 for p in candidatas if p.id in conocidas)
            if repescadas:
                log.info("  %d descartadas antiguas vuelven a revisarse", repescadas)
            candidatas.sort(key=lambda p: p.numero)
            for pub in candidatas:
                if len(nuevas) >= self.max_por_ciclo:
                    log.info("  tope de %d por ciclo alcanzado", self.max_por_ciclo)
                    break
                resultado = self._crear_entrada(pub)
                if resultado is FALLO:
                    # fallo pasajero: ni la publicamos ni la damos por perdida
                    log.info("  %s se queda para la siguiente vuelta", pub.id)
                    continue
                if not resultado:
                    # la recordamos para no volver a pagar por redactarla
                    conocidas[pub.id] = {
                        "id": pub.id,
                        "descartada": True,
                        "version": VERSION_REDACTOR,
                    }
                    continue
                entrada, bins = resultado
                nuevas.append(entrada)
                conocidas[pub.id] = entrada
                binarios.update(bins)
                log.info("  + %s · %s", entrada["categoria"], entrada["titulo"])

        publicables = [p for p in conocidas.values() if not p.get("descartada")]

        if not nuevas and not cambios:
            desfasados = self._estaticos_desfasados(publicables)
            if not desfasados:
                log.info("Sin novedades")
                return 0
            sha = self.repo.commit(desfasados, "Actualiza " + ", ".join(desfasados))
            log.info("Commit %s · %s al dia", (sha or "")[:7], ", ".join(desfasados))
            return 0

        archivos: dict[str, bytes | str] = dict(self.generador.construir(publicables))
        archivos.update(binarios)
        archivos.update(self._inyectar_en_portada(
            sorted(publicables, key=lambda p: p.get("fecha") or "", reverse=True)
        ))
        # guardamos tambien las descartadas para no reprocesarlas
        archivos[RUTA_HUELLA] = self._huella_plantillas() + "\n"
        archivos[RUTA_DATOS] = json.dumps(
            {
                "actualizado": datetime.now(timezone.utc).isoformat(),
                "promos": sorted(
                    conocidas.values(), key=lambda p: p.get("fecha") or "", reverse=True
                ),
            },
            ensure_ascii=False,
            indent=1,
        )

        if nuevas:
            mensaje = (
                f"Nueva promo: {nuevas[0]['titulo'][:60]}"
                if len(nuevas) == 1
                else f"{len(nuevas)} promos nuevas"
            )
        else:
            mensaje = f"{cambios} promos marcadas como agotadas"

        sha = self.repo.commit(archivos, mensaje)
        log.info("Commit %s · %d archivos", (sha or "")[:7], len(archivos))
        return len(nuevas)


def main() -> None:
    publicador = Publicador()
    historico = int(entorno("IMPORTAR_HISTORICO", "0"))
    intervalo = int(entorno("INTERVALO_MIN", "15")) * 60
    una_vez = entorno("SOLO_UNA_VEZ", "") == "1"

    if historico:
        log.info("Importando hasta %d publicaciones por canal...", historico)
        publicador.ciclo(historico=historico)
        log.info("Importacion terminada. Quita IMPORTAR_HISTORICO para el funcionamiento normal.")
        if una_vez:
            return

    while True:
        try:
            publicador.ciclo()
        except Exception:  # noqa: BLE001
            log.exception("Fallo el ciclo, reintento en la siguiente vuelta")
        if una_vez:
            return
        time.sleep(intervalo)


if __name__ == "__main__":
    main()
