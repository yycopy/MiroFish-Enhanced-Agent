"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
memory_bp = Blueprint('memory', __name__)
ingestion_bp = Blueprint('ingestion', __name__)
graph_memory_bp = Blueprint('graph_memory', __name__)
review_bp = Blueprint('review', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import memory  # noqa: E402, F401
from . import ingestion  # noqa: E402, F401
from . import graph_memory  # noqa: E402, F401
from . import review  # noqa: E402, F401
