#!/bin/bash

remote_svr=crm_azure

rsync -avz -e 'ssh -i ~/.susi/CRM_key.pem' \
    --exclude 'recycle' \
    --exclude '.git' \
    --exclude 'backup' \
    --exclude 'MiCRM_Android' \
    --exclude 'micrm_android_mockup' \
    --exclude '__pycache__'  \
    --exclude 'db.sqlite3' \
    --exclude 'venv' \
    --exclude 'media' \
    --exclude '.env' \
    /private/var/www/mi_crm/ $remote_svr:/var/www/mi_crm/
