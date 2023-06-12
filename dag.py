
# type: ignore

from easydags import  ExecNode, DAG


nodes = []


nodes.append( ExecNode(id_= 'f0',
              exec_function = lambda :  0
              ) )  


nodes.append( ExecNode(id_= 'f1',
              exec_function = lambda :  1
              ) )   

def aux(**kwargs):
    f1 = kwargs['f1_result']
    f0 = kwargs['f0_result']
    return f1*2 + f0

nodes.append( ExecNode(id_= 'f2',
              exec_function = aux,
              depends_on_hard= ['f1','f0']) )   


def aux2(**kwargs):
    f2 = kwargs['f2_result']
    return f2 * 2

nodes.append( ExecNode(id_= 'f3',
              exec_function = aux2,
              depends_on_hard = ['f2']) )   


def aux3(**kwargs):
    return 3


import random as rnd


def fail(**kwargs):
    rnd_num = rnd.random()
    if rnd_num > 0.01:
         raise ValueError('This is a random error')
    return kwargs


nodes.append( ExecNode(id_= 'f4',
              exec_function = fail,
              n_trials=1,
              depends_on_soft= ['f3']) )  



nodes.append( ExecNode(id_= 'f5',
              exec_function = fail,
              n_trials=3,
              depends_on_hard= ['f3']) )  



nodes.append( ExecNode(id_= 'f6',
              exec_function = aux3,
              depends_on_hard= ['f3', 'f4','f5']) )  





def execute():
    dag = DAG(nodes,name = 'Example DAG',max_concurrency=8, debug = False)

    dag.execute()
    



if __name__ == "__main__":

    dag = execute()

  


