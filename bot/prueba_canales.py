"""Prueba del lector de canales con la estructura real de t.me/s/.

La maquetacion replica la que sirve Telegram: clases tgme_widget_message,
data-post, time[datetime], .tgme_widget_message_photo_wrap con la foto en
background-image y .tgme_widget_message_text con el texto y los enlaces.
"""
from bs4 import BeautifulSoup

import canales

HTML = """
<main>
<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message text_not_supported_wrap js-widget_message"
      data-post="Mundopromosapp/1783" data-view="x">
  <a class="tgme_widget_message_photo_wrap"
     style="width:800px;background-image:url('https://cdn4.telesco.pe/file/AAA_foto1')"
     href="https://t.me/Mundopromosapp/1783"></a>
  <div class="tgme_widget_message_text js-message_text">
   <i class="emoji"><b>&#128680;</b></i> &iexcl;MUESTRA GRATIS DE LANC&Ocirc;ME! A CASA<br/><br/>
   Consigue una muestra gratis de la nueva cream de Lanc&ocirc;me.<br/>
   <a href="https://www.lancome.es/muestra-gratis" target="_blank">P&Iacute;DELA AQU&Iacute;</a><br/>
   Canal: <a href="https://t.me/Mundopromosapp">@Mundopromosapp</a>
  </div>
  <div class="tgme_widget_message_footer">
   <span class="tgme_widget_message_views">5.5K</span>
   <time datetime="2026-11-06T17:05:03+00:00" class="time">17:05</time>
  </div>
 </div>
</div>

<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message js-widget_message" data-post="Mundopromosapp/1784">
  <div class="tgme_widget_message_grouped_wrap">
   <a class="tgme_widget_message_photo_wrap"
      style="background-image:url('https://cdn4.telesco.pe/file/BBB_foto1')"></a>
   <a class="tgme_widget_message_photo_wrap"
      style="background-image:url('https://cdn4.telesco.pe/file/BBB_foto2')"></a>
  </div>
  <div class="tgme_widget_message_text js-message_text">
   15:25 C&oacute;digos agotados<br/>
   MCFLURRY GRATIS en la App McDonald's con el c&oacute;digo P1ST4CH0
  </div>
  <div class="tgme_widget_message_footer">
   <time datetime="2026-11-07T14:13:03+00:00"></time>
  </div>
 </div>
</div>

<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message js-widget_message" data-post="Mundopromosapp/1782">
  <div class="tgme_widget_message_text js-message_text">
   6 Perfumes GRATIS de Yodeyma a casa. Entra en https://www.yodeyma.com/promo y reg&iacute;strate.
  </div>
  <div class="tgme_widget_message_footer">
   <time datetime="2026-11-03T17:07:34+00:00"></time>
  </div>
 </div>
</div>

<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message js-widget_message" data-post="Mundopromosapp/1780">
  <div class="tgme_widget_message_forwarded_from">
   <a href="https://t.me/otrocanal">Reenviado de Otro Canal</a>
  </div>
  <div class="tgme_widget_message_text js-message_text">Contenido reenviado de otro sitio</div>
  <div class="tgme_widget_message_footer"><time datetime="2026-11-01T10:00:00+00:00"></time></div>
 </div>
</div>
</main>
"""


def parsear(html):
    sopa = BeautifulSoup(html, "html.parser")
    pubs = []
    for nodo in sopa.select(".tgme_widget_message"):
        p = canales._parsear_mensaje(nodo)
        if p:
            pubs.append(p)
    pubs.sort(key=lambda p: p.numero)
    return pubs


def main():
    pubs = parsear(HTML)
    por_id = {p.id: p for p in pubs}
    fallos = []

    def comprobar(condicion, mensaje):
        print(("  OK   " if condicion else "  FALLO") + "  " + mensaje)
        if not condicion:
            fallos.append(mensaje)

    print("Publicaciones encontradas:", len(pubs))
    comprobar(len(pubs) == 4, "lee las 4 publicaciones")
    comprobar([p.numero for p in pubs] == [1780, 1782, 1783, 1784], "las ordena por numero")

    a = por_id["Mundopromosapp/1783"]
    print("\n1783 (muestra con foto y enlace)")
    comprobar(a.canal == "Mundopromosapp", "saca el canal")
    comprobar(a.fecha == "2026-11-06T17:05:03+00:00", "saca la fecha ISO")
    comprobar("LANCÔME" in a.texto, "decodifica los acentos del HTML")
    comprobar("🚨" in a.texto, "conserva los emojis del original")
    comprobar(a.fotos == ["https://cdn4.telesco.pe/file/AAA_foto1"], "saca la foto")
    comprobar(a.enlace_principal == "https://www.lancome.es/muestra-gratis", "saca el enlace de participacion")
    comprobar(not any("t.me" in e for e in a.enlaces), "descarta los enlaces a Telegram")
    comprobar(a.agotada is False, "no la marca como agotada")

    b = por_id["Mundopromosapp/1784"]
    print("\n1784 (album de fotos, editada como agotada)")
    comprobar(len(b.fotos) == 2, "saca las 2 fotos del album")
    comprobar(b.agotada is True, "detecta 'Codigos agotados'")

    c = por_id["Mundopromosapp/1782"]
    print("\n1782 (sin foto, enlace suelto en el texto)")
    comprobar(c.fotos == [], "sin fotos")
    comprobar(c.enlace_principal == "https://www.yodeyma.com/promo", "pilla la URL escrita en el texto")

    d = por_id["Mundopromosapp/1780"]
    print("\n1780 (reenviada)")
    comprobar(d.reenviada is True, "detecta que es un reenvio")

    print("\nDeteccion de agotadas:")
    for frase, esperado in [
        ("Promocion FINALIZADA", True),
        ("Ya no queda stock", True),
        ("se acabaron los codigos", True),
        ("Muestra gratis de champu", False),
        ("Aprovecha que vuela", False),
    ]:
        real = bool(canales.PATRON_AGOTADA.search(frase))
        comprobar(real == esperado, f"{frase!r} -> {real}")

    print("\n" + ("TODO CORRECTO" if not fallos else f"{len(fallos)} FALLOS"))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
