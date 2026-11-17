"""Guarda los comentarios. Usa Postgres si hay DATABASE_URL, si no SQLite.

Asi puedes empezar con un volumen de Railway (gratis) y pasar a Postgres
mas adelante sin tocar el codigo.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone

URL_BD = os.environ.get("DATABASE_URL", "")
RUTA_SQLITE = os.environ.get("RUTA_BD", "/datos/comentarios.db")

ES_POSTGRES = URL_BD.startswith(("postgres://", "postgresql://"))

if ES_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row

_candado = threading.Lock()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class Almacen:
    def __init__(self):
        if ES_POSTGRES:
            self.conexion = psycopg.connect(URL_BD, autocommit=True, row_factory=dict_row)
        else:
            carpeta = os.path.dirname(RUTA_SQLITE)
            if carpeta:
                os.makedirs(carpeta, exist_ok=True)
            self.conexion = sqlite3.connect(RUTA_SQLITE, check_same_thread=False)
            self.conexion.row_factory = sqlite3.Row
        self._crear_tablas()

    # ---------- utilidades ----------

    def _sql(self, consulta: str) -> str:
        """SQLite usa ? y Postgres %s."""
        return consulta.replace("?", "%s") if ES_POSTGRES else consulta

    def _ejecutar(self, consulta: str, parametros=()):
        with _candado:
            cursor = self.conexion.cursor()
            cursor.execute(self._sql(consulta), parametros)
            return cursor

    def _todos(self, consulta: str, parametros=()) -> list[dict]:
        cursor = self._ejecutar(consulta, parametros)
        return [dict(f) for f in cursor.fetchall()]

    def _uno(self, consulta: str, parametros=()) -> dict | None:
        cursor = self._ejecutar(consulta, parametros)
        fila = cursor.fetchone()
        return dict(fila) if fila else None

    def _crear_tablas(self) -> None:
        serial = "SERIAL PRIMARY KEY" if ES_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        self._ejecutar(
            f"""CREATE TABLE IF NOT EXISTS comentarios (
                   id {serial},
                   promo TEXT NOT NULL,
                   nombre TEXT NOT NULL,
                   texto TEXT NOT NULL,
                   fecha TEXT NOT NULL,
                   estado TEXT NOT NULL,
                   autor INTEGER DEFAULT 0,
                   huella TEXT,
                   motivo TEXT
               )"""
        )
        self._ejecutar(
            "CREATE INDEX IF NOT EXISTS idx_promo_estado ON comentarios (promo, estado)"
        )
        self._ejecutar("CREATE INDEX IF NOT EXISTS idx_estado ON comentarios (estado)")
        if not ES_POSTGRES:
            self.conexion.commit()

    # ---------- lectura publica ----------

    def publicados(self, promo: str) -> list[dict]:
        filas = self._todos(
            "SELECT id, nombre, texto, fecha, autor FROM comentarios "
            "WHERE promo = ? AND estado = 'publicado' ORDER BY id ASC",
            (promo,),
        )
        for f in filas:
            f["autor"] = bool(f["autor"])
        return filas

    def cuantos(self, promo: str) -> int:
        fila = self._uno(
            "SELECT COUNT(*) AS n FROM comentarios WHERE promo = ? AND estado = 'publicado'",
            (promo,),
        )
        return int(fila["n"]) if fila else 0

    # ---------- escritura ----------

    def repetido(self, promo: str, huella: str, texto: str) -> bool:
        fila = self._uno(
            "SELECT id FROM comentarios WHERE promo = ? AND huella = ? AND texto = ?",
            (promo, huella, texto),
        )
        return fila is not None

    def ultimos_de(self, huella: str, desde_iso: str) -> int:
        fila = self._uno(
            "SELECT COUNT(*) AS n FROM comentarios WHERE huella = ? AND fecha > ?",
            (huella, desde_iso),
        )
        return int(fila["n"]) if fila else 0

    def guardar(self, promo, nombre, texto, estado, huella, motivo="", autor=False) -> int:
        cursor = self._ejecutar(
            "INSERT INTO comentarios (promo, nombre, texto, fecha, estado, autor, huella, motivo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)" + (" RETURNING id" if ES_POSTGRES else ""),
            (promo, nombre, texto, _ahora(), estado, 1 if autor else 0, huella, motivo),
        )
        if ES_POSTGRES:
            return int(cursor.fetchone()["id"])
        self.conexion.commit()
        return int(cursor.lastrowid)

    # ---------- moderacion ----------

    def pendientes(self, limite: int = 200) -> list[dict]:
        return self._todos(
            "SELECT id, promo, nombre, texto, fecha, motivo FROM comentarios "
            "WHERE estado = 'pendiente' ORDER BY id DESC LIMIT ?",
            (limite,),
        )

    def recientes(self, limite: int = 60) -> list[dict]:
        return self._todos(
            "SELECT id, promo, nombre, texto, fecha, estado FROM comentarios "
            "WHERE estado <> 'pendiente' ORDER BY id DESC LIMIT ?",
            (limite,),
        )

    def resumen(self) -> dict:
        filas = self._todos("SELECT estado, COUNT(*) AS n FROM comentarios GROUP BY estado")
        return {f["estado"]: int(f["n"]) for f in filas}

    def cambiar_estado(self, ident: int, estado: str) -> None:
        self._ejecutar("UPDATE comentarios SET estado = ? WHERE id = ?", (estado, ident))
        if not ES_POSTGRES:
            self.conexion.commit()

    def borrar(self, ident: int) -> None:
        self._ejecutar("DELETE FROM comentarios WHERE id = ?", (ident,))
        if not ES_POSTGRES:
            self.conexion.commit()

    def bloquear_huella(self, ident: int) -> int:
        """Rechaza todo lo de quien escribio ese comentario. Devuelve cuantos."""
        fila = self._uno("SELECT huella FROM comentarios WHERE id = ?", (ident,))
        if not fila or not fila["huella"]:
            return 0
        cursor = self._ejecutar(
            "UPDATE comentarios SET estado = 'spam' WHERE huella = ? AND estado <> 'spam'",
            (fila["huella"],),
        )
        if not ES_POSTGRES:
            self.conexion.commit()
        return cursor.rowcount or 0
