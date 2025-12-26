
set -e

python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

python3 manage.py collectstatic --noinput

mkdir -p staticfiles_build

cp -r staticfiles_build/static/* staticfiles_build/ || echo "No static files found."
