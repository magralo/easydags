from concurrent.futures import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from copy import copy
from datetime import datetime
from typing import Any, Dict, Hashable, List, Optional, Set, Tuple, Union

import networkx as nx
from loguru import logger
from networkx import find_cycle
from networkx.exception import NetworkXNoCycle, NetworkXUnfeasible

from .node import ExecNode


# todo remove dependency on DiGraph!
class DiGraphEx(nx.DiGraph):
    """
    Extends the DiGraph with some methods
    """

    def root_nodes(self) -> List[Hashable]:
        """
        Safely gets the root nodes
        Returns:
            the root nodes
        """
        return [node for node, degree in self.in_degree if degree == 0]

    def leaf_nodes(self) -> List[Hashable]:
        """
        Safely gets the leaf nodes
        Returns:
            the leaf nodes
        """
        return [node for node, degree in self.out_degree if degree == 0]

    def subgraph_leaves(self, nodes: List[Hashable]) -> Set[Hashable]:
        """
        modifies the graph to become a subgraph
        that contains the provided nodes as leaf nodes.
        For example:
        TODO: use the future print to test this function!
        graph =
        "
        A
        | \
        B  C
        |  |\
        D  E F
        "
        subgraph_leaves(D, C, E) ->
        "
        A
        | \
        B  C
        |  |
        D  E
        "
        C is not a node that can be made into leaf nodes
        Args:
            nodes: the list of nodes to be executed
        Returns: the nodes that are provided but can never become leaf nodes:
            Impossible cases are handled using a best effort approach;
                For example, if a node and its children are provided,
                all those nodes will be left in the subgraph. However,
                a warning will be issued
        """

        # keeping only the provided nodes and their ancestors is equivalent to
        # pruning the graph until all leaf nodes are contained inside "nodes"
        if any(node not in self.nodes for node in nodes):
            raise ValueError(
                f"The provided nodes are not in the graph. "
                f"The provided nodes are: {nodes}."
                f"The graph only contains: {self.nodes}."
            )

        nodes_to_keep: Set[Hashable] = set(nodes)
        for node in nodes:
            nodes_to_keep.update(nx.ancestors(self, node))

        self.remove_nodes_from([node for node in list(self.nodes) if node not in nodes_to_keep])

        unremovable_nodes = set(nodes).difference(set(self.leaf_nodes()))

        if len(unremovable_nodes) > 0:
            logger.debug(
                f"The provided nodes contain more nodes than necessary, "
                f"please remove {unremovable_nodes} nodes"
            )

        return unremovable_nodes

    def topological_sort(self) -> List[Hashable]:
        """
        Makes the simple topological sort of the graph nodes
        """
        return list(nx.topological_sort(self))


# TODO: move into a separate module (Helper functions)
def subgraph(
    graph: DiGraphEx, leaves_ids: Optional[List[Union[Hashable, ExecNode]]]
) -> DiGraphEx:
    """returns a copy of the same graph if leaves_ids is None,
    otherwise returns a new graph by applying `graph.subgraph_leaves`

    Args:
        graph (DiGraphEx): graph describing the DAG
        leaves_ids (List[Union[Hashable, ExecNode]]): The leaves that must be executed

    Returns:
        DiGraphEx: The subgraph of the provided graph
    """
    # 0. copy the graph structure so pruning it doesn't mutate the original
    graph = graph.copy()

    # TODO: make the creation of subgraph possible directly from initialization
    # 1. create the subgraph
    if leaves_ids is not None:
        # Extract the ids from the provided leaves/leaves_ids
        leaves_ids = [
            node_id.id if isinstance(node_id, ExecNode) else node_id
            for node_id in leaves_ids
        ]

        graph.subgraph_leaves(leaves_ids)

    return graph


