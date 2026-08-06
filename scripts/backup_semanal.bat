@echo off
rem Lanzador del backup semanal de OAFCare (lo ejecuta el Programador de
rem tareas de Windows). Deja el resultado de cada corrida en
rem backups\backup_log.txt para poder verificar que corrio bien.
cd /d "%~dp0.."
if not exist backups mkdir backups
echo ============================================>> backups\backup_log.txt
echo Backup automatico: %date% %time%>> backups\backup_log.txt
"C:\Users\Cato\PythonPortable\python.exe" scripts\backup_db.py >> backups\backup_log.txt 2>&1
