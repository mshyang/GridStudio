"""
Tests for the behaviour a new user relies on: the pipeline stages chain
without glue code, mistakes produce clear errors, requested totals are met,
and progress output can be switched off.
"""
import warnings

import networkx as nx
import numpy as np
import pytest

import powergrid_synth as pgs
from powergrid_synth import (
    BusTypeAllocator,
    CapacityAllocator,
    DistributionGrid,
    GenerationDispatcher,
    InputConfigurator,
    LoadAllocator,
    PowerGridGenerator,
    TransmissionLineAllocator,
    synthesize,
    synthesize_distribution,
)
from powergrid_synth.distribution import (
    SchweetzerFeederGenerator,
    SchweitzerFeederGenerator,
)

LEVEL_SPECS = [
    {"n": 30, "avg_k": 2.5, "diam": 6, "dist_type": "poisson"},
    {"n": 40, "avg_k": 2.0, "diam": 10, "dist_type": "poisson"},
]
CONNECTION_SPECS = {(0, 1): {"type": "k-stars", "c": 0.174, "gamma": 4.15}}


@pytest.fixture(autouse=True)
def restore_verbosity():
    yield
    pgs.set_verbosity("info")


@pytest.fixture
def topology():
    params = InputConfigurator(seed=3).create_params(LEVEL_SPECS, CONNECTION_SPECS)
    return PowerGridGenerator(seed=3).generate_grid(
        degrees_by_level=params["degrees_by_level"],
        diameters_by_level=params["diameters_by_level"],
        transformer_degrees=params["transformer_degrees"],
        keep_lcc=True,
    )


# ---------------------------------------------------------------------------
# Step-by-step pipeline (the README example)
# ---------------------------------------------------------------------------

class TestStagesChain:
    def test_stages_store_results_on_the_graph(self, topology):
        """Calling the stages in order, with no glue code, yields a full grid."""
        grid = topology
        bus_types = BusTypeAllocator(grid).allocate(max_iter=10)
        capacities = CapacityAllocator(grid).allocate()
        loads = LoadAllocator(grid)
        active = loads.allocate()
        reactive = loads.allocate_reactive()
        dispatch = GenerationDispatcher(grid).dispatch()
        limits = TransmissionLineAllocator(grid).allocate()

        assert nx.get_node_attributes(grid, "bus_type") == bus_types
        assert set(bus_types) == set(grid.nodes)
        assert nx.get_node_attributes(grid, "pg_max") == capacities
        assert nx.get_node_attributes(grid, "pl") == active
        assert nx.get_node_attributes(grid, "ql") == reactive
        assert nx.get_node_attributes(grid, "pg") == dispatch

        generators = {n for n, t in bus_types.items() if t == "Gen"}
        load_buses = {n for n, t in bus_types.items() if t == "Load"}
        assert generators and set(capacities) == generators
        assert load_buses and set(active) == load_buses == set(reactive)
        assert sum(capacities.values()) > 0
        assert sum(active.values()) > 0
        assert sum(dispatch.values()) > 0
        assert len(limits) == grid.number_of_edges()
        assert all("capacity" in d for _, _, d in grid.edges(data=True))

    def test_update_graph_false_leaves_graph_untouched(self, topology):
        grid = topology
        bus_types = BusTypeAllocator(grid).allocate(max_iter=5, update_graph=False)
        assert bus_types
        assert nx.get_node_attributes(grid, "bus_type") == {}

    def test_allocators_created_up_front_see_later_bus_types(self, topology):
        """Stage objects may be created before the earlier stages have run."""
        grid = topology
        capacity_stage = CapacityAllocator(grid)
        load_stage = LoadAllocator(grid)
        BusTypeAllocator(grid).allocate(max_iter=5)
        assert capacity_stage.allocate()
        assert load_stage.allocate()

    def test_rerun_does_not_leave_stale_values(self, topology):
        grid = topology
        BusTypeAllocator(grid).allocate(max_iter=5)
        CapacityAllocator(grid).allocate()
        # Turn every generator into a load and allocate again.
        for n, d in grid.nodes(data=True):
            if d["bus_type"] == "Gen":
                d["bus_type"] = "Load"
        assert CapacityAllocator(grid).allocate() == {}
        assert nx.get_node_attributes(grid, "pg_max") == {}

    def test_allocate_reactive_accepts_explicit_loads(self, topology):
        grid = topology
        BusTypeAllocator(grid).allocate(max_iter=5)
        stage = LoadAllocator(grid)
        reactive = stage.allocate_reactive({0: 10.0, 1: 20.0}, update_graph=False)
        assert set(reactive) == {0, 1}
        assert all(q > 0 for q in reactive.values())


class TestOutOfOrderErrors:
    @pytest.mark.parametrize(
        "run, missing_step",
        [
            (lambda g: CapacityAllocator(g).allocate(), "BusTypeAllocator"),
            (lambda g: LoadAllocator(g).allocate(), "BusTypeAllocator"),
            (lambda g: GenerationDispatcher(g).dispatch(), "BusTypeAllocator"),
            (lambda g: LoadAllocator(g).allocate_reactive(), "LoadAllocator"),
            (lambda g: TransmissionLineAllocator(g).allocate(), "GenerationDispatcher"),
        ],
    )
    def test_stage_before_prerequisite_names_the_missing_step(self, run, missing_step):
        with pytest.raises(ValueError, match=missing_step):
            run(nx.path_graph(6))

    def test_dispatch_without_capacities(self):
        grid = nx.path_graph(4)
        nx.set_node_attributes(grid, {0: "Gen", 1: "Load", 2: "Load", 3: "Conn"}, "bus_type")
        with pytest.raises(ValueError, match="CapacityAllocator"):
            GenerationDispatcher(grid).dispatch()


