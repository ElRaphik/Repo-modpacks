.PHONY: dry-run

# Test dependency updates without modifying files
dry-run:
	python3 update_dependencies.py --dry-run