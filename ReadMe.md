# Roommate Recipe Agent Database

**Database:** MySQL 8.0+ (SQL)

## Run the terminal example with Docker

Install and start Docker Desktop, then set private values for `DB_PASSWORD` and `MYSQL_ROOT_PASSWORD` in `.env`. From the project folder, run:

```bash
docker compose -f compose.yaml up --build --abort-on-container-exit --exit-code-from app app
```

Compose builds the Python image, starts MySQL, initializes the database from `recipe_kb.sql` on the first run, waits for MySQL to become healthy, then runs the terminal example. The database files persist in a Docker volume between runs. MySQL initialization scripts run only when that volume is first created.

## Run the terminal example directly on your computer

1. Start the MySQL server and load `recipe_kb.sql` once. The script creates the database, tables, and demo household data.
2. Create a MySQL app account with access to this database (see the commands below).
3. Replace `DB_PASSWORD` in `.env` with that account's private password. `.env` is excluded from Git.
4. Install the Python dependencies: `python3 -m pip install -r requirements.txt`.
5. Run `python3 main.py`:

   ```bash
   python3 main.py
   ```

The example reads household 1 by default. To read a different household, pass its ID, for example `python3 main.py 2`. Set `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_NAME` if your local MySQL connection uses different values.

Create a separate, limited MySQL account from the MySQL command line (replace the sample password with the same private value used in `.env`):

```sql
CREATE USER 'recipe_app'@'localhost' IDENTIFIED BY 'choose-a-private-password';
GRANT SELECT ON recipe_kb.* TO 'recipe_app'@'localhost';
```

The terminal example only reads data, so it needs only `SELECT`. If the backend later saves recipe requests, grant it only the additional permissions it needs, such as `INSERT` and `UPDATE` on `recipe_requests`.
