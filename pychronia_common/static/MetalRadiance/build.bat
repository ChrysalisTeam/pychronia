rem :loop

python -m scss scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C

watchmedo shell-command scss -c "python -m scss scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C"

rem python -m scss scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C
rem TIMEOUT /T 5
rem goto loop

rem BEWARE - watchdog only recompiles *.scss files WITHOUT underscore prefix, so "touch" metalradiance.scss to trigger it 
rem python -m scss -w scss -o . -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C

rem : --debug-info


