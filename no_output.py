from easydags import  ExecNode, DAG
import time

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

dag = DAG(nodes,name = 'NO HTML OUTPUT',max_concurrency=8, 
          debug = False, 
          draw = False)
#NO HTML OUTPUT_states_run.html would be the name of the output

dag.execute()