"""Lectura de los canales publicos de Telegram via t.me/s/<canal>.

No necesita API ni bot: la vista previa publica de Telegram sirve el HTML
con texto, fotos, fecha y enlaces de cada publicacion.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Marcas de que una promo ya no esta disponible. Aaron edita los posts
# para avisar ("Codigos agotados", "FINALIZADA"...), asi que lo detectamos.
PATRON_AGOTADA = re.compile(
    r"\b(agotad|caducad|finaliz|termin|expirad|ya no (?:est|funciona|queda)|"
    r"se acab|cerrad[ao] el plazo|sin stock|fuera de stock)",
    re.IGNORECASE,
)

RE_URL = re.compile(r"https?://[^\s)\]\"'<>]+")

# Dominios que nunca son el enlace de participacion
DOMINIOS_IGNORADOS = (
    "t.me",
    "telegram.me",
    "telegram.org",
    "telesco.pe",
)


@dataclass
class Publicacion:
    id: str                      # "Mundopromosapp/1788"
    canal: str
    numero: int
    fecha: str | None            # ISO 8601
    texto: str
    fotos: list[str] = field(default_factory=list)
    enlaces: list[str] = field(default_factory=list)
    reenviada: bool = False

    @property
    def agotada(self) -> bool:
        return bool(PATRON_AGOTADA.search(self.texto))

    @property
    def enlace_principal(self) -> str | None:
        return self.enlaces[0] if self.enlaces else None


def _fondo(estilo: str) -> str | None:
    m = re.search(r"url\(['\"]?(.*?)['\"]?\)", estilo or "")
    return m.group(1) if m else None


def _es_enlace_util(url: str) -> bool:
    return not any(d in url for d in DOMINIOS_IGNORADOS)


def _parsear_mensaje(nodo) -> Publicacion | None:
    post = nodo.get("data-post") or ""
    if "/" not in post:
        return None
    canal, _, num = post.partition("/")
    if not num.isdigit():
        return None

    hora = nodo.select_one("time")
    fecha = hora.get("datetime") if hora else None

    nodo_texto = nodo.select_one(".tgme_widget_message_text")
    texto = nodo_texto.get_text("\n", strip=True) if nodo_texto else ""

    fotos = []
    for envoltorio in nodo.select(".tgme_widget_message_photo_wrap"):
        url = _fondo(envoltorio.get("style", ""))
        if url:
            fotos.append(url)

    enlaces: list[str] = []
    if nodo_texto:
        for a in nodo_texto.select("a[href]"):
            href = a["href"]
            if _es_enlace_util(href):
                enlaces.append(href)
    for suelto in RE_URL.findall(texto):
        if _es_enlace_util(suelto):
            enlaces.append(suelto)

    # quitar duplicados conservando el orden
    vistos: set[str] = set()
    enlaces = [u for u in enlaces if not (u in vistos or vistos.add(u))]

    return Publicacion(
        id=post,
        canal=canal,
        numero=int(num),
        fecha=fecha,
        texto=texto,
        fotos=fotos,
        enlaces=enlaces,
        reenviada=bool(nodo.select_one(".tgme_widget_message_forwarded_from")),
    )


def leer_pagina(canal: str, antes: int | None = None, timeout: int = 25) -> list[Publicacion]:
    """Devuelve las publicaciones de una pagina del canal, de vieja a nueva."""
    url = f"https://t.me/s/{canal}"
    if antes:
        url += f"?before={antes}"
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    sopa = BeautifulSoup(resp.text, "html.parser")

    publicaciones = []
    for nodo in sopa.select(".tgme_widget_message"):
        pub = _parsear_mensaje(nodo)
        if pub:
            publicaciones.append(pub)
    publicaciones.sort(key=lambda p: p.numero)
    return publicaciones


def leer_recientes(canal: str) -> list[Publicacion]:
    """Ultimas publicaciones del canal."""
    return leer_pagina(canal)


def leer_historico(canal: str, maximo: int = 200, pausa: float = 1.5) -> list[Publicacion]:
    """Recorre el canal hacia atras hasta juntar `maximo` publicaciones."""
    todas: dict[str, Publicacion] = {}
    cursor: int | None = None

    while len(todas) < maximo:
        lote = leer_pagina(canal, antes=cursor)
        nuevas = [p for p in lote if p.id not in todas]
        if not nuevas:
            break
        for p in nuevas:
            todas[p.id] = p
        cursor = min(p.numero for p in lote)
        if cursor <= 1:
            break
        time.sleep(pausa)  # no apretar a los servidores de Telegram

    ordenadas = sorted(todas.values(), key=lambda p: p.numero, reverse=True)
    return ordenadas[:maximo]
