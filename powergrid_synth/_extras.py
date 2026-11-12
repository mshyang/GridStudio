"""Install hints for the optional export / power-flow dependencies."""

#: Where the package is installed from.  It is not on PyPI yet, so the hint
#: has to name the repository; change this one line after a PyPI release.
INSTALL_SOURCE = "git+https://github.com/mshyang/GridStudio"

#: Shell command that installs the optional dependencies (pandapower,
#: pypowsybl, numba, lightsim2grid).
EXPORT_INSTALL_HINT = f'pip install "powergrid_synth[export] @ {INSTALL_SOURCE}"'
