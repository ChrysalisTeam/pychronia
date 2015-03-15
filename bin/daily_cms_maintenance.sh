
res=0

echo -e "\n***CLEARING OLD DJANGO SESSIONS***\n"
python manage.py clearsessions
res=$(($res + $?))

echo -e "\n***CLEARING OLD DJANGO THUMBNAILS***\n"
python manage.py thumbnail_cleanup
res=$(($res + $?))

echo -e "\n***CLEARING OLD DJANGO REQUEST STATS***\n"
python manage.py purgerequests --noinput 1 month
res=$(($res + $?))

exit $res