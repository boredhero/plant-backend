from plant_server import create_app
from scheduler import start_scheduler

app = create_app()
start_scheduler()
