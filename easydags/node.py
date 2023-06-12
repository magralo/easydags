import inspect
from threading import Lock
from types import FunctionType, MethodType
from typing import Any, Callable, Dict, Hashable, List, Optional
import traceback

from loguru import logger


from .config import Cfg

# TODO: replace exec_nodes with dict
# a temporary variable used to pass in exec_nodes to the DAG during building
exec_nodes: List["ExecNode"] = []
exec_nodes_lock = Lock()
from datetime import datetime


class ExecNode:
    """
    This class is the base executable node of the Directed Acyclic Execution Graph
    """

    def __init__(
        self,
        id_: Hashable,
        exec_function: Callable[..., Any] = lambda **kwargs: None,
        depends_on_hard: Optional[List[Hashable]] = [],
        depends_on_soft: Optional[List[Hashable]] = [],
        output_name: Optional[str] = None,
        priority: int = 0,
        n_trials: int = 1,
        is_sequential: bool = Cfg.TAWAZI_IS_SEQUENTIAL,
    ):
        """
        Args:
            id_ (Hashable): identifier of ExecNode.
            exec_function (Callable, optional): a callable will be executed in the graph.
            This is useful to make Joining ExecNodes (Nodes that enforce dependencies on the graph)
            depends_on (list): a list of ExecNodes' ids that must be executed beforehand.
            argument_name (str): The name of the argument used by ExecNodes that depend on this ExecNode.
            priority (int, optional): priority compared to other ExecNodes;
                the higher the number the higher the priority.
            is_sequential (bool, optional): whether to execute this ExecNode in sequential order with respect to others.
             When this ExecNode must be executed, all other nodes are waited to finish before starting execution.
             Defaults to False.
        """

        self.id = id_
        self.exec_function = exec_function

        depends_on = depends_on_hard.copy()
        depends_on.extend(depends_on_soft)
        self.depends_on = depends_on
        self.depends_on_hard = depends_on_hard
        self.priority: int = priority
        self.compound_priority: int = priority
        self.n_trials: int = n_trials
        self.is_sequential = is_sequential
        self.state = 0

        # a string that identifies the ExecNode.
        # It is either the name of the identifying function or the identifying string id_
        self.__name__ = self.exec_function.__name__ if not isinstance(id_, str) else id_

        # Attempt to automatically assign a good enough argument name
        if isinstance(output_name, str) and output_name != "":
            self.argument_name = output_name
        else:
            # self.argument_name = (
            #    self.id.__name__ if isinstance(self.id, FunctionType) else str(self.id)
            # )
            self.argument_name = f"{str(self.id)}_result"

        # todo remove and make ExecNode immutable
        self.result: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.id} ~ | <{hex(id(self))}>"

    @property
    def computed_dependencies(self) -> bool:
        return isinstance(self.depends_on, list)

    def _add_soft_dependency(self, other):
        depends_on = other.depends_on.copy()

        depends_on.insert(0, self.id)

        other.depends_on = depends_on

        return self

    def __gt__(self, other):
        # soft dependency

        aux = self._add_soft_dependency(other)

        return aux

    def _add_hard_dependency(self, other):
        depends_on = other.depends_on.copy()
        depends_on_hard = other.depends_on_hard.copy()

        depends_on.insert(0, self.id)
        depends_on_hard.insert(0, self.id)

        other.depends_on = depends_on
        other.depends_on_hard = depends_on_hard

        return other

    def __rshift__(self, other):
        # hard dependency
        aux = self._add_hard_dependency(other)

        return aux

    # this is breaking change however
    def execute(
        self,
        node_dict: Dict[Hashable, "ExecNode"],
        debug: bool = True,
        initial_time: str = datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
    ) -> Optional[Dict[str, Any]]:
        """
        Execute the ExecNode directly or according to an execution graph.
        Args:
            node_dict (Dict[Hashable, ExecNode]): A shared dictionary containing the other ExecNodes in the DAG;
                                                the key is the id of the ExecNode.

        Returns: the result of the execution of the current ExecNode
        """
        logger.info(f"Start executing {self.id} at {initial_time}")
        # 1. fabricate the arguments for this ExecNode
        if debug:
            logger.debug(f"Start executing {self.id} with task {self.exec_function}")

        kwargs = {
            node_dict[dep_hash].argument_name: node_dict[dep_hash].result["result"]
            for dep_hash in self.depends_on_hard
        }

        prev_states = {
            node_dict[dep_hash].argument_name: node_dict[dep_hash].result["state"]
            for dep_hash in self.depends_on
        }

        prev_states = [x[1] for x in list(prev_states.items())]

        result = {}

        error = ""

        if len(prev_states) > 0:
            if min(prev_states) == 1:  # all prev nodes are ok
                i = 0

                while i < self.n_trials:
                    try:
                        result["result"] = self.exec_function(**kwargs)
                        result["state"] = 1
                        result["message"] = "Executed as expected"
                        self.state = 1
                        break  # no need for re-trials
                    except:
                        result["result"] = None
                        result["state"] = -1

                        error = traceback.format_exc()
                        msg = f"The error when executing {self.id} on trial {i+1} : {error}"
                        result["message"] = msg
                        self.state = -1
                        logger.info(msg)
                    i += 1
            else:
                result["result"] = None
                result["state"] = 0
                result["message"] = "Did not run"
                self.state = 0

        else:
            i = 0

            while i < self.n_trials:
                try:
                    result["result"] = self.exec_function(**kwargs)
                    result["state"] = 1
                    result["message"] = "Executed as expected"
                    self.state = 1
                    break  # no need for re-trials
                except:
                    result["result"] = None
                    result["state"] = -1
                    error = traceback.format_exc()
                    msg = f"The error when executing {self.id} on trial {i+1} : {error}"
                    result["message"] = msg
                    self.state = -1
                    logger.info(msg)
                i += 1

        result["initial_time"] = initial_time
        final = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
        result["final_time"] = final
        result["duration"] = (
            datetime.strptime(initial_time, "%Y-%m-%d, %H:%M:%S")
            - datetime.strptime(final, "%Y-%m-%d, %H:%M:%S")
        ).total_seconds()
        result["duration"] = str(-int(result["duration"])) + " sec"

        self.result = result

        # 3. useless return value
        if debug:
            logger.debug(f"Finished executing {self.id} with task {self.exec_function}")
        return result


