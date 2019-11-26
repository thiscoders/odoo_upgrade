#!/usr/bin/env bash

cd /home/hrp/dydemo/app_demo/code/hand-china/dy-ap
rm -rf dy_ap_srm_interface
cd /home/hrp/down/dy-ap
git checkout -- .
git pull
mv dy_ap_srm_interface dy_ap_srm_interfac
cp -r dy_ap_srm_interfac /home/hrp/dydemo/app_demo/code/hand-china/dy-ap/
echo 'dy_ap_srm_interface 代码替换成功!'