# Changelog

## 0.2.0 (unreleased)

The project is now called **GridStudio**. The Python package and import name stay `powergrid_synth`, so existing code keeps working.

### Changed behaviour

- **Pipeline stages store their results on the graph.** `BusTypeAllocator.allocate()`, `CapacityAllocator.allocate()`, `LoadAllocator.allocate()`, `LoadAllocator.allocate_reactive()` and `GenerationDispatcher.dispatch()` now write `bus_type`, `pg_max`, `pl`, `ql` and `pg` to the graph in addition to returning them. Before, the caller had to copy each result onto the graph with `networkx.set_node_attributes`; skipping that step silently produced a grid with no generators and no loads. Code that still copies the results by hand keeps working. Pass `update_graph=False` for the old return-only behaviour.
- **Running a stage too early is an error.** A stage that needs `bus_type`, `pg_max`, `pl` or `pg` and finds none on the graph raises a `ValueError` naming the stage to run first, instead of returning an empty result.
- **Distribution feeders meet the requested totals.** Loads now add up to exactly `total_load_mw` and generation to `total_gen_mw`. Before, redrawing negative shares pushed the total above the request, more so on larger feeders (median 1.7 times the requested load at 200 nodes with the default parameters). This changes the power values for a given seed; the topology is unchanged. Pass `match_totals=False` to get the earlier values.
- **Progress output is controlled in one place.** Messages go through the `powergrid_synth` logger instead of `print`. `synthesize()` and `synthesize_distribution()` print one line per stage and accept `verbose=False`. `powergrid_synth.set_verbosity("silent" | "warning" | "info" | "debug")` sets the level for the package; the per-level and per-iteration detail that used to be printed always is now at the `"debug"` level.
- **Unknown export formats are rejected up front.** `synthesize()` and `synthesize_distribution()` raise a `ValueError` before generating anything, instead of printing a note and skipping the format after the pipeline has run. A missing pandapower installation is reported at the same point.
- `SchweetzerFeederGenerator` is renamed `SchweitzerFeederGenerator`. The old name still works and emits a `DeprecationWarning`.
- `generate_feeder()` and `synthesize_distribution()` return `DistributionGrid` objects (a `networkx.Graph` subclass) instead of plain graphs.

### Added

- `synthesize(export_formats=None)` returns the graph without writing files.
- `LoadAllocator.allocate_reactive()` can be called without arguments and then uses the loads stored on the graph.
- In reference mode, `synthesize()` stores the reference grid's voltage levels in `grid.graph["base_kv_map"]`, and `nx_to_pandapower()` / `GridExporter` use it when no mapping is passed, so a later export matches the one made by `synthesize()`.

### Fixed

- Excel export failed with the documented `[export]` extra because `xlsxwriter` was missing from it.
- Error messages for missing optional dependencies suggested `pip install powergrid_synth[export]`, which cannot work while the package is not on PyPI. They now give the install-from-GitHub command.
- A leftover debug statement printed the bare `gamma` value for every transformer connection.
- Built packages had an empty long description on case-sensitive file systems, because `pyproject.toml` pointed at `README.md` while the file was named `readme.md`.

### Documentation

- The README is rewritten: working install command, a description of the attributes on the returned graphs, and a step-by-step example that produces a complete grid.
- UCTE is no longer listed as an export format; pypowsybl's UCTE writer requires UCTE node codes and fails on synthetic grids.
- The README states that AC power flow is not guaranteed to converge on generated grids.
- Two references had DOIs that do not resolve, and the Schweitzer et al. reference had the wrong title, journal and pages; all are corrected.
- The docs no longer tell users to `pip install powergridsynth`, a package that does not exist.

### Licence

- GridStudio is released under the Apache License 2.0, and the repository now contains the `LICENSE` file. The README previously said MIT, with no licence file to back it.

### Repository

- Built documentation (`docs/_build/`) and generated output (`output/`) are no longer tracked.
- The version is defined once, in `powergrid_synth/__init__.py`.

## 0.1.1

Initial release.
