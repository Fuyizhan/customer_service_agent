from sqlalchemy import select
from . import session
from .models import OrderRecord, ShipmentRecord, KnowledgeDoc

async def seed_db():

    # ✅ 重点：函数内部再取，不要顶部导入死引用
    async_session_factory = session.async_session_factory
    if async_session_factory is None:
        raise RuntimeError("必须先调用 init_db_engine 初始化引擎！")
    
    async with async_session_factory() as db:
        # 查重
        result = await db.execute(select(OrderRecord).limit(1))
        if result.scalar_one_or_none():
            print("ℹ️ 数据库已有数据，跳过初始化。")
            return
            
        print("🌱 正在注入种子数据...")
        
        # 订单
        db.add_all([
            OrderRecord(order_id="ORD-001", user_id="U001", product_name="MacBook Pro", amount=14999.0, status="已发货"),
            OrderRecord(order_id="ORD-002", user_id="U002", product_name="iPhone 15", amount=5999.0, status="待付款"),
            OrderRecord(order_id="ORD-003", user_id="U001", product_name="AirPods Pro", amount=1899.0, status="已签收"),
            OrderRecord(order_id="ORD-004", user_id="U003", product_name="华为平板", amount=2499.0, status="已取消"),
        ])
        # 物流
        db.add(ShipmentRecord(order_id="ORD-001", carrier="顺丰速运", tracking_no="SF12345678", current_location="北京市朝阳区", status="运输中"))
        db.add(ShipmentRecord(order_id="ORD-003", carrier="京东物流", tracking_no="JD88776655", current_location="用户签收", status="已签收"))

        
        # 知识库（假向量占位，维度1024，适配百炼text-embedding-v3）
        fake_vector = [0.0] * 1024
        db.add_all([
          KnowledgeDoc(category="退换货政策", title="7天无理由退货规则", 
                        content="自签收之日起7天内，商品未拆封且不影响二次销售的，支持无理由退货。贴身用品、定制商品不支持7天无理由。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="保修政策", title="电子产品保修说明", 
                        content="电子产品自签收之日起提供1年免费保修服务，人为损坏、进水、私自拆机不在保修范围。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="运费政策", title="退货运费承担规则", 
                        content="商品质量问题退货，商家承担运费；7天无理由个人原因退货，由买家承担运费，有运费险可抵扣首重运费。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="发货时效", title="现货商品发货时间", 
                        content="现货订单付款后48小时内安排发出，预售商品以商品详情页标注的发货时间为准，节假日顺延。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="发票服务", title="电子发票开具规则", 
                        content="订单完成后可申请电子发票，发票抬头可选择个人或者企业，开票周期一般1-3个工作日。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="价保政策", title="商品价保说明", 
                        content="签收7天内商品降价，可申请价保补差；活动特价、秒杀商品不参与价保。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="拒收规则", title="快递拒收处理", 
                        content="到货拒收后，包裹退回仓库，商家收到退回商品后处理退款；生鲜、易碎品拒收产生损耗不予退款。", 
                        embedding=fake_vector),
          KnowledgeDoc(category="优惠券", title="优惠券使用限制", 
                        content="优惠券不可叠加使用，限时券过期自动失效，仅支持指定商品，不支持充值类商品。", 
                        embedding=fake_vector),
        ])

        
        await db.commit()
        print("✅ 种子数据注入完成！")

if __name__ == "__main__":
    import asyncio
    from .session import init_db_engine, create_tables_and_extension
    from ..config import settings

    async def main():
        print("正在初始化数据库引擎与表结构...")
        init_db_engine(settings.DATABASE_URL)
        await create_tables_and_extension()
        await seed_db()
        print("✅ 数据库初始化流程结束。")

    asyncio.run(main())