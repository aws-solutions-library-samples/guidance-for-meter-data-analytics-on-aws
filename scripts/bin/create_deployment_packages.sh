#!/usr/bin/env bash

cd ../../functions
HOME=$(pwd)

rm packages/*.zip

functions=(
           "source/adapter/csv/inbound_file_range_extractor" \
           "source/adapter/csv/inbound_file_range_worker" \
           "source/late_arriving_notification" \
           "source/ml_pipeline/crawler/trigger_glue_crawler" \
           "source/ml_pipeline/crawler/get_glue_crawler_state" \
           "source/ml_pipeline/upload_result"  \
           "source/ml_pipeline/split_batch"  \
           "source/ml_pipeline/prepare_training"  \
           "source/ml_pipeline/prepare_batch"  \
           "source/ml_pipeline/batch_anomaly_detection" \
           "source/ml_pipeline/state_topic_subscription" \
           "source/ml_pipeline/load_pipeline_parameter" \
           "source/ml_pipeline/has_endpoint" \
           "source/ml_pipeline/check_pipeline_steps" \
           "source/ml_pipeline/update_meter_ids" \
           "source/ml_pipeline/split_batch_v2"  \
           "source/ml_pipeline/batch_anomaly_detection_v2" \
           "source/ml_pipeline/prepare_training_v2"  \
           "source/weather_load" \
           "source/topology_transformer" \
           "source/ml_pipeline/check_initial_pipeline_run")

for lambda_folder in ${functions[*]};
do
   function_name=${lambda_folder////_}
   function_name=${function_name//source_/}
   echo $function_name
   (cd $lambda_folder; zip -9qr "$HOME/packages/${function_name}.zip" .;cd $HOME)
done

cd -