class DAG:
    """
    Data Structure containing ExecNodes with interdependencies.
    The ExecNodes can be executed in parallel with the following restrictions:
        * Limited number of threads.
        * Parallelization constraint of each ExecNode (is_sequential attribute)
    """

    def __init__(
        self,
        exec_nodes: List[ExecNode] = None,
        name: str = "DAG",
        max_concurrency: int = 1,
        debug: bool = True,
        error_type_fatal: bool = True,
        draw: bool = True
    ):
        """
        Args:
            exec_nodes: all the ExecNodes
            max_concurrency: the maximal number of threads running in parallel
            name: Name of the dag, will be usefull for creating the html output
            degub: weather or not you want degub messages
            error_type_fatal: weather or not you want the whole process to fail if at least one node fails
            draw: Set false if you do not want the html output

        """
        self.graph_ids = DiGraphEx()
        self.name = name

        self.debug = debug
        self.draw = draw

        self.error_type_fatal = error_type_fatal
        # since ExecNodes are modified they must be copied
        self.exec_nodes = exec_nodes

        self.max_concurrency = int(max_concurrency)
        assert (
            max_concurrency >= 1
        ), "Invalid maximum number of threads! Must be a positive integer"
        
        node_ids = [n.id for n in exec_nodes]

        assert len(exec_nodes) == len(set(node_ids)), "All node ids should be unique"

        # variables necessary for DAG construction
        self.backwards_hierarchy: Dict[Hashable, List[Hashable]] = {
            exec_node.id: exec_node.depends_on for exec_node in self.exec_nodes
        }
        self.node_dict: Dict[Hashable, ExecNode] = {
            exec_node.id: exec_node for exec_node in self.exec_nodes
        }

        self.node_dict_by_name: Dict[str, ExecNode] = {
            exec_node.__name__: exec_node for exec_node in self.exec_nodes
        }

        # a sequence of execution to be applied in a for loop
        self.exec_node_sequence: List[ExecNode] = []

        self._build()

    def find_cycle(self) -> Optional[List[Tuple[str, str]]]:
        """
        A DAG doesn't have any dependency cycle.
        This method returns the cycles if found.
        return: A list of the edges responsible for the cycles in case there are some (in forward and backward),
        otherwise nothing.
        return example: [('taxes', 'amount_reconciliation'),('amount_reconciliation', 'taxes')]
        """
        try:
            cycle: List[Tuple[str, str]] = find_cycle(self.graph_ids)
            return cycle
        except NetworkXNoCycle:
            return None

    def _build(self) -> None:
        """
        Builds the graph and the sequence order for the computation.
        """
        # add nodes
        for node_id in self.backwards_hierarchy.keys():
            self.graph_ids.add_node(node_id)

        # add edges
        for node_id, dependencies in self.backwards_hierarchy.items():
            if dependencies is not None:
                edges = [(dep, node_id) for dep in dependencies]
                self.graph_ids.add_edges_from(edges)

        # check for circular dependencies
        cycle = self.find_cycle()
        if cycle:
            raise NetworkXUnfeasible(
                f"the product contains at least a circular dependency: {cycle}"
            )

        # set sequence order
        topological_order = self.graph_ids.topological_sort()

        # calculate the sum of priorities of all recursive children
        self.assign_recursive_children_compound_priority()

        self.exec_node_sequence = [
            self.node_dict[node_name] for node_name in topological_order
        ]

    def assign_recursive_children_compound_priority(self) -> None:
        """
        Assigns a compound priority to all nodes in the graph.
        The compound priority is the sum of the priorities of all children recursively.
        """
        # Iterating in reverse topological order guarantees that a node's compound
        # priority is final before it is added to its dependencies' priorities.
        for node_id in reversed(self.graph_ids.topological_sort()):
            node = self.node_dict[node_id]
            for parent_id in self.backwards_hierarchy[node_id] or []:
                self.node_dict[parent_id].compound_priority += node.compound_priority

    def _render_html(
        self,
        heading: str,
        html_file_name: str,
        titles: Dict[Hashable, str],
        colors: Dict[Hashable, str],
    ) -> None:
        """
        Renders the graph as an interactive pyvis html file.
        Args:
            heading: title displayed inside the html page
            html_file_name: name of the output file
            titles: hover text per node id
            colors: color per node id
        """
        # pyvis' hierarchical layout only needs a level per node: its topological
        # layer (this avoids nx.multipartite_layout, which requires numpy)
        levels = {
            node: layer
            for layer, nodes in enumerate(nx.topological_generations(self.graph_ids))
            for node in nodes
        }

        from pyvis.network import Network

        g = Network(layout=True, directed=True, heading=heading, notebook=False)

        for node_id, level in levels.items():
            g.add_node(
                node_id,
                label=node_id,
                level=level,
                title=titles[node_id],
                color=colors[node_id],
            )

        for e in self.graph_ids.edges:
            g.add_edge(e[0], e[1])

        g.set_options(
            """
        var options = {
            "layout": {
                "hierarchical": {
                    "enabled": true,
                    "direction": "LR",
                    "sortMethod": "directed"
                }
            },
            "physics": {
                "enabled": false
            }
        }
        """
        )

        import re

        html_str = g.generate_html()
        html_str = re.sub(r"<center>.+?<\/h1>\s+<\/center>", "", html_str, count=1, flags=re.DOTALL)
        with open(html_file_name, "w") as h:
            h.write(html_str)

    def only_draw(self, name=None, color="green") -> None:
        """
        Draws the structure of the DAG as an html file named {name}_structure.html
        Args:
            name: name of the output file, defaults to the DAG name
            color: color used for every node
        """
        if name is None:
            name = self.name

        titles = {node_id: f"id: {node_id}" for node_id in self.graph_ids.nodes}
        colors = {node_id: color for node_id in self.graph_ids.nodes}

        self._render_html(
            heading=f"{self.name} structure",
            html_file_name=f"{name}_structure.html",
            titles=titles,
            colors=colors,
        )

    def _draw(self, node_dict: Dict[Hashable, ExecNode], dt_string: str) -> None:
        """
        Draws the DAG with the execution states of the provided run
        as an html file named {self.name}_states_run.html
        Args:
            node_dict: the nodes of the run to draw
            dt_string: timestamp of the run, displayed in the heading
        """
        state_colors = {0: "grey", 1: "green", -1: "red"}

        titles = {}
        colors = {}
        for node_id, node in node_dict.items():
            result = node.result
            if result is None:  # node pruned by leaves_ids, never executed
                titles[node_id] = f"id: {node_id}\n                        state: not executed"
                colors[node_id] = state_colors[0]
                continue
            titles[node_id] = f"""id: {node_id}
                        started at: {result["initial_time"]} and finished at {result["final_time"]}
                        exec_time: {result["duration"]}
                        state: {result["state"]}
                        message: {result["message"]}"""
            colors[node_id] = state_colors[result["state"]]

        self._render_html(
            heading=f"{self.name} execution states after run at {dt_string}",
            html_file_name=f"{self.name}_states_run.html",
            titles=titles,
            colors=colors,
        )

    def execute(
        self,
        leaves_ids: Optional[List[Union[Hashable, ExecNode]]] = None,
        resume: bool = False,
    ) -> Dict[Hashable, Any]:
        """
        Execute the DAG.
        Safe for concurrent execution of the same DAG instance: each run works on
        its own copy of the nodes and returns its own results. After concurrent
        runs, `self.node_dict` (and the html output file, which shares one file
        name per DAG) holds the data of the last run to finish; use the returned
        dictionary to get the results of a specific run.
        Args:
            leaves_ids: The nodes (or the ids of the nodes) to be executed
            resume: if True, nodes that finished successfully in a previous run
                are skipped and keep their previous result (useful to resume a
                partially failed run). If False (default), every node runs fresh.
        Returns:
            node_dict: dictionary mapping node ids to the executed ExecNode copies
                (each carries its `result` for this run)
        """

        dt_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.dt_string = dt_string
        # 0.1 create a subgraph of the graph if necessary
        graph = subgraph(self.graph_ids, leaves_ids)

        # 0.2 copy the nodes in order to modify the results inside every node
        # without mutating the nodes of a previous run (results are reassigned,
        # never mutated in place, so shallow copies are enough).
        # read self.node_dict once so a concurrent run reassigning it can't
        # give this run a mixed view
        source_nodes = self.node_dict
        node_dict = {id_: copy(node) for id_, node in source_nodes.items()}

        # 0.2.1 on a fresh (non-resume) run, discard any state carried over from
        # a previous run so every node is recomputed
        if not resume:
            for node in node_dict.values():
                node.state = 0
                node.result = None

        # 0.3 create variables related to futures
        futures: Dict[Hashable, "Future[Any]"] = {}
        done: Set["Future[Any]"] = set()
        running: Set["Future[Any]"] = set()
        # ids submitted to the executor whose node is still in the graph
        submitted_ids: Set[Hashable] = set()

        # 0.4 create helpers functions encapsulated from the outside
        def get_num_running_threads(_running: Set["Future[Any]"]) -> int:
            # use not future.done() because there is no guarantee that Thread pool will directly execute
            # the submitted thread
            return sum(1 for future in _running if not future.done())

        def get_highest_priority_nodes(nodes: List[ExecNode]) -> List[ExecNode]:
            highest_priority = max(node.priority for node in nodes)
            return [node for node in nodes if node.priority == highest_priority]

        # 0.5 get the candidate root nodes that can be executed.
        # `ready` is kept up to date incrementally: a node is added when its last
        # dependency is removed from the graph and discarded once submitted,
        # so it never needs a full graph rescan.
        ready: Set[Hashable] = set(graph.root_nodes())

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            while len(graph):
                # attempt to run **A SINGLE** root node #

                # 6. block scheduler execution if no root node can be executed.
                #    this can occur in two cases:
                #       1. if maximum concurrency is reached
                #       2. if no runnable node exists (i.e. all root nodes are being executed)
                #    in both cases: block until a node finishes
                #       => a new root node will be available
                num_running_threads = get_num_running_threads(running)
                if (
                    num_running_threads == self.max_concurrency
                    or len(ready) == 0
                ):
                    # must wait and not submit any workers before a worker ends
                    # (that might create a new more prioritized node) to be executed
                    if self.debug:
                        logger.debug(
                            f"Waiting for ExecNodes {running} to finish. Finished running {done}"
                        )
                    done_, running = wait(running, return_when=FIRST_COMPLETED)
                    done = done.union(done_)

                # 1. among the finished futures:
                #       1. checks for exceptions
                #       2. and remove them from the graph
                for id_ in list(submitted_ids):
                    fut = futures[id_]
                    if fut.done():
                        if self.debug:
                            logger.debug(f"Remove ExecNode {id_} from the graph")
                        # surfaces unexpected exceptions raised outside ExecNode.execute's
                        # own error handling (node failures are stored in result, not raised)
                        fut.result()
                        # 1.1 if id_ failed, prune its whole doomed subtree instead of
                        # submitting each descendant just to see it fail on a missing dependency
                        if (
                            node_dict[id_].result is not None
                            and node_dict[id_].result["state"] == -1
                        ):
                            descendants = nx.descendants(graph, id_)
                            if self.debug:
                                logger.debug(
                                    f"Pruning {len(descendants)} descendants of failed ExecNode {id_}"
                                )
                            for d in descendants:
                                d_node = node_dict[d]
                                if d_node.state != 1:
                                    now = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
                                    d_node.result = {
                                        "result": None,
                                        "state": 0,
                                        "message": "Did not run",
                                        "initial_time": now,
                                        "final_time": now,
                                        "duration": "0 sec",
                                    }
                                    d_node.state = 0
                                ready.discard(d)
                            graph.remove_nodes_from(descendants)
                        # successors whose last dependency was id_ become ready
                        successors = list(graph.successors(id_))
                        graph.remove_node(id_)
                        submitted_ids.discard(id_)
                        for successor in successors:
                            if graph.in_degree(successor) == 0:
                                ready.add(successor)

                # 2. the `ready` set holds the root nodes that aren't being executed

                # 3. if no runnable node exist, go to step 6 (wait for a node to finish)
                #   (This **might** create a new root node)
                if len(ready) == 0:
                    if self.debug:
                        logger.debug("No runnable Nodes available")
                    continue

                # 4. choose a node to run
                # 4.1 get the most prioritized node to run
                # 4.1.1 get all the nodes that have the highest priority
                runnable_nodes = [node_dict[node_id] for node_id in ready]
                highest_priority_nodes = get_highest_priority_nodes(runnable_nodes)

                # 4.1.2 get the node with the highest compound priority
                # (arbitrarily selected if multiple are suggested)
                exec_node = max(
                    highest_priority_nodes, key=lambda node: node.compound_priority
                )

                # logger.info(f"{exec_node.id} will run!")

                # 4.2 if the current node must be run sequentially, wait for a running node to finish.
                # in that case we must prune the graph to re-check whether a new root node
                # (maybe with a higher priority) has been created => continue the loop
                # Note: This step might run a number of times in the while loop
                #       before the exec_node gets submitted
                num_running_threads = get_num_running_threads(running)
                if exec_node.is_sequential and num_running_threads != 0:
                    if self.debug:
                        logger.debug(
                            f"{exec_node.id} must not run in parallel."
                            f"Wait for the end of a node in {running}"
                        )
                    done_, running = wait(running, return_when=FIRST_COMPLETED)
                    # go to step 6
                    continue

                # 5.1 submit the exec node to the executor
                if exec_node.state !=1:
                    exec_future = executor.submit(
                        exec_node.execute,
                        node_dict=node_dict,
                        debug=self.debug,
                        initial_time=datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
                    )
                    
                else:
                    logger.info(f"{exec_node.id} already in finished state, wont run")
                    exec_future = executor.submit(lambda: None)

                running.add(exec_future)
                futures[exec_node.id] = exec_future
                ready.discard(exec_node.id)
                submitted_ids.add(exec_node.id)

                # 5.2 wait for the sequential node to finish
                # TODO: not sure this code ever runs
                if exec_node.is_sequential:
                    wait(futures.values(), return_when=ALL_COMPLETED)
        # single atomic reassignment: with concurrent runs, the last one to
        # finish wins; each caller still gets its own results via the return value
        self.node_dict = node_dict

        if self.draw:
            self._draw(node_dict, dt_string)

        # nodes pruned by leaves_ids never ran and have no result
        states = [
            node.result["state"] for node in node_dict.values() if node.result is not None
        ]

        if states and (min(states) != 1) and (self.error_type_fatal):
            raise ValueError("DAG did not finished as expected")

        return node_dict
