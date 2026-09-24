import sqlite3


def get_connection():
    return sqlite3.connect("app.db")


def find_user(cursor, username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()
