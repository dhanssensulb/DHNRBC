"""Run the full Demand data pipeline."""

try:
    from Demand.Layers.bisa import main as run_bisa
    from Demand.Layers.brugis import main as run_brugis
    from Demand.Layers.osm import main as run_osm
    from Demand.Layers.urbis import main as run_urbis
except ImportError:
    from .Layers.bisa import main as run_bisa
    from .Layers.brugis import main as run_brugis
    from .Layers.osm import main as run_osm
    from .Layers.urbis import main as run_urbis


def main():
    run_bisa()
    run_brugis()
    run_urbis()
    run_osm()


if __name__ == '__main__':
    main()