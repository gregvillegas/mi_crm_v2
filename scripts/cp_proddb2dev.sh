#!/bin/bash

echo "Backup database..."
mv db.sqlite3 backup/db.sqlite3-$(date +%Y-%m-%d)
echo "-------------------------------------------------"
sleep 20
echo "Copying Production database to Dev environment..."
sleep 10
scp -i ~/.susi/CRM_key.pem \
    crm_azure:/var/www/mi_crm/db.sqlite3 \
    ./db.sqlite3
echo "-------------------------------------------------" 
echo "Done..."