/* Ampliar las fotos de las promociones.
   En muchas publicaciones la letra pequena (importes, fechas, limites) solo
   esta en la imagen, asi que hay que poder verla entera y con zoom. */
(function () {
  "use strict";

  // Solo la foto grande de cada promocion. En las tarjetas, el clic tiene que
  // seguir llevando a la promocion, que es lo que la gente espera.
  var SELECTOR = "article .portada, .foto-ampliable";

  var estilos = document.createElement("style");
  estilos.textContent =
    '.lupa-capa{position:fixed;inset:0;z-index:10000;background:rgba(8,22,25,.92);' +
    'display:flex;align-items:center;justify-content:center;padding:2.5rem 1rem 1rem;' +
    'opacity:0;transition:opacity .22s ease}' +
    '.lupa-capa.dentro{opacity:1}' +
    '.lupa-img{max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;' +
    'cursor:zoom-in;transition:transform .25s ease;transform-origin:center center;' +
    'box-shadow:0 10px 40px rgba(0,0,0,.5)}' +
    '.lupa-img.zoom{cursor:zoom-out}' +
    '.lupa-x{position:absolute;top:14px;right:16px;width:40px;height:40px;border:0;border-radius:50%;' +
    'background:rgba(255,255,255,.15);color:#fff;font-size:22px;line-height:1;cursor:pointer;' +
    'display:flex;align-items:center;justify-content:center}' +
    '.lupa-x:hover{background:rgba(255,255,255,.3)}' +
    '.lupa-pie{position:absolute;left:0;right:0;bottom:12px;text-align:center;color:rgba(255,255,255,.75);' +
    'font-family:"Instrument Sans",system-ui,sans-serif;font-size:12.5px;padding:0 1rem}' +
    '.lupa-marca{cursor:zoom-in}' +
    '@media(prefers-reduced-motion:reduce){.lupa-capa,.lupa-img{transition:none}}';
  document.head.appendChild(estilos);

  var capa = null;
  var ampliada = false;

  function cerrar() {
    if (!capa) return;
    var fuera = capa;
    capa = null;
    ampliada = false;
    fuera.classList.remove("dentro");
    document.body.style.overflow = "";
    setTimeout(function () {
      if (fuera.parentNode) fuera.parentNode.removeChild(fuera);
    }, 240);
    document.removeEventListener("keydown", porTecla);
  }

  function porTecla(ev) {
    if (ev.key === "Escape") cerrar();
  }

  function abrir(src, texto) {
    if (capa) return;
    capa = document.createElement("div");
    capa.className = "lupa-capa";
    capa.setAttribute("role", "dialog");
    capa.setAttribute("aria-label", "Imagen ampliada");

    var img = document.createElement("img");
    img.className = "lupa-img";
    img.src = src;
    img.alt = texto || "Imagen de la promoción";

    var cerrarBoton = document.createElement("button");
    cerrarBoton.className = "lupa-x";
    cerrarBoton.type = "button";
    cerrarBoton.setAttribute("aria-label", "Cerrar");
    cerrarBoton.innerHTML = "&times;";

    var pie = document.createElement("p");
    pie.className = "lupa-pie";
    pie.textContent = "Toca la imagen para acercarla · Esc o toca fuera para cerrar";

    // Acercar y alejar sobre el punto que se toca
    img.addEventListener("click", function (ev) {
      ev.stopPropagation();
      ampliada = !ampliada;
      if (ampliada) {
        var caja = img.getBoundingClientRect();
        var ox = ((ev.clientX - caja.left) / caja.width) * 100;
        var oy = ((ev.clientY - caja.top) / caja.height) * 100;
        img.style.transformOrigin = ox + "% " + oy + "%";
        img.style.transform = "scale(2.2)";
        img.classList.add("zoom");
      } else {
        img.style.transform = "";
        img.classList.remove("zoom");
      }
    });

    cerrarBoton.addEventListener("click", cerrar);
    capa.addEventListener("click", cerrar);

    capa.appendChild(img);
    capa.appendChild(cerrarBoton);
    capa.appendChild(pie);
    document.body.appendChild(capa);
    document.body.style.overflow = "hidden";
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { if (capa) capa.classList.add("dentro"); });
    });
    document.addEventListener("keydown", porTecla);
  }

  // Un solo escuchador para toda la pagina: vale para las fotos que el bot
  // anada despues sin tener que volver a engancharlas
  document.addEventListener("click", function (ev) {
    var img = ev.target.closest ? ev.target.closest(SELECTOR) : null;
    if (!img || img.tagName !== "IMG") return;
    ev.preventDefault();
    abrir(img.currentSrc || img.src, img.alt);
  });

  // Marcamos las que se pueden ampliar para que se note al pasar por encima
  function marcar() {
    var fotos = document.querySelectorAll("article .portada, .foto-ampliable");
    for (var i = 0; i < fotos.length; i++) fotos[i].classList.add("lupa-marca");
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", marcar);
  } else {
    marcar();
  }
})();
