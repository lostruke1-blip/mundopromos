/* Comentarios de MundoPromos · sin registro, con moderacion.
   Se carga en cada pagina de promo y habla con la API de Railway. */
(function () {
  "use strict";

  var API = window.MP_API || "__API_COMENTARIOS__";
  var hueco = document.getElementById("comentarios");
  if (!hueco) return;
  var promo = hueco.dataset.promo;
  if (!promo) return;

  var MAX = 1200;
  var abierto = Date.now();

  function esc(t) {
    return String(t == null ? "" : t)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function hace(iso) {
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (isNaN(s) || s < 0) return "";
    if (s < 60) return "hace un momento";
    if (s < 3600) { var m = Math.floor(s / 60); return "hace " + m + (m === 1 ? " minuto" : " minutos"); }
    if (s < 86400) { var h = Math.floor(s / 3600); return "hace " + h + (h === 1 ? " hora" : " horas"); }
    var d = Math.floor(s / 86400);
    if (d < 31) return "hace " + d + (d === 1 ? " día" : " días");
    return new Date(iso).toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
  }

  function inicial(n) {
    var c = (n || "?").trim().charAt(0).toUpperCase();
    return /[A-ZÁÉÍÓÚÑ0-9]/.test(c) ? c : "?";
  }

  function color(n) {
    var h = 0;
    for (var i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) % 360;
    return "hsl(" + h + ",42%,42%)";
  }

  hueco.innerHTML =
    '<h2 class="co-titulo">Comentarios <span class="co-cuenta" id="co-cuenta"></span></h2>' +
    '<p class="co-intro">¿Te ha funcionado? ¿Se ha agotado? Cuéntalo y ayudas al resto. ' +
    'No hace falta registrarse: solo tu nombre.</p>' +
    '<form class="co-form" id="co-form" novalidate>' +
      '<input class="co-nombre" id="co-nombre" name="nombre" type="text" maxlength="40" ' +
        'placeholder="Tu nombre" autocomplete="nickname" required>' +
      '<textarea class="co-texto" id="co-texto" name="texto" rows="3" maxlength="' + MAX + '" ' +
        'placeholder="Escribe tu comentario…" required></textarea>' +
      '<div class="co-pieform">' +
        '<span class="co-restante" id="co-restante"></span>' +
        '<button class="co-enviar" id="co-enviar" type="submit">Publicar comentario</button>' +
      '</div>' +
      '<label class="co-trampa" aria-hidden="true">No rellenar<input type="text" name="web" tabindex="-1" autocomplete="off"></label>' +
      '<p class="co-aviso">Al publicar aceptas que guardemos tu nombre y tu comentario para mostrarlos aquí. ' +
      'Lee la <a href="/privacidad.html">política de privacidad</a>. Los comentarios se revisan antes de publicarse.</p>' +
      '<p class="co-estado" id="co-estado" role="status"></p>' +
    '</form>' +
    '<div class="co-lista" id="co-lista"><p class="co-cargando">Cargando comentarios…</p></div>';

  var form = document.getElementById("co-form");
  var campoNombre = document.getElementById("co-nombre");
  var campoTexto = document.getElementById("co-texto");
  var boton = document.getElementById("co-enviar");
  var estado = document.getElementById("co-estado");
  var lista = document.getElementById("co-lista");
  var cuenta = document.getElementById("co-cuenta");
  var restante = document.getElementById("co-restante");

  try {
    var guardado = localStorage.getItem("mp_nombre");
    if (guardado) campoNombre.value = guardado;
  } catch (e) { /* navegacion privada */ }

  campoTexto.addEventListener("input", function () {
    var quedan = MAX - campoTexto.value.length;
    restante.textContent = quedan < 150 ? quedan + " caracteres" : "";
  });

  function pintar(comentarios) {
    if (!comentarios.length) {
      cuenta.textContent = "";
      lista.innerHTML = '<p class="co-vacio">Todavía no hay comentarios. Sé el primero en contar si te ha llegado.</p>';
      return;
    }
    cuenta.textContent = "(" + comentarios.length + ")";
    lista.innerHTML = comentarios.map(function (c) {
      var n = esc(c.nombre);
      return '<article class="co-item">' +
        '<div class="co-avatar" style="background:' + color(n) + '">' + esc(inicial(c.nombre)) + '</div>' +
        '<div class="co-cuerpo">' +
          '<p class="co-meta"><strong>' + n + '</strong>' +
          (c.autor ? '<span class="co-autor">MundoPromos</span>' : '') +
          '<time datetime="' + esc(c.fecha) + '">' + esc(hace(c.fecha)) + '</time></p>' +
          '<p class="co-mensaje">' + esc(c.texto).replace(/\n+/g, "<br>") + '</p>' +
        '</div></article>';
    }).join("");
  }

  function cargar() {
    fetch(API + "/api/comentarios/" + encodeURIComponent(promo), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (d) { pintar(d.comentarios || []); })
      .catch(function () {
        lista.innerHTML = '<p class="co-vacio">No se han podido cargar los comentarios ahora mismo.</p>';
      });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var nombre = campoNombre.value.trim();
    var texto = campoTexto.value.trim();
    estado.className = "co-estado";

    if (nombre.length < 2) { estado.textContent = "Escribe tu nombre."; estado.classList.add("mal"); campoNombre.focus(); return; }
    if (texto.length < 3) { estado.textContent = "El comentario está vacío."; estado.classList.add("mal"); campoTexto.focus(); return; }

    boton.disabled = true;
    boton.textContent = "Enviando…";
    estado.textContent = "";

    fetch(API + "/api/comentarios/" + encodeURIComponent(promo), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre: nombre,
        texto: texto,
        web: form.web.value,                 // trampa antispam
        tiempo: Date.now() - abierto,        // milisegundos en la pagina
        url: location.pathname
      })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "error");
        try { localStorage.setItem("mp_nombre", nombre); } catch (e) { /* ignorar */ }
        campoTexto.value = "";
        restante.textContent = "";
        estado.textContent = res.d.publicado
          ? "¡Publicado! Gracias por contarlo."
          : "Recibido. Lo revisamos y aparecerá en un rato.";
        estado.classList.add("bien");
        if (res.d.publicado) cargar();
      })
      .catch(function (e) {
        estado.textContent = e.message === "repetido"
          ? "Ese comentario ya lo has enviado."
          : "No se ha podido enviar. Inténtalo de nuevo en un minuto.";
        estado.classList.add("mal");
      })
      .then(function () {
        boton.disabled = false;
        boton.textContent = "Publicar comentario";
      });
  });

  cargar();
})();
