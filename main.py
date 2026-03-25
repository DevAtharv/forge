from dotenv import load_dotenv

from forge.bootstrap import create_app


load_dotenv()

app = create_app()
