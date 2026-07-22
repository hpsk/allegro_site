@echo off
echo ALLEGRO_SITE 환경설정
setx ALLEGRO_SITE %~dp0
setx ALLEGRO_LONG_PACKAGE_NAME TRUE

echo tclscripts 복사
IF NOT EXIST %HOME%\cdssetup\OrCAD_Capture (mkdir %HOME%\cdssetup\OrCAD_Capture )
xcopy .\tclscripts "%HOME%\cdssetup\OrCAD_Capture\tclscripts" /E /I /H /Y
