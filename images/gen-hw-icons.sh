#!/bin/sh
sed -e 's/@TEMPLATE@/DirectX/' > hw-accel-dx.svg < hw-template.svg
sed -e 's/@TEMPLATE@/NVDEC/' > hw-accel-nvdec.svg < hw-template.svg
sed -e 's/@TEMPLATE@/NVENC/' > hw-accel-nvenc.svg < hw-template.svg
sed -e 's/@TEMPLATE@/QSV/' > hw-accel-qsv.svg < hw-template.svg
sed -e 's/@TEMPLATE@/VA-API/' > hw-accel-vaapi.svg < hw-template.svg
sed -e 's/@TEMPLATE@/VDPAU/' > hw-accel-vdpau.svg < hw-template.svg
sed -e 's/@TEMPLATE@/VTB/' > hw-accel-vtb.svg < hw-template.svg
