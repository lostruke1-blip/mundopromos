"""Prueba del generador: construye el blog completo en /tmp para revisarlo."""
import json
import os
import re
import shutil
from pathlib import Path

from generador import Generador

SALIDA = Path("/tmp/claude-0/-home-claude/80f5f8ed-3db7-54d8-a491-b70ec09ba097/scratchpad/web")

PROMOS = [
    {
        "id": "Mundopromosapp/1783",
        "canal": "Mundopromosapp",
        "numero": 1783,
        "fecha": "2026-11-06T17:05:03+00:00",
        "actualizado": "2026-11-06T17:20:00+00:00",
        "slug": "muestra-gratis-crema-lancome-1783",
        "titulo": "Muestra gratis de la crema de Lancôme a casa",
        "titulo_seo": "Muestra gratis crema Lancôme (club de probador@s)",
        "descripcion": "Lancôme regala muestras de su nueva crema hidratante. Se pide con el formulario de su web y llega a casa sin coste.",
        "resumen": "Pide la muestra en su web y te llega a casa.",
        "cuerpo_html": "<p>Lancôme está repartiendo muestras de su nueva crema hidratante entre quien se registre en su web. Llega a casa por correo ordinario y no piden ningún pago.</p><h2>Cómo participar</h2><ol><li>Entra en el formulario de Lancôme.</li><li>Rellena tus datos y la dirección de envío.</li><li>Confirma el correo que te mandan.</li></ol><p>El envío tarda unas tres semanas, Mundopromer.</p>",
        "categoria": "muestra",
        "marca": "Lancôme",
        "imagen": "/img/promos/muestra-gratis-crema-lancome-1783.jpg",
        "enlace": "https://www.lancome.es/muestra-gratis",
        "enlaces_extra": [],
        "estado": "activa",
    },
    {
        "id": "Mundopromosapp/1784",
        "canal": "Mundopromosapp",
        "numero": 1784,
        "fecha": "2026-11-07T14:13:03+00:00",
        "actualizado": "2026-11-08T09:00:00+00:00",
        "slug": "mcflurry-gratis-mcdonalds-1784",
        "titulo": "McFlurry gratis en la app de McDonald's",
        "titulo_seo": "McFlurry gratis McDonald's con código",
        "descripcion": "Código para canjear un McFlurry gratis en la app de McDonald's, sin compra mínima.",
        "resumen": "Código para un McFlurry sin compra mínima.",
        "cuerpo_html": "<p>McDonald's repartió un código para canjear un McFlurry gratis desde su app, sin compra mínima y en cualquier restaurante de España.</p><h2>Cómo participar</h2><ol><li>Abre la app de McDonald's.</li><li>Introduce el código en la sección de cupones.</li></ol>",
        "categoria": "gratis",
        "marca": "McDonald's",
        "imagen": None,
        "enlace": "https://www.mcdonalds.es/app",
        "enlaces_extra": [],
        "estado": "agotada",
    },
    {
        "id": "OfertasSupermercadosES/902",
        "canal": "OfertasSupermercadosES",
        "numero": 902,
        "fecha": "2026-11-10T09:30:00+00:00",
        "actualizado": "2026-11-10T09:30:00+00:00",
        "slug": "reembolso-cafe-marcilla-902",
        "titulo": "Reembolso del 100% en el café Marcilla nuevo",
        "titulo_seo": "Reembolso café Marcilla (Sorteo por compra)",
        "descripcion": "Marcilla devuelve el importe del paquete de café si subes el ticket de compra en su promoción.",
        "resumen": "Compra el café, sube el ticket y te devuelven el importe.",
        "cuerpo_html": "<p>Marcilla devuelve el importe íntegro de su café de 250g si subes el ticket a la promoción. Válido en cualquier supermercado de España.</p><h2>Cómo participar</h2><ol><li>Compra el paquete de 250g.</li><li>Sube la foto del ticket en la web de la promoción.</li><li>Recibes el reembolso por transferencia en 30 días.</li></ol><p>En Carrefour, además, el Club suma un 1% en ChequeAhorro.</p>",
        "categoria": "reembolso",
        "marca": "Marcilla",
        "imagen": "/img/promos/reembolso-cafe-marcilla-902.jpg",
        "enlace": "https://www.marcilla.es/reembolso",
        "enlaces_extra": ["https://www.marcilla.es/bases-legales"],
        "estado": "activa",
    },
    {
        "id": "OfertasSupermercadosES/903",
        "canal": "OfertasSupermercadosES",
        "numero": 903,
        "fecha": "2026-11-12T11:00:00+00:00",
        "actualizado": "2026-11-12T11:00:00+00:00",
        "slug": "cupon-5e-dia-mercadona-903",
        "titulo": "Cupón de 5€ de descuento en compras de 30€",
        "titulo_seo": "Cupón 5€ descuento supermercado",
        "descripcion": "Cupón descargable de 5€ de descuento en compras superiores a 30€, válido durante una semana.",
        "resumen": "5€ de descuento en compras de 30€.",
        "cuerpo_html": "<p>Cupón de 5€ de descuento para compras de 30€ o más. Se descarga, se imprime y se entrega en caja.</p><h2>Cómo participar</h2><ol><li>Descarga el cupón.</li><li>Preséntalo en caja antes de pagar.</li></ol>",
        "categoria": "cupon",
        "marca": None,
        "imagen": None,
        "enlace": "https://ejemplo.es/cupon",
        "enlaces_extra": [],
        "estado": "activa",
    },
]


