:loop

python -m scss scss/main.scss -o metalradiance.css -I scss -C 

python -m scss scss/main_mobile.scss -o metalradiance_mobile.css -I scss -C 

rem ;;;;python -m scss -w scss --recursive -o css -I scss
rem ; --debug-info 

TIMEOUT /T 5
goto loop