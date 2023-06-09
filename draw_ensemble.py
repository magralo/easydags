
# type: ignore

from easydags import  ExecNode, DAG
import time

nodes = []


def prepro():
    print('beginning pre pro')
    time.sleep(3)
    print('end pre pro')
    return 'df with cool features'



nodes.append( ExecNode(id_= 'pre_process',
              exec_function = prepro,
              output_name = 'my_cool_df'
              ) )  


def model1(**kwargs):
    df = kwargs['my_cool_df']
    
    print(f'i am using {df} in model 1')
    time.sleep(3)
    print('finish training model1')
    
    return 'model 1 37803'

nodes.append( ExecNode(id_= 'model1',
              exec_function = model1 ,
              depends_on_hard= ['pre_process'],
              output_name = 'model1'
              ) )   



def model2(**kwargs):
    df = kwargs['my_cool_df']
    
    print(f'i am using {df} in model 2')
    time.sleep(3)
    print('finished training model2')
    
    return 'model 2 78373'

nodes.append( ExecNode(id_= 'model2',
              exec_function = model2 ,
              depends_on_hard= ['pre_process'],
              output_name = 'model2'
              ) )  



def ensemble(**kwargs):
    model1 = kwargs['model1']
    model2 = kwargs['model2']
    
    result = f'{model1} and {model2}'
    
    print(result)
    
    return result 

nodes.append( ExecNode(id_= 'ensemble',
              exec_function = ensemble ,
              depends_on_hard= ['model1','model2'],
              output_name = 'ensemble'
              ) )  



dag = DAG(nodes,name = 'Ensemble example',max_concurrency=3, debug = False)

dag.only_draw(name = 'green dag')

dag.only_draw(name = 'yellow dag', color = 'yellow')
    





  