class PreComputedExecNode(ExecNode):
    # todo must change this because two functions in the same DAG can use the same argument name for two constants!
    def __init__(self, func: Callable[..., Any], argument_name: str, value: Any):
        super().__init__(
            id_=f"{hash(func)}_{argument_name}",
            exec_function=lambda: value,
            depends_on=[],
            argument_name=argument_name,
            is_sequential=False,
        )


def get_default_args(func: Callable[..., Any]) -> Dict[str, Any]:
    """
    retrieves the default arguments of a function
    Args:
        func: the function with unknown defaults

    Returns:
        the mapping between the arguments and their default value
    """
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


class LazyExecNode(ExecNode):
    """
    A lazy function simulator that records the dependencies to build the DAG
    """

    def __init__(
        self,
        id_,
        func: Callable[..., Any],
        depends_on=[],
        priority: int = 0,
        argument_name: Optional[str] = None,
        is_sequential: bool = Cfg.TAWAZI_IS_SEQUENTIAL,
    ):
        # TODO: change the id_ of the execNode. Maybe remove it completely
        super().__init__(
            id_=id_,
            exec_function=func,
            depends_on=depends_on,
            priority=priority,
            argument_name=argument_name,
            is_sequential=is_sequential,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> "LazyExecNode":
        """
        Record the dependencies in a global variable to be called later in DAG.
        Returns: LazyExecNode
        """

        # 0. if dependencies are already calculated, there is no need to recalculate them
        if self.computed_dependencies and self in exec_nodes:
            return self

        dependencies = []
        provided_arguments_names = set()

        # TODO: refactor this part.
        function_arguments_names = inspect.getfullargspec(self.exec_function)[0]
        for i, arg in enumerate(args):
            if isinstance(arg, LazyExecNode):
                dependencies.append(arg.id)
            else:
                # if the argument is a custom or constant
                pre_c_exec_node = PreComputedExecNode(
                    self.exec_function, function_arguments_names[i], arg
                )
                exec_nodes.append(pre_c_exec_node)
                dependencies.append(pre_c_exec_node.id)

            provided_arguments_names.add(function_arguments_names[i])

        for argument_name, arg in kwargs.items():
            if isinstance(arg, LazyExecNode):
                dependencies.append(arg.id)
            else:
                # if the argument is a custom or constant
                pre_c_exec_node = PreComputedExecNode(
                    self.exec_function, argument_name, arg
                )
                exec_nodes.append(pre_c_exec_node)
                dependencies.append(pre_c_exec_node.id)

            provided_arguments_names.add(argument_name)

        # Fill default valued parameters with default values if they aren't provided by the user
        default_valued_params = get_default_args(self.exec_function)
        for argument_name in set(function_arguments_names) - provided_arguments_names:
            # if the argument is a custom or constant
            pre_c_exec_node = PreComputedExecNode(
                self.exec_function, argument_name, default_valued_params[argument_name]
            )
            exec_nodes.append(pre_c_exec_node)
            dependencies.append(pre_c_exec_node.id)

        self.depends_on = dependencies

        # in case the same function is called twice
        if self not in exec_nodes:
            exec_nodes.append(self)
        return self

    def __get__(self, instance: "LazyExecNode", owner_cls: Optional[Any] = None) -> Any:
        """
        Simulate func_descr_get() in Objects/funcobject.c
        Args:
            instance:
            owner_cls:

        Returns:

        """
        if instance is None:
            # this is the case when we call the method on the class instead of an instance of the class
            # In this case, we must return a "function" hence an instance of this class
            # https://stackoverflow.com/questions/3798835/understanding-get-and-set-and-python-descriptors
            return self
        return MethodType(self, instance)  # func=self  # obj=instance
