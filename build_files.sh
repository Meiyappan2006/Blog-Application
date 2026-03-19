echo "BUILD START"
python3.12 -m pip install -r requirements.txt
python3.12 manage.py collectstatic --noinput --clear

# Create superuser if environment variables are provided
if [ "$DJANGO_SUPERUSER_USERNAME" ]; then
  python3.12 manage.py createsuperuser --noinput || true
fi

echo "BUILD END"
