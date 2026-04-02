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

# 生成 JWT 密钥
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")

# 创建 .env 文件
if [ ! -f .env ]; then
    cat > .env << EOF
POSTGRES_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
MINIFLUX_DB_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MINIFLUX_ADMIN=admin
MINIFLUX_PASSWORD=$(openssl rand -hex 8 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(8))")
MINIFLUX_API_KEY=
MINIO_USER=infohub
MINIO_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
EOF
    echo "已生成 .env 文件，请检查并填写 MINIFLUX_API_KEY"
else
    echo ".env 文件已存在，跳过"
fi

# 创建输出目录
mkdir -p output

echo ""
echo "=== 初始化完成 ==="
echo "1. 编辑 .env 填写必要配置"
echo "2. 启动服务: docker compose -f docker-compose.private.yml up -d"
echo "3. 获取 Miniflux API Key 后填入 .env"
echo "4. 重启: docker compose -f docker-compose.private.yml restart"
echo "5. 访问 API: http://localhost:8000/health"
echo "6. 注册用户: POST http://localhost:8000/api/v1/auth/register"
