from mangum import Mangum
from app import app  # imports FastAPI instance from app.py

handler = Mangum(app)
