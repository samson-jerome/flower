import uuid
from flower.models.graph import Graph
from flower.models.node import Node, NodeType
from flower.execution.traversal import traverse


def _node(name, **kwargs) -> Node:
    return Node(id=str(uuid.uuid4()), name=name, type=NodeType.NOOP, **kwargs)


def test_traverse_empty_graph_yields_nothing():
    assert list(traverse(Graph())) == []


def test_traverse_single_node():
    n = _node("solo")
    graph = Graph(roots=[n])
    assert list(traverse(graph)) == [n]


def test_traverse_preorder_parent_then_children_then_sibling():
    # root
    # ├── child_a
    # │   └── grandchild
    # └── child_b
    root       = _node("root")
    child_a    = _node("child_a")
    grandchild = _node("grandchild")
    child_b    = _node("child_b")
    child_a.children = [grandchild]
    grandchild.parent = child_a
    root.children = [child_a, child_b]
    child_a.parent = root
    child_b.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root", "child_a", "grandchild", "child_b"]


def test_traverse_multiple_roots_in_list_order():
    first  = _node("first")
    second = _node("second")
    graph = Graph(roots=[first, second])
    assert [n.name for n in traverse(graph)] == ["first", "second"]


def test_traverse_skips_inactive_node_and_its_subtree():
    root  = _node("root")
    child = _node("child", is_active=False)
    grandchild = _node("grandchild")
    child.children = [grandchild]
    grandchild.parent = child
    root.children = [child]
    child.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root"]


def test_traverse_visits_collapsed_node_children():
    root  = _node("root", is_collapsed=True)
    child = _node("child")
    root.children = [child]
    child.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root", "child"]
