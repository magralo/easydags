
# type: ignore

from easydags import  ExecNode, DAG
import time

nodes = []


def example0():
    print('beginning 0')
    time.sleep(3)
    print('end 0')
    return 4



node0 = ExecNode(id_= 'f0',
              exec_function = example0
              )   


def example1(**kwargs):
    f0_result = kwargs['f0_result']
    print('beginning 1')
    print('end 1')
    print(f0_result + 8 )

node1 = ExecNode(id_= 'last',
              exec_function = example1 
              )    

node0 >> node1

nodes = [node0,node1]


def execute():
    dag = DAG(nodes,name = 'Example DAG hard dependency',max_concurrency=8, debug = False)

    dag.execute()
    



if __name__ == "__main__":

    dag = execute()

  


