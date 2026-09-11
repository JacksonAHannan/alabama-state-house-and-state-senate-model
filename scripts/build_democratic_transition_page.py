"""Stable entry point for the current ideology and caucus analysis page."""

try:
    from scripts.build_democratic_transition_page_v2 import OUTPUT, build, main, payload
except ModuleNotFoundError:
    from build_democratic_transition_page_v2 import OUTPUT, build, main, payload


if __name__ == "__main__":
    main()
