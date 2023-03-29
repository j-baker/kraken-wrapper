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
    	  builddsl = super.builddsl.overridePythonAttrs
    	    ( old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools super.poetry ];
                  });
          types-dataclasses = super.types-dataclasses.overridePythonAttrs
    	    ( old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools super.poetry ];
                  });

          });
      in
      rec {
        packages = flake-utils.lib.flattenTree {
          krakenw = (mkPoetryApplication {
            projectDir = ./.;
          });
        };

        devShells.default = pkgs.mkShell {
          name = "Helsing tooling";

          buildInputs = [
	        packages.krakenw
          ];
        };
      }
    );
}