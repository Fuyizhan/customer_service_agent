# src/customer_service_agent/db/ingest_knowledge.py
"""
知识库真实向量入库脚本（离线执行，不走服务启动流程）。
用法：
    uv run python -m src.customer_service_agent.db.ingest_knowledge
"""
import asyncio
from sqlalchemy import select
from . import session
from .models import KnowledgeDoc
from ..config import settings
from ..agents.rag_service import rag_service


# 原始知识库文本（后续可以改成读取 markdown / txt 文件）
KNOWLEDGE_RAW = [
    {
        "category": "退换货政策",
        "title": "7天无理由退货规则",
        "content": "自签收之日起7天内，商品未拆封且不影响二次销售的，支持无理由退货。贴身用品、定制商品不支持7天无理由。",
    },
    {
        "category": "保修政策",
        "title": "电子产品保修说明",
        "content": "电子产品自签收之日起提供1年免费保修服务，人为损坏、进水、私自拆机不在保修范围。",
    },
    {
        "category": "运费政策",
        "title": "退货运费承担规则",
        "content": "商品质量问题退货，商家承担运费；7天无理由个人原因退货，由买家承担运费，有运费险可抵扣首重运费。",
    },
    {
        "category": "发货时效",
        "title": "现货商品发货时间",
        "content": "现货订单付款后48小时内安排发出，预售商品以商品详情页标注的发货时间为准，节假日顺延。",
    },
    {
        "category": "发票服务",
        "title": "电子发票开具规则",
        "content": "订单完成后可申请电子发票，发票抬头可选择个人或者企业，开票周期一般1-3个工作日。",
    },
    {
        "category": "价保政策",
        "title": "商品价保说明",
        "content": "签收7天内商品降价，可申请价保补差；活动特价、秒杀商品不参与价保。",
    },
    {
        "category": "拒收规则",
        "title": "快递拒收处理",
        "content": "到货拒收后，包裹退回仓库，商家收到退回商品后处理退款；生鲜、易碎品拒收产生损耗不予退款。",
    },
    {
        "category": "优惠券",
        "title": "优惠券使用限制",
        "content": "优惠券不可叠加使用，限时券过期自动失效，仅支持指定商品，不支持充值类商品。",
    },
]


async def ingest_knowledge(tenant_id: str = "tenant_001"):
    """逐条生成真实 embedding 并入库，按 title 去重。"""
    async_session_factory = session.async_session_factory
    if async_session_factory is None:
        raise RuntimeError("必须先调用 init_db_engine 初始化引擎！")
    
    async with async_session_factory() as db:
        for item in KNOWLEDGE_RAW:
            # 1. 去重：标题已存在则跳过
            exist = await db.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.title == item["title"])
            )
            if exist.scalar_one_or_none():
                print(f"⏭️  已存在，跳过：{item['title']}")
                continue

            # 2. 调用百炼 Embedding 生成真实向量
            try:
                vector = await rag_service.embeddings.aembed_query(item["content"])
            except Exception as e:
                print(f"❌ Embedding 失败（{item['title']}）：{e}")
                continue

            # 3. 写入数据库
            db.add(KnowledgeDoc(
                tenant_id=tenant_id,
                category=item["category"],
                title=item["title"],
                content=item["content"],
                embedding=vector,
            ))
            print(f"✅ 已入库：{item['title']}")

        await db.commit()
        print("🎉 知识库真实向量导入完成！")


async def main():
    from .session import init_db_engine, create_tables_and_extension
    # 初始化引擎 + 建表（幂等，重复执行不报错）
    init_db_engine(settings.DATABASE_URL)
    await create_tables_and_extension()
    await ingest_knowledge()


if __name__ == "__main__":
    asyncio.run(main())
