
from fastapi import FastAPI
from easydags import  ExecNode, DAG
import time

app = FastAPI()


@app.get("/dag1")
async def dag1():

    nodes = []


    def example0():
        print('beginning 0')
        time.sleep(3)
        print('end 0')
        return 4

    nodes.append( ExecNode(id_= 'f0',
                exec_function = example0
                ) )  

    def example1(**kwargs):
        f0_result = kwargs['f0_result']
        print('beginning 1')
        print('end 1')
        print(f0_result + 8 )

    nodes.append( ExecNode(id_= 'f1',
                exec_function = example1 ,
                depends_on_hard= ['f0']
                ) )   



    
    dag = DAG(nodes,name = 'Example DAG hard dependency',max_concurrency=8, debug = False)

    dag.execute()

    #DO SOMETHING WITH "Example DAG hard dependency_states_run.html" in case you need it

    return {"message": "Updated!"}

@app.get("/dag2")
async def dag2():
    
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

    dag.execute()

    return {"message": "Updated!"}

@app.get("/ready")
async def ready():
    return {"ready"}