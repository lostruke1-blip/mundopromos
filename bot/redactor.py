"""Convierte una publicacion de Telegram en una entrada de blog.

Usa Claude Haiku para reescribir el texto con la voz editorial de MundoPromos
y devolver datos estructurados: titulo, titulo SEO, resumen, cuerpo y categoria.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import unicodedata

import anthropic

log = logging.getLogger("mundopromos.redactor")

MODELO = os.environ.get("MODELO_REDACTOR", "claude-haiku-5-5")
# Cuantas fotos del mensaje se le ensenan al modelo. En un album los
# datos suelen repartirse entre las primeras.
MAX_IMAGENES = int(os.environ.get("MAX_IMAGENES", "3"))

CATEGORIAS = [
    "muestra",      # muestra gratis a casa
    "reembolso",    # pruebalo gratis / cashback / reembolso
    "cupon",        # cupon o descuento de supermercado
    "sorteo",       # sorteo
    "chollo",       # oferta puntual, precio bajo
    "gratis",       # producto o servicio gratis sin compra
]

INSTRUCCIONES = """Eres el redactor de MundoPromos, una web espanola de promociones, muestras gratis y chollos.

Recibes una publicacion de un canal de Telegram (texto, imagenes o las dos cosas)
y la conviertes en una entrada de blog.

LAS IMAGENES
- Casi siempre son capturas o carteles de la promocion, y suelen llevar dentro
  los datos que importan: cuanto se ahorra, el producto exacto, el precio, las
  fechas, el supermercado, las condiciones en letra pequena.
- LEELAS con atencion y saca de ahi la informacion, sobre todo cuando el mensaje
  venga sin texto o con cuatro palabras.
- Transcribe cifras, fechas y nombres de producto tal y como aparecen. No los
  redondees ni los adaptes.
- Si la imagen trae un importe de reembolso, el periodo de validez o un limite
  de tickets, ponlo en el cuerpo: es justo lo que la gente necesita saber.
- Lo que no puedas leer con seguridad, omitelo. Nunca adivines un precio, una
  fecha ni un codigo.
