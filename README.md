# Boost.Convert

## Banco de dados PostgreSQL

O app usa SQLite quando nenhuma variavel de banco e configurada. Para usar PostgreSQL, configure o `.env` com uma URL:

```env
DATABASE_URL=postgresql+psycopg://boost_user:boost_password@localhost:5432/boost_converter
```

Tambem funciona com URLs `postgres://` ou `postgresql://`; o app normaliza para o driver `psycopg`.

Outra opcao e usar variaveis separadas:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=boost_converter
POSTGRES_USER=boost_user
POSTGRES_PASSWORD=boost_password
POSTGRES_SSLMODE=disable
```

Depois de criar o banco no PostgreSQL, aplique as migrations:

```powershell
cd backend
python -m flask --app app:create_app db upgrade
```

Para rodar o servidor:

```powershell
cd backend
python main.py
```
