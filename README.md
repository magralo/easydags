# Easydags: DAGs made easy

This package was heavily inspired by this library: https://github.com/mindee/tawazi and a little bit by Airflow.

## Define a DAG

Maybe all of you already know what is a Directed Acyclic Graph (DAG)... but please think about this definition when using this library:


A DAG represents a collection of tasks you want to run, this is also organized to show relationships between tasks.

- Each node is a task (A,B) 
- Each edge represents a dependency, A->B means we can only execute B after A finishes.

## Double click to dependency 

The concept of dependency in general is preatty simple: A->B means that A needs to run before B.


But after we understand the concept of dependency we might need to complicate that concept a little bit with this two definitions.

Hard dependency:  B need the output of the process A… and the output of A is an actual argument of the function that executes B

Soft dependency:  B need the output of the process A… but the output is stored somewhere else, we just know that A have finished. As an example let's think about 2 queries where we need the table of the first query in the second one.

## Why do we need hard and soft dependencies

Basically i am a developer that works a lot with data pipelines, that means that i usually encounter the following scenario:

1. A query that creates: my_dataset.my_awesome_table
2. A second query that creates another table that depends on my_dataset.my_awesome_table

So what can we do in those cases? well, if we want to have the most recent version of the second table we will need to run the first query before!... but i do not need any result in memory! thats a soft dependency.

On the other hand i also had the following scenario:

1. i have a pre process function
2. i need to run model 1 to get prediction 1
3. i need to run model 2 to get my prediction 2
4. My final prediction will be the mean between prediction 1 and 2 (a simple ensamble)

Lest suppose that the first task leaves the resulting table in my_dataset.clean_data, that will create a soft dependency between the nodes 2,3 and node 1.

But lets suppose that we receive the predictions from model 1 and model 2 in the final node in memory? (something like a pandas dataframe)... that will create a hard dependency!

All hard dependencies can be re_writed as a soft dependency (using local files or databases) but there are some cases when it is easier/cheaper/faster to pass the data directly in memory... thats why we might encounter both kind of dependencies out in the wild!

This library will help you get through all those challenges if you use it wisely, i really hope that this helps someone with a real world problem. 

## How to use this library 

As we said in the definition a DAG is a list of tasks, and each node is a task with some dependencies (or none)... basically we can create a dag following that idea.

1. import the node clase (ExecNode)
2. import the DAG class
3. Create an empty list and start populating with nodes
4. Create nodes, specifiying their tasks (a python function) and define dependencies.
5. Create a DAG using the list of nodes

Here are some examples:


```python
from easydags import  ExecNode, DAG #import some useful classes
import time

nodes = [] #start the empty list


def example0():
    # A dummy function... we just create some "timeout" to crearly show that f1 will run just after f0
    print('beginning 0')
    time.sleep(3)
    print('end 0')



nodes.append( ExecNode(id_= 'f0',# we set the id of the task... must be unique
              exec_function = example0 # we set the task
              ) )  


def example1():
     # A dummy function... this is just to show that f1 runs after f0
    print('beginning 1')
    print('end 1')

nodes.append( ExecNode(id_= 'f1',# we set the id of the task... must be unique
              exec_function = example1 ,# we set the task
              depends_on_soft= ['f0'] # Since we dont need the actual result from our dependency this is as soft one
              ) )   


dag = DAG(nodes,max_concurrency=2) #Create the DAG as the list of nodes

dag.execute() # execute the dag

```









