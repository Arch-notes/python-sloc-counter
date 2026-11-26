resource "aws_s3_bucket" "logs" {
  bucket = "logs"
}

variable "region" {
  default = "ap-northeast-1"
}
