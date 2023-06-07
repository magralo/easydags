import time
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
from typing import Any, Dict, Hashable, List, Optional, Set, Tuple, Union

import networkx as nx
from loguru import logger
from networkx import find_cycle
from networkx.exception import NetworkXNoCycle, NetworkXUnfeasible

import traceback

from .errors import ErrorStrategy
from .node import ExecNode
from datetime import datetime

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

    def remove_recursively(self, root_node: Hashable) -> None:
        """
        Recursively removes all the nodes that depend on the provided one
        Args:
            root_node: the root node
        """
        nodes_to_remove: Set[Hashable] = set()

        def dfs(n: Hashable, graph: DiGraphEx, visited: Set[Hashable]) -> None:
            if n in visited:
                return
            else:
                visited.add(n)
                for child in graph[n].keys():
                    dfs(child, graph, visited)

        dfs(root_node, self, nodes_to_remove)
        for node in nodes_to_remove:
            self.remove_node(node)

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

        # works by pruning the graph until all leaf nodes
        # are contained inside the provided "nodes"
        # in the arguments of this method

        if any([node not in self.nodes for node in nodes]):
            raise ValueError(
                f"The provided nodes are not in the graph. "
                f"The provided nodes are: {nodes}."
                f"The graph only contains: {self.nodes}."
            )

        leaf_nodes = self.leaf_nodes()
        nodes_to_remove = set(leaf_nodes).difference(set(nodes))

        while nodes_to_remove:
            node_to_remove = nodes_to_remove.pop()
            self.remove_node(node_to_remove)

            leaf_nodes = self.leaf_nodes()
            nodes_to_remove = set(leaf_nodes).difference(set(nodes))

        leaf_nodes = self.leaf_nodes()
        unremovable_nodes = set(nodes).difference(set(leaf_nodes))

        if len(unremovable_nodes) > 0:
            if self.debug:
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
def subgraph(graph: DiGraphEx, leaves_ids: Optional[List[Union[Hashable, ExecNode]]]) -> DiGraphEx:
    """returns a deep copy of the same graph if leaves_ids is None,
    otherwise returns a new graph by applying `graph.subgraph_leaves`

    Args:
        graph (DiGraphEx): graph describing the DAG
        leaves_ids (List[Union[Hashable, ExecNode]]): The leaves that must be executed

    Returns:
        DiGraphEx: The subgraph of the provided graph
    """
    # TODO: avoid mutable state, hence avoid doing deep copies ?
    # 0. deep copy the graph ids
    graph = deepcopy(graph)

    # TODO: make the creation of subgraph possible directly from initialization
    # 1. create the subgraph
    if leaves_ids is not None:
        # Extract the ids from the provided leaves/leaves_ids
        leaves_ids = [
            node_id.id if isinstance(node_id, ExecNode) else node_id for node_id in leaves_ids
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
        exec_nodes: List[ExecNode],
        name: str = 'DAG',
        max_concurrency: int = 1,
        debug: bool = True,
        error_type_fatal: bool = True
    ):
        """
        Args:
            exec_nodes: all the ExecNodes
            max_concurrency: the maximal number of threads running in parallel
            name: Name of the dag, will be usefull for creating the html output
            degub: weather or not you want degub messages

        """
        self.graph_ids = DiGraphEx()
    
        self.name = name

        self.debug = debug

        self.error_type_fatal = error_type_fatal
        # since ExecNodes are modified they must be copied
        self.exec_nodes = exec_nodes

        self.max_concurrency = int(max_concurrency)
        assert max_concurrency >= 1, "Invalid maximum number of threads! Must be a positive integer"

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

        self.behavior = ErrorStrategy.strict

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

        self.exec_node_sequence = [self.node_dict[node_name] for node_name in topological_order]

    def assign_recursive_children_compound_priority(self) -> None:
        """
        Assigns a compound priority to all nodes in the graph.
        The compound priority is the sum of the priorities of all children recursively.
        """
        # Note: if there was a forward dependency recorded, this would have been much easier

        graph_ids = deepcopy(self.graph_ids)
        leaf_ids = graph_ids.leaf_nodes()

        # 2. assign the compound priority for all the remaining nodes in the graph:
        # Priority assignment happens by epochs:
        # 2.1. during every epoch, we assign the compound priority for the parents of the current leaf nodes
        # 2.2. at the end of every epoch, we trim the graph from its leaf nodes;
        #       hence the previous parents become the new leaf nodes
        while len(graph_ids) > 0:

            # Epoch level
            for leaf_id in leaf_ids:
                leaf_node = self.node_dict[leaf_id]

                for parent_id in self.backwards_hierarchy[leaf_id]:
                    # increment the compound_priority of the parent node by the leaf priority
                    parent_node = self.node_dict[parent_id]
                    parent_node.compound_priority += leaf_node.compound_priority

                # trim the graph from its leaf nodes
                graph_ids.remove_node(leaf_id)

            # assign the new leaf nodes
            leaf_ids = graph_ids.leaf_nodes()

    def _draw(self,name='Graph', k: float = 0.8, display: bool = True, t: int = 3) -> None:
        """
        Draws the Networkx directed graph.
        Args:
            k: parameter for the layout of the graph, the higher, the further the nodes apart
            display: display the layout created
            t: time to display in seconds
        """


        for layer, nodes in enumerate(nx.topological_generations(self.graph_ids)):
            # `multipartite_layout` expects the layer as a node attribute, so add the
            # numeric layer value as a node attribute
            for node in nodes:
                self.graph_ids.nodes[node]["layer"] = layer

        # Compute the multipartite_layout using the "layer" node attribute
        pos = nx.multipartite_layout(self.graph_ids, subset_key="layer")
        


        print('drawing')

        aux = self.node_dict


        from pyvis.network import Network

        

        # datetime object containing current date and time
        

        head_title = f"{self.name} execution states after run at {self.dt_string}"

        g = Network(layout=True,directed =True,heading=head_title)


        titles = []
        color_map = [] 
        
        for f in  list(pos.keys()):
            state = aux[f].result['state']
            m = aux[f].result['message']
            initial = aux[f].result['initial_time']
            final = aux[f].result['final_time']
            duration = aux[f].result['duration']
            title = f'''id: {f}
                        started at: {initial} and finished at {final}
                        exec_time: {duration}
                        state: {state}
                        message: {m}'''
            titles.append(title)
            
            if state == 0  :
                color_map.append('grey')
            if state == 1  :
                color_map.append('green')
            if state == -1  :
                color_map.append('red')


        aux = [x[0]   for x in pos.values()]

        pos_holder = list(set(aux))

        pos_holder.sort()

        

        level = [pos_holder.index(i) for i in aux]


        for i in range(len(pos.keys())):
            g.add_node(list(pos.keys())[i],
                         label= list(pos.keys())[i],
                         level = level[i],
                         title = titles[i],
                         color= color_map[i])
            

        #g = Network('500px', '500px')

        for key in pos.keys():
            x = pos[key][0]
            y = pos[key][1] 
            




        for e in self.graph_ids.edges :
            
            g.add_edge(e[0],e[1])
            

        g.set_options('''
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
        ''')


        g.show('nx.html')
        

        import re 
        html_str = re.sub(r'<center>.+?<\/h1>\s+<\/center>', '', g.html, 1, re.DOTALL)
        h = open(f'{self.name}_states_run.html','w')
        h.write(html_str)
        h.close()

        

    def execute(
        self, leaves_ids: Optional[List[Union[Hashable, ExecNode]]] = None
    ) -> Dict[Hashable, Any]:
        """
        Thread safe execution of the DAG.
        Args:
            leaves_ids: The nodes (or the ids of the nodes) to be executed
        Returns:
            node_dict: dictionary with keys the name of the function and value the result after the execution
        """

        from datetime import datetime
        now = datetime.now()
        
        self.dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        # 0.1 create a subgraph of the graph if necessary
        graph = subgraph(self.graph_ids, leaves_ids)

        # 0.2 deepcopy the node_dict in order to modify the results inside every node
        node_dict = deepcopy(self.node_dict)

        # 0.3 create variables related to futures
        futures: Dict[Hashable, "Future[Any]"] = {}
        done: Set["Future[Any]"] = set()
        running: Set["Future[Any]"] = set()

        # 0.4 create helpers functions encapsulated from the outside
        def get_num_running_threads(_futures: Dict[Hashable, "Future[Any]"]) -> int:
            # use not future.done() because there is no guarantee that Thread pool will directly execute
            # the submitted thread
            return sum([not future.done() for future in _futures.values()])

        def get_highest_priority_nodes(nodes: List[ExecNode]) -> List[ExecNode]:
            highest_priority = max(node.priority for node in nodes)
            return [node for node in nodes if node.priority == highest_priority]

        # 0.5 get the candidates root nodes that can be executed
        # runnable_nodes_ids will be empty if all root nodes are running
        runnable_nodes_ids = graph.root_nodes()

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            while len(graph):
                # attempt to run **A SINGLE** root node #

                # 6. block scheduler execution if no root node can be executed.
                #    this can occur in two cases:
                #       1. if maximum concurrency is reached
                #       2. if no runnable node exists (i.e. all root nodes are being executed)
                #    in both cases: block until a node finishes
                #       => a new root node will be available
                num_running_threads = get_num_running_threads(futures)
                num_runnable_nodes_ids = len(runnable_nodes_ids)
                if num_running_threads == self.max_concurrency or num_runnable_nodes_ids == 0:
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
                for id_, fut in futures.items():
                    if fut.done() and id_ in graph:
                        if self.debug:
                            logger.debug(f"Remove ExecNode {id_} from the graph")
                        self.handle_exception(graph, fut, id_)
                        graph.remove_node(id_)

                # 2. list the root nodes that aren't being executed
                runnable_nodes_ids = list(set(graph.root_nodes()) - set(futures.keys()))

                # 3. if no runnable node exist, go to step 6 (wait for a node to finish)
                #   (This **might** create a new root node)
                if len(runnable_nodes_ids) == 0:
                    if self.debug:
                        logger.debug("No runnable Nodes available")
                    continue

                # 4. choose a node to run
                # 4.1 get the most prioritized node to run
                # 4.1.1 get all the nodes that have the highest priority
                runnable_nodes = [node_dict[node_id] for node_id in runnable_nodes_ids]
                highest_priority_nodes = get_highest_priority_nodes(runnable_nodes)

                # 4.1.2 get the node with the highest compound priority
                # (randomly selected if multiple are suggested)
                exec_node = sorted(highest_priority_nodes, key=lambda node: node.compound_priority)[
                    -1
                ]

                logger.info(f"{exec_node.id} will run!")

                # 4.2 if the current node must be run sequentially, wait for a running node to finish.
                # in that case we must prune the graph to re-check whether a new root node
                # (maybe with a higher priority) has been created => continue the loop
                # Note: This step might run a number of times in the while loop
                #       before the exec_node gets submitted
                num_running_threads = get_num_running_threads(futures)
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
                exec_future = executor.submit(exec_node.execute, 
                                              node_dict=node_dict, 
                                              debug = self.debug,
                                              initial_time = datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))
                running.add(exec_future)
                futures[exec_node.id] = exec_future

                # 5.2 wait for the sequential node to finish
                # TODO: not sure this code ever runs
                if exec_node.is_sequential:
                    wait(futures.values(), return_when=ALL_COMPLETED)
        self.node_dict = node_dict

        self._draw()

        states = [node_dict[x].result['state'] for x in node_dict]

        if (min(states)!=1) and (self.error_type_fatal):
            raise ValueError('DAG did not finished as expected')

        return self



    def handle_exception(self, graph: DiGraphEx, fut: "Future[Any]", id_: Hashable) -> None:
        """
        This simply raise an error if any

        """


        _res = fut.result()  # noqa: F841


