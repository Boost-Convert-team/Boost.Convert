from extensions import db
from app import create_app
from config import should_auto_create_db
import os

app = create_app()

if __name__ == "__main__":
    if should_auto_create_db(app): 
        with app.app_context(): db.create_all()
    app.run(host="localhost", port=int(os.getenv("PORT", "5001")), debug=True)
