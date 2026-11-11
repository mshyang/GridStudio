"""Small helpers shared by the pipeline stages for reading and writing graph attributes."""

from __future__ import annotations

from typing import Any, Dict, Hashable

import networkx as nx


def require_node_attribute(
    graph: nx.Graph, attr: str, *, needed_by: str, set_by: str
) -> None:
    """Raise a clear error when *graph* has nodes but none carries *attr*.

    The pipeline stages build on each other through node attributes
    (``bus_type`` -> ``pg_max`` -> ``pl`` -> ``pg``).  Running a stage before
    its prerequisite used to produce an empty result without complaint; this
    turns that into an error that names the missing step.
    """
    if graph.number_of_nodes() == 0:
        return
    if any(attr in data for _, data in graph.nodes(data=True)):
        return
    raise ValueError(
        f"{needed_by} needs the {attr!r} node attribute, but no node of the "
        f"graph has it. Run {set_by} on this graph first (it stores its "
        f"result on the graph), or set the attribute yourself with "
        f"networkx.set_node_attributes(graph, values, name={attr!r})."
    )


def store_node_attribute(
    graph: nx.Graph, values: Dict[Hashable, Any], name: str
) -> None:
    """Write *values* to the node attribute *name*, replacing earlier values.

    Nodes that are not in *values* lose the attribute, so re-running a stage
    never leaves results from a previous run behind.
    """
    for _, data in graph.nodes(data=True):
        data.pop(name, None)
    nx.set_node_attributes(graph, values, name=name)
