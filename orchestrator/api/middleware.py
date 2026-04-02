"""租户隔离中间件 — 将 tenant_id 注入请求上下文"""

from uuid import UUID
from fastapi import Request


def get_tenant_id(request: Request) -> UUID:
    """从已认证的 tenant 对象获取 tenant_id"""
    tenant = getattr(request.state, "tenant", None)
    if tenant:
        return tenant.id
    raise ValueError("未认证的请求")
