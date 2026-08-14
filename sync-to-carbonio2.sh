#!/bin/bash

rsync -avz --exclude '.git' --exclude '__pycache__' \
  --exclude 'db.sqlite3' --exclude 'venv' \
  /private/var/www/mi_crm/ carbonio-mi:/var/www/mi_crm2/
