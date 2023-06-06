from .node import ExecNode  # the rest child classes are hidden from the outside
from .dag import DAG
from .ops import op, to_dag
from .errors import ErrorStrategy
from .config import Cfg

"""
easydags is package that allows you to build and deploy dags in a pretty simple manner.
"""
__version__ = "0.0.1"

__all__ = ["ExecNode", "DAG", "op", "to_dag", "ErrorStrategy", "Cfg"]
