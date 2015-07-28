
res=0

echo -e "\n***CLEARING OLD DJANGO SESSIONS***\n"
python manage.py clearsessions
res=$(($res + $?))


echo -e "\n***MAKING BACKUP OF PYCHRONIA GAMES***\n"
python -c "from pychronia_game.scripts import backup_all_games; backup_all_games.execute()"
res=$(($res + $?))

echo -e "\n***MAKING SANITY CHECK OF PYCHRONIA GAMES***\n"
python -c "from pychronia_game.scripts import check_global_sanity; check_global_sanity.execute()"
res=$(($res + $?))

echo -e "\n***RESETTING DEMO OF PYCHRONIA GAME***\n"
python -c "from pychronia_game.scripts import reset_demo_account; reset_demo_account.execute()"
res=$(($res + $?))

echo -e "\n***PACKING ZODB DATABASE***\n"
python dependencies/relstorage/zodbpack.py -d 2 zodbpack.conf
res=$(($res + $?))


# NOT FOR NOW, TO BE ACTIVATED SOON #
#echo -e "\n***NOTIFYING NOVELTIES PYCHRONIA GAMES***\n"
#python -c "from pychronia_game.scripts import notify_novelties_by_email; notify_novelties_by_email.execute()"
#res=$(($res + $?))

exit $res


