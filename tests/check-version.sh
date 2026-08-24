#!/bin/bash
# Check that pypi versions in nvchecker.toml match setup.py
set -euo pipefail

NVCHECKER=".venv/bin/nvchecker"

ERRORS=0

for pypi_package in $(grep '^pypi = "' tests/nvchecker.toml | awk -F'"' '{print $2}'); do
    setup_version=$(grep "${pypi_package}==" setup.py | head -1 | sed 's/.*==//;s/[",'\'']//g')
    echo "[INFO] version check for $pypi_package ..."
    latest_version=$($NVCHECKER --file tests/nvchecker.toml --logger json --entry "$pypi_package" | jq -r .version)
    if [ "$setup_version" != "$latest_version" ]; then
        echo "ERROR: $pypi_package: setup.py has $setup_version, pypi has $latest_version"
        ERRORS=1
    fi
done

exit $ERRORS
