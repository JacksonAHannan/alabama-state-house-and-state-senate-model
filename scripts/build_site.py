"""Compatibility entry point for the canonical public-site build."""

try:
    from scripts.build_blue_oxblood_site import BUILDERS, main
except ModuleNotFoundError:
    from build_blue_oxblood_site import BUILDERS, main


if __name__ == "__main__":
    main()
