#!/usr/bin/env bash

HOME=$(pwd)

rm packages/*.zip

functions=(
           "adapter/mrasco"
           "outage_info"
           "meter_forecast" \
           "redshift/consumption" \
           "get_anomaly"  \
           "late_arriving_notification" \
           "ml_pipeline/crawler/trigger_glue_crawler" \
           "ml_pipeline/crawler/get_glue_crawler_state" \
           "ml_pipeline/upload_result"  \
           "ml_pipeline/split_batch"  \
           "ml_pipeline/prepare_training"  \
           "ml_pipeline/prepare_batch"  \
           "ml_pipeline/batch_anomaly_detection" \
           "ml_pipeline/state_topic_subscription" \
           "ml_pipeline/load_pipeline_parameter" \
           "ml_pipeline/has_endpoint" \
           "ml_pipeline/check_pipeline_steps" \
           "ml_pipeline/update_meter_ids" \
           "ml_pipeline/split_batch_v2"  \
           "ml_pipeline/batch_anomaly_detection_v2" \
           "ml_pipeline/prepare_training_v2"  \
           "weather_load" \
           "ml_pipeline/check_initial_pipeline_run")

for lambda_folder in ${functions[*]};
do
   function_name=${lambda_folder////_}
   echo $function_name
   (cd $lambda_folder; zip -9qr "$HOME/packages/${function_name}.zip" .;cd $HOME)
done