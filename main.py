import sqlite3
import psycopg2
from psycopg2 import sql
import json
import os
from datetime import datetime

CONFIG_FILE = "db_config.json"
DB_TYPE = None

# -------------------------------------------------
# QUERY PLACEHOLDER ADAPTER
# sqlite -> ?
# postgres -> %s
# -------------------------------------------------

def q(query):
    if DB_TYPE == "postgresql":
        return query.replace("?", "%s")
    return query

# -------------------------------------------------
# CONFIG FILE
# -------------------------------------------------

def load_config():

    if os.path.exists(CONFIG_FILE):

        with open(CONFIG_FILE) as f:
            return json.load(f)

    return None


def save_config(cfg):

    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


# -------------------------------------------------
# DATABASE CHOICE
# -------------------------------------------------

def choose_database():

    print("Seleziona database:")
    print("1 - SQLite (locale)")
    print("2 - PostgreSQL (server)")

    scelta = input("Scelta: ")

    if scelta == "2":

        host = input("Host (localhost): ") or "localhost"
        port = input("Port (5432): ") or "5432"
        user = input("User: ")
        password = input("Password: ")
        database = input("Database name: ")

        cfg = {
            "db_type": "postgresql",
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }

    else:

        cfg = {
            "db_type": "sqlite",
            "database": "database.db"
        }

    save_config(cfg)

    return cfg


# -------------------------------------------------
# CREATE DATABASE POSTGRES
# -------------------------------------------------

def create_database_if_not_exists(cfg):

    if cfg["db_type"] != "postgresql":
        return

    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database="postgres"
    )

    conn.autocommit = True

    cur = conn.cursor()

    db_name = cfg["database"]

    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_name,))

    if not cur.fetchone():

        print("Creo database", db_name)

        cur.execute(
            sql.SQL("CREATE DATABASE {}")
            .format(sql.Identifier(db_name))
        )

    cur.close()
    conn.close()


# -------------------------------------------------
# CONNECT
# -------------------------------------------------

def connect_database(cfg):

    if cfg["db_type"] == "sqlite":

        conn = sqlite3.connect(cfg["database"])
        conn.execute("PRAGMA foreign_keys = ON")

        return conn

    else:

        create_database_if_not_exists(cfg)

        return psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"]
        )


# -------------------------------------------------
# CREATE TABLES
# -------------------------------------------------

def crea_database(conn):

    cur = conn.cursor()

    if DB_TYPE == "sqlite":

        cur.executescript("""

        CREATE TABLE IF NOT EXISTS categorie(
        id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS spese(
        id_spesa INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        importo REAL CHECK(importo > 0),
        descrizione TEXT,
        id_categoria INTEGER,
        FOREIGN KEY(id_categoria) REFERENCES categorie(id_categoria)
        );

        CREATE TABLE IF NOT EXISTS budget(
        id_budget INTEGER PRIMARY KEY AUTOINCREMENT,
        mese TEXT NOT NULL,
        importo REAL CHECK(importo > 0),
        id_categoria INTEGER,
        UNIQUE(mese,id_categoria),
        FOREIGN KEY(id_categoria) REFERENCES categorie(id_categoria)
        );

        """)

    else:

        cur.execute("""
        CREATE TABLE IF NOT EXISTS categorie(
        id_categoria SERIAL PRIMARY KEY,
        nome TEXT UNIQUE NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS spese(
        id_spesa SERIAL PRIMARY KEY,
        data DATE NOT NULL,
        importo NUMERIC CHECK(importo > 0),
        descrizione TEXT,
        id_categoria INTEGER REFERENCES categorie(id_categoria)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS budget(
        id_budget SERIAL PRIMARY KEY,
        mese TEXT NOT NULL,
        importo NUMERIC CHECK(importo > 0),
        id_categoria INTEGER REFERENCES categorie(id_categoria),
        UNIQUE(mese,id_categoria)
        )
        """)

    conn.commit()
    cur.close()


# -------------------------------------------------
# TABLE PRINTER
# -------------------------------------------------

