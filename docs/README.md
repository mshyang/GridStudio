# Getting Started

**Source code:** [github.com/mshyang/GridStudio](https://github.com/mshyang/GridStudio)

GridStudio's Python package is called `powergrid_synth`, the project's earlier name. You install and import it under that name.

## Installation

GridStudio is not on PyPI yet, so install it from GitHub. Python 3.10, 3.11 and 3.12 are supported.

```bash
pip install "powergrid_synth[export] @ git+https://github.com/mshyang/GridStudio"
```

The `[export]` extra is what most people want. Without it you get the core only:

| Install | Dependencies | What works |
|---------|--------------|------------|
| core: `pip install git+https://github.com/mshyang/GridStudio` | numpy, scipy, networkx, matplotlib, pandas | Building grids from your own specifications (`mode="synthetic"`, `mode="default"`), every pipeline stage, analysis and plotting |
| with `[export]` | adds pandapower, pypowsybl, numba, lightsim2grid, xlsxwriter, openpyxl | Everything above, plus cloning a reference grid (`mode="reference"`), reading and writing grid files, and power flow |

If you call something that needs the extra without having it, the error message contains the install command.

### From source

```bash
git clone https://github.com/mshyang/GridStudio.git
cd GridStudio
pip install -e ".[dev,export]"
pytest
```

## A first grid

```python
from powergrid_synth import synthesize

grid = synthesize(
    mode="reference",
    reference_case="case118",   # clone the statistical profile of the IEEE 118-bus case
    seed=42,
    export_formats=None,        # return the graph only; pass e.g. ["json", "matpower"] to write files
)

print(grid)                     # PowerGridGraph with 123 nodes and 171 edges
print(grid.nodes[0])            # voltage_level, bus_type and, depending on the type, pg_max / pg / pl / ql
```

The result is a `networkx.Graph` subclass. Buses carry `voltage_level`, `bus_type` (`'Gen'`, `'Load'`, `'Conn'`), `pg_max` and `pg` (generators, MW), `pl` and `ql` (loads, MW and Mvar). Branches carry `type` (`'line'` or `'transformer'`), `r`, `x`, `z` (per unit) and `capacity` (MW).

Two things to keep in mind:

- The same `seed` gives the same grid.
- The number of buses is approximate, because only the largest connected component is kept. Check `grid.number_of_nodes()`.

## A first feeder

```python
from powergrid_synth import synthesize_distribution

feeders = synthesize_distribution(
    mode="default",
    n_feeders=3,
    n_nodes=30,
    total_load_mw=0.8,
    seed=7,
)

feeder = feeders[0]
print(feeder.max_hop, feeder.total_load_mw, feeder.is_radial)
```

## Progress output

Both functions print one line per stage. Pass `verbose=False` to silence a call, or set the level for the whole package:

```python
import powergrid_synth as pgs

pgs.set_verbosity("silent")    # nothing
pgs.set_verbosity("warning")   # problems only
pgs.set_verbosity("info")      # one line per stage (default)
pgs.set_verbosity("debug")     # per-level and per-iteration detail from every stage
```

## Where next

- The [home page](index.rst) summarises both pipelines, the step-by-step API, export formats and power-flow solvers.
- The [examples](examples/index.rst) are notebooks covering each stage.
- The [theory](theory/index.rst) pages explain the models behind each stage.

## Building the documentation

```bash
pip install -r docs/requirements.txt
cd docs
make html
```
