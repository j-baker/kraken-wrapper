{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {

  buildInputs = [
    pkgs.python310
    pkgs.python310.pkgs.flake8
    pkgs.poetry
    pkgs.protobuf
    #pkgs.black
    #pkgs.mypy
    #pkgs.isort
    pkgs.cargo
    pkgs.rustfmt
  ];

}