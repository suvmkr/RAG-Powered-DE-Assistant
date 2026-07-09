"""
orders_fact_pipeline.py
Builds the orders_fact dimensional table from raw order events.
Handles late-arriving data up to 3 days with a watermark strategy.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType


WATERMARK_DAYS = 3
PII_COLUMNS = ["customer_email", "billing_address", "credit_card_last4"]


def build_orders_fact(spark: SparkSession, source_table: str, target_table: str):
    """
    Reads incremental orders from source_table, applies transformations,
    masks PII columns, and merges into target_table (Delta Lake / Iceberg).
    """

    raw_orders = spark.readStream.table(source_table)

    # Watermark for late data
    watermarked = raw_orders.withWatermark("order_timestamp", f"{WATERMARK_DAYS} days")

    # Mask PII
    masked = watermarked
    for col in PII_COLUMNS:
        if col in raw_orders.columns:
            masked = masked.withColumn(col, F.sha2(F.col(col), 256))

    # Aggregate
    orders_fact = (
        masked
        .withColumn("order_date", F.to_date("order_timestamp"))
        .groupBy("order_date", "product_id", "customer_id")
        .agg(
            F.sum("amount").alias("total_amount"),
            F.count("order_id").alias("order_count"),
            F.first("currency").alias("currency"),
        )
    )

    return (
        orders_fact.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"s3://checkpoints/{target_table}")
        .table(target_table)
    )
