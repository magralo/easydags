
# type: ignore

from easydags import  ExecNode, DAG, search_nodes
import time

nodes = []


def prepro():
    #print('beginning pre pro')
    time.sleep(3)
    #print('end pre pro')
    return 'df with cool features'



node0 = ExecNode(id_= 'pre_process',
              exec_function = prepro,
              output_name = 'my_cool_df'
              ) 


def model1(**kwargs):
    df = kwargs['my_cool_df']
    
    #print(f'i am using {df} in model 1')
    time.sleep(3)
    print('finish training model1')
    
    return 'model 1 37803'

node1 = ExecNode(id_= 'model1',
              exec_function = model1 ,
              output_name = 'model1'
              )   



def model2(**kwargs):
    df = kwargs['my_cool_df']
    
    #print(f'i am using {df} in model 2')
    time.sleep(3)
    print('finished training model2')
    
    return 'model 2 5678'

node2 = ExecNode(id_= 'model2',
              exec_function = model2 ,
              output_name = 'model2'
              ) 



def ensemble(**kwargs):
    model1 = kwargs['model1']
    model2 = kwargs['model2']
    
    result = f'{model1} and {model2}'
    
    print(result)
    
    return result 

node3= ExecNode(id_= 'ensemble',
              exec_function = ensemble ,
              output_name = 'ensemble'
              ) 



node0>>node1
node0>>node2

node1>>node3
node2>>node3


nodes = [] 
globs = globals().copy()
for obj_name in globs:         
    if isinstance(globs[obj_name], ExecNode):
        nodes.append(globs[obj_name])




dag = DAG(nodes,name = 'Ensemble example2',max_concurrency=3, debug = False)

dag.execute()
    





  


