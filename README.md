# Skill-Based Internship & Placement Management System

A Flask placement platform for students, companies, and administrators, using PostgreSQL hosted by Supabase.

## Files

- `app.py` - Flask web application and routes.
- `database.py` - Application database helpers and schema initialization.
- `db.py` - Secure Supabase PostgreSQL connection factory.
- `database/schema.sql` - Schema used when the Flask application initializes.
- `sql/01_schema.sql` - Numbered SQL copy of the placement schema for the SQL runner.
- `sql/07_rls.sql` - Row-level security setup with conservative read policies.
- `sql/sample_data.sql` - Idempotent fictional sample rows for placement testing.
- `run_sql.py` - Executes numbered SQL files in order and reports per-file errors.
- `seed.py` - Loads the sample data transactionally from `.env`-configured Supabase.
- `test_connection.py` - Checks connectivity, PostgreSQL version, and public tables.
- `queries.py` - Terminal placement analytics, formatted with tabulate.
- `requirements.txt` - Python packages required by the project.
- `.env.example` - Environment-variable template; never put real credentials in source control.
- `.gitignore` - Excludes local secrets and generated files from Git.

## Setup

1. Create a project at [supabase.com](https://supabase.com/).
2. In the Supabase dashboard, open **Connect** and copy the PostgreSQL session pooler connection string. A session pooler string is useful on networks without IPv6 support.
3. Copy `.env.example` to `.env`. Replace the project reference, region, and password in `SUPABASE_DB_URL`; also set unique `SECRET_KEY` and `ADMIN_PASSWORD` values. Do not commit `.env`.
4. Open PowerShell in the project folder and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

5. Check the Supabase connection:

   ```powershell
   python test_connection.py
   ```

6. Create/update the placement tables and apply the RLS settings:

   ```powershell
   python run_sql.py
   ```

7. Add the fictional sample records:

   ```powershell
   python seed.py
   ```

8. Run the placement analytics menu:

   ```powershell
   python queries.py
   ```

9. Start the existing Flask application:

   ```powershell
   python app.py
   ```

The SQL runner executes numbered files present in `sql` (`01` through `07`). This workspace contains the placement schema and RLS script; it does not contain the transport project's `01_schema.sql` through `06_test.sql`. The transport-only reports and Streamlit dashboard are not included because this database has no route, stop, driver, delay, or crowding tables, and `app.py` is already the Flask application.

## RLS and Data Safety

RLS is enabled for every placement table. Public API roles can read active opportunities and verified company listings; access to accounts, student profiles, applications, and certificates is denied because those tables contain credentials or personal data. The Flask server uses its server-side PostgreSQL connection; never expose its database URL in browser code. Supabase's database owner role bypasses RLS, so use a least-privilege database role for production server access where possible.

## Troubleshooting

- **SSL error:** `db.py` requires TLS using `sslmode=require`. Keep this setting and check that the copied connection URL is complete.
- **IPv6/IPv4 connection issue:** Use the Supabase **session pooler** string from **Connect** instead of a direct database hostname; verify the pooler host and port match the copied string.
- **Wrong password:** Reset the database password in Supabase, update `SUPABASE_DB_URL` in `.env`, and ensure URL-reserved characters in the password are percent-encoded.
- **`relation does not exist`:** Run `python run_sql.py` against the intended project and confirm the SQL completed successfully. Check that the connection URL points to the right Supabase project and that the table is in `public`.

## PowerShell Commands

Run these from the project folder. After copying `.env.example`, edit `.env` with your Supabase connection URL and unique secrets before continuing.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python test_connection.py
python run_sql.py
python seed.py
python queries.py
python app.py
```
