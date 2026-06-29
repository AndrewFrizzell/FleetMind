import os
import sys
# Add project root (fleetmind/) to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, redirect, url_for, session, flash

from fleetmind_db import get_connection

from routes.auth_helpers import (
    login_required
)

from routes.auth_routes import (
    auth_bp
)

from routes.dashboard_routes import (
    dashboard_bp
)

from routes.machine_routes import (
    machine_bp
)

from routes.inspection_routes import (
    inspection_bp
)

from routes.job_routes import (
    job_bp
)

from routes.work_order_routes import (
    work_order_bp
)

from routes.part_routes import (
    part_bp
)

from routes.maintenance_routes import(
    maintenance_bp
)




app = Flask(__name__)
app.secret_key = "dev-secret-change-me" #change this later

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(machine_bp)
app.register_blueprint(inspection_bp)
app.register_blueprint(job_bp)
app.register_blueprint(work_order_bp)
app.register_blueprint(part_bp)
app.register_blueprint(maintenance_bp)


if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)