def mostra_tabella(conn, comandoSql):

    cur = conn.cursor()

    cur.execute(comandoSql)

    righe = cur.fetchall()

    colonne = [desc[0] for desc in cur.description]

    larghezze = []

    for i, col in enumerate(colonne):

        max_len = len(col)

        for r in righe:
            max_len = max(max_len, len(str(r[i])))

        larghezze.append(max_len)

    intestazione = "|"

    for i, col in enumerate(colonne):
        intestazione += f" {col:<{larghezze[i]}} |"

    print(intestazione)

    print("-" * len(intestazione))

    for r in righe:

        row = "|"

        for i, val in enumerate(r):
            row += f" {str(val):<{larghezze[i]}} |"

        print(row)

    cur.close()


# -------------------------------------------------
# MODIFICA RECORD
# -------------------------------------------------

def modifica_record(conn, tabella, campo_set, nuovo_valore, campo_where, valore_where):

    cur = conn.cursor()

    if DB_TYPE == "sqlite":
        placeholder = "?"
    else:
        placeholder = "%s"

    cur.execute(
        q(f"UPDATE {tabella} SET {campo_set}=? WHERE {campo_where}={placeholder}"),
        (nuovo_valore, valore_where)
    )

    conn.commit()

    print("Record aggiornato")

    cur.close()


# -------------------------------------------------
# ELIMINA RECORD
# -------------------------------------------------
def elimina_record(conn, tabella, id_campo, id_record, riferimenti=None):

    cur = conn.cursor()

    if DB_TYPE == "sqlite":
        placeholder = "?"
    elif DB_TYPE == "postgresql":
        placeholder = "%s"
    else:
        raise ValueError("DB_TYPE non supportato")

    try:
        # 1. verifica esistenza
        cur.execute(
            f"SELECT * FROM {tabella} WHERE {id_campo}={placeholder}",
            (id_record,)
        )

        record = cur.fetchone()

        if not record:
            print("Record non trovato")
            return

        # 2. controllo manuale riferimenti (opzionale ma utile)
        if riferimenti:
            for tab_ref, colonna in riferimenti:

                cur.execute(
                    f"SELECT COUNT(*) FROM {tab_ref} WHERE {colonna}={placeholder}",
                    (id_record,)
                )

                if cur.fetchone()[0] > 0:
                    print("Impossibile cancellare: record collegato (FK)")
                    return

        # 3. delete
        cur.execute(
            f"DELETE FROM {tabella} WHERE {id_campo}={placeholder}",
            (id_record,)
        )

        conn.commit()
        print("Record eliminato")

    # 🔥 gestione errore FK PostgreSQL
    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        print("Errore: impossibile eliminare, record ancora referenziato (foreign key)")

    finally:
        cur.close()


# -------------------------------------------------
# CATEGORIE
# -------------------------------------------------

def aggiungi_categoria(conn):

    nome = input("Inserisci nome categoria: ")

    if nome == "":

        print("Nome non valido")

        return

    cur = conn.cursor()

    cur.execute(q("SELECT * FROM categorie WHERE nome=?"), (nome,))

    if cur.fetchone():

        print("La categoria esiste già")

        return

    cur.execute(q("INSERT INTO categorie(nome) VALUES(?)"), (nome,))

    conn.commit()

    print("Categoria inserita")


# -------------------------------------------------
# INSERISCI SPESA
# -------------------------------------------------

