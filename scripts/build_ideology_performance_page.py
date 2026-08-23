"""Compatibility entry point for the merged ideology research page."""
try:
    from scripts.build_democratic_transition_page import build, main, payload
except ModuleNotFoundError:
    from build_democratic_transition_page import build, main, payload

if __name__ == "__main__":
    main()
