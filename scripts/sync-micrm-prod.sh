#!/bin/bash

remote_svr=192.168.1.200

rsync -avz -e 'ssh -p 2223' --exclude '.git' --exclude '__pycache__'  \
    --exclude 'db.sqlite3' --exclude 'venv' \
    /private/var/www/mi_crm/ $remote_svr:/var/www/mi_crm/
