variable "aws_region" {
  description = "Regiao da AWS onde os recursos seriam criados."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Prefixo de nome dos recursos."
  type        = string
  default     = "tlc-elt"
}

variable "environment" {
  description = "Ambiente logico (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR da VPC dedicada ao warehouse."
  type        = string
  default     = "10.42.0.0/16"
}

variable "allowed_cidr_blocks" {
  description = "CIDRs autorizados a abrir conexao na porta 5432 do RDS."
  type        = list(string)
  default     = ["10.42.0.0/16"]
}

variable "db_instance_class" {
  description = "Classe da instancia RDS."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Banco inicial do warehouse (mesmo nome usado pelo dbt)."
  type        = string
  default     = "warehouse"
}

variable "db_username" {
  description = "Usuario master do RDS. A senha e gerada e guardada no Secrets Manager."
  type        = string
  default     = "dw"
}

variable "db_backup_retention_days" {
  description = "Dias de retencao de backup automatico."
  type        = number
  default     = 7
}
