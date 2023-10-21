import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables from the .env file
load_dotenv(dotenv_path='.env')

engine = create_engine(os.getenv('POSTGRES_URL'))
