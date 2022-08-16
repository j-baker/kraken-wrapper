# kraken-wrapper

Provides the `krakenw` command which is a wrapper around Kraken to construct an isolated and reproducible build
environment.

### Features

* Produces isolated environments in PEX format
* Reads build requirements from the `.kraken.py` file header
* Produces lock files (`.kraken.lock`) that can be used to reconstruct an exact build environment <sup>1)</sup>
* Store Python package index credentials in a keychain

<sup>1) The lock files do not contain hashes for installed distributions, but only the exact version numbers from
the resolved build environment.</sup>

## Documentation

__Table of Contents__

* [Requirements header](#requirements-header)
* [Environment variables](#environment-variables)
* [Recommendations](#recommendations)
* [Index credentials](#index-credentials)

### Requirements header

If no `.kraken.lock` file is present, Kraken wrapper will read the header of the `.kraken.py` file to obtain the
requirements to install into the build environment. The format of this header is demonstrated below:

```py
# ::requirements kraken-std>=0.3.0,<0.4.0 --extra-index-url https://...
# ::pythonpath build-support
```

The available options are:

| Option | Description |
| ------ | ----------- |
| `#::requirements` | The content on this line will be parsed similar to the arguments for `pip install`. Every positional argument is a Python requirement specifier. The following options are supported: `--index-url`, `--extra-index-url` and `--interpreter-constraint`. |
| `#::pythonpath` | One or more paths to prepend to `sys.path` when the build environment is created/executed. This is already supported by `kraken-core` but will be used to generate a `.pth` file when using the `VENV` environment type. The `./build-support/` will always be added to `sys.path`. |

### Environment variables

The following environment variables are handled by kraken-wrapper:

| Variable | Description |
| -------- | ----------- |
| `KRAKENW_USE` | If set, it will behave as if the `--use` flag was specified (although the `--use` flag if given will still take precedence over the environment variable). Can be used to enforce a certain type of build environment to use. Available values are `PEX_ZIPAPP`, `PEX_PACKED`, `PEX_LOOSE` and `VENV` (default). |
| `KRAKENW_REINSTALL` | If set to `1`, behaves as if `--reinstall` was specified. |
| `KRAKENW_INCREMENTAL` |  If set to `1`, virtual environment build environments are "incremental", i.e. they will be reused if they already exist and their installed distributions will be upgraded. |

### Recommendations

* When using local requirements, using the `VENV` type is a lot fast because it can leverage Pip's `in-tree-build`
feature. Pex [does not currently support in-tree builds](https://github.com/pantsbuild/pex/issues/1357#issuecomment-860133766).

### Index credentials

  [keyring]: https://github.com/jaraco/keyring

Pip doesn't really have a good way to globally configure credentials for Python package indexes when they are not
configured as an alias in `.piprc` aside from `~/.netrc`. Both of these methods have the drawback that the password
is stored in plain text on disk. Pip does technically support looking up a password from the system keychain using
the [`keyring`][keyring] package, but it doesn't store the username and so will have to ask for it via stdin.

To work around this limitation, kraken-wrapper offers the `auth` command which allows you to configure credentials
where the username is stored in `~/.config/krakenw/config.toml` and the password is stored in the system keychain
(also using the [`keyring`][keyring] package).

    $ krakenw auth example.jfrog.io -u my@email.org 
    Password for my@email.org:

> __Important note__: If no backend for the `keyring` package is available, kraken-wrapper will fall back to writing
> the password as plain text into the same configuration file.
