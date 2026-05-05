release: cd backend && python manage.py migrate --noinput
web: cd backend && gunicorn crm.wsgi --bind 0.0.0.0:$PORT --workers 3 --access-logfile -
