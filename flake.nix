{
  description = "Flake to create kraken wrapper env.";

  inputs = {
    python-builddsl = {
      url = "github:szgula/python-builddsl";
      flake = false;
    };
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

  };

  outputs = { self, python-builddsl, nixpkgs, poetry2nix, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication defaultPoetryOverrides;
        my_overrides = (self: super: {
          # needed for builddsl
          types-dataclasses = super.types-dataclasses.overridePythonAttrs
            (old: {
              buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ];
            });
          cryptography = pkgs.python310Packages.cryptography.overrideAttrs (old: {
            version = "39.0.2";
          });
        });
				environment = with pkgs; [
            python310
            python310.pkgs.flake8
            python310Packages.pip
            poetry
            protobuf
            black
            mypy
            isort
            cargo
            rustfmt
				];
      in
      rec {
        packages = flake-utils.lib.flattenTree rec {
          krakenw = (mkPoetryApplication {
            projectDir = ./.;
            overrides = defaultPoetryOverrides.extend my_overrides;
          });
          default = krakenw;
        };

        devShells.default = pkgs.mkShell {
          name = "Helsing tooling";

          buildInputs = environment ++ [
            packages.krakenw
          ];
        };
      }
    );
}
