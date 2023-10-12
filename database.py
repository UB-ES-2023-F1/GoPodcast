import os

from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv(dotenv_path='env/.env')

engine = create_engine(os.getenv('POSTGRES_URL'))
