"""Decide si un comentario se publica solo, espera revision o es spam."""
from __future__ import annotations

import re
import unicodedata

# Lo que casi siempre es spam en una web de promociones
PALABRAS_SPAM = [
    "casino", "bitcoin", "crypto", "forex", "viagra", "cialis", "porn", "xxx",
    "escort", "prestamo rapido", "credito rapido", "gana dinero", "ganar dinero desde casa",
    "trabaja desde casa", "inversion garantizada", "hackear", "seguidores gratis",
    "telegram.me", "wa.me", "whatsapp +", "bit.ly", "tinyurl", "cutt.ly", "t.co/",
]

# Insultos frecuentes en castellano. No busca moralizar, solo evitar peleas.
PALABRAS_FEAS = [
    "gilipollas", "hijo de puta", "hijaputa", "hijoputa", "cabron", "subnormal",
    "retrasado", "maricon", "puta madre", "mierda de", "payaso de", "imbecil",
    "idiota", "estafador", "ladrones de mierda",
]

URL = re.compile(r"(https?://|www\.|\b[\w-]+\.(?:com|es|net|org|io|xyz|top|ru|click|shop)\b)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
TELEFONO = re.compile(r"(?:\+34[\s-]?)?[6-7]\d{2}[\s-]?\d{3}[\s-]?\d{3}")
REPETIDO = re.compile(r"(.)\1{6,}")
MAYUSCULAS = re.compile(r"[A-ZÁÉÍÓÚÑ]")
LETRAS = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]")


def normalizar(texto: str) -> str:
    """minusculas y sin tildes, para que 'gilipoyas' y 'GILIPOLLAS' casen igual."""
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def _contiene(texto_normalizado: str, lista: list[str]) -> str | None:
    for palabra in lista:
        if palabra in texto_normalizado:
            return palabra
    return None


def revisar(nombre: str, texto: str, milisegundos: int, trampa: str) -> tuple[str, str]:
    """Devuelve (estado, motivo).

    estado: 'publicado' (pasa directo), 'pendiente' (a revisar) o 'spam' (fuera).
    """
    # 1. Trampa invisible: un humano nunca rellena ese campo
    if trampa.strip():
        return "spam", "trampa rellenada"

    # 2. Enviado demasiado rapido para haberlo escrito
    if 0 < milisegundos < 2500:
        return "spam", "enviado en menos de 3 segundos"

    n_texto = normalizar(texto)
    n_nombre = normalizar(nombre)

    palabra = _contiene(n_texto, PALABRAS_SPAM) or _contiene(n_nombre, PALABRAS_SPAM)
    if palabra:
        return "spam", f"palabra de spam: {palabra}"

    if EMAIL.search(texto) or TELEFONO.search(texto):
        return "spam", "incluye contacto personal"

    if URL.search(texto) or URL.search(nombre):
        return "pendiente", "incluye un enlace"

    palabra = _contiene(n_texto, PALABRAS_FEAS) or _contiene(n_nombre, PALABRAS_FEAS)
    if palabra:
        return "pendiente", f"posible insulto: {palabra}"

    letras = LETRAS.findall(texto)
    if len(letras) >= 12:
        proporcion = len(MAYUSCULAS.findall(texto)) / len(letras)
        if proporcion > 0.7:
            return "pendiente", "todo en mayusculas"

    if REPETIDO.search(texto):
        return "pendiente", "caracteres repetidos"

    if len(set(n_texto.split())) <= 1 and len(texto) > 40:
        return "pendiente", "texto repetitivo"

    return "publicado", ""
