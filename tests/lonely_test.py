import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from easydags import  ExecNode, DAG
import time
import networkx as nx

#falta otro test con un nodo rojo y otro gris
def test_running_lonely():

    nodes = []


    def prepro():
        time.sleep(3)
        return 'df with cool features'



    nodes.append( ExecNode(id_= 'pre_process',
            exec_function = prepro,
            output_name = 'my_cool_df'
            ) )  


    def model1(**kwargs):
        df = kwargs['my_cool_df']
        return 'model 1 37803'

    nodes.append( ExecNode(id_= 'model1',
            exec_function = model1 ,
            output_name = 'model1',
            depends_on_hard= ['pre_process']
            ) )   



    def model2(**kwargs):
        time.sleep(3)
        return 'model 2 78373'

    nodes.append( ExecNode(id_= 'model2',
            exec_function = model2 ,
            output_name = 'model2'
            ) )  



    def ensemble(**kwargs):
        model1 = kwargs['model1']
        model2 = 'Null'
        result = f'{model1} and {model2}'
        return result 

    nodes.append( ExecNode(id_= 'ensemble',
            exec_function = ensemble ,
            depends_on_hard= ['model1'],
            output_name = 'ensemble'
            ) )  



    dag = DAG(nodes,name = 'lonely example',
              max_concurrency=3, 
              debug = False)

    dag.execute()
    
        


    ### all nodes
    assert 'pre_process' in dag.graph_ids.nodes
    assert 'model1' in dag.graph_ids.nodes
    assert 'model2' in dag.graph_ids.nodes
    assert 'ensemble' in dag.graph_ids.nodes
      

    ### all edges

    assert ('model1','ensemble') in dag.graph_ids.edges
    assert ('pre_process','model1') in dag.graph_ids.edges



