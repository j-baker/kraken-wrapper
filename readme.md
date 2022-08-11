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