def inserisci_spesa(conn):
    cur=conn.cursor()
    while True:

        data = input("Data YYYY-MM-DD: ")

        try:
            datetime.strptime(data, "%Y-%m-%d")
            break
        except ValueError:
            print("Formato non valido")

    while True:
        try:
            importo = float(input("Importo: "))
            if importo > 0:
                break
            else:
                print("Errore: importo deve essere > 0")
        except ValueError:
            print("Errore: devi inserire un numero valido")

    categoria = input("Categoria: ")
    if DB_TYPE == "sqlite":
        cur.execute("SELECT id_categoria FROM categorie WHERE nome=?", (categoria,))
    else:
        cur.execute("SELECT id_categoria FROM categorie WHERE nome=%s", (categoria,))
    
    risultato = cur.fetchone()

    while risultato is None:

        if risultato is None:
            print("Errore: categoria non esiste")
        if input("vuoi Visualizzare le categorie pesenti ? (Si o No) :").lower() == "si":
            mostra_tabella(conn,"Select * from categorie")
                    
        categoria = input("Categoria: ")
        if DB_TYPE == "sqlite":
            cur.execute("SELECT id_categoria FROM categorie WHERE nome=?", (categoria,))
        else:
            cur.execute("SELECT id_categoria FROM categorie WHERE nome=%s", (categoria,))
        risultato = cur.fetchone()

    id_categoria = risultato[0]

    descrizione = input("Descrizione: ")
    if DB_TYPE == "sqlite":
        cur.execute(q("""

        INSERT INTO spese(data,importo,descrizione,id_categoria)

        VALUES(?,?,?,?)

        """), (data, importo, descrizione, id_categoria))
    else:
       cur.execute(q("""

        INSERT INTO spese(data,importo,descrizione,id_categoria)

        VALUES(%s,%s,%s,%s)

        """), (data, importo, descrizione, id_categoria)) 

    conn.commit()

    print("Spesa inserita")


# -------------------------------------------------
# BUDGET
# -------------------------------------------------

def definisci_budget(conn):
    cur =conn.cursor()
    while True:

        mese = input("Mese YYYY-MM: ")

        try:
            datetime.strptime(mese, "%Y-%m")
            break

        except ValueError:

            print("Formato non valido")

    categoria = input("Categoria: ")

    if DB_TYPE == "sqlite":
      cur.execute(q("SELECT id_categoria FROM categorie WHERE nome=?"), (categoria,))
    else:
      cur.execute(q("SELECT id_categoria FROM categorie WHERE nome=%s"), (categoria,))
    

    risultato = cur.fetchone()
    while risultato is None:

            if risultato is None:
                print("Errore: categoria non esiste")
            if input("vuoi Visualizzare le categorie pesenti ? (Si o No) :").lower() == "si":
                mostra_tabella(conn,"select * from categorie")
                        
            categoria = input("Categoria: ")
            if DB_TYPE == "sqlite":
                cur.execute(q("SELECT id_categoria FROM categorie WHERE nome=?"), (categoria,))
            else:
                cur.execute(q("SELECT id_categoria FROM categorie WHERE nome=%s"), (categoria,))
            risultato = cur.fetchone()

    id_categoria = risultato[0]
    
    
    while True:
            try:
                importo = float(input("Importo: "))
                if importo > 0:
                    break
                else:
                    print("Errore: importo deve essere > 0")
            except ValueError:
                print("Errore: devi inserire un numero valido")

    if DB_TYPE == "sqlite":

        cur.execute(q("""
        INSERT OR REPLACE INTO budget(mese,importo,id_categoria)
        VALUES(?,?,?)
        """), (mese, importo, id_categoria))

    else:

        cur.execute("""
        INSERT INTO budget(mese,importo,id_categoria)
        VALUES(%s,%s,%s)
        ON CONFLICT(mese,id_categoria)
        DO UPDATE SET importo=EXCLUDED.importo
        """, (mese, importo, id_categoria))

    conn.commit()


# -------------------------------------------------
# MENU CATEGORIE
# -------------------------------------------------

def menu_categoria(conn):

    while True:

        print("""

--- GESTIONE CATEGORIE ---

1 aggiungi
2 modifica
3 elimina
4 visualizza
5 indietro

""")

        scelta = input("Scelta: ")

        if scelta == "1":

            aggiungi_categoria(conn)

        elif scelta == "2":

            mostra_tabella(conn, "SELECT * FROM categorie order by nome")

            id_cat = input("ID da modificare: ")

            new_nome = input("Nuovo nome: ")

            modifica_record(conn, "categorie", "nome", new_nome, "id_categoria", id_cat)

        elif scelta == "3":

            mostra_tabella(conn, "SELECT * FROM categorie order by nome")

            elimina_record(conn, "categorie", "id_categoria", input("ID: "), riferimenti=[("budget", "id_categoria")])

        elif scelta == "4":

            mostra_tabella(conn, "SELECT * FROM categorie order by nome")

        elif scelta == "5":

            break


