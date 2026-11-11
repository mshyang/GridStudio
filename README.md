# GridStudio

[![CI](https://github.com/mshyang/GridStudio/actions/workflows/ci.yml/badge.svg)](https://github.com/mshyang/GridStudio/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/power-grid-synthesizer/badge/?version=latest)](https://power-grid-synthesizer.readthedocs.io/en/latest/)
![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

GridStudio generates realistic **synthetic power grids**: multi-voltage transmission networks and radial distribution feeders, complete with bus types, generation, load, dispatch and line parameters. Grids come back as NetworkX graphs that you can export to standard power-system formats or run through a power-flow solver.

It is meant for work that needs many plausible grids when real network data is scarce or confidential: benchmarking, simulation studies, and training data for machine-learning models of power grids.

- **Transmission grids** use the [Chung-Lu-Chain (CLC)](https://arxiv.org/abs/1711.11098) graph model, which reproduces a prescribed degree distribution and diameter per voltage level. Bus types, generation and load (active and reactive), dispatch, and line impedances and limits are then assigned from empirical statistics of real grids (NYISO, WECC).
- **Distribution feeders** use the algorithm of [Schweitzer et al. (2017)](https://doi.org/10.1109/JETCAS.2017.2682934), producing radial MV/LV trees with realistic cable types, cable lengths, loads and distributed generation.

> **Package name.** The Python package is called `powergrid_synth`, the project's earlier name. You install and import it under that name.

## Contents

- [Install](#install)
- [Transmission grids](#transmission-grids)
- [Distribution feeders](#distribution-feeders)
- [Export and power flow](#export-and-power-flow)
- [Progress output](#progress-output)
- [Examples](#examples)
- [Package layout](#package-layout)
- [Documentation](#documentation)
- [Development](#development)
- [References](#references)
- [License](#license)

## Install

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

## Transmission grids

### Quick start

`synthesize()` runs the whole pipeline in one call. There are two modes.

```python
from powergrid_synth import synthesize

# Mode I: clone the statistical profile of an existing grid
grid = synthesize(
    mode="reference",
    reference_case="case118",          # a pandapower or pypowsybl built-in, or pass reference_file=...
    seed=42,
    output_dir="output",
    output_name="ieee118_clone",
    export_formats=["json", "cgmes", "matpower"],
)

# Mode II: build a grid from your own specification (no reference needed)
grid = synthesize(
    mode="synthetic",
    level_specs=[                      # one entry per voltage level, highest voltage first
        {"n": 50,  "avg_k": 3.5, "diam": 10, "dist_type": "dgln"},
        {"n": 150, "avg_k": 2.5, "diam": 15, "dist_type": "dpl"},
        {"n": 300, "avg_k": 2.0, "diam": 20, "dist_type": "poisson"},
    ],
    connection_specs={                 # transformers between level pairs
        (0, 1): {"type": "k-stars", "c": 0.174, "gamma": 4.15},
        (1, 2): {"type": "k-stars", "c": 0.15,  "gamma": 4.15},
    },
    seed=42,
    export_formats=None,               # just return the graph, write nothing
)
```

Each call prints one line per stage:

```text
[1] Loaded reference grid: 118 nodes, 179 edges.
[2] Topology generated: 123 nodes, 171 edges.
[3] Bus types assigned: Gen: 28 (23%), Load: 68 (55%), Conn: 27 (22%)
[4] Generation capacities: total = 10889.0 MW
[5] Loads allocated: total P = 8062.9 MW, Q = 3685.6 Mvar (74% loading)
[6] Generation dispatched: 8101.4 MW (reserve 2787.7 MW)
[7] Transmission lines: 171 lines, avg capacity = 662.7 MVA
...
```

Things worth knowing:

- **The same `seed` gives the same grid.**
- **The number of buses is approximate.** The CLC model pads each level's degree sequence and only the largest connected component is kept, so the result can be smaller or larger than requested. Twelve seeds of the 500-bus specification above gave 420 to 473 buses; twelve clones of the 118-bus IEEE case gave 118 to 126. Check `grid.number_of_nodes()`.
- **Files are written by default.** If you leave `export_formats` out, a JSON file is written to `output/synthetic_grid.json`, replacing any file of that name. Set `output_name` per grid, or pass `export_formats=None`.
- In a level specification, `n` is the number of buses, `avg_k` the average degree, `diam` the target diameter and `dist_type` the degree distribution (`"dgln"` discrete generalised log-normal, `"dpl"` discrete power law, `"poisson"`).

See [`examples/transmission/Synthesize.ipynb`](examples/transmission/Synthesize.ipynb) for a full walkthrough.

### What you get back

A `PowerGridGraph`, which is a `networkx.Graph` with one extra method, `grid.level(i)`, returning the subgraph of one voltage level. Everything is stored in node and edge attributes:

| On | Attribute | Meaning |
|----|-----------|---------|
| node | `voltage_level` | Voltage level index, `0` being the highest voltage |
| node | `bus_type` | `'Gen'`, `'Load'` or `'Conn'` (connection bus, neither generation nor load) |
| node | `pg_max` | Generation capacity in MW (generator buses) |
| node | `pg` | Dispatched generation in MW (generator buses) |
| node | `pl`, `ql` | Active load in MW and reactive load in Mvar (load buses) |
| edge | `type` | `'line'` within a level, `'transformer'` between levels |
| edge | `r`, `x`, `z` | Resistance, reactance and impedance magnitude in per unit |
| edge | `capacity` | Thermal limit in MW |
| graph | `grid.graph["base_kv_map"]` | Level index to kV, taken from the reference grid (reference mode only) |

```python
import networkx as nx

generators = [n for n, d in grid.nodes(data=True) if d["bus_type"] == "Gen"]
total_load = sum(nx.get_node_attributes(grid, "pl").values())
backbone = grid.level(0)
```

### Step by step

Use the individual stages when you want to inspect or replace one of them. Each stage stores its result on the graph and also returns it as a dictionary, so the stages chain without any glue code.

```python
from powergrid_synth import (
    InputConfigurator, PowerGridGenerator, BusTypeAllocator,
    CapacityAllocator, LoadAllocator, GenerationDispatcher,
    TransmissionLineAllocator, GridVisualizer,
)

level_specs = [
    {"n": 50,  "avg_k": 3.5, "diam": 10, "dist_type": "dgln"},
    {"n": 150, "avg_k": 2.5, "diam": 15, "dist_type": "dpl"},
    {"n": 300, "avg_k": 2.0, "diam": 20, "dist_type": "poisson"},
]
connection_specs = {
    (0, 1): {"type": "k-stars", "c": 0.174, "gamma": 4.15},
    (1, 2): {"type": "k-stars", "c": 0.15,  "gamma": 4.15},
}

# 1. Turn the specification into degree sequences
params = InputConfigurator(seed=42).create_params(level_specs, connection_specs)

# 2. Generate the topology (keep_lcc=True drops disconnected fragments)
grid = PowerGridGenerator(seed=42).generate_grid(
    degrees_by_level=params["degrees_by_level"],
    diameters_by_level=params["diameters_by_level"],
    transformer_degrees=params["transformer_degrees"],
    keep_lcc=True,
)

# 3. Run the stages in this order; each one reads what the previous ones wrote
bus_types = BusTypeAllocator(grid).allocate()        # writes bus_type
capacities = CapacityAllocator(grid).allocate()      # writes pg_max
loads = LoadAllocator(grid)
loads.allocate(loading_level="H")                    # writes pl
loads.allocate_reactive()                            # writes ql
dispatch = GenerationDispatcher(grid).dispatch()     # writes pg
limits = TransmissionLineAllocator(grid).allocate()  # writes r, x, z, capacity

# 4. Plot
GridVisualizer().plot_grid(grid, layout="yifan_hu", title="Synthetic grid")
```

Running a stage before the one it depends on raises an error that names the missing step. Pass `update_graph=False` to a stage if you only want the returned dictionary.

| Stage | Class | Method |
|-------|-------|--------|
| 1. Topology | `PowerGridGenerator` | CLC graph model per voltage level; k-stars model for transformers between levels |
| 2. Bus types | `BusTypeAllocator` | Entropy-based Artificial Immune System search that reproduces the observed correlation between bus type and node degree |
| 3. Generation capacity | `CapacityAllocator` | Exponential sampling with heavy tail, assigned by a 2-D capacity-degree probability table |
| 4. Load | `LoadAllocator` | 2-D load-degree probability table; reactive load from sampled power factors |
| 5. Dispatch | `GenerationDispatcher` | Uncommitted, partially committed and fully committed units, then iterative balancing against load |
| 6. Lines | `TransmissionLineAllocator` | Log-normal impedances, Lévy-stable line angles, DC power-flow based swapping, limits from a 2-D table |

The statistical tables for the reference systems (NYISO-2935, WECC-16994) live in `powergrid_synth/core/reference_data.py`; choose between them with `ref_sys_id`.

## Distribution feeders

### Quick start

```python
from powergrid_synth import synthesize_distribution

# Mode I: fit the model to a reference network, then generate similar feeders
feeders = synthesize_distribution(
    mode="reference",
    reference_case="cigre_lv",
    n_feeders=5,
    n_nodes=20,
    total_load_mw=0.5,
    seed=42,
    output_dir="output",               # omit to write nothing
    export_formats=["json"],
)

# Mode II: use the published default parameters (no reference needed)
feeders = synthesize_distribution(
    mode="default",
    n_feeders=10,
    n_nodes=30,
    total_load_mw=0.8,
    total_gen_mw=0.1,
    seed=7,
)

feeder = feeders[0]
print(feeder.max_hop, feeder.total_load_mw, feeder.total_gen_mw, feeder.is_radial)
```

The result is a list of `DistributionGrid` objects, again `networkx.Graph` subclasses, with helpers such as `max_hop`, `total_load_mw`, `total_gen_mw`, `is_radial`, `nodes_at_hop(h)` and `nodes_by_type(...)`.

| On | Attribute | Meaning |
|----|-----------|---------|
| node | `h` | Hop distance from the source (node `0`) |
| node | `node_type` | `'load'`, `'injection'` (generation) or `'intermediate'` (no load) |
| node | `P_mw`, `Q_mvar` | Active and reactive power; positive is load, negative is generation |
| node | `pf` | Power factor |
| edge | `cable_type`, `max_i_ka` | Cable from the built-in library and its current rating |
| edge | `length_km`, `r_ohm`, `x_ohm` | Cable length and total resistance and reactance |

Each feeder's loads add up to exactly `total_load_mw` and its generation to `total_gen_mw`. Pass `match_totals=False` for the unscaled sampling used up to version 0.1.1, which overshoots the requested load on larger feeders.

### Step by step

```python
from powergrid_synth.distribution import (
    SchweitzerFeederGenerator, pandapower_to_feeders, fit_params_from_feeders,
)

# Option A: default parameters (Table III of Schweitzer et al.)
feeder = SchweitzerFeederGenerator(seed=42).generate_feeder(
    n_nodes=50, total_load_mw=8.0, total_gen_mw=1.0,
)

# Option B: fit the parameters to a real network first
import pandapower.networks as pn

reference = pandapower_to_feeders(pn.create_cigre_network_lv())
params = fit_params_from_feeders(reference)
feeder = SchweitzerFeederGenerator(params=params, seed=0).generate_feeder(
    n_nodes=44, total_load_mw=0.7,
)
```

| Step | What happens |
|------|--------------|
| 1. Nodes | Hop distances from a negative binomial distribution, power factors from an empirical CDF |
| 2. Tree | Target degrees from a mixture of Gammas, connected bottom-up into a radial tree |
| 3. Node roles | Intermediate, injection and load nodes chosen by hop distance; power shared out with sampled deviations |
| 4. Cable types | Picked from a cable library by estimated downstream current |
| 5. Cable lengths | Modified Cauchy distribution with a hop-dependent upper bound |

## Export and power flow

Grids convert to pandapower and pypowsybl networks, and from there to files:

```python
from powergrid_synth import GridExporter, nx_to_pandapower, load_grid
import pandapower as pp

exporter = GridExporter(grid)
exporter.to_json("grid.json")              # pandapower JSON
exporter.to_matpower("grid")               # writes grid.mat
exporter.to_cgmes("grid_cgmes")            # writes the EQ / SSH / SV / TP profiles
exporter.to_pypowsybl("grid.xiidm", format="XIIDM")

net = nx_to_pandapower(grid)               # run a power flow yourself
pp.rundcpp(net)

same_grid = load_grid("grid.xiidm")        # read any pypowsybl-supported file back in
```

| Via | Format | Call |
|-----|--------|------|
| pandapower | JSON | `GridExporter.to_json()` |
| | Excel (.xlsx) | `GridExporter.to_excel()` |
| | SQLite | `GridExporter.to_sqlite()` |
| | Pickle | `GridExporter.to_pickle()` |
| pypowsybl | CGMES | `GridExporter.to_cgmes()` |
| | MATPOWER | `GridExporter.to_matpower()` |
| | PSS/E | `GridExporter.to_psse()` |
| | XIIDM, BIIDM, JIIDM, AMPL | `GridExporter.to_pypowsybl(path, format=...)` |

In `synthesize(export_formats=[...])` the names are `"json"`, `"excel"`, `"sqlite"`, `"pickle"`, `"xiidm"`, `"cgmes"`, `"matpower"` and `"psse"`. UCTE export is not supported, because UCTE requires its own node naming scheme.

```text
Export:  NetworkX  <->  pandapower  ->  pypowsybl  ->  CGMES / XIIDM / MATPOWER / PSS/E / ...
Import:  CGMES / XIIDM / MATPOWER / PSS/E / ...  ->  pypowsybl  ->  NetworkX   (load_grid, pypowsybl_to_nx)
```

| Solver | Library | Type | Call |
|--------|---------|------|------|
| Newton-Raphson | pandapower | AC | `pp.runpp(net)` |
| Linear | pandapower | DC | `pp.rundcpp(net)` |
| Load flow | pypowsybl | AC | `pypowsybl.loadflow.run_ac(net)` |
| Load flow | pypowsybl | DC | `pypowsybl.loadflow.run_dc(net)` |
| Built-in | powergrid_synth | DC | `DCPowerFlow(grid).run()` |

**AC convergence is not guaranteed.** Generation and load are balanced for a DC power flow; voltages and reactive power are not tuned. On 20 seeded clones of the IEEE-118 case, pandapower's DC power flow solved all 20 and its AC Newton-Raphson converged on 12. If you need AC-feasible cases, run the AC power flow and keep the grids that converge. [`examples/transmission/ieee_test.ipynb`](examples/transmission/ieee_test.ipynb) shows export and power-flow validation in full.

## Progress output

`synthesize()` and `synthesize_distribution()` print one line per stage. Pass `verbose=False` to silence a call, or set the level for the whole package:

```python
import powergrid_synth as pgs

pgs.set_verbosity("silent")    # nothing
pgs.set_verbosity("warning")   # problems only
pgs.set_verbosity("info")      # one line per stage (default)
pgs.set_verbosity("debug")     # per-level and per-iteration detail from every stage
```

Messages go through the standard `logging` module under the logger name `powergrid_synth`.

## Examples

Start with the two notebooks in bold. The Colab versions install the package for you.

### Transmission

| Notebook | Topic | Colab |
|----------|-------|-------|
| [**Synthesize**](examples/transmission/Synthesize.ipynb) | The full pipeline in one call, both modes | |
| [SynthesizePypowsybl](examples/transmission/SynthesizePypowsybl.ipynb) | Reference grids from pypowsybl built-ins and CGMES files | |
| [TopologyGeneration](examples/transmission/TopologyGeneration.ipynb) | CLC topology generation and input configuration | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/TopologyGeneration_colab.ipynb) |
| [BusTypeAssignment](examples/transmission/BusTypeAssignment.ipynb) | Bus-type allocation | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/BusTypeAssignment_colab.ipynb) |
| [GenLoadSettings](examples/transmission/GenLoadSettings.ipynb) | Generation capacity and load allocation | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/GenLoadSettings_colab.ipynb) |
| [ieee_test](examples/transmission/ieee_test.ipynb) | Validation against IEEE test cases, export and power flow | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/ieee_test_colab.ipynb) |
| [pegase9241_test](examples/transmission/pegase9241_test.ipynb) | A large case: PEGASE 9241 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/pegase9241_test_colab.ipynb) |
| [rte7k_from_source_file](examples/transmission/rte7k_from_source_file.ipynb) | A large case read from a file: RTE 7000 (20 MB notebook, too large for GitHub's preview) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mshyang/GridStudio/blob/main/examples/colab/rte7k_from_source_file_colab.ipynb) |

### Distribution

| Notebook | Topic |
|----------|-------|
| [**DistributionSynth**](examples/distribution/DistributionSynth.ipynb) | Feeder synthesis with default and custom parameters |
| [DistributionSynthFromRef](examples/distribution/DistributionSynthFromRef.ipynb) | Fitting the parameters to a pandapower network |
| [DistributionSynthPypowsybl](examples/distribution/DistributionSynthPypowsybl.ipynb) | Loading CIGRE LV from CGMES, full pipeline and one-call version |
| [CLC4Distribution](examples/distribution/CLC4Distribution.ipynb) | Comparing CLC and Schweitzer topologies at distribution scale |

## Package layout

```text
powergrid_synth/
├── transmission/    CLC pipeline: generator, input_configurator, bus_type_allocator,
│                    capacity_allocator, load_allocator, generation_dispatcher,
│                    transmission (lines), synthesize (one-call function)
├── distribution/    Schweitzer pipeline: distribution_synthesis, distribution_params,
│                    distribution_analysis (fitting), distribution_converter,
│                    distribution_validation, synthesize (one-call function)
└── core/            Shared: grid_graph (graph classes), exporter, data_format_converter,
                     dcpf (built-in DC power flow), analysis, comparison,
                     hierarchical_analysis, visualization, reference_data
```

Everything in the examples above can be imported from `powergrid_synth` directly; the distribution building blocks are in `powergrid_synth.distribution`.

## Documentation

Theory, tutorials and the API reference are at [power-grid-synthesizer.readthedocs.io](https://power-grid-synthesizer.readthedocs.io/en/latest/).

## Development

```bash
git clone https://github.com/mshyang/GridStudio.git
cd GridStudio
pip install -e ".[dev,export]"
pytest
```

Changes between versions are listed in [CHANGELOG.md](CHANGELOG.md).

## References

1. S. G. Aksoy, E. Purvine, E. Cotilla-Sanchez, M. Halappanavar (2019). "A Generative Graph Model for Electrical Infrastructure Networks." *Journal of Complex Networks*, 7(1), 128–162. [arXiv:1711.11098](https://arxiv.org/abs/1711.11098), [doi:10.1093/comnet/cny016](https://doi.org/10.1093/comnet/cny016)
2. S. H. Elyas, Z. Wang (2017). "Improved Synthetic Power Grid Modeling With Correlated Bus Type Assignments." *IEEE Transactions on Power Systems*, 32(5), 3391–3402. [doi:10.1109/TPWRS.2016.2634318](https://doi.org/10.1109/TPWRS.2016.2634318)
3. S. H. Elyas, Z. Wang, R. J. Thomas (2017). "On the Statistical Settings of Generation and Load in a Synthetic Grid Modeling." [arXiv:1706.09294](https://arxiv.org/abs/1706.09294)
4. S. Sadeghian, S. H. Elyas, Z. Wang (2018). "A Novel Algorithm for Statistical Assignment of Transmission Capacities in Synthetic Grid Modeling." *IEEE Power & Energy Society General Meeting*. [doi:10.1109/PESGM.2018.8585532](https://doi.org/10.1109/PESGM.2018.8585532)
5. E. Schweitzer, A. Scaglione, A. Monti, G. A. Pagani (2017). "Automated Generation Algorithm for Synthetic Medium Voltage Radial Distribution Systems." *IEEE Journal on Emerging and Selected Topics in Circuits and Systems*, 7(2), 271–284. [doi:10.1109/JETCAS.2017.2682934](https://doi.org/10.1109/JETCAS.2017.2682934)

## License

GridStudio is released under the [Apache License 2.0](LICENSE).
