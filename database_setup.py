import sqlite3
from sqlite3 import Error

def create_connection(db_file):
    """ Create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"Connected to SQLite database.")
        return conn
    except Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def create_table(conn, create_table_sql):
    """ Create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
        print("Table created successfully.")
    except Error as e:
        print(f"Error creating table: {e}")

def main():
    database = "job_applications.db"

    sql_create_jobs_table = """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        position TEXT NOT NULL,
        status TEXT NOT NULL,
        application_date TEXT,
        last_updated TEXT,
        notes TEXT,
        email_hash TEXT UNIQUE,
        updated INTEGER DEFAULT 0
    );
    """

    # Create a database connection
    conn = create_connection(database)

    # Create table
    if conn is not None:
        create_table(conn, sql_create_jobs_table)
    else:
        print("Error! Cannot create the database connection.")

    # Close the connection
    if conn:
        conn.close()
        print("Database connection closed.")

if __name__ == '__main__':
    main()