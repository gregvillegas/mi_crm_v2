#!/bin/bash

rsync -avz --exclude '.git' --exclude '__pycache__'  \
    --exclude 'db.sqlite3' --exclude 'venv' \
    /private/var/www/mi_crm/ micrm:/var/www/mi_crm/
