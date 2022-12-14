# kraken-wrapper

Provides the `krakenw` command which is a wrapper around Kraken build scripts to construct an isolated and
reproducible build environment as per the dependencies specified in the script.

Build scripts _must_ invoke the `kraken.common.buildscript` function at the top to be compatible with Kraken
wrapper.

<table align="center"><tr><th>Python</th><th>BuildDSL</th></tr>
<tr><td>

```py
from kraken.common import buildscript

buildscript(
    requirements=["kraken-std ^0.4.16"],
)
```

</td><td>

```py
buildscript {
    requires "kraken-std ^0.4.16"
}


```

</td></tr></table>

For backwards compatibility, Kraken wrapper currently still supports reading the build script's dependencies from
the comment block at the top of the file. Build scripts that still use this method will trigger a warning log with
a recommendation of `buildscript()` code to place at the top of the file instead.

## Recommendations

* When using *local requirements*, using the `VENV` type is a lot faster because it can leverage Pip's `in-tree-build`
feature. Pex [does not currently support in-tree builds](https://github.com/pantsbuild/pex/issues/1357#issuecomment-860133766).
  * [`kraken-std`][kraken-std] has a local requirement on itself so that it can use itself to build itself 🤯

[kraken-std]: https://github.com/kraken-build/kraken-std

## Credential management

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
> the password as plain text into the same configuration file. A corresponding warning will be printed.

## Environment variables

The following environment variables are handled by kraken-wrapper:

| Variable | Description |
| -------- | ----------- |
| `KRAKENW_USE` | If set, it will behave as if the `--use` flag was specified (although the `--use` flag if given will still take precedence over the environment variable). Can be used to enforce a certain type of build environment to use. Available values are `PEX_ZIPAPP`, `PEX_PACKED`, `PEX_LOOSE` and `VENV` (default). |
| `KRAKENW_REINSTALL` | If set to `1`, behaves as if `--reinstall` was specified. |
| `KRAKENW_INCREMENTAL` |  If set to `1`, virtual environment build environments are "incremental", i.e. they will be reused if they already exist and their installed distributions will be upgraded. |
