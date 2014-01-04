
for mydir in pychronia_game pychronia_cms pychronia_common 
do
    pushd $mydir
    python ../manage.py makemessages -l fr
    # then use virtaal to translate messages efficiently
    python ../manage.py compilemessages
    popd
done
 






