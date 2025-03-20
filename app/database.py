from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os


# load .env file
load_dotenv()

# call URL form .env variable
# DATABASE_URL = os.getenv("DATABASE_URL") # production db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db") # test db
# Create connection to db 
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

