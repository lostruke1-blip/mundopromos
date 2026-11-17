/* Invitacion a seguir @mundopromos en Instagram.
   Sale una sola vez, cuando la persona ya lleva un rato leyendo, y si la
   cierra no vuelve a aparecer. Se trae sus propios estilos para poder
   cargarse igual en la portada que en las paginas de promo. */
(function () {
  "use strict";

  var CUENTA = "mundopromos";
  var CLAVE = "mp_ig_cerrado";
  var DIAS = 45;
  var SEGUNDOS = 12;
  var SCROLL = 0.35;

  // Si ya lo cerro, ni lo montamos
  try {
    var guardado = localStorage.getItem(CLAVE);
    if (guardado && Date.now() - Number(guardado) < DIAS * 86400000) return;
  } catch (e) { /* navegacion privada: se muestra igual */ }

  // Quien viene de Instagram no necesita que le inviten a Instagram
  if (document.referrer.indexOf("instagram.com") !== -1) return;

  var estilos = document.createElement("style");
  estilos.textContent =
    '.ig-aviso{position:fixed;z-index:9999;right:18px;bottom:18px;width:330px;max-width:calc(100vw - 32px);' +
    'background:#fff;border-radius:18px;padding:1.15rem 1.15rem 1.2rem;' +
    'box-shadow:0 14px 40px rgba(17,38,43,.22),0 2px 8px rgba(17,38,43,.08);' +
    'font-family:"Instrument Sans",system-ui,-apple-system,sans-serif;color:#11262b;' +
    'opacity:0;transform:translateY(16px) scale(.97);transition:opacity .34s ease,transform .34s cubic-bezier(.2,.9,.3,1.2)}' +
    '.ig-aviso.ig-dentro{opacity:1;transform:none}' +
    '.ig-aviso::before{content:"";position:absolute;inset:0;border-radius:18px;padding:2px;' +
    'background:linear-gradient(135deg,#f9ce34,#ee2a7b 48%,#6228d7);' +
    '-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);' +
    '-webkit-mask-composite:xor;mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);' +
    'mask-composite:exclude;pointer-events:none}' +
    '.ig-cerrar{position:absolute;top:8px;right:9px;width:28px;height:28px;border:0;border-radius:50%;' +
    'background:transparent;color:#5f7a7d;font-size:17px;line-height:1;cursor:pointer;display:flex;' +
    'align-items:center;justify-content:center}' +
    '.ig-cerrar:hover{background:#eef5f5;color:#11262b}' +
    '.ig-cab{display:flex;align-items:center;gap:.7rem;margin-bottom:.7rem}' +
    '.ig-foto{width:46px;height:46px;flex:0 0 46px;border-radius:50%;' +
    'background:linear-gradient(135deg,#f9ce34,#ee2a7b 48%,#6228d7);display:flex;align-items:center;' +
    'justify-content:center;color:#fff;font-weight:800;font-size:17px;letter-spacing:-.5px;' +
    'font-family:"Bricolage Grotesque","Instrument Sans",sans-serif}' +
    '.ig-quien b{display:block;font-size:14.5px;font-weight:700;letter-spacing:-.2px}' +
    '.ig-quien span{display:block;font-size:12px;color:#5f7a7d;margin-top:1px}' +
    '.ig-texto{font-size:13.5px;line-height:1.5;color:#28403f;margin-bottom:.9rem}' +
    '.ig-b{display:block;text-align:center;text-decoration:none;font-size:14.5px;font-weight:600;' +
    'color:#fff;background:linear-gradient(135deg,#f9ce34,#ee2a7b 48%,#6228d7);' +
    'padding:.7rem 1rem;border-radius:11px}' +
    '.ig-b:hover{filter:brightness(1.07)}' +
    '.ig-luego{display:block;width:100%;margin-top:.5rem;border:0;background:none;font-family:inherit;' +
    'font-size:12px;color:#5f7a7d;cursor:pointer;padding:.25rem}' +
    '.ig-luego:hover{color:#11262b;text-decoration:underline}' +
    '@media(max-width:520px){.ig-aviso{right:12px;left:12px;bottom:12px;width:auto}}' +
    '@media(prefers-reduced-motion:reduce){.ig-aviso{transition:none}}';
  document.head.appendChild(estilos);

  var caja = document.createElement("aside");
  caja.className = "ig-aviso";
  caja.setAttribute("role", "complementary");
  caja.setAttribute("aria-label", "Síguenos en Instagram");
  caja.innerHTML =
    '<button class="ig-cerrar" type="button" aria-label="Cerrar">&times;</button>' +
    '<div class="ig-cab">' +
      '<div class="ig-foto" aria-hidden="true">MP</div>' +
      '<div class="ig-quien"><b>@' + CUENTA + '</b><span>Instagram</span></div>' +
    '</div>' +
    '<p class="ig-texto">En Instagram subimos las muestras en vídeo, enseñamos lo que nos llega a casa y avisamos de los chollos que vuelan. ¿Te vienes?</p>' +
    '<a class="ig-b" href="https://instagram.com/' + CUENTA + '" target="_blank" rel="noopener">Seguir a @' + CUENTA + '</a>' +
    '<button class="ig-luego" type="button">Ahora no, gracias</button>';

  function cerrar() {
    caja.classList.remove("ig-dentro");
    try { localStorage.setItem(CLAVE, String(Date.now())); } catch (e) { /* ignorar */ }
    setTimeout(function () { if (caja.parentNode) caja.parentNode.removeChild(caja); }, 360);
    document.removeEventListener("keydown", porEscape);
  }

  function porEscape(ev) {
    if (ev.key === "Escape") cerrar();
  }

  caja.querySelector(".ig-cerrar").addEventListener("click", cerrar);
  caja.querySelector(".ig-luego").addEventListener("click", cerrar);
  // Si pulsa seguir, tampoco hay que volver a enseñarselo
  caja.querySelector(".ig-b").addEventListener("click", cerrar);

  var mostrado = false;
  function mostrar() {
    if (mostrado) return;
    mostrado = true;
    document.body.appendChild(caja);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { caja.classList.add("ig-dentro"); });
    });
    document.addEventListener("keydown", porEscape);
    window.removeEventListener("scroll", alBajar);
  }

  function alBajar() {
    var alto = document.documentElement.scrollHeight - window.innerHeight;
    if (alto > 0 && window.scrollY / alto > SCROLL) mostrar();
  }

  // Lo que ocurra antes: que lleve un rato, o que haya bajado un tercio
  setTimeout(mostrar, SEGUNDOS * 1000);
  window.addEventListener("scroll", alBajar, { passive: true });
})();
