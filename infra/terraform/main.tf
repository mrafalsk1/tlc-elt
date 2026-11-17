# --- Rede: VPC propria, sem subnets publicas, para o RDS nao ficar exposto -------------------

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project}-${var.environment}-vpc" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = false

  tags = { Name = "${var.project}-${var.environment}-private-${count.index + 1}" }
}

resource "aws_security_group" "warehouse" {
  name        = "${var.project}-${var.environment}-warehouse"
  description = "Acesso ao Postgres do warehouse (porta 5432) apenas pela rede interna."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Postgres a partir dos CIDRs autorizados"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    description = "Saida livre (patches, replicacao)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-warehouse-sg" }
}

resource "aws_db_subnet_group" "warehouse" {
  name       = "${var.project}-${var.environment}-warehouse"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${var.project}-${var.environment}-warehouse" }
}

# --- Warehouse: Postgres gerenciado, cifrado, sem acesso publico -----------------------------

resource "aws_db_instance" "warehouse" {
  identifier     = "${var.project}-${var.environment}"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username

  # Senha gerada pela AWS e guardada no Secrets Manager: nada de segredo em codigo ou .tfvars.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.warehouse.name
  vpc_security_group_ids = [aws_security_group.warehouse.id]
  publicly_accessible    = false

  backup_retention_period = var.db_backup_retention_days

  # Protecao cresce com o ambiente: em prod nao ha destroy silencioso nem perda de snapshot.
  deletion_protection       = local.is_production
  skip_final_snapshot       = !local.is_production
  final_snapshot_identifier = local.is_production ? "${var.project}-${var.environment}-final" : null

  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = { Name = "${var.project}-${var.environment}-warehouse" }
}

# --- Raw: bucket S3 com versionamento, cifra e bloqueio de acesso publico --------------------

resource "aws_s3_bucket" "raw" {
  bucket        = local.raw_bucket_name
  force_destroy = false

  tags = { Name = local.raw_bucket_name, Layer = "raw" }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "require_tls" {
  bucket = aws_s3_bucket.raw.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.raw.arn,
        "${aws_s3_bucket.raw.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  # Parquet e um arquivo por mes (~50 MB), entao todo o prefixo raw/ e elegivel para IA.
  rule {
    id     = "raw-parquet-tiering"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }

  # Versao antiga de qualquer objeto do bucket expira: sem isso o versionamento cresce sem fim.
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# --- Glue: catalogo + crawler sobre o prefixo raw ---------------------------------------------

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }

    # Fecha o confused deputy: so o Glue desta conta pode assumir a role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${var.project}-${var.environment}-glue"
  description        = "Role do Glue crawler/jobs sobre o bucket raw do ${var.project}."
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

# Policy propria em vez de AWSGlueServiceRole: a managed policy da glue:* e s3:ListAllMyBuckets
# em Resource "*", o que nao e acesso minimo.
data "aws_iam_policy_document" "glue_raw_access" {
  statement {
    sid = "GlueCatalogForCrawler"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:CreatePartition",
      "glue:UpdatePartition",
      "glue:BatchCreatePartition",
      "glue:BatchUpdatePartition",
      "glue:GetCrawler",
      "glue:UpdateCrawler",
      "glue:StartCrawler",
      "glue:GetCrawlerMetrics",
      "glue:GetClassifier",
      "glue:GetClassifiers",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:catalog",
      aws_glue_catalog_database.raw.arn,
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${aws_glue_catalog_database.raw.name}/*",
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:crawler/${var.project}-${var.environment}-raw",
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:classifier/*",
    ]
  }

  statement {
    sid       = "CloudWatchLogsForCrawler"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws-glue/*"]
  }

  statement {
    sid       = "ListRawPrefix"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*"]
    }
  }

  statement {
    sid       = "BucketLocation"
    actions   = ["s3:GetBucketLocation"]
    resources = [aws_s3_bucket.raw.arn]
  }

  # O crawler so le: sem PutObject/DeleteObject.
  statement {
    sid       = "ReadRawObjects"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.raw.arn}/raw/*"]
  }
}

resource "aws_iam_role_policy" "glue_raw_access" {
  name   = "raw-bucket-access"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_raw_access.json
}

resource "aws_glue_catalog_database" "raw" {
  name        = "${replace(var.project, "-", "_")}_${var.environment}_raw"
  description = "Catalogo da camada raw (${var.project}, ${var.environment})."
}

resource "aws_glue_crawler" "raw" {
  name          = "${var.project}-${var.environment}-raw"
  database_name = aws_glue_catalog_database.raw.name
  role          = aws_iam_role.glue.arn
  table_prefix  = "raw_"

  s3_target {
    path = "s3://${aws_s3_bucket.raw.bucket}/raw/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })
}
