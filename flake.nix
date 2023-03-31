{
  description = "A very basic flake";

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

  outputs = { self, python-builddsl, nixpkgs, poetry2nix, flake-utils}:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication defaultPoetryOverrides;
        my_overrides = ( self: super: {
    	# needed for builddsl
          types-dataclasses = super.types-dataclasses.overridePythonAttrs
    	    ( old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ];
                  });

          });
      in
      rec {
        packages = flake-utils.lib.flattenTree {
          krakenw = (mkPoetryApplication {
            projectDir = ./.;
            overrides = defaultPoetryOverrides.extend my_overrides;
          });
        };

        devShells.default = pkgs.mkShell {
          name = "Helsing tooling";

          buildInputs = [
	        pkgs.python310
            pkgs.python310.pkgs.flake8
            pkgs.python310Packages.pip
            #pkgs.python310Packages.cryptography
            pkgs.poetry
            pkgs.protobuf
            pkgs.black
            pkgs.mypy
            pkgs.isort
            pkgs.cargo
            pkgs.rustfmt
            packages.krakenw
          ];
        };
      }
    );
}