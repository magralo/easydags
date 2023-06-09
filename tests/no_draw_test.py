import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from easydags import  ExecNode, DAG
import time
import networkx as nx

def test_running_ok():

    nodes = []


    def example0():
        print('beginning 0')
        time.sleep(3)
        print('end 0')



    nodes.append( ExecNode(id_= 'f0',
                exec_function = example0
                ) )  


    def example1():
        print('beginning 1')
        print('end 1')

    nodes.append( ExecNode(id_= 'f1',
                exec_function = example1 ,
                depends_on_soft= ['f0']
                ) )   

    dag = DAG(nodes,name = 'NO HTML OUTPUT TEST',max_concurrency=8, 
            debug = False, 
            draw = False)
    #NO HTML OUTPUT_states_run.html would be the name of the output

    dag.execute()

    dag.execute()
    
    ids = list(dag.graph_ids)
        
    nodes_states = dag.node_dict



        
    states =[nodes_states[f].result['state'] for f in ids]
    

    assert min(states) == 1

    import os.path

    exist = os.path.exists('NO HTML OUTPUT TEST_states_run.html')

    assert not exist