# -------------------------------------------------
# MENU BUDGET
# -------------------------------------------------

def menu_budget(conn):

    while True:

        print("""

--- GESTIONE BUDGET ---

1 aggiungi
2 modifica
3 elimina
4 visualizza
5 indietro

""")

        scelta = input("Scelta: ")

        if scelta == "1":

            definisci_budget(conn)

        elif scelta == "2":

            mostra_tabella(conn, "SELECT * FROM budget")

            id_b = input("ID budget: ")

            new_val = input("Nuovo importo: ")

            modifica_record(conn, "budget", "importo", new_val, "id_budget", id_b)

        elif scelta == "3":

            mostra_tabella(conn, "SELECT * FROM budget")

            elimina_record(conn, "budget", "id_budget", input("ID: "),riferimenti=[("categorie","id_categoria")])

        elif scelta == "4":

            mostra_tabella(conn, "SELECT * FROM budget")

        elif scelta == "5":

            break
        else:
            print("Scelta non valida")

# -------------------------------------------------
# MENU REPORT
# -------------------------------------------------

def menu_report(conn):

    while True:

        print("""

--- REPORT ---

1 totale spese per categoria
2 Spese vs Budget              
3 elenco spese
4 elimina spesa
5 indietro

""")

        scelta = input("Scelta: ")

        if scelta == "1":
            #report_totale_categoria()
            mostra_tabella(conn,"""
            SELECT c.nome as Categoria, SUM(s.importo) as "Tot. Spese"
            FROM spese s
            JOIN categorie c ON s.id_categoria = c.id_categoria
            GROUP BY c.nome
    """)

        elif scelta == "2":
            #report_budget()
            mostra_tabella(conn, """SELECT 
            b.mese,
            c.nome AS Categoria,
            b.importo AS Budget,
            COALESCE(SUM(s.importo),0) AS "Totale Spese",
            CASE 
                WHEN (b.importo - COALESCE(SUM(s.importo),0)) >= 0
                THEN 'OK'
                ELSE 'Sforato di ' || (COALESCE(SUM(s.importo),0) - b.importo)
            END AS stato
            FROM budget b
            JOIN categorie c ON c.id_categoria = b.id_categoria
            LEFT JOIN spese s 
            ON s.id_categoria = b.id_categoria
            AND substr(CAST(s.data AS TEXT),1,7) = b.mese
            GROUP BY b.mese, c.nome, b.importo;""")

        elif scelta == "3":
          #  report_spese()
            mostra_tabella(conn,"""
            SELECT data, nome as categoria, importo, descrizione
            FROM spese
            JOIN categorie
            ON spese.id_categoria = categorie.id_categoria
            ORDER BY data
            """)

        elif scelta == "4":
            mostra_tabella(conn,"""SELECT b.id_spesa as id , b.data, c.nome as Categoria , b.importo ,
            b.descrizione 
            FROM spese b
            JOIN categorie c ON b.id_categoria = c.id_categoria
            order by b.id_spesa""")
            elimina_record(conn,"spese","id_spesa",input("inserisci Id : "))

        elif scelta == "5":
             break        

        else:
            print("Scelta non valida")

# -------------------------------------------------
# MENU PRINCIPALE
# -------------------------------------------------

def menu(conn):

    while True:

        print("""

----- SISTEMA SPESE PERSONALI -----

1 gestione categorie
2 inserisci spesa
3 gestione budget
4 report
5 esci

""")

        scelta = input("Scelta: ")

        if scelta == "1":

            menu_categoria(conn)

        elif scelta == "2":

            inserisci_spesa(conn)   

        elif scelta == "3":

            menu_budget(conn)

        elif scelta == "4":

            menu_report(conn)

        elif scelta == "5":
             print("Uscita...")
             break
        
        else:
            print("Scelta non valida")


# -------------------------------------------------
# START
# -------------------------------------------------

cfg = load_config()

if not cfg:

    cfg = choose_database()

DB_TYPE = cfg["db_type"]

conn = connect_database(cfg)

crea_database(conn)

print("Database pronto")

menu(conn)

conn.close()
