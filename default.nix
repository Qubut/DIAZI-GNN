{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python311              # or python312, depending on preference
    poetry
    jupyter
    texliveFull
    pandoc
    python311Packages.ipykernel
    graphviz
    black
  ];

  shellHook = ''
    poetry install
    echo "Run 'jupyter lab' to start the Jupyter interface."
  '';
}
