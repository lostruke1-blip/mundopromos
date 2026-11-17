"""Panel de moderacion: una sola pagina, sin JavaScript."""
from __future__ import annotations

from datetime import datetime
from html import escape

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha(iso: str) -> str:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    return f"{d.day} {MESES[d.month - 1]} · {d.hour:02d}:{d.minute:02d}"


def _boton(ficha, ident, que, etiqueta, clase, confirmar=""):
    extra = f' onsubmit="return confirm(\'{confirmar}\')"' if confirmar else ""
    return (
        f'<form method="post" action="/panel/accion"{extra}>'
        f'<input type="hidden" name="ficha" value="{escape(ficha)}">'
        f'<input type="hidden" name="id" value="{ident}">'
        f'<input type="hidden" name="que" value="{que}">'
        f'<button class="b {clase}">{etiqueta}</button></form>'
    )


def _tarjeta_pendiente(c, ficha):
    motivo = f'<span class="motivo">{escape(c.get("motivo") or "")}</span>' if c.get("motivo") else ""
    return f"""
    <article class="c">
      <p class="meta"><strong>{escape(c["nombre"])}</strong> · {fecha(c["fecha"])} ·
         <a href="https://mundopromos.com/promo/{escape(c["promo"])}.html" target="_blank">{escape(c["promo"])}</a>
         {motivo}</p>
      <p class="txt">{escape(c["texto"])}</p>
      <div class="acciones">
        {_boton(ficha, c["id"], "aprobar", "Publicar", "ok")}
        {_boton(ficha, c["id"], "rechazar", "Rechazar", "no")}
        {_boton(ficha, c["id"], "bloquear", "Bloquear a esta persona", "bloq",
                "Esto rechaza todos sus comentarios. Seguro?")}
      </div>
    </article>"""


def _fila_reciente(c, ficha):
    return f"""
    <tr>
      <td><span class="e e-{escape(c["estado"])}">{escape(c["estado"])}</span></td>
      <td><strong>{escape(c["nombre"])}</strong><br><span class="peq">{fecha(c["fecha"])}</span></td>
      <td class="txt">{escape(c["texto"][:220])}</td>
      <td class="acciones">
        {_boton(ficha, c["id"], "aprobar", "Publicar", "ok") if c["estado"] != "publicado" else
         _boton(ficha, c["id"], "rechazar", "Ocultar", "no")}
        {_boton(ficha, c["id"], "borrar", "Borrar", "del", "Se borra para siempre. Seguro?")}
      </td>
    </tr>"""


def pagina_panel(pendientes, recientes, resumen, ficha) -> str:
    cuerpo_pendientes = (
        "".join(_tarjeta_pendiente(c, ficha) for c in pendientes)
        if pendientes
        else '<p class="vacio">No hay nada pendiente. Todo al día.</p>'
    )
    filas = "".join(_fila_reciente(c, ficha) for c in recientes)

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Moderación · MundoPromos</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#eef5f5;color:#11262b;line-height:1.55}}
header{{background:#06999a;color:#fff;padding:1rem 1.2rem;display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}}
header h1{{font-size:1.2rem;font-weight:800}}
header .r{{font-size:13px;opacity:.9}}
main{{max-width:900px;margin:0 auto;padding:1.4rem 1rem 3rem}}
h2{{font-size:1.05rem;margin:1.6rem 0 .7rem}}
.c{{background:#fff;border:1px solid #cfe6e6;border-radius:12px;padding:.9rem 1rem;margin-bottom:.8rem}}
.meta{{font-size:12.5px;color:#5f7a7d;margin-bottom:.4rem}}
.meta a{{color:#04747a}}
.motivo{{background:#fef3c7;color:#92400e;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:.4rem}}
.txt{{font-size:14.5px;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:anywhere}}
.acciones{{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.7rem}}
.b{{font:inherit;font-size:13px;font-weight:600;border:0;border-radius:8px;padding:.45rem .9rem;cursor:pointer;color:#fff}}
.ok{{background:#12734a}} .no{{background:#8a9a9b}} .bloq{{background:#b45309}} .del{{background:#c0392b}}
.vacio{{color:#5f7a7d;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #cfe6e6;border-radius:12px;overflow:hidden}}
td{{padding:.6rem .7rem;border-top:1px solid #e7f1f1;vertical-align:top;font-size:13px}}
tr:first-child td{{border-top:0}}
.peq{{font-size:11.5px;color:#5f7a7d}}
.e{{font-size:10.5px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:20px}}
.e-publicado{{background:#dcf5e6;color:#12734a}}
.e-rechazado{{background:#eceff0;color:#5f7a7d}}
.e-spam{{background:#ffe4e6;color:#be123c}}
@media(max-width:620px){{table,tbody,tr,td{{display:block;width:100%}}td{{border-top:0}}tr{{border-top:1px solid #e7f1f1;padding:.5rem 0}}}}
</style></head><body>
<header>
  <h1>Moderación de comentarios</h1>
  <span class="r">{resumen.get('publicado', 0)} publicados ·
    {resumen.get('pendiente', 0)} pendientes ·
    {resumen.get('spam', 0)} spam ·
    {resumen.get('rechazado', 0)} rechazados</span>
</header>
<main>
  <h2>Pendientes de revisar ({len(pendientes)})</h2>
  {cuerpo_pendientes}
  <h2>Últimos movimientos</h2>
  <table><tbody>{filas or '<tr><td class="vacio">Todavía nada.</td></tr>'}</tbody></table>
</main>
</body></html>"""
