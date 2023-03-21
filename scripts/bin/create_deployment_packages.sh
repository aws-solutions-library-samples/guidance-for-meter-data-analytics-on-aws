#!/usr/bin/env bash

cd ../../functions
HOME=$(pwd)

rm packages/*.zip

dirlist=(`ls $HOME/source`)

for lambda_folder in ${dirlist[*]};
do
   function_name=${lambda_folder////_}
   function_name=${function_name//source_/}
   echo $function_name

   mkdir -p $HOME/packages/${function_name}
   (cd source/$lambda_folder; zip -9qr "$HOME/packages/${function_name}/lambda.zip" .;cd $HOME)
done

cd -