"""API de comentarios de MundoPromos.

Rutas publicas:
  GET  /api/comentarios/<promo>   lista los comentarios publicados
  POST /api/comentarios/<promo>   recibe uno nuevo

Panel de moderacion (usuario y clave):
  GET  /panel                     cola de pendientes y ultimos publicados
  POST /panel/accion              aprobar, rechazar, borrar o bloquear

Variables de entorno:
  PANEL_USUARIO, PANEL_CLAVE   acceso al panel (obligatorias)
  ORIGENES                     dominios permitidos, separados por coma
  DATABASE_URL                 Postgres; si no, SQLite en RUTA_BD
  RUTA_BD                      por defecto /datos/comentarios.db
  SAL                          cadena secreta para anonimizar las IP
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, Response, jsonify, request

import filtro
from almacen import Almacen
from panel import pagina_panel

MAX_NOMBRE = 40
MAX_TEXTO = 1200
MAX_POR_HORA = 6

ORIGENES = [
    o.strip().rstrip("/")
    for o in os.environ.get(
        "ORIGENES", "https://mundopromos.com,https://www.mundopromos.com"
    ).split(",")
    if o.strip()
]
SAL = os.environ.get("SAL", "mundopromos-sal-por-defecto")
PANEL_USUARIO = os.environ.get("PANEL_USUARIO", "")
PANEL_CLAVE = os.environ.get("PANEL_CLAVE", "")

app = Flask(__name__)
almacen = Almacen()


# ---------- utilidades ----------

def huella_de(peticion) -> str:
    """Identificador anonimo del visitante: no guardamos la IP en claro."""
    adelante = peticion.headers.get("X-Forwarded-For", "")
    ip = adelante.split(",")[0].strip() if adelante else (peticion.remote_addr or "")
    agente = peticion.headers.get("User-Agent", "")[:120]
    return hashlib.sha256(f"{SAL}|{ip}|{agente}".encode()).hexdigest()[:32]


def con_cors(respuesta: Response) -> Response:
    origen = request.headers.get("Origin", "").rstrip("/")
    if origen in ORIGENES:
        respuesta.headers["Access-Control-Allow-Origin"] = origen
        respuesta.headers["Vary"] = "Origin"
        respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        respuesta.headers["Access-Control-Max-Age"] = "86400"
    return respuesta


app.after_request(con_cors)


def pide_clave(funcion):
    @wraps(funcion)
    def envoltorio(*args, **kwargs):
        if not PANEL_USUARIO or not PANEL_CLAVE:
            return Response("Panel sin configurar: faltan PANEL_USUARIO y PANEL_CLAVE.", 503)
        auth = request.authorization
        correcto = (
            auth
            and hmac.compare_digest(auth.username or "", PANEL_USUARIO)
            and hmac.compare_digest(auth.password or "", PANEL_CLAVE)
        )
        if not correcto:
            return Response(
                "Acceso restringido", 401,
                {"WWW-Authenticate": 'Basic realm="Moderacion MundoPromos"'},
            )
        return funcion(*args, **kwargs)

    return envoltorio


def limpiar(valor, maximo: int) -> str:
    if not isinstance(valor, str):
        return ""
    # fuera caracteres de control, que solo sirven para romper cosas
    texto = "".join(c for c in valor if c == "\n" or c >= " ")
    return texto.strip()[:maximo]


# ---------- API publica ----------

@app.route("/api/comentarios/<promo>", methods=["GET", "OPTIONS"])
def listar(promo):
    if request.method == "OPTIONS":
        return Response(status=204)
    promo = limpiar(promo, 120)
    return jsonify({"promo": promo, "comentarios": almacen.publicados(promo)})


@app.route("/api/comentarios/<promo>", methods=["POST"])
def recibir(promo):
    promo = limpiar(promo, 120)
    datos = request.get_json(silent=True) or {}

    nombre = limpiar(datos.get("nombre"), MAX_NOMBRE)
    texto = limpiar(datos.get("texto"), MAX_TEXTO)
    trampa = limpiar(datos.get("web"), 100)
    try:
        milisegundos = int(datos.get("tiempo") or 0)
    except (TypeError, ValueError):
        milisegundos = 0

    if len(nombre) < 2:
        return jsonify({"error": "nombre"}), 400
    if len(texto) < 3:
        return jsonify({"error": "texto"}), 400

    huella = huella_de(request)

    if almacen.repetido(promo, huella, texto):
        return jsonify({"error": "repetido"}), 409

    hace_una_hora = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if almacen.ultimos_de(huella, hace_una_hora) >= MAX_POR_HORA:
        return jsonify({"error": "demasiados"}), 429

    estado, motivo = filtro.revisar(nombre, texto, milisegundos, trampa)
    almacen.guardar(promo, nombre, texto, estado, huella, motivo)

    # al spam le decimos lo mismo que a los demas: que no sepa que ha caido
    return jsonify({"publicado": estado == "publicado"}), 201


@app.route("/salud")
def salud():
    return jsonify({"estado": "ok", "resumen": almacen.resumen()})


# ---------- panel de moderacion ----------

@app.route("/panel")
@pide_clave
def panel():
    return Response(
        pagina_panel(
            pendientes=almacen.pendientes(),
            recientes=almacen.recientes(),
            resumen=almacen.resumen(),
            ficha=sesion_ficha(),
        ),
        mimetype="text/html",
    )


def sesion_ficha() -> str:
    """Ficha anti-CSRF.

    Se deriva de la clave del panel en vez de sortearla, para que todos los
    procesos de gunicorn calculen la misma: si cada uno tuviera la suya, el
    boton de aprobar fallaria segun que proceso atendiese el clic.
    """
    return hmac.new(
        f"{SAL}|{PANEL_CLAVE}".encode(), b"ficha-panel", hashlib.sha256
    ).hexdigest()[:32]


@app.route("/panel/accion", methods=["POST"])
@pide_clave
def accion():
    if not hmac.compare_digest(request.form.get("ficha", ""), sesion_ficha()):
        return Response("Sesion caducada, recarga el panel.", 400)

    try:
        ident = int(request.form.get("id", ""))
    except ValueError:
        return Response("Falta el comentario.", 400)

    que = request.form.get("que", "")
    if que == "aprobar":
        almacen.cambiar_estado(ident, "publicado")
    elif que == "rechazar":
        almacen.cambiar_estado(ident, "rechazado")
    elif que == "borrar":
        almacen.borrar(ident)
    elif que == "bloquear":
        almacen.bloquear_huella(ident)
    else:
        return Response("Accion desconocida.", 400)

    return Response(status=303, headers={"Location": "/panel"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
