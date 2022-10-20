#!/bin/bash

echo "Update requirements.txt file"
poetry export --without-hashes -f requirements.txt --output requirements.txt
