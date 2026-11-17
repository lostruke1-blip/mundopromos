"""Prueba la API de comentarios de punta a punta, con una base de datos de usar y tirar."""
import os
import tempfile

os.environ["RUTA_BD"] = os.path.join(tempfile.mkdtemp(), "prueba.db")
os.environ["PANEL_USUARIO"] = "aaron"
os.environ["PANEL_CLAVE"] = "clave-de-prueba"
os.environ["ORIGENES"] = "https://mundopromos.com,https://www.mundopromos.com"
os.environ.pop("DATABASE_URL", None)

import app as api  # noqa: E402

PROMO = "reembolso-cafe-marcilla-902"
fallos = []


def comprobar(condicion, mensaje):
    print(("  OK   " if condicion else "  FALLO") + "  " + mensaje)
    if not condicion:
        fallos.append(mensaje)


def enviar(cliente, nombre, texto, tiempo=9000, trampa="", ip="80.1.2.3", promo=PROMO):
    return cliente.post(
        f"/api/comentarios/{promo}",
        json={"nombre": nombre, "texto": texto, "tiempo": tiempo, "web": trampa},
        headers={"X-Forwarded-For": ip, "User-Agent": "navegador-de-prueba"},
    )


def main():
    cliente = api.app.test_client()

    print("Comentario normal")
    r = enviar(cliente, "Marta", "Me llegó ayer la muestra, tardó dos semanas. Gracias!")
    comprobar(r.status_code == 201, "lo acepta")
    comprobar(r.get_json()["publicado"] is True, "lo publica solo")

    r = cliente.get(f"/api/comentarios/{PROMO}")
    lista = r.get_json()["comentarios"]
    comprobar(len(lista) == 1, "aparece al leer la promo")
    comprobar(lista[0]["nombre"] == "Marta", "guarda bien el nombre")
    comprobar("huella" not in lista[0] and "ip" not in lista[0], "no filtra datos del visitante")

    r = cliente.get("/api/comentarios/otra-promo-cualquiera")
    comprobar(r.get_json()["comentarios"] == [], "no mezcla promos")

    print("\nAntispam")
    r = enviar(cliente, "Bot", "Visita mi web", trampa="http://spam.ru", ip="1.1.1.1")
    comprobar(r.get_json()["publicado"] is False, "cae en la trampa invisible")

    r = enviar(cliente, "Bot2", "Comentario instantaneo del robot", tiempo=400, ip="1.1.1.2")
    comprobar(r.get_json()["publicado"] is False, "rechaza lo enviado en menos de 3 segundos")

    r = enviar(cliente, "Pepe", "Gana dinero desde casa con bitcoin facil", ip="1.1.1.3")
    comprobar(r.get_json()["publicado"] is False, "detecta palabras de spam")

    r = enviar(cliente, "Ana", "Escribeme a ana@correo.com y te cuento", ip="1.1.1.4")
    comprobar(r.get_json()["publicado"] is False, "bloquea correos en el texto")

    r = enviar(cliente, "Luis", "Mi movil es 612 345 678 por si acaso", ip="1.1.1.5")
    comprobar(r.get_json()["publicado"] is False, "bloquea telefonos")

    r = enviar(cliente, "Sara", "Mira esto en https://otracosa.com a ver", ip="1.1.1.6")
    comprobar(r.get_json()["publicado"] is False, "deja los enlaces para revisar")

    r = enviar(cliente, "Juan", "ESTO ES UNA VERGUENZA NO FUNCIONA NADA DE NADA", ip="1.1.1.7")
    comprobar(r.get_json()["publicado"] is False, "deja las mayusculas para revisar")

    r = enviar(cliente, "Nerea", "Vaya gilipollas el de la marca", ip="1.1.1.8")
    comprobar(r.get_json()["publicado"] is False, "deja los insultos para revisar")

    r = enviar(cliente, "Eva", "¿Alguien sabe si sigue funcionando? A mí no me llegó ná", ip="1.1.1.9")
    comprobar(r.get_json()["publicado"] is True, "no se pasa de listo con un comentario normal")

    print("\nLimites")
    r = enviar(cliente, "Marta", "Me llegó ayer la muestra, tardó dos semanas. Gracias!")
    comprobar(r.status_code == 409, "rechaza el duplicado exacto")

    for i in range(8):
        enviar(cliente, "Pesado", f"Comentario numero {i} para ver si me corta", ip="5.5.5.5")
    r = enviar(cliente, "Pesado", "Y otro mas todavia por si cuela", ip="5.5.5.5")
    comprobar(r.status_code == 429, "corta a quien escribe sin parar")

    r = enviar(cliente, "A", "hola")
    comprobar(r.status_code == 400, "exige un nombre de verdad")
    r = enviar(cliente, "Carlos", "ok")
    comprobar(r.status_code == 400, "exige un comentario de verdad")

    largo = enviar(cliente, "Carlos", "x" * 5000, ip="7.7.7.7")
    comprobar(largo.status_code == 201, "acepta un texto larguisimo recortandolo")
    texto_guardado = api.almacen._uno(
        "SELECT texto FROM comentarios WHERE nombre = ? ORDER BY id DESC", ("Carlos",))["texto"]
    comprobar(len(texto_guardado) == 1200, "lo recorta a 1200 caracteres")

    print("\nSeguridad")
    r = enviar(cliente, "<script>alert(1)</script>", "Texto <b>con html</b>", ip="9.9.9.9")
    guardado = api.almacen._uno(
        "SELECT nombre FROM comentarios WHERE id = ?",
        (api.almacen._uno("SELECT MAX(id) AS m FROM comentarios")["m"],))
    comprobar("<script>" in guardado["nombre"], "guarda el texto tal cual (el escapado va al pintar)")

    r = cliente.get(f"/api/comentarios/{PROMO}", headers={"Origin": "https://mundopromos.com"})
    comprobar(r.headers.get("Access-Control-Allow-Origin") == "https://mundopromos.com",
              "permite el dominio de la web")
    r = cliente.get(f"/api/comentarios/{PROMO}", headers={"Origin": "https://sitio-pirata.com"})
    comprobar("Access-Control-Allow-Origin" not in r.headers, "no permite otros dominios")

    print("\nPanel de moderacion")
    r = cliente.get("/panel")
    comprobar(r.status_code == 401, "el panel pide clave")
    r = cliente.get("/panel", headers={"Authorization": "Basic YWFyb246bWFsYQ=="})
    comprobar(r.status_code == 401, "rechaza la clave incorrecta")

    import base64
    cabecera = {"Authorization": "Basic " + base64.b64encode(b"aaron:clave-de-prueba").decode()}
    r = cliente.get("/panel", headers=cabecera)
    comprobar(r.status_code == 200, "entra con la clave correcta")
    pagina = r.get_data(as_text=True)
    comprobar("Pendientes de revisar" in pagina, "muestra la cola")
    comprobar("&lt;script&gt;" in pagina, "escapa el HTML de los comentarios")
    comprobar("incluye un enlace" in pagina, "explica por que esta pendiente")

    pendiente = api.almacen.pendientes()[0]
    r = cliente.post("/panel/accion", headers=cabecera,
                     data={"ficha": "inventada", "id": pendiente["id"], "que": "aprobar"})
    comprobar(r.status_code == 400, "no acepta acciones sin la ficha de sesion")

    r = cliente.post("/panel/accion", headers=cabecera,
                     data={"ficha": api.sesion_ficha(), "id": pendiente["id"], "que": "aprobar"})
    comprobar(r.status_code == 303, "aprueba el comentario")
    publicados = [c["texto"] for c in api.almacen.publicados(pendiente["promo"])]
    comprobar(pendiente["texto"] in publicados, "el aprobado ya se ve en la web")

    otro = api.almacen.pendientes()[0]
    cliente.post("/panel/accion", headers=cabecera,
                 data={"ficha": api.sesion_ficha(), "id": otro["id"], "que": "borrar"})
    comprobar(api.almacen._uno("SELECT id FROM comentarios WHERE id = ?", (otro["id"],)) is None,
              "borra del todo")

    enviar(cliente, "Trol", "Mensaje uno del trol para la prueba", ip="6.6.6.6")
    enviar(cliente, "Trol", "Mensaje dos del trol para la prueba", ip="6.6.6.6")
    del_trol = api.almacen._uno(
        "SELECT id FROM comentarios WHERE nombre = ? ORDER BY id DESC", ("Trol",))
    cliente.post("/panel/accion", headers=cabecera,
                 data={"ficha": api.sesion_ficha(), "id": del_trol["id"], "que": "bloquear"})
    quedan = [c for c in api.almacen.publicados(PROMO) if c["nombre"] == "Trol"]
    comprobar(not quedan, "bloquear se lleva todos los mensajes de esa persona")

    r = cliente.get("/salud")
    comprobar(r.status_code == 200 and "resumen" in r.get_json(), "responde el chequeo de salud")

    print("\n" + ("TODO CORRECTO" if not fallos else f"{len(fallos)} FALLOS"))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
