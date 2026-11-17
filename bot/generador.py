"""Genera los archivos HTML del blog a partir de la lista de promociones."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

ETIQUETAS = {
    "muestra": "Muestra gratis",
    "reembolso": "Reembolso",
    "cupon": "Cupón",
    "sorteo": "Sorteo",
    "chollo": "Chollo",
    "gratis": "Gratis",
}

RUTA_PLANTILLAS = Path(__file__).parent / "plantillas"


def fecha_legible(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


class Generador:
    def __init__(self, sitio: str = "https://mundopromos.com", api_comentarios: str = ""):
        self.sitio = sitio.rstrip("/")
        self.api_comentarios = (api_comentarios or "").rstrip("/")
        self.env = Environment(
            loader=FileSystemLoader(str(RUTA_PLANTILLAS)),
            autoescape=select_autoescape(enabled_extensions=(), default=False),
        )

    # ---------- piezas ----------

    def _ld_json(self, p: dict) -> str:
        datos = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": p["titulo"][:110],
            "description": p.get("descripcion", ""),
            "datePublished": p.get("fecha"),
            "dateModified": p.get("actualizado", p.get("fecha")),
            "author": {"@type": "Organization", "name": "MundoPromos"},
            "publisher": {
                "@type": "Organization",
                "name": "MundoPromos",
                "logo": {"@type": "ImageObject", "url": f"{self.sitio}/og.png"},
            },
            "mainEntityOfPage": f"{self.sitio}/promo/{p['slug']}.html",
        }
        if p.get("imagen"):
            datos["image"] = f"{self.sitio}{p['imagen']}"

        # La miga de pan, para que Google la muestre bajo el titulo
        miga = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio",
                 "item": f"{self.sitio}/"},
                {"@type": "ListItem", "position": 2, "name": "Promociones",
                 "item": f"{self.sitio}/promos.html"},
                {"@type": "ListItem", "position": 3,
                 "name": ETIQUETAS.get(p["categoria"], p["categoria"]),
                 "item": f"{self.sitio}/promos-{p['categoria']}.html"},
            ],
        }
        return json.dumps([datos, miga], ensure_ascii=False, indent=1)

    def pagina_promo(self, p: dict, relacionadas: list[dict]) -> str:
        plantilla = self.env.get_template("promo.html")
        canal = "Mundopromosapp" if p.get("canal") == "Mundopromosapp" else "OfertasSupermercadosES"
        return plantilla.render(
            p=p,
            sitio=self.sitio,
            etiqueta_categoria=ETIQUETAS.get(p["categoria"], p["categoria"]),
            fecha_legible=fecha_legible(p.get("fecha")),
            datos_estructurados=self._ld_json(p),
            relacionadas=[self._enriquecer(r) for r in relacionadas],
            canal_telegram=canal,
            anio=datetime.now(timezone.utc).year,
        )

    def _enriquecer(self, p: dict) -> dict:
        return dict(
            p,
            fecha_legible=fecha_legible(p.get("fecha")),
            etiqueta=ETIQUETAS.get(p.get("categoria"), p.get("categoria", "")),
        )

    def pagina_indice(self, promos: list[dict]) -> str:
        plantilla = self.env.get_template("indice.html")
        enriquecidas = [self._enriquecer(p) for p in promos]
        return plantilla.render(
            promos=enriquecidas,
            sitio=self.sitio,
            activas=sum(1 for p in promos if p.get("estado") != "agotada"),
            anio=datetime.now(timezone.utc).year,
        )

    def sitemap(self, promos: list[dict]) -> str:
        urls = [
            f"  <url>\n    <loc>{self.sitio}/</loc>\n"
            f"    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>",
            f"  <url>\n    <loc>{self.sitio}/promos.html</loc>\n"
            f"    <changefreq>hourly</changefreq>\n    <priority>0.9</priority>\n  </url>",
        ]
        # Las paginas de categoria tambien tienen que entrar: son las que
        # pueden posicionar por "muestras gratis", "cupones supermercado"...
        categorias = {p["categoria"] for p in promos if p.get("categoria") in ETIQUETAS}
        for cat in sorted(categorias):
            urls.append(
                f"  <url>\n    <loc>{self.sitio}/promos-{cat}.html</loc>\n"
                f"    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>"
            )
        for p in promos:
            fecha = (p.get("actualizado") or p.get("fecha") or "")[:10]
            urls.append(
                f"  <url>\n    <loc>{self.sitio}/promo/{p['slug']}.html</loc>\n"
                + (f"    <lastmod>{fecha}</lastmod>\n" if fecha else "")
                + "    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )

    def tarjetas_inicio(self, promos: list[dict], cuantas: int = 6) -> str:
        """Fragmento que se inyecta en la portada entre los marcadores."""
        trozos = []
        for p in promos[:cuantas]:
            img = (
                f'<img src="{p["imagen"]}" alt="{p["titulo"]}" width="400" height="168" loading="lazy">'
                if p.get("imagen")
                else '<div class="sinfoto">🎁</div>'
            )
            caducada = " caducada" if p.get("estado") == "agotada" else ""
            trozos.append(
                f'<a class="tarjeta{caducada}" href="/promo/{p["slug"]}.html">{img}'
                f'<div class="cuerpo"><span class="etiqueta cat-{p["categoria"]}">'
                f'{ETIQUETAS.get(p["categoria"], p["categoria"])}</span>'
                f'<h3>{p["titulo"]}</h3><p>{p.get("resumen","")}</p>'
                f'<span class="pie">{fecha_legible(p.get("fecha"))}</span></div></a>'
            )
        return "\n      ".join(trozos)

    # ---------- todo junto ----------

    def construir(self, promos: list[dict]) -> dict[str, str]:
        """Devuelve {ruta_en_repo: contenido} de todo el blog."""
        ordenadas = sorted(promos, key=lambda p: p.get("fecha") or "", reverse=True)
        archivos: dict[str, str] = {}

        archivos["promos.css"] = (RUTA_PLANTILLAS / "estilos.css").read_text(encoding="utf-8")
        archivos["comentarios.js"] = (
            (RUTA_PLANTILLAS / "comentarios.js")
            .read_text(encoding="utf-8")
            .replace("__API_COMENTARIOS__", self.api_comentarios)
        )

        for i, p in enumerate(ordenadas):
            relacionadas = [
                r for r in ordenadas
                if r["slug"] != p["slug"] and r.get("estado") != "agotada"
            ][:3]
            archivos[f"promo/{p['slug']}.html"] = self.pagina_promo(p, relacionadas)

        archivos["promos.html"] = self.pagina_indice(ordenadas[:60])

        for cat in ETIQUETAS:
            de_la_cat = [p for p in ordenadas if p["categoria"] == cat][:60]
            if de_la_cat:
                archivos[f"promos-{cat}.html"] = self.pagina_indice(de_la_cat)

        archivos["sitemap.xml"] = self.sitemap(ordenadas[:500])
        archivos["promos/datos.json"] = json.dumps(
            {"actualizado": datetime.now(timezone.utc).isoformat(), "promos": ordenadas},
            ensure_ascii=False,
            indent=1,
        )
        return archivos