def main():
    gen = Generador("https://mundopromos.com", os.environ.get("API_COMENTARIOS", ""))
    archivos = gen.construir(PROMOS)

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    for ruta, contenido in archivos.items():
        destino = SALIDA / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")

    print(f"{len(archivos)} archivos generados en {SALIDA}\n")
    for ruta in sorted(archivos):
        print(f"  {len(archivos[ruta]):>7} B  {ruta}")

    fallos = []

    def comprobar(condicion, mensaje):
        print(("  OK   " if condicion else "  FALLO") + "  " + mensaje)
        if not condicion:
            fallos.append(mensaje)

    print("\nComprobaciones:")
    esperadas = {
        "promos.css", "promos.html", "sitemap.xml", "promos/datos.json",
        "promo/muestra-gratis-crema-lancome-1783.html",
        "promo/mcflurry-gratis-mcdonalds-1784.html",
        "promo/reembolso-cafe-marcilla-902.html",
        "promo/cupon-5e-dia-mercadona-903.html",
        "promos-muestra.html", "promos-reembolso.html",
        "promos-cupon.html", "promos-gratis.html",
    }
    comprobar(esperadas <= set(archivos), "crea todas las paginas esperadas")
    comprobar("promos-sorteo.html" not in archivos, "no crea categorias vacias")

    promo = archivos["promo/reembolso-cafe-marcilla-902.html"]
    comprobar("{{" not in promo and "{%" not in promo, "no quedan trozos de plantilla sin rellenar")
    comprobar("10 de noviembre de 2026" in promo, "fecha en espanol")
    comprobar('rel="noopener nofollow"' in promo, "enlace externo con nofollow")
    comprobar('<link rel="canonical" href="https://mundopromos.com/promo/reembolso-cafe-marcilla-902.html">' in promo,
               "canonical correcto")
    comprobar("<h2>Cómo participar</h2>" in promo, "el cuerpo HTML no se escapa")
    comprobar('id="comentarios" data-promo="reembolso-cafe-marcilla-902"' in promo, "hueco de comentarios")
    comprobar("ChequeAhorro" in promo, "respeta el texto redactado")

    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', promo, re.S)
    comprobar(ld is not None, "incluye datos estructurados")
    if ld:
        try:
            datos = json.loads(ld.group(1))
            comprobar(datos["@type"] == "Article", "JSON-LD valido de tipo Article")
            comprobar(datos["image"] == "https://mundopromos.com/img/promos/reembolso-cafe-marcilla-902.jpg",
                       "imagen absoluta en el JSON-LD")
        except json.JSONDecodeError as e:
            comprobar(False, f"JSON-LD invalido: {e}")

    agotada = archivos["promo/mcflurry-gratis-mcdonalds-1784.html"]
    comprobar("ya no está disponible" in agotada, "aviso de promocion agotada")
    comprobar("Promoción finalizada" in agotada, "boton desactivado")
    comprobar("https://www.mcdonalds.es/app" not in agotada, "no enlaza a una promo caducada")
    comprobar("🎁" in agotada, "marcador cuando no hay foto")

    indice = archivos["promos.html"]
    comprobar("{{" not in indice and "{%" not in indice, "indice sin restos de plantilla")
    comprobar(indice.count('class="tarjeta') == 4, "las 4 promos en el indice")
    comprobar("3 promociones activas" in indice, "cuenta bien las activas")
    primera = indice.index("cupon-5e-dia-mercadona-903")
    ultima = indice.index("muestra-gratis-crema-lancome-1783")
    comprobar(primera < ultima, "ordenadas de mas nueva a mas vieja")

    mapa = archivos["sitemap.xml"]
    comprobar(mapa.count("<loc>") == 6, "sitemap con portada, indice y 4 promos")
    comprobar("<lastmod>2026-11-12</lastmod>" in mapa, "lastmod en el sitemap")

    tarjetas = gen.tarjetas_inicio([p for p in PROMOS if p["estado"] != "agotada"])
    comprobar(tarjetas.count('class="tarjeta') == 3, "tarjetas de portada solo con activas")
    comprobar("mcflurry" not in tarjetas, "la agotada no sale en portada")

    print("\n" + ("TODO CORRECTO" if not fallos else f"{len(fallos)} FALLOS"))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
