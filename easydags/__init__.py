from .node import ExecNode,search_nodes  # the rest child classes are hidden from the outside
from .dag import DAG
from .ops import op, to_dag
from .config import Cfg

"""
easydags is package that allows you to build and deploy dags in a pretty simple manner.
"""
__version__ = "2.0.0"

__all__ = ["ExecNode", "DAG", "op", "to_dag", "Cfg", 'search_nodes']
