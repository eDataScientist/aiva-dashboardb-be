import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def check_columns():
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5433/aiva_dashboard"
    )
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'conversation_grades' ORDER BY ordinal_position"
            )
        )
        columns = result.fetchall()
        for col in columns:
            print(f"{col[0]}: {col[1]}")
    await engine.dispose()


asyncio.run(check_columns())
