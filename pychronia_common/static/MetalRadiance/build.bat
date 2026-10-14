rem :loop

rem NOTE: we use scss_build.py instead of "python -m scss" because pyscss==1.4.0 is abandoned
rem and incompatible with Python 3.11+'s "re" module; scss_build.py patches it at runtime, see
rem that file for details.

python scss_build.py scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C

watchmedo shell-command scss -c "python scss_build.py scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C"

rem python scss_build.py scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C
rem TIMEOUT /T 5
rem goto loop

rem BEWARE - watchdog only recompiles *.scss files WITHOUT underscore prefix, so "touch" metalradiance.scss to trigger it
rem python scss_build.py -w scss -o . -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C

rem : --debug-info


