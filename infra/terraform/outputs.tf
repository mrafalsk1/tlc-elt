output "raw_bucket_name" {
  description = "Bucket S3 da camada raw (equivalente ao ./data/raw local)."
  value       = aws_s3_bucket.raw.bucket
}

output "raw_bucket_arn" {
  description = "ARN do bucket raw, usado nas policies do Glue."
  value       = aws_s3_bucket.raw.arn
}

output "warehouse_endpoint" {
  description = "Host:porta do Postgres do warehouse."
  value       = aws_db_instance.warehouse.endpoint
}

output "warehouse_db_name" {
  description = "Banco inicial do warehouse."
  value       = aws_db_instance.warehouse.db_name
}

output "warehouse_master_secret_arn" {
  description = "ARN do segredo (Secrets Manager) com a senha master gerada pela AWS."
  value       = aws_db_instance.warehouse.master_user_secret[0].secret_arn
  sensitive   = true
}

output "glue_database_name" {
  description = "Nome do banco no Glue Data Catalog."
  value       = aws_glue_catalog_database.raw.name
}

output "glue_crawler_name" {
  description = "Crawler que popula o catalogo a partir do prefixo raw/."
  value       = aws_glue_crawler.raw.name
}

output "glue_role_arn" {
  description = "Role assumida pelo Glue."
  value       = aws_iam_role.glue.arn
}
