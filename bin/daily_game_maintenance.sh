
res=0

echo -e "\n***CLEARING OLD DJANGO SESSIONS***\n"
python manage.py clearsessions
res=$(($res + $?))


echo -e "\n***MAKING BACKUP OF PYCHRONIA GAMES***\n"
python manage.py backup_all_games
res=$(($res + $?))

echo -e "\n***MAKING SANITY CHECK OF PYCHRONIA GAMES***\n"
python manage.py check_global_sanity
res=$(($res + $?))

echo -e "\n***RESETTING DEMO OF PYCHRONIA GAME***\n"
python manage.py reset_demo_account
res=$(($res + $?))

echo -e "\n***PACKING ZODB DATABASE***\n"
python -m relstorage.zodbpack -d 2 zodbpack.conf
res=$(($res + $?))


# NOT FOR NOW, TO BE ACTIVATED SOON #
#echo -e "\n***NOTIFYING NOVELTIES PYCHRONIA GAMES***\n"
#python manage.py notify_novelties_by_email
#res=$(($res + $?))

exit $res


