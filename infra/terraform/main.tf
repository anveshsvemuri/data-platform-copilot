data "aws_caller_identity" "current" {}

locals {
  container_name = "copilot"
  image           = "${aws_ecr_repository.copilot.repository_url}@${var.image_digest}"
  server_url      = "https://${aws_lb.copilot.dns_name}/mcp"
}

resource "aws_ecr_repository" "copilot" {
  name                 = var.name_prefix
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "copilot" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "copilot" {
  name = var.name_prefix

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

data "aws_iam_policy_document" "task_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-execution"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "read_token" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.mcp_token_secret_arn]
  }
}

resource "aws_iam_role_policy" "read_token" {
  name   = "read-mcp-token"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.read_token.json
}

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

resource "aws_security_group" "load_balancer" {
  name        = "${var.name_prefix}-alb"
  description = "Restrict MCP ingress to explicitly trusted networks"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "trusted_http_clients" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.load_balancer.id
  description       = "Trusted MCP client HTTP or HTTPS redirect"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_ingress_rule" "trusted_https_clients" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.load_balancer.id
  description       = "Trusted MCP client HTTPS"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value
}

resource "aws_security_group" "service" {
  name        = "${var.name_prefix}-service"
  description = "Accept MCP traffic only from the load balancer"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "load_balancer_to_service" {
  security_group_id            = aws_security_group.service.id
  description                  = "MCP traffic from load balancer"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.load_balancer.id
}

resource "aws_vpc_security_group_egress_rule" "load_balancer_to_service" {
  security_group_id            = aws_security_group.load_balancer.id
  description                  = "Forward only to MCP tasks"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.service.id
}

resource "aws_vpc_security_group_egress_rule" "service_https" {
  security_group_id = aws_security_group.service.id
  description       = "AWS API and optional model-provider access"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_lb" "copilot" {
  name                       = substr(var.name_prefix, 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.load_balancer.id]
  subnets                    = var.public_subnet_ids
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "copilot" {
  name        = substr("${var.name_prefix}-mcp", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled             = true
    path                = "/mcp"
    matcher             = "401"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.copilot.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.copilot.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.copilot.arn
  }
}

resource "aws_ecs_task_definition" "copilot" {
  family                   = var.name_prefix
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name                   = local.container_name
    image                  = local.image
    essential              = true
    readonlyRootFilesystem = true
    user                   = "10001"
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "MCP_TRANSPORT", value = "streamable-http" },
      { name = "MCP_HOST", value = "0.0.0.0" },
      { name = "MCP_PORT", value = "8000" },
      { name = "MCP_SERVER_URL", value = local.server_url }
    ]
    secrets = [{
      name      = "MCP_BEARER_TOKEN"
      valueFrom = var.mcp_token_secret_arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.copilot.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "mcp"
      }
    }
  }])
}

resource "aws_ecs_service" "copilot" {
  name            = var.name_prefix
  cluster         = aws_ecs_cluster.copilot.id
  task_definition = aws_ecs_task_definition.copilot.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.copilot.arn
    container_name   = local.container_name
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http, aws_lb_listener.https]
}
