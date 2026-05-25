set -e

export DJANGO_SETTINGS_MODULE=hotel_prj.settings

echo "Installing dependencies..."
python3 -m pip install -r requirements.txt --target .vercel/python

echo "Collecting static files..."
python3 manage.py collectstatic --noinput

echo "Build completed successfully"
