# JSON-to-Neo4j Graph Processing with Leiden Community Detection

This is a streamlined, containerized pipeline that ingests JSON data, constructs a Neo4j graph, and applies the **Leiden** algorithm for community detection. By leveraging **Nix** for development environments, **direnv** for environment variable management, and **Podman** for container orchestration.

![1737878031863](image/README/1737878031863.png)

## Key Features

- **Automated Graph Creation**: Dynamically constructs nodes and relationships from JSON data.
- **Leiden Algorithm**: Integrates with Neo4j’s Graph Data Science (GDS) library to run community detection on the ingested graph.
- **Asynchronous I/O**: Utilizes `aiofiles` for non-blocking file operations, speeding up ingestion of large data sets.
- **Functional Style**: Employs the `returns` library to build maintainable and composable data-processing pipelines.
- **Reproducible Environments**: Uses **Nix** + **direnv** to ensure consistent development environments across systems.
- **Containerized Deployment**: Provides a `podman-compose.yml` to launch Neo4j (with GDS plugin) in a predictable, isolated manner.

## Prerequisites

1. **Nix**
2. **direnv**
3. **Podman** + **Podman Compose** (or Docker, if you adapt the `podman-compose.yml`)
4. **Poetry** (for Python package management)
5. **Python 3.11+**

## Quick Setup

1. **Clone the Repo**
2. **Install Nix globally**:

   ```sh
   sh <(curl -L https://nixos.org/nix/install) --daemon
   ```

   or locally

   ```sh
   sh <(curl -L https://nixos.org/nix/install) --no-daemon
   ```
3. **Install direnv** [https://direnv.net/docs/installation.html](https://direnv.net/docs/installation.html)
4. **Enable Nix Shell (via direnv)**

   - Ensure direnv is installed and enabled in your shell.
   - Run `direnv allow` inside the project directory to activate the Nix environment.
5. **Start Neo4j**

   ```bash
   podman-compose up -d
   ```

   This launches a Neo4j instance (with GDS plugin enabled) on the specified ports.

## Usage

1. **Jupyter Lab**

   - For interactive development, run:
     ```bash
     jupyter lab
     ```
   - Open `dev.ipynb` to experiment with code snippets and see log outputs for debugging.
2. **Monitor Neo4j**

   - Visit the Neo4j Browser at [http://localhost:7474](http://localhost:7474) (or the port specified in `.env`).
   - Use your configured credentials to log in and run Cypher queries to explore the data.

## Key Commands

- **Stop the Neo4j Container**:
  ```bash
  podman-compose down
  ```
- **Update Dependencies**:
  ```bash
  poetry update
  ```
- **Format Code**:
  ```bash
  black **/*.py
  ```

## FAQ

1. **Why Nix + direnv?**
   They guarantee a consistent development environment. Everyone on the project has the same packages, making setup less error-prone.
2. **Why Podman instead of Docker?**
   Podman is a rootless container engine aimed at better security practices. You can adapt `podman-compose.yml` to Docker if desired.
3. **What if I want to run a different GDS algorithm?**
   The code uses the GDS plugin in Neo4j. You can modify the relevant methods in `json_graph_loader.py` to call other GDS procedures (e.g., PageRank, Louvain).
4. **How do I handle large-scale JSON data?**
   The asynchronous design helps, but you might also consider splitting JSON files or increasing hardware resources depending on the dataset’s size.

## License

This project is released under the [MIT License](LICENSE). Feel free to use, modify, and distribute it as you see fit, while attributing original authors.

## Contact

- **Author**: Qubut (s-aahmed@haw-landshut.de)
- **Issues / PRs**: [GitHub Issues](https://github.com/your-org/gnn/issues)
