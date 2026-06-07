#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Collect static files safely without asking for confirmation prompts
python manage.py collectstatic --no-input

# 3. Run outstanding database migrations against Supabase
python manage.py migrate