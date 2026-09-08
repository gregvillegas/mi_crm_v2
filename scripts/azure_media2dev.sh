#!/bin/bash

remote_svr=crm_azure

rsync -avz -e 'ssh -i ~/.susi/CRM_key.pem' --exclude '.git' --exclude '__pycache__'  \
    --exclude 'db.sqlite3' --exclude 'venv' \
    $remote_svr:/var/www/mi_crm/media/signatures/  /private/var/www/mi_crm/media/signatures/
