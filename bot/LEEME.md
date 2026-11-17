# MundoPromos · publicación automática

Dos servicios que se despliegan en Railway desde el mismo repositorio:

| Carpeta | Qué hace | Tipo de servicio |
|---|---|---|
| raíz (`main.py`) | Lee los canales de Telegram cada 15 min, convierte lo nuevo en entradas de blog y hace commit en GitHub. Netlify despliega solo. | Worker |
| `api/` | Recibe y sirve los comentarios. Incluye el panel de moderación. | Web |

No hace falta ningún bot de Telegram ni permisos: se lee la vista pública de los canales (`t.me/s/<canal>`), que es lo mismo que ve cualquiera sin cuenta. Por eso también entran los mensajes que escribes a mano.

---

## 1. Lo que tienes que crear antes

**Clave de la API de Claude** → console.anthropic.com → API Keys → Create Key.
Sirve para reescribir cada mensaje de Telegram como entrada de blog. Con el modelo Haiku sale a unos **0,02 € por promoción**: publicando 10 al día son menos de 6 € al año.

**Token de GitHub** → github.com/settings/personal-access-tokens/new (fine-grained)
- Repository access: *Only select repositories* → `lostruke1-blip/mundopromos`
- Permissions → Repository permissions → **Contents: Read and write**
- Expiración: la máxima que te deje

Las dos van **solo** en las variables de Railway. Nunca en el repositorio, que es público.

---

## 2. Servicio del publicador (worker)

Variables:

```
ANTHROPIC_API_KEY    sk-ant-...
GITHUB_TOKEN         github_pat_...
GITHUB_PROPIETARIO   lostruke1-blip
GITHUB_REPO          mundopromos
API_COMENTARIOS      https://<tu-servicio-api>.up.railway.app
```

Opcionales, con sus valores por defecto:

```
CANALES              Mundopromosapp,OfertasSupermercadosES
INTERVALO_MIN        15
MAX_POR_CICLO        8        tope de promos nuevas por vuelta
SITIO                https://mundopromos.com
MODELO_REDACTOR      claude-haiku-5-5
SOLO_UNA_VEZ         1 para hacer una vuelta y parar
IMPORTAR_HISTORICO   0 normalmente; ver abajo
```

Arranque: `python main.py`

## 3. Servicio de comentarios (web)

Variables:

```
PANEL_USUARIO   el usuario con el que entras a moderar
PANEL_CLAVE     una contraseña larga, que no uses en ningún otro sitio
SAL             una cadena aleatoria cualquiera, larga
ORIGENES        https://mundopromos.com,https://www.mundopromos.com
```

Para guardar los comentarios, una de las dos:

- **Volumen** (más barato): añade un volumen montado en `/datos`. No hace falta nada más.
- **Postgres**: añade el plugin y Railway pone `DATABASE_URL` sola. El código la detecta y la usa.

Arranque: el `Procfile` ya lo lleva.

El panel de moderación queda en `https://<tu-servicio>.up.railway.app/panel`.
Pide usuario y contraseña y lleva `noindex`, así que no sale en Google.

---

## 4. Primera vez: importar el histórico

Con todo desplegado y funcionando, en el worker:

1. Pon `IMPORTAR_HISTORICO=200` y `MAX_POR_CICLO=200`
2. Despliega y mira los registros: irá publicando de las más antiguas a las más nuevas
3. Cuando termine (`Importacion terminada`), **quita las dos variables** y vuelve a desplegar

Las que tengan "agotada", "finalizada", "ya no queda" y parecidas se publican marcadas como caducadas, para que la web no prometa algo que ya no está. Doscientas publicaciones por canal son unos 8 € de API una sola vez.

---

## 5. Cómo funciona el día a día

1. Publicas algo en cualquiera de los dos canales
2. Como mucho 15 minutos después, el worker lo ve
3. Lo reescribe como entrada: título, resumen, cuerpo con "Cómo participar", categoría
4. Descarga la foto, la reduce a 1200px y la guarda en el repositorio
5. Genera la página, el listado, el sitemap y mete la tarjeta en la portada
6. Hace **un solo commit** con todo, para que Netlify despliegue una vez
7. Netlify publica en un par de minutos

Si editas un mensaje de Telegram añadiendo "Códigos agotados" o similar, la entrada se marca sola como caducada en la siguiente vuelta: el botón se apaga y la tarjeta sale en gris.

Lo que no se publica: los reenvíos de otros canales y lo que no tenga sustancia (un "buenos días", una foto suelta). El redactor lo descarta y queda anotado para no volver a pagar por analizarlo.

---

## 6. Qué cambia en la web

- **Pestaña nueva "🔥 Lo último"**, la primera y la que se abre al entrar
- **`/promos.html`**: el listado completo, con filtros por categoría
- **`/promo/<nombre>.html`**: una página por promoción, con datos estructurados de artículo para Google y comentarios al final
- **`/promos-muestra.html`, `-reembolso`, `-cupon`...**: un listado por categoría

Cada página es un HTML de verdad, no contenido cargado con JavaScript. Es lo que hace que Google las indexe, que es de donde venía el tráfico de la web antigua.

---

## 7. Probarlo en tu ordenador

```bash
pip install -r requirements.txt
python prueba_canales.py      # el lector de Telegram
python prueba_generador.py    # genera el blog de ejemplo
cd api && python prueba_api.py  # comentarios, antispam y panel
```

Para una vuelta real sin dejarlo arrancado:

```bash
SOLO_UNA_VEZ=1 MAX_POR_CICLO=1 python main.py
```
