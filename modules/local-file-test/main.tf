resource "local_file" "this" {
  filename = "${path.root}/${var.filename}"
  content  = var.content
}
