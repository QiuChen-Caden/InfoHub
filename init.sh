#!/bin/bash
set -e

echo "=== InfoHub 初始化脚本 ==="

# 生成 Fernet 加密密钥
if [ -z "$ENCRYPTION_KEY" ]; then
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
    if [ -z "$ENCRYPTION_KEY" ]; then
        echo "请先安装 cryptography: pip install cryptography"
        echo "或手动设置 ENCRYPTION_KEY 环境变量"
        exit 1
    fi
fi

# 预先生成所有密码（避免 heredoc 内 command substitution 失败静默）
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
POSTGRES_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
MINIFLUX_DB_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
MINIFLUX_PASSWORD=$(openssl rand -hex 8 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(8))")
REDIS_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")

# 验证所有密码生成成功
for var_name in JWT_SECRET POSTGRES_PASSWORD MINIFLUX_DB_PASSWORD MINIFLUX_PASSWORD REDIS_PASSWORD ENCRYPTION_KEY; do
    eval val=\$$var_name
    if [ -z "$val" ]; then
        echo "错误: $var_name 生成失败"
        exit 1
    fi
done

# 创建 .env 文件
if [ ! -f .env ]; then
    cat > .env << EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
MINIFLUX_DB_PASSWORD=${MINIFLUX_DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MINIFLUX_ADMIN=admin
MINIFLUX_PASSWORD=${MINIFLUX_PASSWORD}
MINIFLUX_API_KEY=
AI_API_KEY=
AI_MODEL=deepseek/deepseek-chat
AI_API_BASE=
BOOTSTRAP_EMAIL=admin@example.com
BOOTSTRAP_PASSWORD=
EOF
    chmod 600 .env
    echo "已生成 .env 文件（权限 600），请检查并填写必要配置"
else
    echo ".env 文件已存在，跳过"
fi

# 创建输出目录
mkdir -p output

echo ""
echo "=== 初始化完成 ==="
echo "1. 编辑 .env 填写 BOOTSTRAP_PASSWORD 和 AI_API_KEY"
echo "2. 启动服务: docker compose up -d"
echo "3. 访问 API: http://localhost:8500/health"
echo "4. 注册用户: POST http://localhost:8500/api/v1/auth/register"
