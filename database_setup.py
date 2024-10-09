import sqlite3
from sqlite3 import Error
import logging

def create_connection(db_file):
    """ Create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        logging.info("Connected to SQLite database.")
        return conn
    except Error as e:
        logging.error(f"Error connecting to database: {e}")
    return conn

def create_table(conn, create_table_sql):
    """ Create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
        logging.info("Table created successfully.")
    except Error as e:
        logging.error(f"Error creating table: {e}")

def initialize_database():
    database = "job_applications.db"

    sql_create_jobs_table = """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        position TEXT NOT NULL,
        status TEXT NOT NULL,
        application_date TEXT,
        last_updated TEXT,
        content TEXT,
        updated INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0
    );
    """

    # Create a database connection
    conn = create_connection(database)

    # Create table
    if conn is not None:
        create_table(conn, sql_create_jobs_table)
        conn.close()
        logging.info("Database setup successfully.")
    else:
        logging.error("Error! Cannot create the database connection.")