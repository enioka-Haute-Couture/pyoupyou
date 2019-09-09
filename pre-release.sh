#!/bin/bash

echo "Update requirements.txt file"
pipenv lock -r > requirements.txt
