import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

import pytest

from easydags import ExecNode, DAG


def ok(**kwargs):
    return 'ok'


def fail(**kwargs):
    raise ValueError('This is a random error')


def run(nodes, max_concurrency=3):
    dag = DAG(nodes, name='allow failure', max_concurrency=max_concurrency,
              debug=False, draw=False, error_type_fatal=False)
    return {id_: n.result['state'] for id_, n in dag.execute().items()}


def test_allowed_failure_does_not_block():
    a = ExecNode(id_='a', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok)
    a >= b

    assert run([a, b]) == {'a': -1, 'b': 1}


def test_same_upstream_blocks_other_edges():
    a = ExecNode(id_='a', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok)
    c = ExecNode(id_='c', exec_function=ok)
    d = ExecNode(id_='d', exec_function=ok)
    a >= b
    a > c
    c > d

    assert run([a, b, c, d]) == {'a': -1, 'b': 1, 'c': 0, 'd': 0}


def test_other_blocking_dependency_still_blocks():
    a = ExecNode(id_='a', exec_function=fail)
    x = ExecNode(id_='x', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok)
    a >= b
    x > b

    assert run([a, x, b]) == {'a': -1, 'x': -1, 'b': 0}


def test_allowed_dependency_that_did_not_run():
    # b is pruned because a failed; c allows it and must still run (and the DAG must finish)
    a = ExecNode(id_='a', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok)
    c = ExecNode(id_='c', exec_function=ok)
    d = ExecNode(id_='d', exec_function=ok)
    a > b
    b >= c
    c > d

    assert run([a, b, c, d], max_concurrency=1) == {'a': -1, 'b': 0, 'c': 1, 'd': 1}


def test_allowed_dependency_that_succeeds():
    a = ExecNode(id_='a', exec_function=ok)
    b = ExecNode(id_='b', exec_function=ok)
    a >= b

    assert run([a, b]) == {'a': 1, 'b': 1}


def test_constructor_argument():
    a = ExecNode(id_='a', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok, depends_on_soft=['a'], allow_failure_of=['a'])
    c = ExecNode(id_='c', exec_function=ok, depends_on_soft=['a'])

    assert run([a, b, c]) == {'a': -1, 'b': 1, 'c': 0}


def test_failure_is_still_fatal():
    a = ExecNode(id_='a', exec_function=fail)
    b = ExecNode(id_='b', exec_function=ok)
    a >= b

    dag = DAG([a, b], name='allow failure', debug=False, draw=False)
    with pytest.raises(ValueError):
        dag.execute()
    assert dag.node_dict['b'].result['state'] == 1