# ---------------------------------------------------------------------------
# synthesize()
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_no_export_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        grid = synthesize(
            mode="synthetic",
            level_specs=LEVEL_SPECS,
            connection_specs=CONNECTION_SPECS,
            seed=1,
            export_formats=None,
        )
        assert grid.number_of_nodes() > 0
        assert list(tmp_path.iterdir()) == []

    def test_unknown_export_format_fails_before_running(self):
        with pytest.raises(ValueError, match="Unknown export format"):
            synthesize(
                mode="synthetic",
                level_specs=LEVEL_SPECS,
                connection_specs=CONNECTION_SPECS,
                export_formats=["json", "jsn"],
            )

    def test_same_seed_same_grid(self):
        def run():
            g = synthesize(
                mode="synthetic",
                level_specs=LEVEL_SPECS,
                connection_specs=CONNECTION_SPECS,
                seed=11,
                export_formats=None,
                verbose=False,
            )
            return sorted(g.edges()), nx.get_node_attributes(g, "pl")

        assert run() == run()

    def test_reference_voltages_are_kept_on_the_graph(self):
        pytest.importorskip("pandapower")
        grid = synthesize(
            mode="reference",
            reference_case="case14",
            seed=2,
            export_formats=None,
            verbose=False,
        )
        kv = grid.graph["base_kv_map"]
        assert set(kv) == {d["voltage_level"] for _, d in grid.nodes(data=True)}

        from powergrid_synth import nx_to_pandapower
        net = nx_to_pandapower(grid)
        assert set(np.round(net.bus.vn_kv.unique(), 6)) <= set(np.round(list(kv.values()), 6))


# ---------------------------------------------------------------------------
# Progress output
# ---------------------------------------------------------------------------

class TestVerbosity:
    def _run(self, **kwargs):
        return synthesize(
            mode="synthetic",
            level_specs=LEVEL_SPECS,
            connection_specs=CONNECTION_SPECS,
            seed=1,
            export_formats=None,
            **kwargs,
        )

    def test_default_prints_one_line_per_stage(self, capsys):
        self._run()
        out = capsys.readouterr().out
        for tag in ("[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]"):
            assert tag in out
        # Per-iteration detail belongs to the debug level.
        assert "Iter 0" not in out

    def test_verbose_false_is_silent(self, capsys):
        self._run(verbose=False)
        assert capsys.readouterr().out == ""

    def test_set_verbosity_silent_and_debug(self, capsys):
        pgs.set_verbosity("silent")
        self._run()
        assert capsys.readouterr().out == ""

        pgs.set_verbosity("debug")
        self._run()
        assert "Starting Bus Type Allocation" in capsys.readouterr().out

    def test_verbose_false_restores_previous_level(self, capsys):
        self._run(verbose=False)
        capsys.readouterr()
        self._run()
        assert "[1]" in capsys.readouterr().out

    def test_unknown_level_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown verbosity"):
            pgs.set_verbosity("loud")


# ---------------------------------------------------------------------------
# Distribution feeders
# ---------------------------------------------------------------------------

class TestFeederTotals:
    @pytest.mark.parametrize("n_nodes", [20, 60, 200])
    def test_totals_match_the_request(self, n_nodes):
        feeder = SchweitzerFeederGenerator(seed=5).generate_feeder(
            n_nodes=n_nodes, total_load_mw=8.0, total_gen_mw=1.0
        )
        assert isinstance(feeder, DistributionGrid)
        assert feeder.total_load_mw == pytest.approx(8.0)
        assert feeder.total_gen_mw == pytest.approx(1.0)

    def test_match_totals_false_keeps_the_sampled_shares(self):
        kwargs = dict(n_nodes=80, total_load_mw=8.0, total_gen_mw=1.0)
        scaled = SchweitzerFeederGenerator(seed=5).generate_feeder(**kwargs)
        raw = SchweitzerFeederGenerator(seed=5).generate_feeder(match_totals=False, **kwargs)

        assert sorted(scaled.edges()) == sorted(raw.edges())
        loads = [n for n, d in raw.nodes(data=True) if d["P_mw"] > 0]
        ratios = [scaled.nodes[n]["P_mw"] / raw.nodes[n]["P_mw"] for n in loads]
        # Same shares, one common scale factor.
        assert np.allclose(ratios, ratios[0])
        assert raw.total_load_mw != pytest.approx(8.0)

    def test_synthesize_distribution_returns_distribution_grids(self):
        feeders = synthesize_distribution(
            mode="default", n_feeders=3, n_nodes=25, total_load_mw=0.6, seed=4, verbose=False
        )
        assert len(feeders) == 3
        for feeder in feeders:
            assert isinstance(feeder, DistributionGrid)
            assert feeder.is_radial
            assert feeder.total_load_mw == pytest.approx(0.6)

    def test_unknown_distribution_export_format(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown export format"):
            synthesize_distribution(
                mode="default", output_dir=str(tmp_path), export_formats=["cgmes"], verbose=False
            )


class TestDeprecatedName:
    def test_old_spelling_still_works_and_warns(self):
        with pytest.warns(DeprecationWarning, match="SchweitzerFeederGenerator"):
            generator = SchweetzerFeederGenerator(seed=1)
        assert isinstance(generator, SchweitzerFeederGenerator)

    def test_new_spelling_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SchweitzerFeederGenerator(seed=1)
