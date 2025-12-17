#!/usr/bin/env bash
# Build script for deployment

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Seed initial data (courts, equipment, coaches, pricing rules, admin user)
python manage.py seed_data
