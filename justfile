# Justfile for Madrid Open Data project
# Run with: just <command>

# Show RAMPA banner
banner:
    #!/usr/bin/env bash
    uv run -c "import pyfiglet; print(pyfiglet.figlet_format('RAMPA', font='slant'))"

# Default command
default:
    @just banner
    @just --list

# Start the API server
api: banner
    #!/usr/bin/env bash
    echo "Starting Madrid Open Data API server..."
    uv run uvicorn rest_api:app --host 0.0.0.0 --port 8000 --reload

# Start the API server in development mode with auto-reload
api-dev: banner
    #!/usr/bin/env bash
    echo "Starting Madrid Open Data API server in development mode..."
    uv run uvicorn rest_api:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# Run the main setup process
setup: banner
    #!/usr/bin/env bash
    echo "Running Madrid Open Data setup..."
    uv run setup.py

# Run network setup specifically
setup-network: banner
    #!/usr/bin/env bash
    echo "Setting up network data..."
    uv run setup_network.py

# Install dependencies using uv
install: banner
    #!/usr/bin/env bash
    echo "Installing dependencies..."
    uv sync

# Install dependencies in development mode
install-dev: banner
    #!/usr/bin/env bash
    echo "Installing dependencies in development mode..."
    uv sync --dev

# Run data transformations
transform: banner
    #!/usr/bin/env bash
    echo "Running data transformations..."
    uv run -m rampa.duckdb.src.run_transformations

# Clean up databases
cleanup: banner
    #!/usr/bin/env bash
    echo "Cleaning up databases..."
    uv run cleanup_databases.py

# Run tests
test: banner
    #!/usr/bin/env bash
    echo "Running tests..."
    uv run pytest

# Format code with ruff
format: banner
    #!/usr/bin/env bash
    echo "Formatting code..."
    uv run ruff format .

# Lint code with ruff
lint: banner
    #!/usr/bin/env bash
    echo "Linting code..."
    uv run ruff check .

# Fix linting issues automatically
lint-fix: banner
    #!/usr/bin/env bash
    echo "Fixing linting issues..."
    uv run ruff check --fix .

# Show project status
status: banner
    #!/usr/bin/env bash
    echo "Project Status:"
    echo "Python version: $(uv run --version)"
    echo "UV version: $(uv --version)"
    echo "Current directory: $(pwd)"
    echo "Available commands:"
    @just --list

# Help command
help: banner
    @echo "Madrid Open Data Project Commands:"
    @echo ""
    @echo "  api          - Start the API server"
    @echo "  api-dev      - Start the API server in development mode"
    @echo "  setup        - Run the main setup process"
    @echo "  setup-network- Run network setup specifically"
    @echo "  install      - Install dependencies"
    @echo "  install-dev  - Install dependencies in development mode"
    @echo "  transform    - Run data transformations"
    @echo "  cleanup      - Clean up databases"
    @echo "  test         - Run tests"
    @echo "  format       - Format code with ruff"
    @echo "  lint         - Lint code with ruff"
    @echo "  lint-fix     - Fix linting issues automatically"
    @echo "  status       - Show project status"
    @echo "  help         - Show this help message"
