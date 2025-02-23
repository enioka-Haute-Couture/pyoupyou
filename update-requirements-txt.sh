#!/bin/bash

echo "Update requirements.txt file"
uv export --format requirements-txt --no-header --no-dev --no-hashes --frozen -o requirements.txt
