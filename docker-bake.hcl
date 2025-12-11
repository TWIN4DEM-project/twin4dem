group "default" {
  targets = ["frontend_prod", "backend_prod"]
}

target frontend_prod {
  context = "."
  dockerfile = "./frontend/Dockerfile"
  target = "frontend_prod"
  tags = ["frontend_prod"]
}

target backend_prod {
  context = "."
  dockerfile = "./backend/Dockerfile"
  target = "web_prod"
  contexts = {
    frontend_prod = "target:frontend_prod"
  }
  tags = ["backend_prod"]
}