- No describas la imagen ("en la foto se ve...", "el cartel dice...", "la imagen
  esta recortada"): el lector no la esta mirando, y hablarle de ella le confunde.
  Usa lo que pone para contar la promocion y ya esta.
- Si falta un dato (las fechas, el limite, la letra pequena), no lo menciones como
  ausencia: remite a las bases o a la web de la promocion con naturalidad.
- Si la imagen lleva una marca de agua de MundoPromos, ignorala.

VOZ EDITORIAL
- Escribes en espanol de Espana, cercano y directo, sin sonar a nota de prensa.
- A los seguidores se les llama "Mundopromer" cuando te diriges a ellos.
- Nada de exagerar ni de prometer lo que el texto original no dice.
- Si el original no deja claro algo, no te lo inventes: omitelo.

REGLAS DE FORMATO (importantes)
- NUNCA incluyas enlaces dentro del cuerpo. Los enlaces van como botones aparte.
- No copies el texto original: reescribelo entero con tus palabras.
- Unidades y precios sin espacio: 5€, 500g, 1,5L, 20%.
- Quita los emojis decorativos del original. Puedes usar alguno suelto si aporta.
- Quita llamadas tipo "activa notificaciones", "corred", "reenvia a tus amigas".
- El cuerpo va en HTML simple: solo <p>, <ul>, <li> y <strong>. Nada mas.
- El cuerpo tiene dos partes: primero de que va la promocion, y despues una
  seccion con los pasos en lista cuyo titulo es EXACTAMENTE este, con tilde:
  <h2>Cómo participar</h2>
- Esa seccion empieza con una frase suelta en su propio <p>, y DESPUES va la
  lista de pasos. Esa frase nunca va dentro de un <li>.
- La PRIMERA FRASE de esa seccion debe ser distinta cada vez: varia la formula,
  no empieces siempre igual.

ORTOGRAFIA
- Estas instrucciones van sin tildes para evitar problemas de codificacion,
  pero TU RESPUESTA debe llevar la ortografia correcta del espanol: tildes,
  enes y signos de apertura (¿ ¡) donde toquen. "Cómo", "más", "según",
  "gratis para ti", "participación", etc.

TITULO SEO
- Si es un sorteo normal, anade " (Sorteo)" al final.
- Si es un sorteo por compra, anade " (Sorteo por compra)".
- Si es un club de probadores, anade " (club de probador@s)".
- En los demas casos, sin sufijo.
- Refleja el tono del original: si el original dice "Siguelos", no pongas "Siguenos".

CASOS ESPECIALES
- Si la promocion es de Carrefour, menciona que con la tarjeta Club Carrefour se
  acumula el 1% de cada compra en ChequeAhorro.
- Si la muestra sale como publicidad en redes y no hay enlace directo, dilo
  claramente y explica que hay que interactuar con las cuentas oficiales de la
  marca para que el anuncio aparezca.

Devuelves SOLO un objeto JSON valido, sin texto alrededor, con estas claves:
{
  "titulo": "titulo corto para la tarjeta, maximo 70 caracteres",
  "titulo_seo": "titulo para Google, maximo 60 caracteres, con sufijo si toca",
  "descripcion": "meta descripcion atractiva e informativa, 120-155 caracteres, sin la URL de la web",
  "resumen": "una o dos frases para la tarjeta de la portada",
  "cuerpo_html": "<p>...</p><h2>Cómo participar</h2><ul><li>...</li></ul>",
  "categoria": "una de: muestra, reembolso, cupon, sorteo, chollo, gratis",
  "marca": "marca o tienda principal, o null si no se identifica",
  "publicable": true
}

Pon "publicable": false solo si ni el texto ni las imagenes contienen una
promocion real (por ejemplo un aviso del canal, un saludo, un meme o un mensaje
administrativo), o si las imagenes estan tan borrosas que no sacas nada en claro."""


class _Fallo:
    """Marca un fallo tecnico, no un 'esto no se publica'.

    Importa distinguirlos: lo que no es publicable se anota para no volver a
    analizarlo (y no volver a pagarlo), pero un fallo pasajero debe
    reintentarse en la siguiente vuelta en vez de perder la promocion.
    """

    def __bool__(self):
        return False

    def __repr__(self):
        return "FALLO"


FALLO = _Fallo()


def _limpiar_json(bruto: str) -> str:
    bruto = bruto.strip()
    if bruto.startswith("```"):
        bruto = re.sub(r"^```(?:json)?\s*", "", bruto)
        bruto = re.sub(r"\s*```$", "", bruto)
    return bruto


def generar_slug(texto: str, numero: int) -> str:
    base = unicodedata.normalize("NFKD", texto or "promo")
    base = base.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    base = "-".join(base.split("-")[:9]) or "promo"
    return f"{base}-{numero}"


class Redactor:
    def __init__(self, api_key: str | None = None, modelo: str = MODELO):
        self.cliente = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.modelo = modelo

    def redactar(
        self,
        texto: str,
        canal: str,
        enlaces: list[str],
        imagenes: list[bytes] | None = None,
    ) -> dict | None:
        """Devuelve el dict de la entrada o None si no es publicable.

        Con imagenes basta aunque no venga texto: muchas promociones se
        publican como una captura sin mas, y los datos estan dentro.
        """
        texto = (texto or "").strip()
        imagenes = [i for i in (imagenes or []) if i][:MAX_IMAGENES]

        # Sin imagen seguimos exigiendo algo de texto; con imagen, no hace falta
        if not imagenes and len(texto) < 25:
            return None

        if texto:
            parte_texto = f"Texto original publicado en Telegram:\n---\n{texto[:4000]}\n---"
        else:
            parte_texto = (
                "La publicacion no lleva texto: solo la imagen. Saca de ella "
                "todo lo que necesites para escribir la entrada."
            )

        contexto = (
            f"Canal de origen: {canal}\n"
            f"Enlaces detectados (NO los metas en el cuerpo, son para los botones): "
            f"{', '.join(enlaces[:5]) if enlaces else 'ninguno'}\n\n"
            f"{parte_texto}"
        )

        contenido: list[dict] = []
        for imagen in imagenes:
            contenido.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(imagen).decode(),
                    },
                }
            )
        contenido.append({"type": "text", "text": contexto})

        try:
            respuesta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=3000,
                system=INSTRUCCIONES,
                messages=[{"role": "user", "content": contenido}],
            )
        except Exception as e:  # noqa: BLE001 - red, limites, caidas
            log.warning("La API fallo (%s), lo reintento en la siguiente vuelta", e)
            return FALLO

        bruto = "".join(
            bloque.text for bloque in respuesta.content if getattr(bloque, "type", "") == "text"
        )

        if respuesta.stop_reason == "max_tokens":
            log.warning("Respuesta cortada por longitud, lo reintento mas adelante")
            return FALLO

        try:
            datos = json.loads(_limpiar_json(bruto))
        except json.JSONDecodeError:
            log.warning("El modelo no devolvio JSON valido: %s", bruto[:160])
            return FALLO

        if not datos.get("publicable", True):
            return None
        if not datos.get("titulo") or not datos.get("cuerpo_html"):
            log.warning("Respuesta sin titulo o sin cuerpo, lo reintento")
            return FALLO

        # El modelo a veces escribe el titular sin tilde. Lo corregimos aqui
        # para que la seccion se llame siempre igual en toda la web.
        datos["cuerpo_html"] = re.sub(
            r"<h2>\s*C[oó]mo participar\s*</h2>",
            "<h2>Cómo participar</h2>",
            datos["cuerpo_html"],
            flags=re.IGNORECASE,
        )

        datos.setdefault("categoria", "chollo")
        if datos["categoria"] not in CATEGORIAS:
            datos["categoria"] = "chollo"
        datos.setdefault("titulo_seo", datos["titulo"])
        datos.setdefault("descripcion", datos.get("resumen", ""))
        datos.setdefault("resumen", "")
        datos.setdefault("marca", None)
        return datos
