# src/customer_service_agent/agents/tools.py
from langchain_core.tools import tool
from sqlalchemy import select
from customer_service_agent.db.models import OrderRecord, ShipmentRecord
from customer_service_agent.db import session
@tool
async def query_order_status(order_id: str) -> str:
    """根据订单号查询订单状态和基本信息。必须传入精确的订单号，例如 ORD-001。"""
    # 实时读取，拿到最新的factory，规避快照None
    factory = session.async_session_factory
    if factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db_engine")
    async with factory() as db:
        result = await db.execute(select(OrderRecord).where(OrderRecord.order_id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return f"系统中未找到订单号为 {order_id} 的订单，请确认订单号是否正确。"
        return f"订单号: {order.order_id}, 商品: {order.product_name}, 金额: {order.amount}元, 状态: {order.status}"

@tool
async def query_shipment_info(order_id: str) -> str:
    """根据订单号查询物流进度。必须传入精确的订单号，例如 ORD-001。"""
    # 实时读取，拿到最新的factory，规避快照None
    factory = session.async_session_factory
    if factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db_engine")
    async with factory() as db:
        result = await db.execute(select(ShipmentRecord).where(ShipmentRecord.order_id == order_id))
        shipment = result.scalar_one_or_none()
        if not shipment:
            return f"未找到订单 {order_id} 的物流信息。"
        return f"订单 {order_id} 由 {shipment.carrier} 承运，运单号 {shipment.tracking_no}，当前位置: {shipment.current_location}，状态: {shipment.status}"