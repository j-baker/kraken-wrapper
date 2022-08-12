# kraken-wrapper

Provides the `krakenw` command which is a wrapper around Kraken to construct an isolated and reproducible build
environment.

__Features__

* Produces isolated environments in PEX format
* Reads build requirements from the `.kraken.py` file header
* Produces lock files (`.kraken.lock`) that can be used to reconstruct an exact build environment <sup>1)</sup>

<sup>1) The lock files do not contain hashes for installed distributions, but only the exact version numbers from
the resolved build environment.</sup>

__Requirements header__

If no `.kraken.lock` file is present, Kraken wrapper will read the header of the `.kraken.py` file to obtain the
requirements to install into the build environment. The format of this header is demonstrated below:

```py
# ::requirements kraken-std>=0.3.0,<0.4.0 --extra-index-url https://...
# ::pythonpath build-support
```

The available options are:

* **`requirements`**: Here you can specify any number of Pip requirements or local requirements (of the
    format `dist-name @ path/to/dist`) as well as `--index-url`, `--extra-index-url` and `--interpreter-constraint`.
* **`pythonpath`**: One or more paths to add the `sys.path` before your build script is executed. The `build-script` folder
    is always added by default (as is the default behaviour by the `kraken-core` Python script project loader).

__Environment variables__

* `KRAKENW_USE`: If set, it will behave as if the `--use` flag was specified (although the `--use` flag if given
    will still take precedence over the environment variable). Can be used to enforce a certain type of build
    environment to use (available values are `PEX_ZIPAPP` (default), `PEX_PACKED`, `PEX_LOOSE` and `VENV`).
* `KRAKENW_REINSTALL`: If set to `1`, behaves as if `--reinstall` was specified.
* `KRAKENW_INCREMENTAL`: If set to `1`, virtual environment build environments are "incremental", i.e. they will
    be reused if they already exist and their installed distributions will be upgraded.

__Recommendations__

When using local requirements, using the `VENV` type is a lot fast because it can leverage Pip's `in-tree-build`
feature. Pex [does not currently support in-tree builds](https://github.com/pantsbuild/pex/issues/1357#issuecomment-860133766).
