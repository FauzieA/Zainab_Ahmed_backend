#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Collect static files safely
python manage.py collectstatic --no-input

# 3. Run outstanding database migrations against Supabase
python manage.py migrate

# 4. AUTOMATIC SUPERUSER CREATION FOR FREE TIER
# The "|| true" ensures future deploys don't crash when the account already exists!
python manage.py createsuperuser --no-input || true