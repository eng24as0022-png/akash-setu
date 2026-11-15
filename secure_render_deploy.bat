@echo off
title Akash Setu - Secure Render Deployer
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0secure_render_deploy.ps1"
pause
