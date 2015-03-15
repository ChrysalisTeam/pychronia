
res=0

python manage.py clearsessions
res=$(($res + $?))

python manage.py thumbnail_cleanup
res=$(($res + $?))

python manage.py purgerequests --noinput 1 month
res=$(($res + $?))

exit $res