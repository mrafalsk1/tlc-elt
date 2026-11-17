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

  backup_retention_period    = var.db_backup_retention_days
  auto_minor_version_upgrade = true
  deletion_protection        = false # dev: permite destruir; em prod, true
  skip_final_snapshot        = true
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

  rule {
    id     = "raw-tiering"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
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
  }
}

resource "aws_iam_role" "glue" {
  name               = "${var.project}-${var.environment}-glue"
  description        = "Role do Glue crawler/jobs sobre o bucket raw do ${var.project}."
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "glue_raw_access" {
  statement {
    sid       = "ListRawBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.raw.arn]
  }

  statement {
    sid       = "ReadWriteRawObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.raw.arn}/*"]
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
