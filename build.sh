#!/usr/bin/env bash
# Build script for deployment

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Create superuser if it doesn't exist (optional - for first deployment)
# python manage.py seed_data
