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

import json
import logging
import os
import time
from datetime import datetime, timezone

import canales
from generador import Generador
from redactor import Redactor, generar_slug
from repositorio import Repositorio, descargar_imagen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mundopromos")

RUTA_DATOS = "promos/datos.json"

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

        redactado = self.redactor.redactar(pub.texto, pub.canal, pub.enlaces)
        if not redactado:
            log.info("  %s descartada por el redactor", pub.id)
            return None

        slug = generar_slug(redactado["titulo"], pub.numero)

        binarios: dict[str, bytes] = {}
        ruta_imagen = None
        if pub.fotos:
            datos = descargar_imagen(pub.fotos[0])
            if datos:
                ruta_imagen = f"/img/promos/{slug}.jpg"
                binarios[f"img/promos/{slug}.jpg"] = datos

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

    def _estaticos_desfasados(self, promos: list[dict]) -> dict[str, str]:
        """Archivos fijos de la web que ya no coinciden con lo que toca.

        Sin esto, cambiar API_COMENTARIOS o retocar los estilos no llegaba
        nunca a la web si no habia ninguna promo nueva ese dia.
        """
        generados = self.generador.construir(promos)
        desfasados = {}
        for ruta in ("comentarios.js", "promos.css", "instagram.js"):
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
            candidatas = [p for p in publicaciones if p.id not in conocidas]
            candidatas.sort(key=lambda p: p.numero)
            for pub in candidatas:
                if len(nuevas) >= self.max_por_ciclo:
                    log.info("  tope de %d por ciclo alcanzado", self.max_por_ciclo)
                    break
                resultado = self._crear_entrada(pub)
                if not resultado:
                    # la recordamos para no volver a pagar por redactarla
                    conocidas[pub.id] = {"id": pub.id, "descartada": True}
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
